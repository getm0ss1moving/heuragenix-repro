"""Canonical timing metrics for the HA-PR EDA harness.

Canonical convention (v1, 2026-09-22)
------------------------------------
OpenROAD/OpenSTA reports two signed slacks, and their names are easy to misread:

    DRT::worst_slack_max  = worst slack in the max-delay (setup) analysis
    DRT::worst_slack_min  = worst slack in the min-delay (hold) analysis
    DRT::tns_max          = total negative slack of the setup analysis
    DRT::tns_min          = total negative slack of the hold analysis (if present)

Sign convention: higher is better.
    setup_wns_ns >= 0  means setup is met.
    hold_wns_ns  >= 0  means hold is met.
    setup_tns_ns is usually <= 0; closer to 0 is better.

The old harness mistakenly used DRT::worst_slack_min as "WNS".  That value is
the hold/min-corner slack.  All new code must use this module and the explicit
field names below.  Legacy fields are accepted only by canonicalize_record():

    legacy wns_min_ns  -> hold_wns_ns
    legacy wns_max_ns  -> setup_wns_ns
    legacy wns_ns/wns_ps from old phase0.py -> hold_wns_ns (ambiguous)
    legacy wns_ns from openlane_ingest (source=openlane1) -> setup_wns_ns
    legacy tns_ns/tns_ps -> setup_tns_ns (old phase0.py used DRT::tns_max)
"""

from __future__ import annotations

import json
from pathlib import Path

TIMING_VERSION = "setup_hold_v1_2026-09-22"

SETUP_WNS_KEYS = ["DRT::worst_slack_max", "RSZ::worst_slack_max"]
HOLD_WNS_KEYS = ["DRT::worst_slack_min", "RSZ::worst_slack_min"]
SETUP_TNS_KEYS = ["DRT::tns_max", "RSZ::tns_max"]
HOLD_TNS_KEYS = ["DRT::tns_min", "RSZ::tns_min"]

CANONICAL_FIELDS = [
    "setup_wns_ns",
    "hold_wns_ns",
    "setup_tns_ns",
    "hold_tns_ns",
]


def fnum(value, default=None):
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _pick(mapping, keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return fnum(mapping[key])
    return None


def extract_timing_from_raw(raw):
    """Extract canonical timing fields from an OpenROAD metrics_raw dict."""
    return {
        "setup_wns_ns": _pick(raw, SETUP_WNS_KEYS),
        "hold_wns_ns": _pick(raw, HOLD_WNS_KEYS),
        "setup_tns_ns": _pick(raw, SETUP_TNS_KEYS),
        "hold_tns_ns": _pick(raw, HOLD_TNS_KEYS),
    }


def canonicalize_record(record):
    """Return a copy of record with explicit canonical timing fields.

    Precedence:
    1. explicit canonical fields already present;
    2. nested timing dict;
    3. raw OpenROAD metrics dict;
    4. legacy fields (with documented ambiguity handling).
    """
    if not isinstance(record, dict):
        return {}
    out = dict(record)
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    timing = record.get("timing") if isinstance(record.get("timing"), dict) else {}

    for field in CANONICAL_FIELDS:
        value = fnum(record.get(field))
        if value is None:
            value = fnum(timing.get(field))
        if value is None and raw:
            value = _pick(raw, {
                "setup_wns_ns": SETUP_WNS_KEYS,
                "hold_wns_ns": HOLD_WNS_KEYS,
                "setup_tns_ns": SETUP_TNS_KEYS,
                "hold_tns_ns": HOLD_TNS_KEYS,
            }[field])
        if value is None:
            # legacy derived records from the old harness
            if field == "hold_wns_ns":
                value = fnum(record.get("wns_min_ns"))
                if value is None:
                    value = fnum(record.get("wns_ps"))
                if value is None and fnum(record.get("wns_ns")) is not None and record.get("source") != "openlane1":
                    value = fnum(record.get("wns_ns"))
            elif field == "setup_wns_ns":
                value = fnum(record.get("wns_max_ns"))
                if value is None and record.get("source") == "openlane1":
                    value = fnum(record.get("wns_ns"))
            elif field == "setup_tns_ns":
                value = fnum(record.get("tns_ns"))
                if value is None:
                    value = fnum(record.get("tns_ps"))
        out[field] = value

    out["timing_convention"] = record.get("timing_convention", TIMING_VERSION)
    return out


def guard_status(candidate, base, guard_ns=0.02):
    """Canonical setup+hold timing guard.

    Rule per analysis:
        cand >= base - guard_ns
        and if base >= 0 then cand >= 0 (do not turn a met check into a violation)
    Returns a dict with per-check status.
    """
    cand = canonicalize_record(candidate)
    base = canonicalize_record(base)
    status = {"guard_ns": guard_ns, "checks": {}, "ok": True}
    for name in ["setup_wns_ns", "hold_wns_ns"]:
        c = fnum(cand.get(name))
        b = fnum(base.get(name))
        label = name.replace("_wns_ns", "")
        if c is None or b is None:
            status["checks"][label] = {
                "checked": False,
                "ok": None,
                "reason": "missing_" + name,
                "base": b,
                "candidate": c,
            }
            continue
        ok = (c >= b - guard_ns) and not (b >= 0.0 and c < 0.0)
        reason = "ok"
        if not ok:
            if b >= 0.0 and c < 0.0:
                reason = "new_violation_from_met_baseline"
            else:
                reason = "degrades_more_than_guard"
        status["checks"][label] = {
            "checked": True,
            "ok": ok,
            "reason": reason,
            "base": b,
            "candidate": c,
        }
        if not ok:
            status["ok"] = False
    return status


def timing_guard_ok(candidate, base, guard_ns=0.02, require_setup=True):
    status = guard_status(candidate, base, guard_ns=guard_ns)
    setup = status["checks"].get("setup", {})
    if require_setup and not setup.get("checked", False):
        return False
    return bool(status["ok"])


def utility(candidate, base):
    """Soft utility used AFTER the timing gate.

    Canonical v2: WNS is a hard gate, not a soft objective.
        U = 0.5*d_HPWL + 0.4*d_|TNS| + 0.1*d_power
    TNS uses setup TNS magnitude; HPWL/power are relative improvements.
    """
    cand = canonicalize_record(candidate)
    base = canonicalize_record(base)

    hp = fnum(cand.get("hpwl_route_um"))
    bhp = fnum(base.get("hpwl_route_um"))
    tns = fnum(cand.get("setup_tns_ns"))
    btns = fnum(base.get("setup_tns_ns"))
    power = fnum(cand.get("total_power_w"))
    bpow = fnum(base.get("total_power_w"))

    d_hpwl = ((bhp - hp) / bhp) if (hp is not None and bhp not in (None, 0)) else 0.0
    d_tns = ((abs(btns) - abs(tns)) / abs(btns)) if (tns is not None and btns not in (None, 0)) else 0.0
    d_power = ((bpow - power) / bpow) if (power is not None and bpow not in (None, 0)) else 0.0
    return 0.5 * d_hpwl + 0.4 * d_tns + 0.1 * d_power


def utility_spec():
    return (
        "timing_gate_first: setup_wns_ns >= base_setup_wns_ns - 0.02 ns and "
        "hold_wns_ns >= base_hold_wns_ns - 0.02 ns; if base is nonnegative, "
        "candidate must stay nonnegative; then U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power"
    )


def audit_records(records, label=""):
    """Return a short audit summary for a list of records."""
    rows = []
    for rec in records:
        c = canonicalize_record(rec)
        rows.append({field: c.get(field) for field in CANONICAL_FIELDS})
    missing = {field: sum(1 for row in rows if row[field] is None) for field in CANONICAL_FIELDS}
    return {"label": label, "n": len(rows), "missing": missing, "fields": CANONICAL_FIELDS}


def _main():
    import argparse

    parser = argparse.ArgumentParser(description="Audit canonical timing fields")
    parser.add_argument("json_files", nargs="+", help="JSON files containing records or sweep objects")
    args = parser.parse_args()
    for path_str in args.json_files:
        path = Path(path_str)
        obj = json.loads(path.read_text())
        if isinstance(obj, dict) and isinstance(obj.get("runs"), list):
            records = obj["runs"]
        elif isinstance(obj, list):
            records = obj
        else:
            records = [obj]
        print(json.dumps(audit_records(records, label=str(path)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
