"""Offline status snapshot for the HA-PR EDA handoff (no server access).

Run: python3 harness/session_status.py
It answers: which canonical artifacts exist, how many checkpoint labels are
done, which (design, stage) controls are still missing, and what to run next.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CS = ROOT / "results" / "canonical_server"
STAGES = ("post_global_place", "post_cts")
SHORT = {"post_global_place": "pgp", "post_cts": "pcts"}


def load_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def is_control(rec):
    return rec.get("action") in ({}, None)


def main():
    states = load_jsonl(CS / "checkpoint_states_v1.jsonl")
    replay_v1 = load_jsonl(CS / "checkpoint_replay_v1.jsonl")
    replay_v2 = load_jsonl(CS / "checkpoint_replay_v2.jsonl")
    plan = load_jsonl(CS / "replay_batch_plan_v2.jsonl")
    replayable = [s for s in states if s.get("stage") in STAGES]

    print("=" * 66)
    print("HA-PR EDA session status (offline)")
    print("=" * 66)
    print("canonical dir:", CS)
    for name in ["PHASE0_STATS_4designs_server.json", "PHASE0_SELECTOR_4designs_server.json",
                 "PHASE0_SELECTOR_4designs_server_api.json", "selector_dataset_v4.jsonl",
                 "checkpoint_states_v1.jsonl", "checkpoint_replay_v1.jsonl"]:
        print("  [%s] %s" % ("ok" if (CS / name).exists() else "MISS", name))
    print("-" * 66)
    print("states: %d total, %d replayable (post-GP/post-CTS)" % (len(states), len(replayable)))
    for (design, stage), n in sorted(Counter((s.get("design"), s.get("stage")) for s in replayable).items()):
        print("  %-5s %-18s %d" % (design, stage, n))
    print("replay labels: v1=%d, v2=%d" % (len(replay_v1), len(replay_v2)))
    for label, rows in (("v1", replay_v1), ("v2", replay_v2)):
        if rows:
            print("  %s by design/stage: %s" % (label, dict(Counter(
                (r.get("design"), r.get("stage")) for r in rows))))
            print("  %s gate_ok=%d failed_rc=%d controls=%d" % (
                label, sum(1 for r in rows if r.get("gate_ok")),
                sum(1 for r in rows if r.get("returncode") not in (0, None)),
                sum(1 for r in rows if is_control(r))))
    matched_controls, missing = [], []
    for s in replayable:
        rid = "replay_%s_%s_control" % (s.get("run_id"), SHORT.get(s.get("stage")))
        (matched_controls if any(r.get("run_id") == rid for r in replay_v2) else missing).append(rid)
    print("control coverage: %d/%d replayable checkpoints" % (len(matched_controls), len(replayable)))
    if missing:
        print("  missing controls (first 10):")
        for rid in missing[:10]:
            print("   ", rid)
    print("-" * 66)
    if plan:
        print("plan v2: %d tasks, status=%s" % (
            len(plan), dict(Counter(t.get("status") for t in plan))))
        print("  planned by action: %s" % dict(Counter(
            t.get("action_id") for t in plan if t.get("status") == "planned")))
        print("  planned by design: %s" % dict(Counter(
            t.get("design") for t in plan if t.get("status") == "planned")))
    else:
        print("plan v2: not generated yet")
    print("-" * 66)
    print("next:")
    print("  1) python3 harness/smoke_test.py")
    print("  2) python3 harness/plan_replay_batch.py --design gcd --action-ids control,layeradj_std,grt200 --limit 6 \
  --plan-out results/canonical_server/replay_batch_plan_smoke.jsonl")
    print("  3) read HANDOFF_SESSION3_NEXT.md then run a server smoke batch under tmux")
    print("handoff:", ROOT / "HANDOFF_SESSION3_NEXT.md")


if __name__ == "__main__":
    main()
