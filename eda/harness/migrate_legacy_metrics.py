"""Migrate legacy timing fields to the canonical setup/hold convention.

Modes
-----
--runs-dir DIR       scan DIR/*/metrics.json, canonicalize timing fields, write
                     metrics_canonical.json (and optionally update metrics.json)
--candidates FILE... canonicalize candidate/sweep JSON files, write
                     <stem>.canonical.json next to the source unless --out-dir
--audit FILE...      print missing-field audit only

Canonical fields: setup_wns_ns, hold_wns_ns, setup_tns_ns, hold_tns_ns.
See harness/metrics_schema.py and docs/METRIC_CONVENTIONS.md.
"""

import argparse
import json
from pathlib import Path

import metrics_schema


def migrate_run(run_dir, in_place=False, out_name="metrics_canonical.json"):
    rd = Path(run_dir)
    metrics_path = rd / "metrics.json"
    if not metrics_path.exists():
        return None
    metrics = json.loads(metrics_path.read_text())
    canonical = metrics_schema.canonicalize_record(metrics)
    # keep canonical fields at top level; do not clobber legacy keys
    out = dict(metrics)
    for field in metrics_schema.CANONICAL_FIELDS:
        out[field] = canonical.get(field)
    out["timing_convention"] = metrics_schema.TIMING_VERSION
    (rd / out_name).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    if in_place:
        metrics_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out


def migrate_candidates(path, out_dir=None):
    src = Path(path)
    obj = json.loads(src.read_text())
    if isinstance(obj, dict) and isinstance(obj.get("runs"), list):
        for rec in obj["runs"]:
            rec.update(metrics_schema.canonicalize_record(rec))
        out_obj = obj
    elif isinstance(obj, list):
        out_obj = [metrics_schema.canonicalize_record(rec) for rec in obj]
    else:
        out_obj = metrics_schema.canonicalize_record(obj)
    if out_dir:
        dest = Path(out_dir) / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
    else:
        dest = src.with_suffix(".canonical.json")
    dest.write_text(json.dumps(out_obj, indent=2, ensure_ascii=False))
    return dest


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy WNS fields to canonical setup/hold convention")
    parser.add_argument("--runs-dir", default=None)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--candidates", nargs="*", default=[])
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--audit", nargs="*", default=[])
    args = parser.parse_args()
    if args.runs_dir:
        runs_dir = Path(args.runs_dir)
        n = 0
        for rd in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
            out = migrate_run(rd, in_place=args.in_place)
            if out is not None:
                n += 1
        print("migrated_runs", n)
    for path in args.candidates:
        dest = migrate_candidates(path, out_dir=args.out_dir)
        print("migrated_candidates", dest)
    for path in args.audit:
        obj = json.loads(Path(path).read_text())
        records = obj.get("runs", []) if isinstance(obj, dict) else (obj if isinstance(obj, list) else [obj])
        print(json.dumps(metrics_schema.audit_records(records, label=str(path)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
