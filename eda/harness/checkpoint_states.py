"""Build unlabeled checkpoint state cards from existing run DEF snapshots.

Purpose: Phase 0 currently has candidate outcomes only from flow_start.  This
script extracts post_global_place / post_cts / post_route state features from
each run's DEF snapshots, so Phase 1 can reuse the same states for checkpoint
replay with different skills.

Note: these records have no action labels yet; they are state cards, not a
supervised selector dataset.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import lef_def

STAGES = [
    ("post_global_place", "global_place"),
    ("post_cts", "cts"),
    ("post_route", "route"),
]

TIMING_KEYS = {
    "DRT": {
        "setup_wns_ns": "DRT::worst_slack_max",
        "hold_wns_ns": "DRT::worst_slack_min",
        "setup_tns_ns": "DRT::tns_max",
        "hold_tns_ns": "DRT::tns_min",
    },
    "RSZ": {
        "setup_wns_ns": "RSZ::worst_slack_max",
        "hold_wns_ns": "RSZ::worst_slack_min",
        "setup_tns_ns": "RSZ::tns_max",
        "hold_tns_ns": "RSZ::tns_min",
    },
}


def fnum(v):
    try:
        return float(v)
    except Exception:
        return None


def timing_for_stage(raw, stage):
    group = "DRT" if stage == "post_route" else "RSZ"
    out = {}
    for field, key in TIMING_KEYS[group].items():
        out[field] = fnum(raw.get(key))
    if all(out.get(f) is None for f in out):
        alt = "RSZ" if group == "DRT" else "DRT"
        for field, key in TIMING_KEYS[alt].items():
            out[field] = fnum(raw.get(key))
    return out


def main():
    parser = argparse.ArgumentParser(description="Build checkpoint state cards from run DEF snapshots")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--lef", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    runs_dir = Path(args.runs_dir)
    lef = Path(args.lef)
    records = []
    summary = {}
    for rd in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        mp = rd / "metrics.json"
        if not mp.exists():
            continue
        metrics = json.loads(mp.read_text())
        meta_path = rd / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        raw = metrics.get("raw") or {}
        if not raw:
            rp = rd / "metrics_raw.json"
            if rp.exists():
                try:
                    raw = json.loads(rp.read_text())
                except Exception:
                    raw = {}
        design = metrics.get("design") or rd.name.split("_")[0]
        for stage, suffix in STAGES:
            def_path = rd / "results" / ("%s_sky130hd_%s.def" % (design, suffix))
            if not def_path.exists():
                continue
            try:
                geo = lef_def.def_metrics(str(def_path), str(lef), 1000.0, 1000.0)
            except Exception as exc:
                geo = {"error": str(exc)}
            timing = timing_for_stage(raw, stage)
            rec = {
                "design": design,
                "run_id": rd.name,
                "variant": meta.get("overrides", {}),
                "stage": stage,
                "checkpoint_def": str(def_path),
                "hpwl_um": geo.get("hpwl_um"),
                "hpwl_no_ports_um": geo.get("hpwl_no_ports_um"),
                "hpwl_origin_um": geo.get("hpwl_origin_um"),
                "components": geo.get("components"),
                "nets": geo.get("nets"),
                "pin_hits": geo.get("pin_hits"),
                "pin_misses": geo.get("pin_misses"),
                "setup_wns_ns": timing.get("setup_wns_ns"),
                "hold_wns_ns": timing.get("hold_wns_ns"),
                "setup_tns_ns": timing.get("setup_tns_ns"),
                "hold_tns_ns": timing.get("hold_tns_ns"),
                "power_w": metrics.get("total_power_w") if stage == "post_route" else None,
                "drc_violations": metrics.get("drc_violations") if stage == "post_route" else None,
                "antenna_errors": metrics.get("antenna_errors") if stage == "post_route" else None,
                "metric_convention_version": metrics.get("metric_convention_version", "metrics_v2_2026-09-22"),
                "timing_convention": "setup_hold_v1_2026-09-22",
                "source": "checkpoint_states_v1_unlabeled",
            }
            records.append(rec)
            summary[(design, stage)] = summary.get((design, stage), 0) + 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps({
        "n_records": len(records),
        "n_designs": len({r["design"] for r in records}),
        "by_design_stage": {"%s/%s" % k: v for k, v in sorted(summary.items())},
        "note": "unlabeled checkpoint state cards; action labels require checkpoint replay",
    }, indent=2, ensure_ascii=False))
    print(json.dumps({"n_records": len(records), "summary": str(summary_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
