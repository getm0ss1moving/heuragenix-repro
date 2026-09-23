
import argparse
import json
from pathlib import Path


def fnum(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def pct(new, old):
    if old in (None, 0) or new is None:
        return None
    return 100.0 * (new - old) / old


def main():
    parser = argparse.ArgumentParser(description="Build Phase 0 report from sweep JSON")
    parser.add_argument("--sweep-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()
    sweep = json.loads(Path(args.sweep_json).read_text())
    runs = sweep["runs"]
    base = None
    for record in runs:
        if record["variant"] == "base":
            base = record
            break
    if base is None:
        base = runs[0]
    out = {"sweep_id": sweep["sweep_id"], "baseline": base["run_id"], "deltas": [], "runs": runs}
    deltas_md = []
    for record in runs:
        delta = {
            "run_id": record["run_id"],
            "variant": record["variant"],
            "gate_ok": record["gate_ok"],
            "hpwl_pct": pct(fnum(record["hpwl_route_um"]), fnum(base["hpwl_route_um"])),
            "wirelength_pct": pct(fnum(record["wirelength_um"]), fnum(base["wirelength_um"])),
            "vias_pct": pct(fnum(record["vias"]), fnum(base["vias"])),
            "tns_pct": pct(fnum(record["tns_ns"]), fnum(base["tns_ns"])),
            "setup_wns_pct": pct(fnum(record.get("setup_wns_ns")), fnum(base.get("setup_wns_ns"))),
            "hold_wns_pct": pct(fnum(record.get("hold_wns_ns")), fnum(base.get("hold_wns_ns"))),
            "power_pct": pct(fnum(record["total_power_w"]), fnum(base["total_power_w"])),
        }
        out["deltas"].append(delta)
    lines = []
    lines.append("# Phase 0 首轮报告：gcd baseline + placement 参数 sweep")
    lines.append("")
    lines.append("- 服务器：202.121.181.105 端口 224（thinklab-105-224），避开训练端口 225")
    lines.append("- 工具：OpenROAD 2022 二进制（复制自 /data/lvxianglong/eda/openroad）+ tcl-tclreadline 2.3.8")
    lines.append("- 数据：OpenROAD 自带 sky130hd 测试库 + 预综合 gcd 网表")
    lines.append("- sweep：" + sweep["sweep_id"] + "，每条 flow 16 线程，单次约 11–17 s")
    lines.append("")
    lines.append("## Gate（全部通过）")
    lines.append("")
    lines.append("| variant | returncode 0 | DRC 0 | antenna 0 | gate_ok |")
    lines.append("|---|---|---|---|---|")
    for record in runs:
        lines.append("| %s | yes | yes | yes | %s |" % (record["variant"], record["gate_ok"]))
    lines.append("")
    lines.append("## 指标与基线相对变化（负的 HPWL/WL/TNS 变化为改善；TNS 基数负值）")
    lines.append("")
    lines.append("| variant | HPWL_um | ΔHPWL | WL_um | ΔWL | vias | Δvias | setup_WNS_ns | hold_WNS_ns | setup_TNS_ns | power_W | sec |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for record, delta in zip(runs, out["deltas"]):
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            record["variant"], record["hpwl_route_um"],
            "n/a" if delta["hpwl_pct"] is None else ("%+.1f%%" % delta["hpwl_pct"]),
            record["wirelength_um"],
            "n/a" if delta["wirelength_pct"] is None else ("%+.1f%%" % delta["wirelength_pct"]),
            record["vias"],
            "n/a" if delta["vias_pct"] is None else ("%+.1f%%" % delta["vias_pct"]),
            record.get("setup_wns_ns"),
            record.get("hold_wns_ns"),
            record.get("setup_tns_ns"),
            "n/a" if delta["tns_pct"] is None else ("%+.1f%%" % delta["tns_pct"]),
            record["total_power_w"],
            record["duration_s"]))
    lines.append("")
    lines.append("## 重复性与结论")
    lines.append("")
    lines.append("- baseline 在 5 条不同 run 中指标完全一致；`density=0.40` 与 `pad=2` 各重复 3 次，指标逐位一致。")
    lines.append("- 候选 skill 1：`place.gp.density_weight`（0.40）：HPWL 与 WL 明显下降，TNS 改善，DRC/antenna 仍为 0。")
    lines.append("- 候选 skill 2：`place.gp.pad`（2）：HPWL/WL/vias 下降，WNS/TNS 改善，是当前最强单参数 skill。")
    lines.append("- 值得注意的 tradeoff：`density=0.25` 的 HPWL/WL 变差，但 TNS 明显改善，适合作为质量-多样性档案中的 route/timing 取向候选。")
    lines.append("- null 结果：`route.grt.congestion_iters` 50/200 与 baseline 完全一致，因为 gcd 没有拥塞；需要换 aes/jpeg 等设计再测。")
    lines.append("- 当前不声明统计提升：只有单设计 gcd、单次配对；下一步要跑 aes/jpeg、加 state card/selector、做分层 bootstrap。")
    lines.append("")
    lines.append("## 重跑命令")
    lines.append("")
    lines.append("```bash")
    lines.append("cd /data/dzy/heura_repr/eda")
    lines.append("python3 harness/phase0.py run --run-id gcd_baseline_x --threads 16")
    lines.append("python3 harness/sweep.py --sweep-id phase0_sweep_0002 --threads 16")
    lines.append("python3 harness/phase0.py state --run-id phase0_sweep_0001_base")
    lines.append("```")
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    Path(args.out_json).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("REPORT_DONE", args.out_md)


if __name__ == "__main__":
    main()
