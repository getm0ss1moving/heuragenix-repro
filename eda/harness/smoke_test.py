"""Offline smoke tests for the canonical timing schema and record collection.

Run from eda/:  python3 harness/smoke_test.py
No OpenROAD or network required.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics_schema as ms
import collect_runs
import build_selector_dataset as bsd
import metric_rules


def test_canonicalization():
    raw = {
        "DRT::worst_slack_max": "-1.0944",
        "DRT::worst_slack_min": "0.0402",
        "DRT::tns_max": "-129.9",
    }
    c = ms.canonicalize_record({"raw": raw})
    assert abs(c["setup_wns_ns"] - (-1.0944)) < 1e-9
    assert abs(c["hold_wns_ns"] - 0.0402) < 1e-9
    assert abs(c["setup_tns_ns"] - (-129.9)) < 1e-9
    legacy = ms.canonicalize_record({"wns_min_ns": 0.0402, "wns_max_ns": -1.0944, "tns_ns": -129.9})
    assert abs(legacy["setup_wns_ns"] - (-1.0944)) < 1e-9
    assert abs(legacy["hold_wns_ns"] - 0.0402) < 1e-9
    assert abs(legacy["setup_tns_ns"] - (-129.9)) < 1e-9
    print("ok canonicalization")


def test_guard():
    base = {"setup_wns_ns": -1.0944, "hold_wns_ns": 0.0402}
    layeradj = {"setup_wns_ns": -1.1072, "hold_wns_ns": 0.0446}
    pad2 = {"setup_wns_ns": -0.8861, "hold_wns_ns": -0.1783}
    assert ms.timing_guard_ok(layeradj, base)
    assert not ms.timing_guard_ok(pad2, base)
    status = ms.guard_status(pad2, base)
    assert status["checks"]["hold"]["reason"] == "new_violation_from_met_baseline"
    print("ok guard")


def test_utility():
    base = {"hpwl_route_um": 100.0, "setup_tns_ns": -10.0, "total_power_w": 1.0}
    good = {"hpwl_route_um": 90.0, "setup_tns_ns": -8.0, "total_power_w": 0.9}
    bad = {"hpwl_route_um": 110.0, "setup_tns_ns": -12.0, "total_power_w": 1.1}
    assert ms.utility(good, base) > ms.utility(bad, base)
    print("ok utility")


def test_collect_record():
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        rd = runs / "r1"
        rd.mkdir(parents=True)
        metrics = {
            "raw": {
                "DRT::worst_slack_max": "-1.0944",
                "DRT::worst_slack_min": "0.0402",
                "DRT::tns_max": "-129.9",
                "drt::wire length::total": "1234",
                "drt::vias::total": "567",
            },
            "def_route": {"hpwl_um": 1000.0},
            "drc_violations": 0,
            "antenna_errors": 0,
            "total_power_w": 0.04,
            "duration_s": 300.0,
            "instance_count": 96000,
            "design_area_um2": 1.0,
        }
        meta = {"returncode": 0, "duration_s": 300.0, "overrides": {}}
        (rd / "metrics.json").write_text(json.dumps(metrics))
        (rd / "meta.json").write_text(json.dumps(meta))
        rec = collect_runs.record_from_run(str(runs), "r1", "base")
        assert abs(rec["setup_wns_ns"] - (-1.0944)) < 1e-9
        assert abs(rec["hold_wns_ns"] - 0.0402) < 1e-9
        assert abs(rec["setup_tns_ns"] - (-129.9)) < 1e-9
        print("ok collect_record")


def test_build_dataset():
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        for run_id, raw, hpwl, power in [
            ("base", {"DRT::worst_slack_max": "-1.0944", "DRT::worst_slack_min": "0.0402", "DRT::tns_max": "-129.9"}, 1000.0, 0.040),
            ("pad2", {"DRT::worst_slack_max": "-0.8861", "DRT::worst_slack_min": "-0.1783", "DRT::tns_max": "-65.0"}, 880.0, 0.038),
            ("layeradj", {"DRT::worst_slack_max": "-1.1072", "DRT::worst_slack_min": "0.0446", "DRT::tns_max": "-128.6"}, 995.0, 0.040),
        ]:
            rd = runs / run_id
            rd.mkdir(parents=True)
            metrics = {
                "raw": dict(raw, **{"drt::wire length::total": "1000", "drt::vias::total": "100"}),
                "def_route": {"hpwl_um": hpwl},
                "drc_violations": 0,
                "antenna_errors": 0,
                "total_power_w": power,
                "duration_s": 100.0,
                "instance_count": 1000,
            }
            meta = {"returncode": 0, "duration_s": 100.0, "overrides": {}}
            (rd / "metrics.json").write_text(json.dumps(metrics))
            (rd / "meta.json").write_text(json.dumps(meta))
        record = bsd.build_for_design("demo", "base", {"pad_2": "pad2", "layeradj": "layeradj"}, str(runs))
        assert record["oracle_skill"] == "layeradj", record["oracle_skill"]
        cands = {c["skill_id"]: c for c in record["candidates"]}
        assert cands["pad_2"]["timing_guard_ok"] is False
        assert cands["layeradj"]["timing_guard_ok"] is True
        print("ok build_dataset")


def test_metric_rules():
    raw = {
        "tritonRoute_violations": "2", "Short_violations": "1", "MetSpc_violations": "1",
        "OffGrid_violations": "0", "MinHole_violations": "0", "Other_violations": "0",
        "Magic_violations": "3", "klayout_violations": "0",
        "power_typical_internal_uW": "0.00082",
        "power_typical_switching_uW": "0.000319",
        "power_typical_leakage_uW": "1.88e-07",
        "synth_cell_count": "301", "TotalCells": "1108", "HPWL": "4514213",
    }
    viol = metric_rules.openlane_violations(raw)
    drc, detailed, magic, klayout = metric_rules.canonical_drc(viol)
    assert drc == 3.0, (drc, detailed, magic, klayout)
    assert detailed == 2.0
    assert abs(metric_rules.openlane_power_w(raw) - 0.001139188) < 1e-12
    logic, synth, total = metric_rules.openlane_cells(raw)
    assert (logic, synth, total) == (301.0, 301.0, 1108.0)
    db, um = metric_rules.hpwl_db_to_um(raw["HPWL"])
    assert db == 4514213.0 and abs(um - 4514.213) < 1e-9
    print("ok metric_rules")


def test_def_port_pin():
    with tempfile.TemporaryDirectory() as tmp:
        lef = Path(tmp) / "cells.lef"
        lef.write_text(
            "MACRO INV\n  SIZE 1 BY 1 ;\n  PIN A\n    PORT\n      RECT 0 0 1 1 ;\n    END\n  END A\nEND INV\n"
        )
        def_file = Path(tmp) / "t.def"
        def_file.write_text(
            "UNITS DISTANCE MICRONS 1000 ;\n"
            "COMPONENTS 2 ;\n"
            "- u1 INV + PLACED ( 1000 1000 ) N ;\n"
            "- u2 INV + PLACED ( 3000 1000 ) N ;\n"
            "END COMPONENTS\n"
            "PINS 1 ;\n"
            "- p + NET n + DIRECTION INPUT + PORT\n"
            "  + PLACED ( 10000 5000 ) N ;\n"
            "END PINS\n"
            "NETS 1 ;\n"
            "- n ( u1 A ) ( u2 A )\n"
            "  ( PIN p ) + USE SIGNAL ;\n"
            "END NETS\n"
        )
        import lef_def
        m = lef_def.def_metrics(str(def_file), str(lef), 1000.0, 1000.0)
        assert m["pin_hits"] == 2, m
        assert m["port_pin_hits"] == 1, m
        assert abs(m["hpwl_um"] - 12.0) < 1e-6, m
        assert abs(m["hpwl_no_ports_um"] - 2.0) < 1e-6, m
    print("ok def_port_pin")


if __name__ == "__main__":
    test_canonicalization()
    test_guard()
    test_utility()
    test_collect_record()
    test_build_dataset()
    test_metric_rules()
    test_def_port_pin()
    print("SMOKE_TEST_PASS")
