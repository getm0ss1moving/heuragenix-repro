"""Canonical metric rules for OpenLane 1 metrics.csv and OpenROAD logs.

These rules were audited on 2026-09-22:
- OpenLane 1 power_* columns named *_uW actually contain W (validated against
  rcx_sta.power.rpt and eda-101/parse_reports.py).
- OpenLane 1 DRC columns include the detailed-router total plus its subcategory
  counts plus Magic/KLayout signoff counts.  Summing everything double counts
  the detailed route.  We expose each source separately and define the canonical
  drc_violations = max(KLayout, Magic) when signoff DRC is available, otherwise
  the detailed-router total.
- TotalCells includes filler/decap/welltap physical cells; logic cell count is
  synth_cell_count.  The canonical instance_count is the logic count.
- HPWL column is OpenROAD global-placement HPWL in DEF DB units (typically
  1000 DB/um); convert to um by /1000 and label the source.
- Detailed-route wire length is in um and vias is a count.
"""

from __future__ import annotations

import re


def fnum(value, default=None):
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


DRC_KEYS = [
    "tritonRoute_violations", "Short_violations", "MetSpc_violations",
    "OffGrid_violations", "MinHole_violations", "Other_violations",
    "Magic_violations", "klayout_violations",
]

POWER_KEYS = [
    "power_typical_internal_uW",
    "power_typical_switching_uW",
    "power_typical_leakage_uW",
]

POWER_LINE_RE = re.compile(
    r"^\s*Total\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)"
)


def openlane_violations(raw):
    return {key: fnum(raw.get(key)) for key in DRC_KEYS + ["pin_antenna_violations", "net_antenna_violations"]}


def canonical_drc(viol):
    """Return (drc_violations, detailed_route, magic, klayout)."""
    detailed = fnum(viol.get("tritonRoute_violations"))
    sub_keys = ["Short_violations", "MetSpc_violations", "OffGrid_violations",
                "MinHole_violations", "Other_violations"]
    sub_sum = sum(v for v in (fnum(viol.get(k)) for k in sub_keys) if v is not None and v >= 0)
    drc_detailed = detailed if (detailed is not None and detailed >= 0) else sub_sum
    magic = fnum(viol.get("Magic_violations"))
    magic = magic if (magic is not None and magic >= 0) else None
    klayout = fnum(viol.get("klayout_violations"))
    klayout = klayout if (klayout is not None and klayout >= 0) else None
    signoff = [v for v in (magic, klayout) if v is not None]
    drc = max(signoff) if signoff else drc_detailed
    return drc, drc_detailed, magic, klayout


def openlane_antenna(viol):
    pin = fnum(viol.get("pin_antenna_violations"))
    net = fnum(viol.get("net_antenna_violations"))
    total = sum(v for v in (pin, net) if v is not None and v >= 0)
    return total, pin, net


def openlane_power_w(raw):
    vals = [fnum(raw.get(k)) for k in POWER_KEYS]
    return sum(v for v in vals if v is not None and v >= 0)


def openlane_cells(raw):
    synth = fnum(raw.get("synth_cell_count"))
    total = fnum(raw.get("TotalCells"))
    logic = synth if (synth is not None and synth >= 0) else total
    return logic, synth, total


def hpwl_db_to_um(value):
    v = fnum(value)
    if v is None or v < 0:
        return None, None
    return v, v / 1000.0


def parse_power_log_line(text):
    """Return the last OpenSTA power Total line as a dict (values in W)."""
    matches = [m.groups() for m in (POWER_LINE_RE.match(line) for line in text.splitlines()) if m]
    if not matches:
        return {}
    vals = matches[-1]
    try:
        return {
            "internal_power_w": float(vals[0]),
            "switching_power_w": float(vals[1]),
            "leakage_power_w": float(vals[2]),
            "total_power_w": float(vals[3]),
            "power_source": "OpenSTA rcx_sta Total line (W)",
        }
    except Exception:
        return {}
