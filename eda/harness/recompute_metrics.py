"""Recompute canonical metrics from existing run artifacts.

This is the server-side migration path after the 2026-09-22 metric audit.
It does NOT rerun the flow; it recomputes derived fields from DEF snapshots and
flow.log so old runs can be upgraded without burning tool time.

Modes
-----
--runs-dir DIR         recompute runs/*/metrics.json in place (optional --in-place)
--sweep JSON           recompute records in a legacy sweep/candidate JSON
--openlane-ingest DIR  print the command to re-ingest an OpenLane run

Default LEF search:
  $HEURA_EDA_BASE/flow/sky130hd/sky130_fd_sc_hd_merged.lef
  ./pdk/sky130A/sky130_fd_sc_hd.lef
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import lef_def
import metric_rules
import metrics_schema


def default_lef():
    candidates = []
    base = os.environ.get("HEURA_EDA_BASE")
    if base:
        candidates.append(Path(base) / "flow" / "sky130hd" / "sky130_fd_sc_hd_merged.lef")
    candidates.append(Path.cwd() / "pdk" / "sky130A" / "sky130_fd_sc_hd.lef")
    for p in candidates:
        if p.exists():
            return p
    return None


def design_dims(design, fallback=(1000.0, 1000.0)):
    try:
        import phase0
        cfg = phase0.DESIGNS.get(design)
        if cfg:
            return float(cfg["die_w"]), float(cfg["die_h"])
    except Exception:
        pass
    return fallback


def recompute_run(run_dir, lef, in_place=False):
    rd = Path(run_dir)
    metrics_path = rd / "metrics.json"
    if not metrics_path.exists():
        return None
    metrics = json.loads(metrics_path.read_text())
    design = metrics.get("design", rd.name)
    die_w, die_h = design_dims(design)
    updated = dict(metrics)

    # timing canonical fields
    canonical = metrics_schema.canonicalize_record(metrics)
    updated.update(metrics_schema.extract_timing_from_raw(metrics.get("raw", {}) or {}))
    for field in metrics_schema.CANONICAL_FIELDS:
        if updated.get(field) is not None:
            canonical[field] = updated[field]
    for field in metrics_schema.CANONICAL_FIELDS:
        updated[field] = canonical.get(field)

    # geometry
    changed_geom = 0
    for label, suffix in [("global_place", "global_place"), ("cts", "cts"), ("route", "route")]:
        fp = rd / "results" / ("%s_sky130hd_%s.def" % (design, suffix))
        if fp.exists():
            updated["def_" + label] = lef_def.def_metrics(str(fp), str(lef), die_w, die_h)
            changed_geom += 1

    # power from flow.log
    log_path = rd / "flow.log"
    if log_path.exists():
        power = metric_rules.parse_power_log_line(log_path.read_text(errors="replace"))
        if power:
            updated.update(power)

    updated["metric_convention_version"] = "metrics_v2_2026-09-22"
    updated["recomputed_from_artifacts"] = True
    updated["recompute_note"] = (
        "setup=DRT::worst_slack_max, hold=DRT::worst_slack_min, tns=DRT::tns_max; "
        "HPWL=pin-offset with top-level ports (hpwl_no_ports_um also stored); "
        "power=OpenSTA Total line in W"
    )
    if in_place:
        metrics_path.write_text(json.dumps(updated, indent=2, ensure_ascii=False))
    return updated


def recompute_sweep(sweep_path, runs_dir, lef, in_place=False, out_suffix=".recomputed"):
    src = Path(sweep_path)
    obj = json.loads(src.read_text())
    runs = obj.get("runs", []) if isinstance(obj, dict) else obj
    cache = {}
    changed = 0
    for rec in runs:
        run_id = rec.get("run_id")
        if not run_id:
            continue
        rd = Path(runs_dir) / run_id
        if run_id not in cache:
            cache[run_id] = recompute_run(rd, lef, in_place=False)
        updated = cache[run_id]
        if not updated:
            continue
        route = updated.get("def_route", {}) or {}
        rec["hpwl_route_um"] = route.get("hpwl_um")
        rec["hpwl_no_ports_um"] = route.get("hpwl_no_ports_um")
        rec["hpwl_origin_um"] = route.get("hpwl_origin_um")
        rec["hpwl_convention"] = route.get("hpwl_convention")
        rec["setup_wns_ns"] = updated.get("setup_wns_ns")
        rec["hold_wns_ns"] = updated.get("hold_wns_ns")
        rec["setup_tns_ns"] = updated.get("setup_tns_ns")
        rec["hold_tns_ns"] = updated.get("hold_tns_ns")
        rec["total_power_w"] = updated.get("total_power_w")
        rec["metric_convention_version"] = updated.get("metric_convention_version")
        changed += 1
    if in_place:
        src.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
        dest = src
    else:
        dest = src.with_suffix(src.suffix + out_suffix)
        dest.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    return dest, changed


def main():
    parser = argparse.ArgumentParser(description="Recompute canonical metrics from existing run artifacts")
    parser.add_argument("--runs-dir", default=None)
    parser.add_argument("--sweep", nargs="*", default=[])
    parser.add_argument("--runs-for-sweep", default=None, help="run dir root used by --sweep records")
    parser.add_argument("--lef", default=None)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    lef = Path(args.lef) if args.lef else default_lef()
    if lef is None or not lef.exists():
        raise SystemExit("LEF not found; pass --lef")
    if args.runs_dir:
        runs_dir = Path(args.runs_dir)
        n = 0
        for rd in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
            out = recompute_run(rd, lef, in_place=args.in_place)
            if out is not None:
                n += 1
        print("recomputed_runs", n, "in_place", args.in_place, "dry_run", args.dry_run)
    for sweep in args.sweep:
        runs_root = args.runs_for_sweep or args.runs_dir
        if runs_root is None:
            raise SystemExit("--runs-for-sweep (or --runs-dir) is required with --sweep")
        dest, n = recompute_sweep(sweep, runs_root, lef, in_place=args.in_place)
        print("recomputed_sweep", sweep, "->", dest, "records", n)


if __name__ == "__main__":
    main()
