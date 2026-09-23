
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import lef_def
import metric_rules


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1048576)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def as_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def runtime_s(value):
    if value is None:
        return None
    match = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:([0-9.]+)s)?", str(value))
    if not match:
        return None
    hours = float(match.group(1) or 0.0)
    minutes = float(match.group(2) or 0.0)
    seconds = float(match.group(3) or 0.0)
    return round(hours * 3600.0 + minutes * 60.0 + seconds, 3)


def main():
    parser = argparse.ArgumentParser(description="Ingest an OpenLane 1 run into the HA-PR Phase 0 format")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--lef", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    lef = Path(args.lef).resolve()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_csv = run_dir / "reports" / "metrics.csv"
    rows = list(csv.reader(metrics_csv.open()))
    header = rows[0]
    values = rows[1] if len(rows) > 1 else []
    raw = dict(zip(header, values))
    design = raw.get("design_name", run_dir.name)
    stage_defs = {
        "floorplan": run_dir / "results" / "floorplan" / (design + ".def"),
        "placement": run_dir / "results" / "placement" / (design + ".def"),
        "cts": run_dir / "results" / "cts" / (design + ".def"),
        "routing": run_dir / "results" / "routing" / (design + ".def"),
        "final": run_dir / "results" / "final" / "def" / (design + ".def"),
    }
    hpwl = {}
    for stage, def_path in stage_defs.items():
        if def_path.exists():
            hpwl[stage] = lef_def.def_metrics(def_path, lef, 1000.0, 1000.0)
    viol = metric_rules.openlane_violations(raw)
    drc_violations, drc_detailed, magic, klayout = metric_rules.canonical_drc(viol)
    antenna_total, antenna_pin, antenna_net = metric_rules.openlane_antenna(viol)
    power_w = metric_rules.openlane_power_w(raw)
    logic_cells, synth_cells, total_cells = metric_rules.openlane_cells(raw)
    hpwl_db, hpwl_um = metric_rules.hpwl_db_to_um(raw.get("HPWL"))
    metrics = {
        "source": "openlane1",
        "design": design,
        "flow_status": raw.get("flow_status"),
        "runtime_s": runtime_s(raw.get("total_runtime")),
        "instance_count": logic_cells,
        "logic_cell_count": logic_cells,
        "total_cell_count": total_cells,
        "area_um2": as_float(raw.get("CoreArea_um^2")),
        "core_area_um2": as_float(raw.get("CoreArea_um^2")),
        "die_area_mm2": as_float(raw.get("DIEAREA_mm^2")),
        "utilization_pct": as_float(raw.get("Final_Util")),
        "utilization_convention": "Final_Util percent of core area from OpenLane signoff report",
        "setup_wns_ns": as_float(raw.get("wns")),
        "setup_tns_ns": as_float(raw.get("tns")),
        "hold_wns_ns": None,
        "hold_tns_ns": None,
        "timing_convention": "setup_hold_v1_2026-09-22",
        "timing_source_note": "OpenLane metrics.csv wns/tns treated as setup (max-delay) WNS/TNS; hold fields require OpenROAD raw metrics.",
        "power_w": round(power_w, 12),
        "power_unit_note": "OpenLane 1 columns named power_*_uW contain values in W; summed without 1e6 conversion.",
        "wirelength_um": as_float(raw.get("wire_length")),
        "wirelength_source": "detailed router log Total wire length (um)",
        "vias": as_float(raw.get("vias")),
        "vias_source": "detailed router log Total number of vias",
        "drc_violations": drc_violations,
        "drc_detailed_route": drc_detailed,
        "drc_magic": magic,
        "drc_klayout": klayout,
        "drc_source_note": "canonical drc = max(KLayout, Magic) if signoff DRC available, else detailed-route total; subcategory counts are not summed with tritonRoute total",
        "antenna_pin_violations": antenna_pin,
        "antenna_net_violations": antenna_net,
        "antenna_violations": antenna_total,
        "lvs_errors": as_float(raw.get("lvs_total_errors")),
        "hpwl_metric_csv_db": hpwl_db,
        "hpwl_metric_csv_um": hpwl_um,
        "hpwl_metric_source": "OpenLane global placement log HPWL (DB units), converted /1000 to um; separate from DEF pin-offset HPWL",
        "metric_convention_version": "metrics_v2_2026-09-22",
        "fidelity": {
            "stage_defs": {k: str(v) for k, v in stage_defs.items() if v.exists()},
            "hpwl_by_stage": hpwl,
            "pdk_lef": str(lef),
        },
    }
    meta = {
        "run_id": run_dir.name,
        "source": "openlane1",
        "design": design,
        "run_dir": str(run_dir),
        "openlane_commit": (run_dir / "OPENLANE_COMMIT").read_text().strip() if (run_dir / "OPENLANE_COMMIT").exists() else None,
        "pdk_sources": (run_dir / "PDK_SOURCES").read_text().strip() if (run_dir / "PDK_SOURCES").exists() else None,
        "artifacts": {},
    }
    for rel in ["reports/metrics.csv", "results/placement/" + design + ".def",
                "results/cts/" + design + ".def", "results/routing/" + design + ".def",
                "results/final/def/" + design + ".def", "openlane.log"]:
        fp = run_dir / rel
        if fp.exists():
            meta["artifacts"][rel] = {"size": fp.stat().st_size, "sha256": sha256(fp)}
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    gate = {
        "flow_completed": str(metrics["flow_status"]).lower().find("completed") >= 0,
        "drc_zero": (metrics["drc_violations"] == 0),
        "lvs_zero": (metrics["lvs_errors"] == 0),
    }
    card = {
        "run_id": run_dir.name,
        "design": design,
        "stage": "post_signoff",
        "legality": gate,
        "metrics": {
            "instance_count": metrics["instance_count"],
            "logic_cell_count": metrics["logic_cell_count"],
            "total_cell_count": metrics["total_cell_count"],
            "hpwl_placement_um": (hpwl.get("placement") or {}).get("hpwl_um"),
            "hpwl_routing_um": (hpwl.get("routing") or {}).get("hpwl_um"),
            "setup_wns_ns": metrics["setup_wns_ns"],
            "hold_wns_ns": metrics["hold_wns_ns"],
            "setup_tns_ns": metrics["setup_tns_ns"],
            "drc_violations": metrics["drc_violations"],
            "drc_detailed_route": metrics["drc_detailed_route"],
            "drc_klayout": metrics["drc_klayout"],
            "drc_magic": metrics["drc_magic"],
            "lvs_errors": metrics["lvs_errors"],
            "power_w": metrics["power_w"],
            "wirelength_um": metrics["wirelength_um"],
            "vias": metrics["vias"],
            "runtime_s": metrics["runtime_s"],
            "metric_convention_version": metrics["metric_convention_version"],
        },
        "budget": {"time_left_s": None},
    }
    (out_dir / "state_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False))
    print(json.dumps(card, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
