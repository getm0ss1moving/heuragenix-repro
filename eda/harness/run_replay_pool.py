"""Dynamic bounded-parallel runner for HA-PR checkpoint replay (session 4).

Reads the resume-safe plan from plan_replay_batch.py, runs pending tasks with a
bounded process pool, one part JSONL per task, and merges records into the
canonical out JSONL. Re-run safely: run_ids already in out / parts / --seed-jsonl
are skipped. Use --dry-run to inspect the pending set.

Usage (server 224):
  python3 harness/run_replay_pool.py \
    --plan results/canonical_server/replay_batch_plan_v2.jsonl \
    --out-jsonl results/canonical_server/checkpoint_replay_v2.jsonl \
    --parts-dir results/canonical_server/v2_parts \
    --failures results/canonical_server/replay_batch_v2_failures.tsv \
    --seed-jsonl results/canonical_server/checkpoint_replay_v2_smoke.jsonl \
    --seed-jsonl results/canonical_server/checkpoint_replay_pilot.jsonl \
    --jobs 8
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = os.environ.get("HEURA_EDA_BASE", "/data/dzy/heura_repr/eda")


def load_jsonl(path, label=""):
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
        except Exception:
            print("[pool] WARN ignoring malformed line %s:%d (%s)" % (p, n, label), flush=True)
    return rows


def rec_ok(rec):
    if not isinstance(rec, dict):
        return False
    if not str(rec.get("run_id", "")):
        return False
    return rec.get("returncode") in (0, "0")


def append_jsonl(path, rec):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def append_text(path, line):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(line + "\n")


def main():
    ap = argparse.ArgumentParser(description="Bounded-parallel checkpoint replay pool")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out-jsonl", required=True)
    ap.add_argument("--parts-dir", required=True)
    ap.add_argument("--failures", required=True)
    ap.add_argument("--seed-jsonl", action="append", default=[])
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--only-design", default="")
    ap.add_argument("--only-stage", default="")
    ap.add_argument("--only-action", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = Path(args.base)
    if not base.exists():
        raise SystemExit("[pool] base not found: %s" % base)

    plan_rows = load_jsonl(args.plan, "plan")
    tasks, seen = [], set()
    for r in plan_rows:
        rid = str(r.get("run_id", ""))
        if not rid or rid in seen:
            continue
        seen.add(rid)
        tasks.append(r)
    by_id = {str(r["run_id"]): r for r in tasks}

    done = {}
    for f in args.seed_jsonl:
        for rec in load_jsonl(f, "seed"):
            rid = str(rec.get("run_id", ""))
            if rid in by_id and rec_ok(rec):
                done[rid] = rec
    out_path = Path(args.out_jsonl)
    out_rows = load_jsonl(out_path, "out")
    kept = []
    seen_out = set()
    dropped = 0
    for rec in out_rows:
        rid = str(rec.get("run_id", ""))
        if not rid or rid in seen_out or not rec_ok(rec):
            dropped += 1
            continue
        seen_out.add(rid)
        kept.append(rec)
    if dropped:
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w") as fh:
            for rec in kept:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp, out_path)
        print("[pool] compacted out: dropped %d invalid/duplicate records" % dropped, flush=True)
    out_ids = set()
    for rec in kept:
        rid = str(rec.get("run_id", ""))
        out_ids.add(rid)
        if rid in by_id:
            done[rid] = rec
    parts_dir = Path(args.parts_dir)
    if parts_dir.exists():
        for part_file in sorted(parts_dir.glob("*.jsonl")):
            for rec in load_jsonl(part_file, "part"):
                rid = str(rec.get("run_id", ""))
                if rid in by_id and rec_ok(rec):
                    done[rid] = rec

    merged = 0
    for rid in sorted(done):
        if rid in out_ids:
            continue
        append_jsonl(out_path, done[rid])
        out_ids.add(rid)
        merged += 1

    def selected(r):
        if args.only_design and str(r.get("design")) not in args.only_design.split(","):
            return False
        if args.only_stage and str(r.get("stage")) not in args.only_stage.split(","):
            return False
        if args.only_action and str(r.get("action_id")) not in args.only_action.split(","):
            return False
        return r.get("status") != "skip_done"

    pending = [r for r in tasks if str(r["run_id"]) not in done and selected(r)]
    print("[pool] plan_rows=%d unique_tasks=%d done_seed_out_parts=%d merged_into_out=%d pending=%d jobs=%d"
          % (len(plan_rows), len(tasks), len(done), merged, len(pending), args.jobs), flush=True)
    if args.dry_run:
        for r in pending[:30]:
            print("[dry-run] %-70s %-4s %-18s %s" % (r["run_id"], r["design"], r["stage"], r.get("action_id")), flush=True)
        print("[pool] dry-run end pending=%d" % len(pending), flush=True)
        return

    parts_dir.mkdir(parents=True, exist_ok=True)
    fail_path = Path(args.failures)
    failures = []
    start = time.time()
    total = len(pending)
    finished = 0
    acc_s = 0.0
    nice = shutil.which("nice")

    def run_one(task):
        rid = str(task["run_id"])
        part_path = parts_dir / ("%s.jsonl" % rid)
        if part_path.exists():
            rows = load_jsonl(part_path, "part-resume")
            if rows and str(rows[-1].get("run_id")) == rid and rec_ok(rows[-1]):
                return task, rows[-1], 0.0, True
            part_path.unlink()
        cmd = [sys.executable, str(HERE / "checkpoint_replay.py"),
               "--design", str(task["design"]),
               "--stage", str(task["stage"]),
               "--checkpoint-def", str(task["checkpoint_def"]),
               "--run-id", rid,
               "--action", json.dumps(task.get("action") or {}, ensure_ascii=False, separators=(",", ":")),
               "--out-jsonl", str(part_path),
               "--timeout", str(args.timeout)]
        if nice:
            cmd = [nice, "-n", "10"] + cmd
        env = os.environ.copy()
        env["HEURA_EDA_BASE"] = str(base)
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=str(base), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        dt = time.time() - t0
        rows = load_jsonl(part_path, "part-result")
        rec = rows[-1] if rows else None
        if rec is not None and str(rec.get("run_id")) != rid:
            rec = None
        ok = proc.returncode == 0 and rec is not None and rec_ok(rec)
        return task, rec, dt, ok

    if total == 0:
        print("[pool] nothing to do; all planned run_ids already present", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        futs = {ex.submit(run_one, t): t for t in pending}
        for fut in as_completed(futs):
            task = futs[fut]
            rid = str(task["run_id"])
            try:
                _, rec, dt, ok = fut.result()
            except Exception as exc:
                rec, dt, ok = None, 0.0, False
                print("[pool] EXC %s: %r" % (rid, exc), flush=True)
            finished += 1
            acc_s += dt
            if ok and rec is not None:
                append_jsonl(out_path, rec)
                done[rid] = rec
                print("[%d/%d] OK   %-64s %6.0fs" % (finished, total, rid, dt), flush=True)
            else:
                append_text(fail_path, "%s\tFAILED" % rid)
                failures.append(rid)
                print("[%d/%d] FAIL %-64s %6.0fs" % (finished, total, rid, dt), flush=True)

    elapsed = time.time() - start
    ok_n = total - len(failures)
    print("[pool] DONE ok=%d fail=%d elapsed=%.0fs avg_run=%.1fs out=%s failures=%s"
          % (ok_n, len(failures), elapsed, (acc_s / total if total else 0.0), out_path, fail_path), flush=True)
    if failures:
        print("[pool] failed run_ids: %s" % ",".join(failures[:50]), flush=True)


if __name__ == "__main__":
    main()
