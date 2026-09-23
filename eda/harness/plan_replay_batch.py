"""Plan batch checkpoint replay for HA-PR EDA (session-3 handoff).

Reads checkpoint_states_v1.jsonl + config/replay_actions_v1.json; writes a
resume-safe plan + optional shell runner. Dry-run unless --execute.
Invoke as: python3 harness/plan_replay_batch.py [options]
"""
from __future__ import annotations
import argparse, json, os, re, shlex, shutil, subprocess, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_CATALOG = ROOT / "config" / "replay_actions_v1.json"
DEFAULT_STATES = ROOT / "results" / "canonical_server" / "checkpoint_states_v1.jsonl"
DEFAULT_BASE = os.environ.get("HEURA_EDA_BASE", "/data/dzy/heura_repr/eda")
DEFAULT_OUT = Path(DEFAULT_BASE) / "results" / "canonical_server" / "checkpoint_replay_v2.jsonl"
DEFAULT_PLAN = ROOT / "results" / "canonical_server" / "replay_batch_plan_v2.jsonl"
STAGE_ORDER = {"post_global_place": 0, "post_cts": 1}
DESIGN_ORDER = {"gcd": 0, "jpeg": 1, "aes": 2, "ibex": 3}
STAGE_SHORT = {"post_global_place": "pgp", "post_cts": "pcts"}


def sanitize(value):
    return re.sub(r"[^0-9A-Za-z_]+", "_", str(value)).strip("_")


def load_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception as exc:
            raise SystemExit("bad JSONL %s:%d: %s" % (path, n, exc))
    return rows


def split_csv(value):
    return [x.strip() for x in value.split(",") if x.strip()] if value else []


def load_catalog(path):
    data = json.loads(path.read_text())
    actions = data.get("actions", [])
    if not actions or actions[0].get("id") not in ("control",):
        raise SystemExit("action catalog must start with id=control: %s" % path)
    return data.get("version", "unknown"), data.get("design_defaults", {}), actions


def action_is_default(design, action, defaults):
    if not action:
        return False
    d = defaults.get(design, {})
    return all(k in d and d[k] == v for k, v in action.items())


def build_tasks(args):
    version, defaults, actions = load_catalog(Path(args.actions))
    states = load_jsonl(Path(args.states))
    replayable = [s for s in states if s.get("stage") in STAGE_ORDER]
    replayable.sort(key=lambda s: (
        DESIGN_ORDER.get(s.get("design"), 99),
        STAGE_ORDER.get(s.get("stage"), 99),
        str(s.get("run_id", "")),
    ))
    designs = set(split_csv(args.design))
    stages = set(split_csv(args.stages))
    action_ids = set(split_csv(args.action_ids))

    existing = {}
    out_path = Path(args.out_jsonl)
    if out_path.exists():
        for rec in load_jsonl(out_path):
            if rec.get("run_id"):
                existing[str(rec["run_id"])] = rec

    tasks, skipped_default = [], 0
    for state in replayable:
        design = str(state.get("design"))
        stage = str(state.get("stage"))
        if designs and design not in designs:
            continue
        if stages and stage not in stages:
            continue
        state_run = str(state.get("run_id"))
        checkpoint_rel = str(state.get("checkpoint_def"))
        checkpoint_abs = checkpoint_rel if checkpoint_rel.startswith("/") else str(Path(args.base) / checkpoint_rel)
        for entry in actions:
            aid = str(entry.get("id"))
            if action_ids and aid not in action_ids:
                continue
            action = entry.get("action") or {}
            if aid not in ("control",) and action_is_default(design, action, defaults):
                skipped_default += 1
                continue
            run_id = sanitize("replay_%s_%s_%s" % (state_run, STAGE_SHORT.get(stage, stage), aid))
            status = "planned"
            if not args.no_resume and run_id in existing:
                status = "skip_done"
            tasks.append({
                "task_index": 0, "run_id": run_id, "design": design, "stage": stage,
                "checkpoint_run_id": state_run, "checkpoint_def": checkpoint_abs,
                "action_id": aid, "action": action, "output_jsonl": str(out_path),
                "artifact_dir": str(Path(args.base) / "runs_replay" / run_id),
                "status": status,
            })
    if args.limit and len(tasks) > args.limit:
        tasks = tasks[:args.limit]
    for i, task in enumerate(tasks, 1):
        task["task_index"] = i
    summary = {
        "states_total": len(states), "states_replayable": len(replayable),
        "existing_output_records": len(existing), "skipped_design_default": skipped_default,
        "planned": sum(1 for t in tasks if t["status"] == "planned"),
        "skip_done": sum(1 for t in tasks if t["status"] == "skip_done"),
    }
    return version, tasks, summary


def write_plan(path, tasks, summary):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for task in tasks:
            fh.write(json.dumps(task, ensure_ascii=False) + "\n")
    summary_path = path.with_suffix(path.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return summary_path


def write_script(path, tasks, args, summary):
    path.parent.mkdir(parents=True, exist_ok=True)
    L = []
    L.append("set -uo pipefail")
    L.append('BASE="${HEURA_EDA_BASE:-%s}"' % args.base)
    L.append('OUT="%s"' % args.out_jsonl)
    L.append('FAIL="%s"' % (path.parent / "replay_batch_v2_failures.tsv"))
    L.append('cd "$BASE" || { echo "BASE not found: $BASE"; exit 2; }')
    L.append('mkdir -p "$(dirname "$OUT")" "$(dirname "$FAIL")"')
    L.append('touch "$FAIL"')
    L.append('run_one() {')
    L.append('  local rid="$1"; shift')
    L.append('  if grep -q "\\"run_id\\": \\"$rid\\"" "$OUT" 2>/dev/null; then')
    L.append('    echo "[skip] $rid"; return 0')
    L.append('  fi')
    L.append('  echo "[run ] $rid"')
    L.append('  if nice -n 10 python3 harness/checkpoint_replay.py "$@" --run-id "$rid" --out-jsonl "$OUT"; then')
    L.append('    return 0')
    L.append('  fi')
    L.append('  echo -e "$rid\\tFAILED" >> "$FAIL"')
    L.append('  return 0')
    L.append('}')
    for task in tasks:
        if task["status"] not in ("planned",):
            continue
        parts = [
            "run_one", shlex.quote(task["run_id"]),
            "--design", shlex.quote(task["design"]),
            "--stage", shlex.quote(task["stage"]),
            "--checkpoint-def", shlex.quote(task["checkpoint_def"]),
            "--action", shlex.quote(json.dumps(task["action"], ensure_ascii=False, separators=(",", ":"))),
            "--timeout", "1800",
        ]
        L.append(" ".join(parts))
    L.append('echo "REPLAY_BATCH_DONE planned=%d skip_done=%d failures=$(grep -c FAILED "$FAIL" 2>/dev/null || echo 0)"' % (summary["planned"], summary["skip_done"]))
    path.write_text("\n".join(L) + "\n")
    os.chmod(path, 0o755)
    return path


def run_execute(tasks, args):
    base = Path(args.base)
    if not base.exists():
        raise SystemExit("--execute requires existing HEURA_EDA_BASE: %s" % base)
    out_path = Path(args.out_jsonl)
    fail_path = Path(args.plan_out).parent / "replay_batch_v2_failures.tsv"
    existing = set()
    if out_path.exists():
        existing = {str(r.get("run_id")) for r in load_jsonl(out_path)}
    failures = []
    for task in tasks:
        if task["status"] not in ("planned",) or task["run_id"] in existing:
            print("[skip] %s" % task["run_id"], flush=True)
            continue
        raw = json.dumps(task["action"], ensure_ascii=False, separators=(",", ":"))
        cmd = [sys.executable, str(HERE / "checkpoint_replay.py"),
               "--design", task["design"], "--stage", task["stage"],
               "--checkpoint-def", task["checkpoint_def"], "--run-id", task["run_id"],
               "--action", raw, "--out-jsonl", str(out_path), "--timeout", "1800"]
        if shutil.which("nice"):
            cmd = ["nice", "-n", "10"] + cmd
        env = os.environ.copy()
        env["HEURA_EDA_BASE"] = args.base
        print("[run ] %s" % task["run_id"], flush=True)
        proc = subprocess.run(cmd, cwd=str(base), env=env)
        if proc.returncode not in (0,):
            failures.append(task["run_id"])
            fail_path.parent.mkdir(parents=True, exist_ok=True)
            with fail_path.open("a") as fh:
                fh.write("%s\tFAILED\n" % task["run_id"])
    planned = sum(1 for t in tasks if t["status"] == "planned")
    print("EXECUTE_DONE planned=%d failures=%d" % (planned, len(failures)))
    return failures


def main():
    p = argparse.ArgumentParser(description="Plan/execute batch checkpoint replay (session-3 handoff)")
    p.add_argument("--base", default=DEFAULT_BASE, help="server HA-PR base used to build absolute paths in plan")
    p.add_argument("--states", default=str(DEFAULT_STATES))
    p.add_argument("--actions", default=str(DEFAULT_CATALOG))
    p.add_argument("--out-jsonl", default=str(DEFAULT_OUT))
    p.add_argument("--plan-out", default=str(DEFAULT_PLAN))
    p.add_argument("--write-script", default=None, metavar="PATH", help="also write resume-safe sequential bash runner")
    p.add_argument("--execute", action="store_true", help="execute planned tasks sequentially (server side)")
    p.add_argument("--no-resume", action="store_true", help="ignore run_ids already in --out-jsonl")
    p.add_argument("--limit", type=int, default=0, help="limit selected tasks (smoke test)")
    p.add_argument("--design", default="", help="comma list: gcd,aes,jpeg,ibex")
    p.add_argument("--stages", default="", help="comma list: post_global_place,post_cts")
    p.add_argument("--action-ids", default="", help="comma list of action ids from catalog")
    args = p.parse_args()

    if not Path(args.states).exists():
        raise SystemExit("states not found: %s" % args.states)
    version, tasks, summary = build_tasks(args)
    summary["action_catalog"] = version
    summary["out_jsonl"] = args.out_jsonl
    summary_path = write_plan(Path(args.plan_out), tasks, summary)
    by_design = Counter(t["design"] for t in tasks if t["status"] == "planned")
    by_action = Counter(t["action_id"] for t in tasks if t["status"] == "planned")
    print(json.dumps({
        "action_catalog": version,
        "states_total": summary["states_total"],
        "states_replayable": summary["states_replayable"],
        "tasks_selected": len(tasks),
        "planned": summary["planned"],
        "skip_done": summary["skip_done"],
        "skipped_design_default_actions": summary["skipped_design_default"],
        "by_design": dict(by_design),
        "by_action": dict(by_action),
        "plan": args.plan_out,
        "summary": str(summary_path),
        "out_jsonl": args.out_jsonl,
    }, indent=2, ensure_ascii=False))
    if args.write_script:
        print("SCRIPT %s" % write_script(Path(args.write_script), tasks, args, summary))
    if args.execute:
        run_execute(tasks, args)


if __name__ == "__main__":
    main()
