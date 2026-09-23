
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import lef_def
import verifier
import metrics_schema
import metric_rules

BASE = Path(os.environ.get("HEURA_EDA_BASE", "/data/dzy/heura_repr/eda"))
FLOW = BASE / "flow"
TOOLS = BASE / "tools"
RUNS = BASE / "runs"
OPENROAD = TOOLS / "openroad" / "bin" / "openroad"
LIB_PATHS = [TOOLS / "openroad_syslibs", TOOLS / "tclreadline" / "lib"]
LIBDIR = ":".join(str(p) for p in LIB_PATHS if p.exists())
TCL_PATHS = [TOOLS / "openroad_syslibs" / "share_tcltk" / "tcl8.6"]
TCLDIR = ":".join(str(p) for p in TCL_PATHS if p.exists())
DIE_W = 299.96
DIE_H = 300.128

DESIGNS = {
    "gcd": {
        "v": "gcd_sky130hd.v", "sdc": "gcd_sky130hd.sdc", "top": "gcd",
        "die": "0 0 299.96 300.128", "core": "9.996 10.08 289.964 290.048",
        "die_w": 299.96, "die_h": 300.128,
    },
    "aes": {
        "v": "aes_sky130hd.v", "sdc": "aes_sky130hd.sdc", "top": "aes_cipher_top",
        "die": "0 0 2000 2000", "core": "30 30 1770 1770",
        "die_w": 2000.0, "die_h": 2000.0, "slew_margin": 20,
    },
    "jpeg": {
        "v": "jpeg_sky130hd.v", "sdc": "jpeg_sky130hd.sdc", "top": "jpeg_encoder",
        "die": "0 0 3000.04 2999.8", "core": "10.07 9.8 2989.97 2990",
        "die_w": 3000.04, "die_h": 2999.8, "slew_margin": 20, "cap_margin": 20,
    },
    "ibex": {
        "v": "ibex_sky130hd.v", "sdc": "ibex_sky130hd.sdc", "top": "ibex_core",
        "die": "0 0 3000.08 2999.8", "core": "10.07 11.2 2990.01 2990",
        "die_w": 3000.08, "die_h": 2999.8, "slew_margin": 30, "cap_margin": 25,
    },
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1048576)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def fmt_val(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def ensure_flow_param():
    dst = FLOW / "flow_param.tcl"
    if dst.exists():
        return dst
    text = (FLOW / "flow.tcl").read_text()
    text = text.replace("-congestion_iterations 100", "-congestion_iterations $global_route_congestion_iterations")
    old = "set_thread_count [exec getconf _NPROCESSORS_ONLN]"
    new = "set num_threads 16\nif { [info exists env(EDA_THREADS)] } { set num_threads $env(EDA_THREADS) }\nset_thread_count $num_threads"
    text = text.replace(old, new)
    dst.write_text(text)
    return dst


def create_run(run_id, design):
    cfg = DESIGNS[design]
    rd = RUNS / run_id
    if rd.exists():
        shutil.rmtree(rd)
    rd.mkdir(parents=True)
    (rd / "results").mkdir()
    names = ["helpers.tcl", "flow_helpers.tcl", "flow_metrics.tcl", "sky130hd",
             "flow_param.tcl", cfg["v"], cfg["sdc"]]
    for name in names:
        src = FLOW / name
        if not src.exists():
            raise SystemExit("missing shared file: " + str(src))
        (rd / name).symlink_to(src)
    return rd


def write_run_tcl(rd, overrides, design):
    cfg = DESIGNS[design]
    lines = []
    lines.append("source helpers.tcl")
    lines.append("source flow_helpers.tcl")
    lines.append("source sky130hd/sky130hd.vars")
    lines.append('set synth_verilog "%s"' % cfg["v"])
    lines.append('set design "%s"' % design)
    lines.append('set top_module "%s"' % cfg["top"])
    lines.append('set sdc_file "%s"' % cfg["sdc"])
    lines.append("set die_area {%s}" % cfg["die"])
    lines.append("set core_area {%s}" % cfg["core"])
    if "slew_margin" in cfg:
        lines.append("set slew_margin %s" % cfg["slew_margin"])
    if "cap_margin" in cfg:
        lines.append("set cap_margin %s" % cfg["cap_margin"])
    for key, val in overrides.items():
        lines.append("set %s %s" % (key, fmt_val(val)))
    lines.append("if { [info exists global_route_congestion_iterations] } { } else { set global_route_congestion_iterations 100 }")
    lines.append("utl::open_metrics " + str(rd / "metrics_raw.json"))
    lines.append("source -echo flow_param.tcl")
    lines.append('puts "EDA_RUN_DONE"')
    lines.append("exit")
    (rd / "run.tcl").write_text("\n".join(lines) + "\n")


def parse_log_power(log_text):
    """Parse OpenSTA rcx_sta power summary (values in W)."""
    return metric_rules.parse_power_log_line(log_text)


def extract_metrics(rd, design):
    cfg = DESIGNS[design]
    raw = {}
    p = rd / "metrics_raw.json"
    if p.exists():
        try:
            raw = json.loads(p.read_text())
        except Exception as exc:
            raw = {"_parse_error": str(exc)}
    log_text = ""
    log_path = rd / "flow.log"
    if log_path.exists():
        log_text = log_path.read_text(errors="replace")
    metrics = {"raw": raw}
    aliases = {
        "instance_count": "IFP::instance_count",
        "clock_skew_ns": "DRT::clock_skew",
        "drc_violations": "DRT::drv",
        "antenna_errors": "GRT::ANT::errors",
        "utilization_pct": "DPL::utilization",
        "design_area_um2": "DPL::design_area",
        "clock_period_ns": "DRT::clock_period",
    }
    for key, raw_key in aliases.items():
        if raw_key in raw:
            metrics[key] = raw[raw_key]
    metrics.update(metrics_schema.extract_timing_from_raw(raw))
    metrics["timing_convention"] = metrics_schema.TIMING_VERSION
    metrics["metric_convention_version"] = "metrics_v2_2026-09-22"
    metrics["instance_count_source"] = "IFP::instance_count"
    metrics["wirelength_source"] = "drt::wire length::total"
    metrics["vias_source"] = "drt::vias::total"
    metrics["drc_source_note"] = "drc_violations = DRT::drv (detailed-route total); signoff DRC via OpenLane ingest"
    if "drt::wire length::total" in raw:
        metrics["detailed_wirelength_um"] = raw["drt::wire length::total"]
    if "drt::vias::total" in raw:
        metrics["vias"] = raw["drt::vias::total"]
    metrics.update(parse_log_power(log_text))
    match = re.search(r"Design area\s+([0-9.]+)\s+u\^2\s+([0-9.]+)%", log_text)
    if match:
        metrics["design_area_um2_log"] = float(match.group(1))
        metrics["utilization_pct_log"] = float(match.group(2))
    lef_path = FLOW / "sky130hd" / "sky130_fd_sc_hd_merged.lef"
    for label, suffix in [("global_place", "global_place"),
                          ("cts", "cts"),
                          ("route", "route")]:
        name = "%s_sky130hd_%s.def" % (design, suffix)
        fp = rd / "results" / name
        if fp.exists():
            metrics["def_" + label] = lef_def.def_metrics(fp, lef_path, cfg["die_w"], cfg["die_h"])
    wl = rd / "wirelength_detailed.txt"
    if wl.exists():
        txt = wl.read_text(errors="replace")
        metrics["wirelength_report"] = txt[:4000]
        nums = re.findall(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", txt)
        if nums:
            try:
                metrics["wirelength_detailed_um"] = float(nums[-1])
            except Exception:
                pass
    return metrics


def run_variant(run_id, overrides, threads, design="gcd"):
    ensure_flow_param()
    rd = create_run(run_id, design)
    write_run_tcl(rd, overrides, design)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(LIBDIR)
    if TCLDIR:
        env["TCL_LIBRARY"] = TCLDIR
    env["EDA_THREADS"] = str(threads)
    t0 = time.time()
    with open(rd / "flow.log", "w") as fh:
        proc = subprocess.run(
            [str(OPENROAD), "-exit", "-no_init", "-no_splash", "run.tcl"],
            cwd=str(rd), env=env, stdout=fh, stderr=subprocess.STDOUT,
        )
    duration = time.time() - t0
    metrics = extract_metrics(rd, design)
    metrics["duration_s"] = round(duration, 2)
    metrics["returncode"] = proc.returncode
    metrics["design"] = design
    metrics["run_id"] = run_id
    route_def = rd / "results" / (design + "_sky130hd_route.def")
    if route_def.exists():
        try:
            ref_def = BASE / "reference" / (design + "_route.def")
            verify_result = verifier.verify_def(
                route_def, FLOW / "sky130hd" / "sky130_fd_sc_hd_merged.lef", design,
                ref_def=str(ref_def) if ref_def.exists() else None,
                netlist=str(rd / DESIGNS[design]["v"]),
            )
            (rd / "verify.json").write_text(json.dumps(verify_result, indent=2, ensure_ascii=False))
            metrics["l1_verdict"] = verify_result["verdict"]
            metrics["l1_verify"] = verify_result["checks"]
        except Exception as exc:
            metrics["l1_verify_error"] = str(exc)
    (rd / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    meta = {
        "run_id": run_id,
        "design": design,
        "overrides": overrides,
        "threads": threads,
        "returncode": proc.returncode,
        "duration_s": round(duration, 2),
        "openroad_sha256": sha256(OPENROAD),
        "flow_param_sha256": sha256(FLOW / "flow_param.tcl"),
        "artifacts": {},
    }
    for name in ["flow.log", "metrics_raw.json", "metrics.json", "wirelength_detailed.txt"]:
        fp = rd / name
        if fp.exists():
            meta["artifacts"][name] = {"size": fp.stat().st_size, "sha256": sha256(fp)}
    results = rd / "results"
    if results.exists():
        for fp in sorted(results.iterdir()):
            if fp.is_file():
                meta["artifacts"]["results/" + fp.name] = {"size": fp.stat().st_size, "sha256": sha256(fp)}
    (rd / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return rd, metrics, meta


def state_card(run_id):
    rd = RUNS / run_id
    metrics = json.loads((rd / "metrics.json").read_text())
    canonical = metrics_schema.canonicalize_record(metrics)
    design = metrics.get("design", "gcd")
    route_def = metrics.get("def_route", {})
    gate = {
        "returncode_zero": metrics.get("returncode") == 0,
        "drc_zero": metrics.get("drc_violations") in (0, "0"),
        "antenna_zero": metrics.get("antenna_errors") in (0, "0"),
    }
    card = {
        "run_id": run_id,
        "design": design,
        "stage": "post_route",
        "legality": gate,
        "metrics": {
            "instance_count": metrics.get("instance_count"),
            "instance_count_source": metrics.get("instance_count_source"),
            "hpwl_um": route_def.get("hpwl_um"),
            "hpwl_no_ports_um": route_def.get("hpwl_no_ports_um"),
            "hpwl_origin_um": route_def.get("hpwl_origin_um"),
            "hpwl_convention": route_def.get("hpwl_convention"),
            "utilization_pct": metrics.get("utilization_pct"),
            "setup_wns_ns": canonical.get("setup_wns_ns"),
            "hold_wns_ns": canonical.get("hold_wns_ns"),
            "setup_tns_ns": canonical.get("setup_tns_ns"),
            "hold_tns_ns": canonical.get("hold_tns_ns"),
            "clock_skew_ns": metrics.get("clock_skew_ns"),
            "drc_violations": metrics.get("drc_violations"),
            "drc_detailed_route": metrics.get("drc_detailed_route", metrics.get("drc_violations")),
            "antenna_errors": metrics.get("antenna_errors"),
            "total_power_w": metrics.get("total_power_w"),
            "power_source": metrics.get("power_source"),
            "wirelength_um": metrics.get("detailed_wirelength_um"),
            "wirelength_source": metrics.get("wirelength_source"),
            "vias": metrics.get("vias"),
            "vias_source": metrics.get("vias_source"),
            "duration_s": metrics.get("duration_s"),
            "metric_convention_version": metrics.get("metric_convention_version"),
        },
        "severity": {},
        "budget": {"time_left_s": None},
    }
    (rd / "state_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False))
    return card


def main():
    parser = argparse.ArgumentParser(description="Phase 0 harness for HA-PR EDA")
    sub = parser.add_subparsers(dest="cmd")
    run_p = sub.add_parser("run", help="run one OpenROAD flow variant")
    run_p.add_argument("--run-id", required=True)
    run_p.add_argument("--design", default="gcd", choices=["gcd", "aes", "jpeg", "ibex"])
    run_p.add_argument("--density", type=float)
    run_p.add_argument("--pad", type=int)
    run_p.add_argument("--grt-iters", type=int)
    run_p.add_argument("--layer-adj", default=None, help="e.g. met1:0.4,met2:0.4,met3:0.3")
    run_p.add_argument("--threads", type=int, default=16)
    state_p = sub.add_parser("state", help="build state card from a run")
    state_p.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.cmd == "run":
        overrides = {}
        if args.density is not None:
            overrides["global_place_density"] = args.density
        if args.pad is not None:
            overrides["global_place_pad"] = args.pad
        if args.grt_iters is not None:
            overrides["global_route_congestion_iterations"] = args.grt_iters
        if args.layer_adj:
            items = []
            for token in args.layer_adj.split(","):
                if ":" in token:
                    layer, value = token.split(":", 1)
                    items.append("{ %s %s }" % (layer.strip(), value.strip()))
            if items:
                overrides["global_routing_layer_adjustments"] = "{" + " ".join(items) + "}"
        rd, metrics, meta = run_variant(args.run_id, overrides, args.threads, args.design)
        print("RUN", args.run_id, "RC", meta["returncode"], "DUR", meta["duration_s"])
        print("METRICS", json.dumps({
            "setup_wns_ns": metrics.get("setup_wns_ns"),
            "hold_wns_ns": metrics.get("hold_wns_ns"),
            "setup_tns_ns": metrics.get("setup_tns_ns"),
            "hold_tns_ns": metrics.get("hold_tns_ns"),
            "drc": metrics.get("drc_violations"),
            "antenna": metrics.get("antenna_errors"),
            "hpwl_route": (metrics.get("def_route") or {}).get("hpwl_um"),
            "power_w": metrics.get("total_power_w"),
        }, ensure_ascii=False))
    elif args.cmd == "state":
        card = state_card(args.run_id)
        print(json.dumps(card, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
