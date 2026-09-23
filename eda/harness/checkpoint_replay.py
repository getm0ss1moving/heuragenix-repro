"""Checkpoint replay for HA-PR EDA.

Resume the OpenROAD flow from a checkpoint DEF (post_global_place or post_cts),
apply downstream actions (global route congestion / layer adjustments / etc.),
run the remaining flow, and record canonical final metrics.

This is the first label-generating mechanism for checkpoint-level decision data.
Usage example (server 224):
  python3 harness/checkpoint_replay.py \
    --design gcd --stage post_global_place \
    --checkpoint-def runs/phase0_sweep_0002_base/results/gcd_sky130hd_global_place.def \
    --run-id replay_gcd_pgp_base \
    --action '{}' \
    --out-jsonl results/canonical_server/checkpoint_replay_v1.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lef_def
import metrics_schema
import metric_rules

BASE = Path(os.environ.get("HEURA_EDA_BASE", "/data/dzy/heura_repr/eda"))
FLOW = BASE / "flow"
TOOLS = BASE / "tools"
OPENROAD = TOOLS / "openroad" / "bin" / "openroad"
REPLAY_ROOT = BASE / "runs_replay"
LIB_PATHS = [TOOLS / "openroad_syslibs", TOOLS / "tclreadline" / "lib"]


def design_cfg(design):
    import phase0
    cfg = phase0.DESIGNS[design]
    return {
        "top": cfg["top"],
        "sdc": cfg["sdc"],
        "die": cfg["die"],
        "core": cfg["core"],
        "slew_margin": cfg.get("slew_margin", 0),
        "cap_margin": cfg.get("cap_margin", 0),
        "v": cfg["v"],
    }


def layer_list_tcl(layers):
    if not layers:
        return "{}"
    parts = []
    for item in layers:
        layer, value = item[0], item[1]
        parts.append("{ %s %s }" % (layer, value))
    return "{ " + " ".join(parts) + " }"


def make_tcl(run_dir, design, cfg, checkpoint_def, stage, action):
    flow_param = (FLOW / "flow_param.tcl").read_text(errors="replace")
    lines = flow_param.splitlines()
    text = "\n".join(lines)
    if stage == "post_global_place":
        marker = "# Repair max slew/cap/fanout violations and normalize slews"
        idx = text.find(marker)
    elif stage == "post_cts":
        marker = "# Setup/hold timing repair"
        idx = text.find(marker)
    else:
        raise SystemExit("unsupported stage: " + stage)
    if idx < 0:
        raise SystemExit("stage marker not found: " + marker)
    remainder = text[idx:]

    if stage == "post_cts":
        wire_rc = """source $layer_rc_file
set_wire_rc -signal -layer $wire_rc_layer
set_wire_rc -clock -layer $wire_rc_layer_clk
set_dont_use $dont_use

"""
        remainder = wire_rc + remainder

    # re-apply routing setup before global routing (prefix reads DEF instead of placement)
    route_setup = """# replay: routing setup before global route
foreach layer_adjustment $global_routing_layer_adjustments {
  lassign $layer_adjustment layer adjustment
  set_global_routing_layer_adjustment $layer $adjustment
}
set_routing_layers -signal $global_routing_layers -clock $global_routing_clock_layers
set_macro_extension 2

"""
    gr_marker = "# Global routing"
    if gr_marker in remainder:
        remainder = remainder.replace(gr_marker, route_setup + gr_marker, 1)

    congestion = int(action.get("global_route_congestion_iterations", 100))
    layer_adjustments = action.get("global_routing_layer_adjustments", [])
    slew_margin = action.get("slew_margin", cfg["slew_margin"])
    cap_margin = action.get("cap_margin", cfg["cap_margin"])

    prefix = """source helpers.tcl
source flow_helpers.tcl
source sky130hd/sky130hd.vars
set synth_verilog "%(v)s"
set design "%(design)s"
set top_module "%(top)s"
set sdc_file "%(sdc)s"
set die_area {%(die)s}
set core_area {%(core)s}
set slew_margin %(slew)s
set cap_margin %(cap)s
set global_route_congestion_iterations %(congestion)d
set global_routing_layer_adjustments %(layers)s
utl::open_metrics %(metrics)s
read_libraries
read_def %(checkpoint)s
read_sdc $sdc_file
""" % {
        "v": cfg["v"], "design": design, "top": cfg["top"], "sdc": cfg["sdc"],
        "die": cfg["die"], "core": cfg["core"], "slew": slew_margin, "cap": cap_margin,
        "congestion": congestion, "layers": layer_list_tcl(layer_adjustments),
        "metrics": str(run_dir / "metrics_raw.json"), "checkpoint": checkpoint_def,
    }
    tail = """
puts "REPLAY_DONE"
exit
"""
    return prefix + remainder + tail


def run_openroad(run_dir, tcl_path, timeout, log_path):
    env = os.environ.copy()
    libs = [str(p) for p in LIB_PATHS if p.exists()]
    env["LD_LIBRARY_PATH"] = ":".join(libs + [env.get("LD_LIBRARY_PATH", "")])
    start = time.time()
    proc = subprocess.run(
        [str(OPENROAD), "-exit", "-no_init", "-no_splash", str(tcl_path)],
        cwd=str(run_dir), env=env, capture_output=True, text=True, timeout=timeout,
    )
    duration = time.time() - start
    log_path.write_text(proc.stdout + "\n--- STDERR ---\n" + proc.stderr)
    return proc.returncode, duration


def collect_metrics(run_dir, design, lef, cfg):
    raw_path = run_dir / "metrics_raw.json"
    raw = {}
    if raw_path.exists():
        try:
            raw = json.loads(raw_path.read_text())
        except Exception:
            pass
    timing = metrics_schema.extract_timing_from_raw(raw)
    route_def = run_dir / "results" / ("%s_sky130hd_route.def" % design)
    geo = {}
    if route_def.exists():
        try:
            geo = lef_def.def_metrics(str(route_def), str(lef), 1000.0, 1000.0)
        except Exception as exc:
            geo = {"error": str(exc)}
    metrics = {
        "design": design,
        "setup_wns_ns": timing.get("setup_wns_ns"),
        "hold_wns_ns": timing.get("hold_wns_ns"),
        "setup_tns_ns": timing.get("setup_tns_ns"),
        "hold_tns_ns": timing.get("hold_tns_ns"),
        "drc_violations": metric_rules.fnum(raw.get("DRT::drv")),
        "vias": metric_rules.fnum(raw.get("drt::vias::total")),
        "wirelength_um": metric_rules.fnum(raw.get("drt::wire length::total")),
        "instance_count": metric_rules.fnum(raw.get("IFP::instance_count")),
        "hpwl_um": geo.get("hpwl_um"),
        "hpwl_no_ports_um": geo.get("hpwl_no_ports_um"),
        "hpwl_origin_um": geo.get("hpwl_origin_um"),
        "route_def": str(route_def),
        "metric_convention_version": "metrics_v2_2026-09-22",
        "timing_convention": metrics_schema.TIMING_VERSION,
    }
    log_path = run_dir / "flow.log"
    if log_path.exists():
        power = metric_rules.parse_power_log_line(log_path.read_text(errors="replace"))
        metrics.update(power)
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Checkpoint replay from a DEF snapshot")
    parser.add_argument("--design", required=True, choices=["gcd", "aes", "jpeg", "ibex"])
    parser.add_argument("--stage", required=True, choices=["post_global_place", "post_cts"])
    parser.add_argument("--checkpoint-def", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--action", default="{}", help="JSON dict of downstream action params")
    parser.add_argument("--out-jsonl", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    action = json.loads(args.action)
    checkpoint_def = str(Path(args.checkpoint_def).resolve())
    cfg = design_cfg(args.design)
    lef = FLOW / "sky130hd" / "sky130_fd_sc_hd_merged.lef"
    run_dir = REPLAY_ROOT / args.run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    (run_dir / "results").mkdir()
    for name in ["helpers.tcl", "flow_helpers.tcl", "flow_param.tcl", "sky130hd", cfg["v"], cfg["sdc"]]:
        src = FLOW / name
        if src.exists():
            (run_dir / name).symlink_to(src)
    tcl_path = run_dir / "replay.tcl"
    tcl_path.write_text(make_tcl(run_dir, args.design, cfg, checkpoint_def, args.stage, action))
    rc, duration = run_openroad(run_dir, tcl_path, args.timeout, run_dir / "flow.log")
    metrics = collect_metrics(run_dir, args.design, lef, cfg)
    record = {
        "run_id": args.run_id,
        "design": args.design,
        "stage": args.stage,
        "checkpoint_def": checkpoint_def,
        "action": action,
        "returncode": rc,
        "duration_s": round(duration, 3),
        "gate_ok": (rc == 0 and metrics.get("drc_violations") in (0, 0.0, None)),
        "metrics": metrics,
        "artifact_dir": str(run_dir),
    }
    out = Path(args.out_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
