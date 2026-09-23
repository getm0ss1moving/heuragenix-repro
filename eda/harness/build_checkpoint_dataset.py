"""Build checkpoint-level selector dataset v5 for HA-PR EDA (handoff P1).

Inputs:
  - checkpoint_states_v1.jsonl       (state cards, no labels)
  - checkpoint_replay_v2.jsonl       (replay labels: control + actions per checkpoint)
  - replay_batch_plan_v2.jsonl       (run_id -> checkpoint_run_id / action_id mapping)

Every action sample is paired with the control replay of the SAME checkpoint/stage.
Gate (canonical):
  setup_wns_ns >= control - 0.02 ns; hold_wns_ns >= control - 0.02 ns;
  if control value is nonnegative, action must stay nonnegative; DRC must not increase.
Soft utility (after gate):
  U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power  (relative improvements, higher better)

Outputs:
  selector_dataset_v5_checkpoint.jsonl   one line per action sample
  selector_sft_v5_checkpoint.jsonl       one line per checkpoint decision point
  selector_preferences_v5_checkpoint.jsonl
  selector_dataset_v5_summary.json
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metrics_schema  # noqa: E402

RANK_ORDER = {
    "post_global_place": 0,
    "post_cts": 1,
}
DESIGN_ORDER = {"gcd": 0, "jpeg": 1, "aes": 2, "ibex": 3}
SELECTION_UNSAFE_PENALTY = 1.0


def fnum(value, default=None):
    try:
        if value is None:
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def load_jsonl(path):
    rows = []
    for n, line in enumerate(Path(path).read_text(errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception as exc:
            raise SystemExit("bad JSONL %s:%d: %s" % (path, n, exc))
    return rows


def metric_bundle(m):
    m = m or {}
    return {
        "hpwl_route_um": fnum(m.get("hpwl_um")),
        "hpwl_no_ports_um": fnum(m.get("hpwl_no_ports_um")),
        "hpwl_origin_um": fnum(m.get("hpwl_origin_um")),
        "wirelength_um": fnum(m.get("wirelength_um")),
        "vias": fnum(m.get("vias")),
        "instance_count": fnum(m.get("instance_count")),
        "setup_wns_ns": fnum(m.get("setup_wns_ns")),
        "hold_wns_ns": fnum(m.get("hold_wns_ns")),
        "setup_tns_ns": fnum(m.get("setup_tns_ns")),
        "hold_tns_ns": fnum(m.get("hold_tns_ns")),
        "power_w": fnum(m.get("total_power_w")),
        "drc_violations": fnum(m.get("drc_violations")),
        "route_def": m.get("route_def"),
        "metric_convention_version": m.get("metric_convention_version"),
        "timing_convention": m.get("timing_convention"),
    }


def state_card_bundle(state):
    return {
        "design": state.get("design"),
        "family": state.get("design"),
        "stage": state.get("stage"),
        "checkpoint_run_id": state.get("run_id"),
        "checkpoint_def": state.get("checkpoint_def"),
        "checkpoint_metrics": {
            "hpwl_um": fnum(state.get("hpwl_um")),
            "hpwl_no_ports_um": fnum(state.get("hpwl_no_ports_um")),
            "hpwl_origin_um": fnum(state.get("hpwl_origin_um")),
            "components": fnum(state.get("components")),
            "nets": fnum(state.get("nets")),
            "pin_hits": fnum(state.get("pin_hits")),
            "pin_misses": fnum(state.get("pin_misses")),
            "setup_wns_ns": fnum(state.get("setup_wns_ns")),
            "hold_wns_ns": fnum(state.get("hold_wns_ns")),
            "setup_tns_ns": fnum(state.get("setup_tns_ns")),
            "hold_tns_ns": fnum(state.get("hold_tns_ns")),
            "metric_convention_version": state.get("metric_convention_version"),
            "timing_convention": state.get("timing_convention"),
        },
    }


def delta_block(cand, base):
    out = {}
    for key in [
        "hpwl_route_um", "hpwl_no_ports_um", "hpwl_origin_um", "wirelength_um",
        "vias", "instance_count", "setup_wns_ns", "hold_wns_ns",
        "setup_tns_ns", "hold_tns_ns", "power_w", "drc_violations",
    ]:
        cv, bv = fnum(cand.get(key)), fnum(base.get(key))
        out[key] = None if (cv is None or bv is None) else cv - bv
    return out


def relative_block(cand, base):
    out = {}
    for key in ["hpwl_route_um", "wirelength_um", "vias", "setup_tns_ns", "power_w"]:
        cv, bv = fnum(cand.get(key)), fnum(base.get(key))
        if cv is None or bv in (None, 0):
            out[key + "_rel"] = None
        else:
            out[key + "_rel"] = (bv - cv) / abs(bv)
    return out


def evaluate_gate(cand_metrics, base_metrics, cand_rc):
    status = metrics_schema.guard_status(cand_metrics, base_metrics)
    drc_c = fnum(cand_metrics.get("drc_violations"))
    drc_b = fnum(base_metrics.get("drc_violations"))
    drc_ok = True if (drc_c is None or drc_b is None) else (drc_c <= drc_b)
    rc_ok = cand_rc in (0, "0")
    setup_checked = bool(status["checks"].get("setup", {}).get("checked"))
    gate_ok = bool(rc_ok and drc_ok and status["ok"] and setup_checked)
    return {
        "gate_ok": gate_ok,
        "rc_ok": rc_ok,
        "drc_ok": drc_ok,
        "timing_guard": status,
    }


def build(states_path, replay_path, plan_path, guard_ns=0.02):
    states = load_jsonl(states_path)
    plan = load_jsonl(plan_path)
    replay = load_jsonl(replay_path)
    state_by_key = {}
    for s in states:
        state_by_key[(str(s.get("design")), str(s.get("run_id")), str(s.get("stage")))] = s
    plan_by_run = {str(t.get("run_id")): t for t in plan}
    replay_by_run = {str(r.get("run_id")): r for r in replay if r.get("run_id")}

    groups = defaultdict(dict)
    for rid, task in plan_by_run.items():
        rec = replay_by_run.get(rid)
        if rec is None:
            continue
        key = (str(task.get("design")), str(task.get("checkpoint_run_id")), str(task.get("stage")))
        groups[key][str(task.get("action_id"))] = (task, rec)

    samples = []
    decision_errors = []
    controls_missing = []
    for key in sorted(groups, key=lambda k: (DESIGN_ORDER.get(k[0], 99), RANK_ORDER.get(k[2], 99), k[1])):
        design, checkpoint_run_id, stage = key
        by_action = groups[key]
        control = by_action.get("control") or by_action.get("")
        if control is None:
            controls_missing.append("%s/%s/%s" % key)
            continue
        control_task, control_rec = control
        state = state_by_key.get((design, checkpoint_run_id, stage))
        if state is None:
            decision_errors.append("missing state card: %s" % (key,))
            continue
        base_metrics = metric_bundle(control_rec.get("metrics"))
        base_ok = control_rec.get("returncode") in (0, "0")
        for action_id, (task, rec) in sorted(by_action.items()):
            if action_id in ("control", ""):
                continue
            cand_metrics = metric_bundle(rec.get("metrics"))
            gate = evaluate_gate(cand_metrics, base_metrics, rec.get("returncode"))
            util = metrics_schema.utility(cand_metrics, base_metrics)
            selection = util if gate["gate_ok"] else util - SELECTION_UNSAFE_PENALTY
            samples.append({
                "sample_id": str(rec.get("run_id")),
                "decision_id": "ckpt_%s_%s" % (checkpoint_run_id, stage),
                "design": design,
                "family": design,
                "stage": stage,
                "checkpoint_run_id": checkpoint_run_id,
                "checkpoint_def": control_task.get("checkpoint_def"),
                "state": state_card_bundle(state),
                "action_id": action_id,
                "action": task.get("action") or {},
                "control_run_id": str(control_rec.get("run_id")),
                "candidate_run_id": str(rec.get("run_id")),
                "returncode": rec.get("returncode"),
                "duration_s": fnum(rec.get("duration_s")),
                "control_rc_ok": base_ok,
                "control_metrics": base_metrics,
                "candidate_metrics": cand_metrics,
                "gate_ok": gate["gate_ok"],
                "rc_ok": gate["rc_ok"],
                "drc_ok": gate["drc_ok"],
                "timing_guard": gate["timing_guard"],
                "utility": util,
                "selection_score": selection,
                "delta": delta_block(cand_metrics, base_metrics),
                "relative": relative_block(cand_metrics, base_metrics),
                "cost_s": fnum(rec.get("duration_s")),
                "control_cost_s": fnum(control_rec.get("duration_s")),
                "metric_convention_version": "metrics_v2_2026-09-22",
                "timing_convention": metrics_schema.TIMING_VERSION,
                "utility_spec": metrics_schema.utility_spec(),
                "guard_ns": guard_ns,
            })
    return samples, controls_missing, decision_errors


def group_decisions(samples):
    groups = defaultdict(list)
    for s in samples:
        groups[s["decision_id"]].append(s)
    out = []
    for did, rows in groups.items():
        rows = sorted(rows, key=lambda r: r["action_id"])
        ranked = sorted(rows, key=lambda r: (r["gate_ok"], r["selection_score"]), reverse=True)
        safe = [r for r in ranked if r["gate_ok"]]
        oracle = safe[0]["action_id"] if safe else None
        for rank, r in enumerate(ranked, 1):
            r["action_rank"] = rank
            r["is_oracle"] = (r["action_id"] == oracle)
        out.append({
            "decision_id": did,
            "design": rows[0]["design"],
            "family": rows[0]["family"],
            "stage": rows[0]["stage"],
            "checkpoint_run_id": rows[0]["checkpoint_run_id"],
            "checkpoint_def": rows[0]["checkpoint_def"],
            "state": rows[0]["state"],
            "control_run_id": rows[0]["control_run_id"],
            "control_metrics": rows[0]["control_metrics"],
            "control_cost_s": rows[0]["control_cost_s"],
            "n_candidates": len(rows),
            "n_gate_ok": sum(1 for r in rows if r["gate_ok"]),
            "oracle_action_id": oracle,
            "oracle_utility": safe[0]["utility"] if safe else None,
            "oracle_guard_ok_pct": (100.0 * len(safe) / len(rows)) if rows else None,
            "candidates": rows,
            "utility_spec": metrics_schema.utility_spec(),
        })
    return out


def to_sft(decision):
    lines = []
    lines.append("Design state (checkpoint): " + json.dumps(decision["state"], ensure_ascii=False))
    lines.append("Control (do nothing) metrics: " + json.dumps(decision["control_metrics"], ensure_ascii=False))
    lines.append("Candidate downstream actions (after the checkpoint):")
    control_line = {
        "action_id": "control",
        "action": {},
        "gate_ok": True,
        "delta": {k: 0.0 for k in decision["candidates"][0]["delta"]},
        "utility": 0.0,
        "cost_s": decision["control_cost_s"],
    }
    lines.append(json.dumps(control_line, ensure_ascii=False))
    for c in sorted(decision["candidates"], key=lambda r: r["action_id"]):
        lines.append(json.dumps({
            "action_id": c["action_id"],
            "action": c["action"],
            "gate_ok": c["gate_ok"],
            "delta": c["delta"],
            "utility": c["utility"],
            "cost_s": c["cost_s"],
        }, ensure_ascii=False))
    lines.append(
        "Timing gate (canonical): setup_wns_ns >= control_setup_wns_ns - 0.02 ns and "
        "hold_wns_ns >= control_hold_wns_ns - 0.02 ns; if the control value is nonnegative the "
        "candidate must stay nonnegative; DRC must not increase. WNS is a gate only; among "
        "timing-safe candidates choose by U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power. "
        "Output JSON with action_id."
    )
    return {
        "messages": [
            {"role": "system", "content": "You are an EDA hyper-heuristic selector at a checkpoint decision point. Output JSON only."},
            {"role": "user", "content": "\n".join(lines)},
            {"role": "assistant", "content": json.dumps({"action_id": decision["oracle_action_id"]}, ensure_ascii=False)},
        ],
        "design": decision["design"],
        "stage": decision["stage"],
        "decision_id": decision["decision_id"],
        "oracle_action_id": decision["oracle_action_id"],
    }


def to_preferences(decisions):
    prefs = []
    for d in decisions:
        ranked = sorted(d["candidates"], key=lambda r: (r["gate_ok"], r["selection_score"]), reverse=True)
        safe = [c for c in ranked if c["gate_ok"]]
        pos = [{"action_id": c["action_id"], "utility": c["utility"], "selection_score": c["selection_score"]} for c in safe if c["selection_score"] > 0.0]
        neg = [{"action_id": c["action_id"], "utility": c["utility"], "selection_score": c["selection_score"]} for c in safe if c["selection_score"] < 0.0]
        prefs.append({
            "decision_id": d["decision_id"],
            "design": d["design"],
            "stage": d["stage"],
            "state": d["state"],
            "control_run_id": d["control_run_id"],
            "oracle_action_id": d["oracle_action_id"],
            "positives": pos,
            "negatives": neg,
            "ranking": [{"action_id": c["action_id"], "gate_ok": c["gate_ok"], "utility": c["utility"], "selection_score": c["selection_score"]} for c in ranked],
        })
    return prefs


def validate(samples, decisions):
    errors = []
    warnings = []
    seen = set()
    for s in samples:
        key = (s["checkpoint_run_id"], s["stage"], s["action_id"])
        if key in seen:
            errors.append("duplicate sample key: %s" % (key,))
        seen.add(key)
        for field in ["setup_wns_ns", "hpwl_route_um", "drc_violations"]:
            if fnum(s["candidate_metrics"].get(field)) is None:
                warnings.append("missing candidate metric %s in %s" % (field, s["sample_id"]))
        for field, val in (s.get("delta") or {}).items():
            if val is not None and not math.isfinite(val):
                errors.append("non-finite delta %s in %s" % (field, s["sample_id"]))
    for d in decisions:
        actions = [c["action_id"] for c in d["candidates"]]
        if len(actions) != len(set(actions)):
            errors.append("duplicate actions in decision %s" % d["decision_id"])
        if not d["control_run_id"]:
            errors.append("missing control for %s" % d["decision_id"])
    return errors, warnings


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Build checkpoint selector dataset v5")
    ap.add_argument("--states", default="results/canonical_server/checkpoint_states_v1.jsonl")
    ap.add_argument("--replay", default="results/canonical_server/checkpoint_replay_v2.jsonl")
    ap.add_argument("--plan", default="results/canonical_server/replay_batch_plan_v2.jsonl")
    ap.add_argument("--out-jsonl", default="results/canonical_server/selector_dataset_v5_checkpoint.jsonl")
    ap.add_argument("--out-sft", default="results/canonical_server/selector_sft_v5_checkpoint.jsonl")
    ap.add_argument("--out-preferences", default="results/canonical_server/selector_preferences_v5_checkpoint.jsonl")
    ap.add_argument("--out-summary", default="results/canonical_server/selector_dataset_v5_summary.json")
    ap.add_argument("--guard-ns", type=float, default=0.02)
    ap.add_argument("--strict", action="store_true", help="exit 1 if validation errors found")
    args = ap.parse_args()

    samples, controls_missing, decision_errors = build(args.states, args.replay, args.plan, args.guard_ns)
    decisions = group_decisions(samples)
    decisions.sort(key=lambda d: (DESIGN_ORDER.get(d["design"], 99), RANK_ORDER.get(d["stage"], 99), d["checkpoint_run_id"]))
    errors, warnings = validate(samples, decisions)
    errors = errors + ["missing control: %s" % m for m in controls_missing] + decision_errors

    flat = []
    for d in decisions:
        for c in d["candidates"]:
            flat.append(c)
    flat.sort(key=lambda s: (DESIGN_ORDER.get(s["design"], 99), RANK_ORDER.get(s["stage"], 99), s["checkpoint_run_id"], s["action_id"]))
    sft = [to_sft(d) for d in decisions if d["oracle_action_id"]]
    prefs = to_preferences(decisions)

    by_design = Counter(s["design"] for s in flat)
    by_stage = Counter(s["stage"] for s in flat)
    by_action = Counter(s["action_id"] for s in flat)
    gate_by_action = Counter()
    total_by_action = Counter()
    for s in flat:
        total_by_action[s["action_id"]] += 1
        if s["gate_ok"]:
            gate_by_action[s["action_id"]] += 1
    oracle_dist = Counter(d["oracle_action_id"] for d in decisions if d["oracle_action_id"])
    summary = {
        "version": "selector_dataset_v5_checkpoint_2026-09-22",
        "n_states_total": len(load_jsonl(args.states)),
        "n_states_replayable": sum(1 for s in load_jsonl(args.states) if s.get("stage") in RANK_ORDER),
        "n_decisions": len(decisions),
        "n_controls": len({d["control_run_id"] for d in decisions}),
        "n_action_samples": len(flat),
        "n_sft": len(sft),
        "n_preferences": len(prefs),
        "by_design": dict(by_design),
        "by_stage": dict(by_stage),
        "by_action": dict(by_action),
        "gate_ok_by_action": {a: "%d/%d" % (gate_by_action[a], total_by_action[a]) for a in sorted(total_by_action)},
        "gate_ok_rate": (sum(1 for s in flat if s["gate_ok"]) / len(flat)) if flat else None,
        "oracle_action_distribution": dict(oracle_dist),
        "hold_wns_coverage": (sum(1 for s in flat if s["candidate_metrics"].get("hold_wns_ns") is not None) / len(flat)) if flat else None,
        "power_coverage": (sum(1 for s in flat if s["candidate_metrics"].get("power_w") is not None) / len(flat)) if flat else None,
        "no_oracle_decisions": [d["decision_id"] for d in decisions if not d["oracle_action_id"]],
        "missing_controls": controls_missing,
        "n_validation_errors": len(errors),
        "n_warnings": len(warnings),
        "errors": errors[:100],
        "warnings": sorted(set(warnings))[:100],
        "utility_spec": metrics_schema.utility_spec(),
        "gate_spec": "setup/hold >= control - %.3f ns; control nonnegative implies candidate nonnegative; DRC not increased" % args.guard_ns,
    }

    write_jsonl(args.out_jsonl, flat)
    write_jsonl(args.out_sft, sft)
    write_jsonl(args.out_preferences, prefs)
    Path(args.out_summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.strict and errors:
        raise SystemExit("checkpoint dataset validation failed: %d errors" % len(errors))


if __name__ == "__main__":
    main()
