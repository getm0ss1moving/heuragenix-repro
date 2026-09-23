"""Validate checkpoint_replay_v2.jsonl against plan v2 and checkpoint state cards.

Acceptance gates for PHASE0_REPORT_0011:
  - >=200 replay records;
  - every replayable checkpoint (post-GP/post-CTS) has a control record;
  - no duplicate run_id;
  - every record maps to a plan task with same checkpoint_def / action / stage;
  - all non-control actions have a same-checkpoint control;
  - failure rate < 5% (failures from the pool TSV or returncode not 0);
  - key metrics present (setup_wns_ns, hpwl_um, drc_violations).
Exit code 1 if a hard gate fails.
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path):
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception as exc:
            raise SystemExit("bad JSONL %s:%d: %s" % (p, n, exc))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Validate checkpoint replay v2 batch")
    ap.add_argument("--states", default="results/canonical_server/checkpoint_states_v1.jsonl")
    ap.add_argument("--plan", default="results/canonical_server/replay_batch_plan_v2.jsonl")
    ap.add_argument("--replay", default="results/canonical_server/checkpoint_replay_v2.jsonl")
    ap.add_argument("--failures", default="results/canonical_server/replay_batch_v2_failures.tsv")
    ap.add_argument("--min-records", type=int, default=200)
    ap.add_argument("--out-json", default=None, help="optional path to write the summary JSON")
    args = ap.parse_args()

    states = load_jsonl(args.states)
    plan = load_jsonl(args.plan)
    replay = load_jsonl(args.replay)
    failures = []
    fp = Path(args.failures)
    if fp.exists():
        for line in fp.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and "\t" in line:
                failures.append(line.split("\t")[0])
    failures = sorted(set(failures))

    plan_by_id = {str(t.get("run_id")): t for t in plan}
    replayable = [s for s in states if s.get("stage") in ("post_global_place", "post_cts")]

    errors, warnings = [], []
    ids = [str(r.get("run_id")) for r in replay]
    dups = [k for k, v in Counter(ids).items() if v > 1]
    if dups:
        errors.append("duplicate run_id: %s" % dups[:10])
    if len(replay) < args.min_records:
        errors.append("record count %d < min_records %d" % (len(replay), args.min_records))

    mapped = [r for r in replay if str(r.get("run_id")) in plan_by_id]
    unmapped = [str(r.get("run_id")) for r in replay if str(r.get("run_id")) not in plan_by_id]
    if unmapped:
        errors.append("records not in plan: %s" % unmapped[:10])

    plan_ids = set(plan_by_id)
    replay_ids = set(ids)
    missing_tasks = sorted(plan_ids - replay_ids)
    extra_ids = sorted(replay_ids - plan_ids)
    if extra_ids:
        errors.append("replay run_ids not in plan: %s" % extra_ids[:10])

    mismatch = []
    for r in mapped:
        t = plan_by_id[str(r.get("run_id"))]
        checks = [
            (str(r.get("design")) == str(t.get("design")), "design"),
            (str(r.get("stage")) == str(t.get("stage")), "stage"),
            (str(t.get("action_id")) == "control" or r.get("action") == t.get("action"), "action"),
        ]
        for ok, label in checks:
            if not ok:
                mismatch.append("%s:%s" % (r.get("run_id"), label))
                break
    if mismatch:
        errors.append("plan/replay mismatches: %s" % mismatch[:10])

    control_keys = set()
    action_keys = set()
    by_ckpt_actions = defaultdict(set)
    for r in replay:
        t = plan_by_id.get(str(r.get("run_id")))
        if not t:
            continue
        key = (str(t.get("design")), str(t.get("checkpoint_run_id")), str(t.get("stage")))
        aid = str(t.get("action_id"))
        if aid in ("control", ""):
            control_keys.add(key)
        else:
            action_keys.add(key)
        by_ckpt_actions[key].add(aid)

    expected_keys = {(str(s.get("design")), str(s.get("run_id")), str(s.get("stage"))) for s in replayable}
    missing_controls = sorted("%s/%s/%s" % k for k in expected_keys - control_keys)
    if missing_controls:
        errors.append("missing controls: %s" % missing_controls[:10])
    missing_action_controls = sorted("%s/%s/%s" % k for k in action_keys - control_keys)
    if missing_action_controls:
        errors.append("action without same-checkpoint control: %s" % missing_action_controls[:10])

    rc_bad = [str(r.get("run_id")) for r in replay if r.get("returncode") not in (0, "0")]
    replay_ok_ids = {str(r.get("run_id")) for r in replay if r.get("returncode") in (0, "0")}
    retried_ok = sorted(set(failures) & replay_ok_ids)
    effective_failures = [rid for rid in failures if rid not in replay_ok_ids]
    gate_bad = [str(r.get("run_id")) for r in replay if not r.get("gate_ok")]
    fail_rate = (len(rc_bad) / len(replay)) if replay else 1.0
    if fail_rate >= 0.05:
        errors.append("returncode failure rate %.3f >= 5%%" % fail_rate)

    metric_fields = ["setup_wns_ns", "hpwl_um", "drc_violations"]
    for r in replay:
        m = r.get("metrics") or {}
        missing = [f for f in metric_fields if m.get(f) is None]
        if missing:
            warnings.append("%s missing %s" % (r.get("run_id"), ",".join(missing)))

    by_design_stage = Counter((str(r.get("design")), str(r.get("stage"))) for r in replay)
    by_action = Counter()
    for r in replay:
        t = plan_by_id.get(str(r.get("run_id")))
        if t:
            by_action[str(t.get("action_id"))] += 1
    power_ok = sum(1 for r in replay if (r.get("metrics") or {}).get("total_power_w") is not None)
    hold_ok = sum(1 for r in replay if (r.get("metrics") or {}).get("hold_wns_ns") is not None)
    summary = {
        "records": len(replay),
        "plan_tasks": len(plan),
        "missing_tasks": len(missing_tasks),
        "missing_task_ids_first10": missing_tasks[:10],
        "replayable_checkpoints": len(replayable),
        "control_coverage": "%d/%d" % (len(control_keys & expected_keys), len(expected_keys)),
        "missing_controls": missing_controls,
        "duplicate_run_ids": dups,
        "returncode_bad": len(rc_bad),
        "returncode_fail_rate": fail_rate,
        "gate_ok": len(replay) - len(gate_bad),
        "pool_failure_ids": effective_failures,
        "pool_failure_count": len(effective_failures),
        "pool_failure_ids_raw": failures,
        "retried_ok_ids": retried_ok,
        "by_design_stage": {"%s/%s" % k: v for k, v in sorted(by_design_stage.items())},
        "by_action": dict(by_action),
        "power_coverage": "%d/%d" % (power_ok, len(replay)),
        "hold_wns_coverage": "%d/%d" % (hold_ok, len(replay)),
        "actions_per_checkpoint": sorted(set(len(v) for v in by_ckpt_actions.values())),
        "n_errors": len(errors),
        "n_warnings": len(warnings),
        "errors": errors,
        "warnings": sorted(set(warnings))[:20],
    }
    if args.out_json:
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit("VALIDATE_REPLAY_V2_FAILED")
    print("VALIDATE_REPLAY_V2_PASS")


if __name__ == "__main__":
    main()
