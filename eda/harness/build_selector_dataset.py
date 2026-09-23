
import argparse
import json
from pathlib import Path

import metrics_schema


def fnum(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def load_run(runs_dir, run_id):
    rd = Path(runs_dir) / run_id
    metrics = json.loads((rd / "metrics.json").read_text())
    meta = json.loads((rd / "meta.json").read_text())
    return metrics, meta


def metric_bundle(metrics):
    canonical = metrics_schema.canonicalize_record(metrics)
    raw = metrics.get("raw", {}) or {}
    route = metrics.get("def_route", {}) or {}
    return {
        "hpwl_route_um": route.get("hpwl_um"),
        "hpwl_no_ports_um": route.get("hpwl_no_ports_um"),
        "hpwl_origin_um": route.get("hpwl_origin_um"),
        "hpwl_convention": route.get("hpwl_convention"),
        "wirelength_um": fnum(metrics.get("detailed_wirelength_um")) if metrics.get("detailed_wirelength_um") is not None else fnum(raw.get("drt::wire length::total")),
        "vias": fnum(metrics.get("vias")) if metrics.get("vias") is not None else fnum(raw.get("drt::vias::total")),
        "setup_wns_ns": canonical.get("setup_wns_ns"),
        "hold_wns_ns": canonical.get("hold_wns_ns"),
        "setup_tns_ns": canonical.get("setup_tns_ns"),
        "hold_tns_ns": canonical.get("hold_tns_ns"),
        "clock_skew_ns": fnum(metrics.get("clock_skew_ns")) if metrics.get("clock_skew_ns") is not None else fnum(metrics.get("clock_skew_ps")),
        "power_w": fnum(metrics.get("total_power_w")),
        "runtime_s": fnum(metrics.get("duration_s")),
        "instance_count": fnum(metrics.get("instance_count")),
        "drc_violations": fnum(metrics.get("drc_violations")),
        "antenna_errors": fnum(metrics.get("antenna_errors")),
        "l1_verdict": metrics.get("l1_verdict"),
        "area_um2": fnum(metrics.get("design_area_um2")),
        "utilization_pct": fnum(metrics.get("utilization_pct")),
        "clock_period_ns": fnum(metrics.get("clock_period_ns")),
    }


def timing_guard_ok(metrics, base, guard_ns=0.02):
    return metrics_schema.timing_guard_ok(metrics, base, guard_ns=guard_ns, require_setup=True)


SCORE_UNSAFE_PENALTY = 1.0


def utility(metrics, base):
    return metrics_schema.utility(metrics, base)


def selection_score(metrics, base):
    score = utility(metrics, base)
    if metrics.get("gate_ok") and timing_guard_ok(metrics, base):
        return score
    return score - SCORE_UNSAFE_PENALTY


def build_for_design(design, base_id, candidate_ids, runs_dir):
    base_metrics, base_meta = load_run(runs_dir, base_id)
    base_bundle = metric_bundle(base_metrics)
    base_gate = (base_meta.get("returncode") == 0
                 and fnum(base_metrics.get("drc_violations")) == 0.0
                 and fnum(base_metrics.get("antenna_errors")) == 0.0)
    candidates = []
    for skill_id, run_id in candidate_ids.items():
        metrics, meta = load_run(runs_dir, run_id)
        bundle = metric_bundle(metrics)
        gate = (meta.get("returncode") == 0
                and fnum(metrics.get("drc_violations")) == 0.0
                and fnum(metrics.get("antenna_errors")) == 0.0)
        if metrics.get("l1_verdict") is not None:
            gate = gate and bool(metrics.get("l1_verdict"))
        delta = {}
        for key in ["hpwl_route_um", "hpwl_no_ports_um", "wirelength_um", "vias", "setup_wns_ns", "hold_wns_ns", "setup_tns_ns", "power_w", "runtime_s"]:
            bv = fnum(base_bundle.get(key))
            cv = fnum(bundle.get(key))
            delta[key] = None if (bv is None or cv is None) else cv - bv
        candidates.append({
            "skill_id": skill_id,
            "run_id": run_id,
            "overrides": meta.get("overrides", {}),
            "gate_ok": gate,
            "timing_guard_ok": timing_guard_ok(bundle, base_bundle),
            "selection_score": selection_score(bundle, base_bundle),
            "cost_s": bundle["runtime_s"],
            "metrics": bundle,
            "delta": delta,
            "utility": utility(bundle, base_bundle),
        })
    valid = [c for c in candidates if c["gate_ok"] and c["timing_guard_ok"]]
    if not valid:
        valid = [c for c in candidates if c["gate_ok"]]
    oracle = max(valid, key=lambda c: c["utility"])["skill_id"] if valid else None
    state_metrics = {}
    for key in ["def_global_place", "def_cts", "def_route"]:
        d = base_metrics.get(key)
        if d:
            state_metrics[key] = {k: d.get(k) for k in ["hpwl_um", "hpwl_origin_um", "components", "nets", "pin_hits", "pin_misses", "cell_area_um2", "utilization_pct_of_die"]}
    base_utility = utility(base_bundle, base_bundle)
    record = {
        "design": design,
        "decision_point": "flow_start",
        "base_utility": base_utility,
        "base_selection_score": 0.0,
        "state": {
            "design": design,
            "family": design,
            "base_metrics": base_bundle,
            "base_gate_ok": base_gate,
            "stage_metrics": state_metrics,
        },
        "candidates": candidates,
        "oracle_skill": oracle,
        "utility_spec": metrics_schema.utility_spec(),
    }
    return record


def to_sft(record):
    lines = []
    lines.append("Design state: " + json.dumps(record["state"], ensure_ascii=False))
    lines.append("Candidate skills:")
    for c in record["candidates"]:
        lines.append(json.dumps({
            "skill_id": c["skill_id"],
            "overrides": c["overrides"],
            "gate_ok": c["gate_ok"],
            "delta": c["delta"],
            "utility": c["utility"],
            "cost_s": c["cost_s"],
        }, ensure_ascii=False))
    lines.append("Timing gate (canonical): setup_wns_ns >= base_setup_wns_ns - 0.02 ns and hold_wns_ns >= base_hold_wns_ns - 0.02 ns; if a baseline value is nonnegative, the candidate must stay nonnegative for that analysis. WNS is a gate only; among timing-safe candidates choose by U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power. Output JSON with skill_id.")
    return {
        "messages": [
            {"role": "system", "content": "You are an EDA hyper-heuristic selector. Output JSON only."},
            {"role": "user", "content": "\n".join(lines)},
            {"role": "assistant", "content": json.dumps({"skill_id": record["oracle_skill"]}, ensure_ascii=False)},
        ],
        "design": record["design"],
        "oracle_skill": record["oracle_skill"],
    }


def main():
    parser = argparse.ArgumentParser(description="Build selector distillation dataset from Phase 0 runs")
    parser.add_argument("--config", required=True)
    parser.add_argument("--runs-dir", required=True)
    parser.add_argument("--out-jsonl", required=True)
    parser.add_argument("--out-sft", required=True)
    parser.add_argument("--out-summary", required=True)
    parser.add_argument("--out-preferences", default=None)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    records = []
    for design, item in config["designs"].items():
        record = build_for_design(design, item["base"], item["candidates"], args.runs_dir)
        records.append(record)
    Path(args.out_jsonl).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
    sft = [to_sft(r) for r in records if r["oracle_skill"]]
    Path(args.out_sft).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in sft) + "\n")
    if args.out_preferences:
        prefs = []
        for record in records:
            base_utility = record.get("base_utility")
            base_score = record.get("base_selection_score")
            valid = [c for c in record["candidates"] if c["gate_ok"]]
            ranked = sorted(valid, key=lambda c: c["selection_score"], reverse=True)
            pos = [{"skill_id": c["skill_id"], "utility": c["utility"], "selection_score": c["selection_score"], "timing_guard_ok": c["timing_guard_ok"]} for c in ranked if base_score is not None and c["selection_score"] > base_score]
            neg = [{"skill_id": c["skill_id"], "utility": c["utility"], "selection_score": c["selection_score"], "timing_guard_ok": c["timing_guard_ok"]} for c in ranked if base_score is not None and c["selection_score"] < base_score]
            prefs.append({
                "design": record["design"],
                "decision_point": record["decision_point"],
                "state": record["state"],
                "base_utility": base_utility,
        "base_selection_score": 0.0,
                "base_selection_score": base_score,
                "positives": pos,
                "negatives": neg,
                "ranking": [{"skill_id": c["skill_id"], "utility": c["utility"], "selection_score": c["selection_score"], "timing_guard_ok": c["timing_guard_ok"]} for c in ranked],
            })
        Path(args.out_preferences).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in prefs) + "\n")
    summary = {
        "n_designs": len(records),
        "oracles": {r["design"]: r["oracle_skill"] for r in records},
        "n_candidates": {r["design"]: len(r["candidates"]) for r in records},
        "n_sft": len(sft),
        "utility_spec": records[0]["utility_spec"] if records else None,
    }
    Path(args.out_summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
