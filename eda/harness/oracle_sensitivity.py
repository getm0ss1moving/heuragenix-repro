"""Compare gate-safe candidate rankings under several utility policies.

Outputs a table per design/policy so Phase 0 can see whether the "oracle"
is robust or just an artifact of arbitrary weights.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import metrics_schema


def fnum(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def gates(candidate, base):
    return candidate.get("gate_ok") and metrics_schema.timing_guard_ok(candidate, base, require_setup=True)


def gains(candidate, base):
    hp = fnum(candidate.get("hpwl_route_um"))
    bhp = fnum(base.get("hpwl_route_um"), 1.0)
    tns = fnum(candidate.get("setup_tns_ns"))
    btns = fnum(base.get("setup_tns_ns"))
    wns = fnum(candidate.get("setup_wns_ns"))
    bwns = fnum(base.get("setup_wns_ns"))
    power = fnum(candidate.get("total_power_w"))
    bpow = fnum(base.get("total_power_w"), 1.0)
    d_hpwl = (bhp - hp) / bhp if bhp else 0.0
    d_tns = (abs(btns) - abs(tns)) / abs(btns) if btns else 0.0
    d_wns = (wns - bwns) / max(abs(bwns), 0.05)
    d_power = (bpow - power) / bpow if bpow else 0.0
    return {"hpwl": d_hpwl, "tns": d_tns, "wns": d_wns, "power": d_power}


POLICIES = {
    "weighted_v2(0.5/0.4/0.1)": lambda g: 0.5 * g["hpwl"] + 0.4 * g["tns"] + 0.1 * g["power"],
    "equal_v2(1/3)": lambda g: (g["hpwl"] + g["tns"] + g["power"]) / 3.0,
    "old_4item(0.4/0.3/0.2/0.1)": lambda g: 0.4 * g["hpwl"] + 0.3 * g["tns"] + 0.2 * g["wns"] + 0.1 * g["power"],
}


def lex_key(candidate, base, primary):
    c = dict(candidate)
    # prefer lower HPWL, higher (less negative) TNS, lower power
    hp = fnum(c.get("hpwl_route_um"), 1e30)
    tns = -fnum(c.get("setup_tns_ns"), -1e30)
    power = fnum(c.get("total_power_w"), 1e30)
    order = {"hpwl": (hp, tns, power), "tns": (tns, hp, power), "power": (power, hp, tns)}
    return order[primary]


def load_design(path):
    obj = json.loads(Path(path).read_text())
    runs = {r["variant"]: r for r in obj["runs"]}
    return obj.get("design", Path(path).stem), runs


def main():
    parser = argparse.ArgumentParser(description="Oracle sensitivity under utility policies")
    parser.add_argument("--sweep", nargs="+", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()
    out = {"policies": list(POLICIES) + ["lex_hpwl", "lex_tns", "lex_power"], "designs": {}}
    lines = ["# Oracle sensitivity（gate-safe only）", ""]
    for path in args.sweep:
        design, runs = load_design(path)
        base = runs["base"]
        safe = {k: v for k, v in runs.items() if k != "base" and gates(v, base)}
        rows = {}
        for name, fn in POLICIES.items():
            choice = max(safe, key=lambda k: fn(gains(safe[k], base))) if safe else None
            rows[name] = choice
        for primary in ["hpwl", "tns", "power"]:
            choice = min(safe, key=lambda k: lex_key(safe[k], base, primary)) if safe else None
            rows["lex_" + primary] = choice
        out["designs"][design] = {
            "safe_candidates": sorted(safe),
            "choices": rows,
        }
        lines.append("## " + design)
        lines.append("")
        lines.append("| policy | chosen |")
        lines.append("|---|---|")
        for name, choice in rows.items():
            lines.append("| %s | %s |" % (name, choice))
        lines.append("")
    Path(args.out_json).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
