
import argparse
import json
import re
from pathlib import Path

import lef_def

CORE = {
    "gcd": (9.996, 10.08, 289.964, 290.048),
    "aes": (30.0, 30.0, 1770.0, 1770.0),
    "jpeg": (10.07, 9.8, 2989.97, 2990.0),
}


def rectangles(comps, lef, dbu):
    boxes = []
    for inst, item in comps.items():
        master, xr, yr, orient = item
        info = lef.get(master)
        if info is None:
            continue
        w, h = info["size"]
        x = xr / dbu
        y = yr / dbu
        boxes.append((x, y, x + w, y + h, inst))
    return boxes


def overlap_count(boxes, max_pairs=200000, eps=1e-6):
    rows = {}
    for b in boxes:
        key = round(b[1], 3)
        rows.setdefault(key, []).append(b)
    pairs = 0
    examples = []
    truncated = False
    for _key, group in rows.items():
        group.sort(key=lambda b: b[0])
        if not group:
            continue
        max_x2 = group[0][2]
        anchor = group[0]
        for b in group[1:]:
            if b[0] < max_x2 - eps:
                pairs += 1
                if len(examples) < 10:
                    examples.append([anchor[4], b[4]])
                max_x2 = max(max_x2, b[2])
                if pairs > max_pairs:
                    return pairs, examples, "truncated"
            else:
                anchor = b
                max_x2 = b[2]
    return pairs, examples, "ok"


def fixed_map(def_path):
    text = Path(def_path).read_text(errors="replace")
    dbu = lef_def._dbu_from_text(text)
    fixed = {}
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("COMPONENTS"):
            section = "comp"
            continue
        if line.startswith("END COMPONENTS"):
            section = None
            continue
        if section == "comp" and line.startswith("- ") and "+ FIXED" in line:
            toks = line[2:].split()
            match = re.search(r"\(\s*(-?[0-9.]+)\s+(-?[0-9.]+)\s*\)", line)
            if len(toks) >= 2 and match:
                try:
                    fixed[toks[0]] = (float(match.group(1)) / dbu, float(match.group(2)) / dbu, toks[1])
                except Exception:
                    pass
    return fixed


def row_ys(def_text, dbu):
    ys = set()
    for raw in def_text.splitlines():
        line = raw.strip()
        m = re.match(r"ROW\s+\S+\s+\S+\s+\d+\s+(\d+)", line)
        if m:
            ys.add(round(float(m.group(1)) / dbu, 6))
    return ys


def die_area(def_text, dbu):
    m = re.search(r"DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", def_text)
    if m:
        vals = [float(m.group(i)) / dbu for i in range(1, 5)]
        return (vals[0], vals[1], vals[2], vals[3])
    return None


def verify_def(def_path, lef_path, design, max_overlap_pairs=200000, ref_def=None, netlist=None):
    def_path = Path(def_path)
    text = def_path.read_text(errors="replace")
    dbu, comps, ports, nets = lef_def.def_parts(def_path)
    lef = lef_def.lef_info(lef_path)
    boxes = rectangles(comps, lef, dbu)
    pairs, examples, ov_status = overlap_count(boxes, max_overlap_pairs)
    row_set = row_ys(text, dbu)
    row_bad = 0
    for _inst, (master, xr, yr, orient) in comps.items():
        y = round(yr / dbu, 6)
        if row_set and y not in row_set:
            row_bad += 1
    die = die_area(text, dbu)
    boundary_bad = 0
    if die is not None:
        for b in boxes:
            if b[0] < die[0] - 1e-3 or b[1] < die[1] - 1e-3 or b[2] > die[2] + 1e-3 or b[3] > die[3] + 1e-3:
                boundary_bad += 1
    core = CORE.get(design)
    core_bad = 0
    if core is not None:
        for b in boxes:
            if b[0] < core[0] - 1e-3 or b[1] < core[1] - 1e-3 or b[2] > core[2] + 1e-3 or b[3] > core[3] + 1e-3:
                core_bad += 1
    net_bad = 0
    for pairs_list in nets:
        if len(pairs_list) < 2:
            net_bad += 1
            continue
        for inst, _pin in pairs_list:
            if inst == "PIN":
                continue
            if (inst not in comps) and (inst not in ports):
                net_bad += 1
                break
    fixed_changed = None
    if ref_def is not None:
        ref_fixed = fixed_map(ref_def)
        cand_fixed = fixed_map(def_path)
        fixed_changed = 0
        for inst, value in ref_fixed.items():
            if inst in cand_fixed:
                if not (cand_fixed[inst][0] == value[0] and cand_fixed[inst][1] == value[1] and cand_fixed[inst][2] == value[2]):
                    fixed_changed += 1
    netlist_sha = None
    if netlist is not None:
        import hashlib
        h = hashlib.sha256()
        with open(netlist, "rb") as fh:
            while True:
                chunk = fh.read(1048576)
                if not chunk:
                    break
                h.update(chunk)
        netlist_sha = h.hexdigest()
    checks = {
        "components": len(comps),
        "nets": len(nets),
        "overlap_pairs": pairs,
        "overlap_examples": examples,
        "overlap_status": ov_status,
        "row_violations": row_bad,
        "die_boundary_violations": boundary_bad,
        "core_boundary_violations": core_bad,
        "net_violations": net_bad,
        "die_area_um": die,
        "core_area_um": core,
        "fixed_changed": fixed_changed,
        "netlist_sha256": netlist_sha,
    }
    verdict = (pairs == 0 and row_bad == 0 and boundary_bad == 0 and core_bad == 0 and net_bad == 0)
    if fixed_changed is not None:
        verdict = verdict and (fixed_changed == 0)
    return {"def": str(def_path), "design": design, "verdict": verdict, "checks": checks}


def main():
    parser = argparse.ArgumentParser(description="L0/L1 verifier for DEF checkpoints")
    parser.add_argument("--def", required=True)
    parser.add_argument("--lef", required=True)
    parser.add_argument("--design", default="gcd")
    parser.add_argument("--out", required=True)
    parser.add_argument("--ref-def", default=None)
    parser.add_argument("--netlist", default=None)
    args = parser.parse_args()
    result = verify_def(getattr(args, "def"), args.lef, args.design, ref_def=args.ref_def, netlist=args.netlist)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
