
import argparse
import json
import os

import metrics_schema
from pathlib import Path

DEFAULT_RUNS = os.environ.get("HEURA_EDA_BASE", "/data/dzy/heura_repr/eda") + "/runs"


def fnum(value):
    try:
        return float(value)
    except Exception:
        return None


def record_from_run(runs_dir, run_id, variant):
    rd = Path(runs_dir) / run_id
    metrics = json.loads((rd / "metrics.json").read_text())
    meta = json.loads((rd / "meta.json").read_text())
    raw = metrics.get("raw", {}) or {}
    canonical = metrics_schema.canonicalize_record(metrics)
    def_route = metrics.get("def_route", {}) or {}
    gate = (meta.get("returncode") == 0
            and fnum(metrics.get("drc_violations")) == 0.0
            and fnum(metrics.get("antenna_errors")) == 0.0)
    if metrics.get("l1_verdict") is not None:
        gate = gate and bool(metrics.get("l1_verdict"))
    return {
        "run_id": run_id,
        "variant": variant,
        "overrides": meta.get("overrides", {}),
        "returncode": meta.get("returncode"),
        "duration_s": meta.get("duration_s"),
        "gate_ok": gate,
        "hpwl_route_um": def_route.get("hpwl_um"),
        "hpwl_no_ports_um": def_route.get("hpwl_no_ports_um"),
        "hpwl_origin_um": def_route.get("hpwl_origin_um"),
        "hpwl_convention": def_route.get("hpwl_convention"),
        "wirelength_um": fnum(metrics.get("detailed_wirelength_um")) or fnum(raw.get("drt::wire length::total")),
        "vias": fnum(metrics.get("vias")) or fnum(raw.get("drt::vias::total")),
        "setup_wns_ns": canonical.get("setup_wns_ns"),
        "hold_wns_ns": canonical.get("hold_wns_ns"),
        "setup_tns_ns": canonical.get("setup_tns_ns"),
        "hold_tns_ns": canonical.get("hold_tns_ns"),
        "clock_skew_ns": fnum(metrics.get("clock_skew_ns")) if metrics.get("clock_skew_ns") is not None else fnum(metrics.get("clock_skew_ps")),
        "drc": fnum(metrics.get("drc_violations")),
        "antenna": fnum(metrics.get("antenna_errors")),
        "l1_verdict": metrics.get("l1_verdict"),
        "total_power_w": fnum(metrics.get("total_power_w")),
        "instance_count": fnum(metrics.get("instance_count")),
        "design_area_um2": fnum(metrics.get("design_area_um2")),
    }


def main():
    parser = argparse.ArgumentParser(description="Collect run dirs into a sweep-like JSON")
    parser.add_argument("--design", required=True)
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pair", nargs="+", action="append", required=True, help="variant=run_id pairs")
    args = parser.parse_args()
    runs = []
    pairs = []
    for group in args.pair:
        pairs.extend(group)
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit("pair must be variant=run_id: " + pair)
        variant, run_id = pair.split("=", 1)
        runs.append(record_from_run(args.runs_dir, run_id, variant))
    out = {"sweep_id": args.design + "_collected", "design": args.design, "threads": None, "runs": runs}
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
