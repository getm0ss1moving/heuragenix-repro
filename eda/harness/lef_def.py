"""LEF/DEF geometry helpers with explicit HPWL conventions.

Canonical conventions
---------------------
- DEF coordinates are integer DB units; UNITS DISTANCE MICRONS <dbu> (usually 1000).
- HPWL uses pin centers, not cell origins.  LEF pin center = bbox center of all
  PORT RECTs minus MACRO ORIGIN.  The offset is transformed by the DEF
  component orientation before adding to the component origin.
- NETS section only (SPECIALNETS are skipped); both component pins and
  top-level ports written as ``( PIN portName )`` are included.
- Multi-line net/component/pin records (continuation lines starting with "+")
  are supported; routing attributes after "+ ROUTED/FIXED/..." are not treated
  as pin connections.
- ``hpwl_um`` = pin-offset HPWL; ``hpwl_origin_um`` = component-origin HPWL
  (old, no pin offset) kept only for regression comparison.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ORIENT_SETS = {"N", "S", "E", "W", "FN", "FS", "FE", "FW"}
ROUTE_ATTRS = {
    "ROUTED", "FIXED", "COVER", "SHIELD", "NOSHIELD", "SOURCE", "WEIGHT",
    "PROPERTY", "USE", "NETS", "SPECIALNETS",
}


def _transform(dx, dy, orient):
    """LEF orientation transform of a pin offset.

    Mapping to OpenDB orientations used by OpenLane:
      N->R0, W->R90, S->R180, E->R270, FN->MY, FS->MX, FW->MXR90, FE->MYR90.
    The matrices are the standard LEF pin-offset matrices; see
    docs/METRIC_CONVENTIONS.md for the verification note.
    """
    if orient == "N":
        return dx, dy
    if orient == "S":
        return -dx, -dy
    if orient == "W":
        return -dy, dx
    if orient == "E":
        return dy, -dx
    if orient == "FN":
        return -dx, dy
    if orient == "FS":
        return dx, -dy
    if orient == "FE":
        return dy, dx
    if orient == "FW":
        return -dy, -dx
    return dx, dy


def lef_info(path):
    """Parse MACRO sizes/origins and PIN centers from a LEF file."""
    text = Path(path).read_text(errors="replace")
    masters = {}
    cur = None
    cur_pin = None
    in_port = False
    rects = []
    origin = (0.0, 0.0)
    size = (0.0, 0.0)
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("MACRO "):
            cur = line.split()[1]
            masters[cur] = {"size": (0.0, 0.0), "origin": (0.0, 0.0), "pins": {}}
            cur_pin = None
            in_port = False
            rects = []
            origin = (0.0, 0.0)
            size = (0.0, 0.0)
            continue
        if cur is None:
            continue
        if line.startswith("ORIGIN "):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    origin = (float(parts[1]), float(parts[2]))
                except Exception:
                    pass
        elif line.startswith("SIZE "):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    size = (float(parts[1]), float(parts[3]))
                except Exception:
                    pass
        elif line.startswith("PIN "):
            cur_pin = line.split()[1]
            rects = []
            in_port = False
        elif line == "PORT":
            in_port = True
        elif line == "END" and in_port:
            in_port = False
        elif line.startswith("RECT ") and cur_pin and in_port:
            parts = line.split()
            if len(parts) >= 5:
                try:
                    x1, y1, x2, y2 = (float(parts[1]), float(parts[2]),
                                      float(parts[3]), float(parts[4]))
                    rects.append((x1, y1, x2, y2))
                except Exception:
                    pass
        elif line.startswith("END ") and cur_pin:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == cur_pin:
                if rects:
                    xs1 = min(r[0] for r in rects)
                    ys1 = min(r[1] for r in rects)
                    xs2 = max(r[2] for r in rects)
                    ys2 = max(r[3] for r in rects)
                    cx = (xs1 + xs2) / 2.0 - origin[0]
                    cy = (ys1 + ys2) / 2.0 - origin[1]
                    masters[cur]["pins"][cur_pin] = (round(cx, 6), round(cy, 6))
                else:
                    masters[cur]["pins"][cur_pin] = (0.0, 0.0)
                cur_pin = None
        elif line.startswith("END ") and cur:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == cur:
                masters[cur]["size"] = size
                masters[cur]["origin"] = origin
                cur = None
    return masters


def _dbu_from_text(text):
    m = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+([0-9]+)", text[:4000])
    if m:
        return float(m.group(1))
    return 1000.0


def _is_route_attr(line):
    body = line[1:].strip()
    if not body:
        return False
    return body.split()[0].upper() in ROUTE_ATTRS


def _parse_comp_record(text):
    m = re.match(r"-\s+(\S+)\s+(\S+)", text)
    if not m:
        return None
    name, master = m.group(1), m.group(2)
    pos = re.search(r"(?:PLACED|FIXED|COVER)\s*\(\s*(-?[0-9.]+)\s+(-?[0-9.]+)\s*\)", text)
    if not pos:
        return None
    ori = re.search(r"\)\s+([A-Z]{1,2})\b", text)
    orient = ori.group(1) if ori and ori.group(1) in ORIENT_SETS else "N"
    try:
        return name, (master, float(pos.group(1)), float(pos.group(2)), orient)
    except Exception:
        return None


def _parse_pin_record(text):
    m = re.match(r"-\s+(\S+)", text)
    if not m:
        return None
    name = m.group(1)
    pos = re.search(r"(?:PLACED|FIXED)\s*\(\s*(-?[0-9.]+)\s+(-?[0-9.]+)\s*\)", text)
    if not pos:
        return None
    try:
        return name, (float(pos.group(1)), float(pos.group(2)))
    except Exception:
        return None


def _flush(kind, buf, comps, ports, nets):
    if not buf:
        return
    text = "\n".join(buf)
    if kind == "comp":
        rec = _parse_comp_record(text)
        if rec is not None:
            comps[rec[0]] = rec[1]
    elif kind == "pins":
        rec = _parse_pin_record(text)
        if rec is not None:
            ports[rec[0]] = rec[1]
    elif kind == "nets":
        # stop pin extraction at routing attributes; keep only the initial part
        pin_lines = []
        for line in buf:
            if line.startswith("+") and _is_route_attr(line):
                break
            pin_lines.append(line)
        pin_text = "\n".join(pin_lines)
        pairs = re.findall(r"\(\s*(\S+)\s+(\S+)\s*\)", pin_text)
        if len(pairs) >= 2:
            nets.append(pairs)


def def_parts(def_path):
    """Parse DEF components, ports and NETS pin connections.

    Returns (dbu, comps, ports, nets).
    """
    text = Path(def_path).read_text(errors="replace")
    dbu = _dbu_from_text(text)
    comps = {}
    ports = {}
    nets = []
    section = None
    kind = None
    buf = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("COMPONENTS"):
            _flush(kind, buf, comps, ports, nets)
            kind, buf, section = None, [], "comp"
            continue
        if line.startswith("END COMPONENTS"):
            _flush(kind, buf, comps, ports, nets)
            kind, buf, section = None, [], None
            continue
        if line.startswith("PINS"):
            _flush(kind, buf, comps, ports, nets)
            kind, buf, section = None, [], "pins"
            continue
        if line.startswith("END PINS"):
            _flush(kind, buf, comps, ports, nets)
            kind, buf, section = None, [], None
            continue
        if line.startswith("NETS"):
            _flush(kind, buf, comps, ports, nets)
            kind, buf, section = None, [], "nets"
            continue
        if line.startswith("END NETS"):
            _flush(kind, buf, comps, ports, nets)
            kind, buf, section = None, [], None
            continue
        if section is None:
            continue
        if line.startswith("- "):
            _flush(kind, buf, comps, ports, nets)
            kind, buf = section, [line]
        elif line.startswith("+") and buf:
            buf.append(line)
        elif buf and line:
            # some writers put record attributes on a continuation without "+"
            buf.append(line)
    _flush(kind, buf, comps, ports, nets)
    return dbu, comps, ports, nets


def def_metrics(def_path, lef_path, die_w, die_h):
    """Compute canonical geometry metrics for one DEF snapshot."""
    dbu, comps, ports, nets = def_parts(def_path)
    lef = lef_info(lef_path)
    hpwl = 0.0
    hpwl_no_ports = 0.0
    hpwl_origin = 0.0
    pin_hits = 0
    pin_misses = 0
    port_pin_hits = 0
    port_pin_misses = 0
    for pairs in nets:
        xs, ys = [], []
        xs_np, ys_np = [], []
        xs0, ys0 = [], []
        for inst, pin in pairs:
            if inst == "PIN":
                # DEF top-level port connection: ( PIN portName )
                if pin in ports:
                    xp, yp = ports[pin]
                    x0, y0 = xp / dbu, yp / dbu
                    xs.append(x0)
                    ys.append(y0)
                    xs0.append(x0)
                    ys0.append(y0)
                    port_pin_hits += 1
                else:
                    port_pin_misses += 1
                continue
            if inst in comps:
                master, xr, yr, orient = comps[inst]
                x0 = xr / dbu
                y0 = yr / dbu
                xs0.append(x0)
                ys0.append(y0)
                info = lef.get(master) or {}
                pin_map = info.get("pins") or {}
                off = pin_map.get(pin)
                if off is None:
                    pin_misses += 1
                    xs.append(x0)
                    ys.append(y0)
                    xs_np.append(x0)
                    ys_np.append(y0)
                else:
                    pin_hits += 1
                    dx, dy = _transform(off[0], off[1], orient)
                    xs.append(x0 + dx)
                    ys.append(y0 + dy)
                    xs_np.append(x0 + dx)
                    ys_np.append(y0 + dy)
            elif inst in ports:
                xp, yp = ports[inst]
                x0, y0 = xp / dbu, yp / dbu
                xs.append(x0)
                ys.append(y0)
                xs0.append(x0)
                ys0.append(y0)
                port_pin_hits += 1
        if len(xs) >= 2:
            hpwl += (max(xs) - min(xs)) + (max(ys) - min(ys))
        if len(xs_np) >= 2:
            hpwl_no_ports += (max(xs_np) - min(xs_np)) + (max(ys_np) - min(ys_np))
        if len(xs0) >= 2:
            hpwl_origin += (max(xs0) - min(xs0)) + (max(ys0) - min(ys0))
    cell_area = 0.0
    for _inst, (master, _x, _y, _o) in comps.items():
        info = lef.get(master)
        if info is not None:
            w, h = info["size"]
            cell_area += w * h
    return {
        "components": len(comps),
        "ports": len(ports),
        "nets": len(nets),
        "hpwl_um": round(hpwl, 3),
        "hpwl_no_ports_um": round(hpwl_no_ports, 3),
        "hpwl_origin_um": round(hpwl_origin, 3),
        "pin_hits": pin_hits,
        "pin_misses": pin_misses,
        "port_pin_hits": port_pin_hits,
        "port_pin_misses": port_pin_misses,
        "cell_area_um2": round(cell_area, 3),
        "utilization_pct_of_die": round(100.0 * cell_area / (die_w * die_h), 4),
        "hpwl_convention": "pin_offset_v1_2026-09-22",
    }


def main():
    parser = argparse.ArgumentParser(description="LEF/DEF geometry metrics (canonical pin-offset HPWL)")
    parser.add_argument("--def", dest="def_path", required=True)
    parser.add_argument("--lef", required=True)
    parser.add_argument("--die-w", type=float, default=1000.0)
    parser.add_argument("--die-h", type=float, default=1000.0)
    args = parser.parse_args()
    metrics = def_metrics(args.def_path, args.lef, args.die_w, args.die_h)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
