
import argparse
import json
import random
import statistics
from pathlib import Path

import metrics_schema


FIELDS = ["hpwl_route_um", "hpwl_no_ports_um", "wirelength_um", "vias", "setup_wns_ns", "hold_wns_ns", "setup_tns_ns", "hold_tns_ns", "total_power_w", "duration_s"]
TIMING_FIELDS = {"setup_wns_ns", "hold_wns_ns", "setup_tns_ns", "hold_tns_ns"}


def fnum(value):
    try:
        return float(value)
    except Exception:
        return None


def load_table(paths):
    table = {}
    for path in paths:
        sweep = json.loads(Path(path).read_text())
        design = sweep.get("design", "gcd")
        table.setdefault(design, {})
        for record in sweep["runs"]:
            if record.get("gate_ok"):
                table[design][record["variant"]] = metrics_schema.canonicalize_record(record)
    return table


def bootstrap_mean(values, n=5000, seed=0):
    random.seed(seed)
    if not values:
        return None, None, None
    means = []
    for _ in range(n):
        sample = [random.choice(values) for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo = means[int(0.025 * n)]
    hi = means[int(0.975 * n) - 1]
    return sum(values) / len(values), lo, hi


def main():
    parser = argparse.ArgumentParser(description="Phase 0 paired effect + bootstrap CI")
    parser.add_argument("--sweep", nargs="+", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--bootstrap", type=int, default=5000)
    args = parser.parse_args()
    table = load_table(args.sweep)
    designs = sorted(table.keys())
    candidates = sorted(set().union(*[set(v.keys()) for v in table.values()]))
    candidates = [c for c in candidates if c != "base"]
    out = {"designs": designs, "candidates": {}, "bootstrap_n": args.bootstrap}
    for cand in candidates:
        per_field = {field: [] for field in FIELDS}
        per_field_pct = {field: [] for field in FIELDS}
        pairs = []
        for design in designs:
            if cand not in table[design] or "base" not in table[design]:
                continue
            c = table[design][cand]
            b = table[design]["base"]
            row = {"design": design}
            for field in FIELDS:
                cv = fnum(c.get(field))
                bv = fnum(b.get(field))
                if cv is None or bv is None:
                    continue
                delta = cv - bv
                per_field[field].append(delta)
                if bv not in (0, None) and field not in TIMING_FIELDS:
                    per_field_pct[field].append(100.0 * delta / bv)
                row[field + "_delta"] = delta
                row[field + "_base"] = bv
                row[field + "_cand"] = cv
            pairs.append(row)
        cand_out = {"pairs": pairs, "fields": {}}
        for field in FIELDS:
            mean, lo, hi = bootstrap_mean(per_field[field], n=args.bootstrap)
            cand_out["fields"][field] = {
                "n": len(per_field[field]),
                "mean_delta": mean,
                "ci95_low": lo,
                "ci95_high": hi,
                "mean_pct": (sum(per_field_pct[field]) / len(per_field_pct[field])) if per_field_pct[field] else None,
                "signed_ns_no_pct": field in TIMING_FIELDS,
            }
        out["candidates"][cand] = cand_out
    Path(args.out_json).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    lines = ["# Phase 0 paired effect + bootstrap CI", "", "Designs: " + ", ".join(designs), "", "> signed WNS/TNS 为 ns 绝对差；不要用负基数百分比。表中 timing 行的 mean_pct 已停用。", ""]
    for cand, data in out["candidates"].items():
        lines.append("## " + cand)
        lines.append("")
        lines.append("| field | n | mean_delta | 95% CI | mean_pct |")
        lines.append("|---|---|---|---|---|")
        for field, stats in data["fields"].items():
            lines.append("| %s | %s | %s | [%s, %s] | %s |" % (
                field, stats["n"], stats["mean_delta"], stats["ci95_low"], stats["ci95_high"], stats["mean_pct"]))
        lines.append("")
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    print("STATS_DONE", args.out_json)


if __name__ == "__main__":
    main()
