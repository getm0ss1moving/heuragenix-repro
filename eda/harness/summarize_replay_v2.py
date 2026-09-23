"""Summarize checkpoint_replay_v2 labels: paired action effects + oracle distribution.

Usage:
  python3 harness/summarize_replay_v2.py \
    --replay results/canonical_server/checkpoint_replay_v2.jsonl \
    --plan results/canonical_server/replay_batch_plan_v2.jsonl \
    --out-json results/canonical_server/PHASE0_REPLAY_V2_SUMMARY.json \
    --out-md results/canonical_server/PHASE0_REPLAY_V2_SUMMARY.md
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metrics_schema  # noqa: E402
import build_checkpoint_dataset as bcd  # noqa: E402


def mean(values):
    vals = [v for v in values if v is not None]
    return (sum(vals) / len(vals)) if vals else None


def main():
    ap = argparse.ArgumentParser(description="Summarize replay v2 labels")
    ap.add_argument("--replay", default="results/canonical_server/checkpoint_replay_v2.jsonl")
    ap.add_argument("--plan", default="results/canonical_server/replay_batch_plan_v2.jsonl")
    ap.add_argument("--out-json", default="results/canonical_server/PHASE0_REPLAY_V2_SUMMARY.json")
    ap.add_argument("--out-md", default="results/canonical_server/PHASE0_REPLAY_V2_SUMMARY.md")
    args = ap.parse_args()

    plan = bcd.load_jsonl(args.plan)
    replay = bcd.load_jsonl(args.replay)
    plan_by_id = {str(t.get("run_id")): t for t in plan}
    by_decision = defaultdict(dict)
    for r in replay:
        task = plan_by_id.get(str(r.get("run_id")))
        if not task:
            continue
        key = (str(task.get("design")), str(task.get("checkpoint_run_id")), str(task.get("stage")))
        by_decision[key][str(task.get("action_id"))] = r

    effects = defaultdict(list)
    oracle_count = Counter()
    decisions = []
    for key, actions in sorted(by_decision.items()):
        control = actions.get("control") or actions.get("")
        if control is None:
            continue
        base_bundle = bcd.metric_bundle(control.get("metrics"))
        decision = {
            "design": key[0], "checkpoint_run_id": key[1], "stage": key[2],
            "control_run_id": control.get("run_id"), "candidates": {},
        }
        for aid, rec in sorted(actions.items()):
            if aid in ("control", ""):
                continue
            bundle = bcd.metric_bundle(rec.get("metrics"))
            gate = bcd.evaluate_gate(bundle, base_bundle, rec.get("returncode"))
            util = metrics_schema.utility(bundle, base_bundle)
            delta = bcd.delta_block(bundle, base_bundle)
            effects[(key[0], key[2], aid)].append({
                "delta_setup_wns_ns": delta.get("setup_wns_ns"),
                "delta_hold_wns_ns": delta.get("hold_wns_ns"),
                "delta_setup_tns_ns": delta.get("setup_tns_ns"),
                "delta_hold_tns_ns": delta.get("hold_tns_ns"),
                "delta_hpwl_um": delta.get("hpwl_route_um"),
                "delta_wirelength_um": delta.get("wirelength_um"),
                "delta_vias": delta.get("vias"),
                "delta_power_w": delta.get("power_w"),
                "gate_ok": gate["gate_ok"],
                "utility": util,
                "duration_s": rec.get("duration_s"),
            })
            decision["candidates"][aid] = {"gate_ok": gate["gate_ok"], "utility": util, "duration_s": rec.get("duration_s")}
        safe = [a for a, c in decision["candidates"].items() if c["gate_ok"]]
        oracle = max(safe, key=lambda a: decision["candidates"][a]["utility"]) if safe else None
        decision["oracle_action"] = oracle
        for a, c in decision["candidates"].items():
            c["is_oracle"] = (a == oracle)
        if oracle:
            oracle_count[(key[0], key[2], oracle)] += 1
        decisions.append(decision)

    effect_rows = []
    for (design, stage, aid), rows in sorted(effects.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        effect_rows.append({
            "design": design, "stage": stage, "action_id": aid,
            "n": len(rows),
            "gate_ok": sum(1 for r in rows if r["gate_ok"]),
            "mean_delta_setup_wns_ns": mean([r["delta_setup_wns_ns"] for r in rows]),
            "mean_delta_hold_wns_ns": mean([r["delta_hold_wns_ns"] for r in rows]),
            "mean_delta_setup_tns_ns": mean([r["delta_setup_tns_ns"] for r in rows]),
            "mean_delta_hpwl_um": mean([r["delta_hpwl_um"] for r in rows]),
            "mean_delta_wirelength_um": mean([r["delta_wirelength_um"] for r in rows]),
            "mean_delta_vias": mean([r["delta_vias"] for r in rows]),
            "mean_delta_power_w": mean([r["delta_power_w"] for r in rows]),
            "mean_utility": mean([r["utility"] for r in rows]),
            "mean_duration_s": mean([r["duration_s"] for r in rows]),
        })

    summary = {
        "records": len(replay),
        "decisions": len(decisions),
        "controls": sum(1 for d in decisions),
        "by_design_stage_action": effect_rows,
        "oracle_action_counts": {"%s/%s/%s" % k: v for k, v in sorted(oracle_count.items())},
        "utility_spec": metrics_schema.utility_spec(),
    }
    Path(args.out_json).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    lines = ["# checkpoint replay v2 summary (paired vs same-checkpoint control)", "",
             "| design | stage | action | n | gate_ok | d_setupWNS | d_holdWNS | d_TNS | d_HPWL(um) | d_WL(um) | d_vias | d_power(W) | U | dur(s) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in effect_rows:
        def fmt(x):
            return "NA" if x is None else ("%.4g" % x)
        lines.append("| %s | %s | %s | %d | %d | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["design"], r["stage"], r["action_id"], r["n"], r["gate_ok"],
            fmt(r["mean_delta_setup_wns_ns"]), fmt(r["mean_delta_hold_wns_ns"]),
            fmt(r["mean_delta_setup_tns_ns"]), fmt(r["mean_delta_hpwl_um"]),
            fmt(r["mean_delta_wirelength_um"]), fmt(r["mean_delta_vias"]),
            fmt(r["mean_delta_power_w"]), fmt(r["mean_utility"]), fmt(r["mean_duration_s"])))
    lines.append("")
    lines.append("Oracle (per-decision, gate-safe, canonical U) counts:")
    for k, v in sorted(oracle_count.items()):
        lines.append("- %s/%s/%s: %d" % (k[0], k[1], k[2], v))
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    print(json.dumps({"records": summary["records"], "decisions": summary["decisions"],
                      "effect_rows": len(effect_rows)}, indent=2))
    print("SUMMARY_WRITTEN", args.out_json, args.out_md)


if __name__ == "__main__":
    main()
