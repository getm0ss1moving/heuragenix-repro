
import argparse
import json
import time
from pathlib import Path
import phase0
import metrics_schema


def fnum(value):
    try:
        return float(value)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Phase 0 parameter sweep")
    parser.add_argument("--sweep-id", required=True)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--design", default="gcd", choices=["gcd", "aes", "jpeg", "ibex"])
    args = parser.parse_args()
    variants = [
        {"name": "base", "overrides": {}},
        {"name": "density_025", "overrides": {"global_place_density": 0.25}},
        {"name": "density_035", "overrides": {"global_place_density": 0.35}},
        {"name": "density_040", "overrides": {"global_place_density": 0.40}},
        {"name": "pad_2", "overrides": {"global_place_pad": 2}},
        {"name": "pad_6", "overrides": {"global_place_pad": 6}},
        {"name": "grt_50", "overrides": {"global_route_congestion_iterations": 50}},
        {"name": "grt_200", "overrides": {"global_route_congestion_iterations": 200}},
    ]
    summary = {"sweep_id": args.sweep_id, "design": args.design, "threads": args.threads, "runs": []}
    for variant in variants:
        run_id = args.sweep_id + "_" + variant["name"]
        rd, metrics, meta = phase0.run_variant(run_id, variant["overrides"], args.threads, args.design)
        route_def = metrics.get("def_route", {}) or {}
        raw = metrics.get("raw", {}) or {}
        canonical = metrics_schema.canonicalize_record(metrics)
        record = {
            "run_id": run_id,
            "variant": variant["name"],
            "overrides": variant["overrides"],
            "returncode": meta["returncode"],
            "duration_s": meta["duration_s"],
            "gate_ok": (meta["returncode"] == 0
                        and fnum(metrics.get("drc_violations")) == 0.0
                        and fnum(metrics.get("antenna_errors")) == 0.0
                        and (metrics.get("l1_verdict") is not False)),
            "hpwl_route_um": route_def.get("hpwl_um"),
            "hpwl_no_ports_um": route_def.get("hpwl_no_ports_um"),
            "hpwl_origin_um": route_def.get("hpwl_origin_um"),
            "hpwl_convention": route_def.get("hpwl_convention"),
            "wirelength_um": fnum(raw.get("drt::wire length::total")),
            "vias": fnum(raw.get("drt::vias::total")),
            "setup_wns_ns": canonical.get("setup_wns_ns"),
            "hold_wns_ns": canonical.get("hold_wns_ns"),
            "setup_tns_ns": canonical.get("setup_tns_ns"),
            "hold_tns_ns": canonical.get("hold_tns_ns"),
            "clock_skew_ns": fnum(metrics.get("clock_skew_ns")),
            "drc": fnum(metrics.get("drc_violations")),
            "antenna": fnum(metrics.get("antenna_errors")),
            "total_power_w": fnum(metrics.get("total_power_w")),
            "instance_count": fnum(metrics.get("instance_count")),
            "design_area_um2": fnum(metrics.get("design_area_um2")),
        }
        summary["runs"].append(record)
        print(json.dumps(record, ensure_ascii=False))
    outdir = phase0.BASE / "results"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / (args.sweep_id + ".json")).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    lines = []
    lines.append("# Phase 0 sweep: " + args.sweep_id)
    lines.append("")
    lines.append("| variant | gate | HPWL_um | WL_um | vias | setup_WNS_ns | hold_WNS_ns | setup_TNS_ns | skew_ns | DRC | ant | power_W | sec |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in summary["runs"]:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["variant"], r["gate_ok"], r["hpwl_route_um"], r["wirelength_um"], r["vias"],
            r["setup_wns_ns"], r["hold_wns_ns"], r["setup_tns_ns"], r["clock_skew_ns"],
            r["drc"], r["antenna"], r["total_power_w"], r["duration_s"]))
    (outdir / (args.sweep_id + ".md")).write_text("\n".join(lines) + "\n")
    print("SWEEP_DONE", args.sweep_id)


if __name__ == "__main__":
    main()
