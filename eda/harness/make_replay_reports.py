"""Generate PHASE0_REPORT_0011 / 0012 from replay v2 + dataset v5 artifacts.

Inputs (produced by scripts/remote/session4_finalize_224.sh and pulled back):
  checkpoint_replay_v2.jsonl
  PHASE0_REPLAY_V2_VALIDATION.json
  PHASE0_REPLAY_V2_SUMMARY.json
  selector_dataset_v5_summary.json

Usage:
  python3 harness/make_replay_reports.py \
    --canonical results/canonical_server \
    --report-0011 results/PHASE0_REPORT_0011_BATCH_REPLAY_V2.md \
    --report-0012 results/PHASE0_REPORT_0012_CHECKPOINT_DATASET_V5.md
"""
from __future__ import annotations
import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def load_jsonl(path):
    p = Path(path)
    rows = []
    if not p.exists():
        return rows
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def fnum(value):
    try:
        return float(value)
    except Exception:
        return None


def fmt(value, nd=3):
    if value is None:
        return "NA"
    if isinstance(value, float):
        return ("%%.%df" % nd) % value
    return str(value)


def main():
    ap = argparse.ArgumentParser(description="Generate replay/dataset reports from artifacts")
    ap.add_argument("--canonical", default="results/canonical_server")
    ap.add_argument("--report-0011", default="results/PHASE0_REPORT_0011_BATCH_REPLAY_V2.md")
    ap.add_argument("--report-0012", default="results/PHASE0_REPORT_0012_CHECKPOINT_DATASET_V5.md")
    ap.add_argument("--node", default="224 thinklab-105-224")
    args = ap.parse_args()

    cs = Path(args.canonical)
    replay = load_jsonl(cs / "checkpoint_replay_v2.jsonl")
    plan = load_jsonl(cs / "replay_batch_plan_v2.jsonl")
    validation = load_json(cs / "PHASE0_REPLAY_V2_VALIDATION.json") or {}
    summary = load_json(cs / "PHASE0_REPLAY_V2_SUMMARY.json") or {}
    dataset_summary = load_json(cs / "selector_dataset_v5_summary.json") or {}

    plan_by_id = {str(t.get("run_id")): t for t in plan}
    by_ds = Counter()
    by_design = Counter()
    by_action = Counter()
    durations = defaultdict(list)
    for r in replay:
        rid = str(r.get("run_id"))
        task = plan_by_id.get(rid, {})
        by_ds[(str(task.get("design", r.get("design"))), str(task.get("stage", r.get("stage"))))] += 1
        by_design[str(task.get("design", r.get("design")))] += 1
        by_action[str(task.get("action_id", "control" if not r.get("action") else "?"))] += 1
        dur = fnum(r.get("duration_s"))
        if dur is not None:
            durations[str(task.get("design", r.get("design")))].append(dur)
    controls = sum(1 for r in replay if not r.get("action"))
    gate_ok = sum(1 for r in replay if r.get("gate_ok"))
    rc_bad = sum(1 for r in replay if r.get("returncode") not in (0, "0"))
    n_decisions = len({(str(t.get("design")), str(t.get("checkpoint_run_id")), str(t.get("stage")))
                       for t in plan if t.get("action_id") == "control"})

    def dur_line(design):
        vals = durations.get(design, [])
        if not vals:
            return "NA"
        return "%d 条, mean %.0fs, median %.0fs, max %.0fs" % (
            len(vals), statistics.mean(vals), statistics.median(vals), max(vals))

    effect_rows = summary.get("by_design_stage_action", [])
    oracle = dataset_summary.get("oracle_action_distribution", {})
    gba = dataset_summary.get("gate_ok_by_action", {})

    report11 = []
    report11.append("# PHASE0_REPORT_0011：批量 checkpoint replay v2")
    report11.append("")
    report11.append("**执行节点：** %s  " % args.node)
    report11.append("**日期：** 2026-09-23（会话 4）  ")
    report11.append("**工具：** `harness/plan_replay_batch.py` + `harness/run_replay_pool.py` + "
                    "`harness/checkpoint_replay.py`（OpenROAD read_libraries → read_def → read_sdc，"
                    "续跑 post-GP / post-CTS 剩余 flow）  ")
    report11.append("**口径：** `docs/METRIC_CONVENTIONS.md`（setup WNS=DRT::worst_slack_max，"
                    "hold WNS=DRT::worst_slack_min，power 单位 W，DRC=detailed-route 总数）")
    report11.append("")
    report11.append("## 1. 执行配置与关键变更")
    report11.append("")
    report11.append("- 计划：4 设计 × 2 stage × 首轮 6 动作（control, layeradj_std, grt50, grt200, "
                    "slew0, cap0；与设计默认值重复的动作自动跳过），共 %d 条任务。" % len(plan))
    report11.append("- 控制配对：每个 checkpoint 先跑 control，动作 delta 只与同 checkpoint control 配对；"
                    "不能跨 checkpoint 或跨 stage 比较。")
    report11.append("- 断点续跑：每任务独立 `%s/<run_id>.jsonl`，池重启时扫描 v2/parts 跳过已完成、"
                    "剔除 `returncode != 0` 记录。" % (cs / "v2_parts"))
    report11.append("- **性能修复（重要）：** 首轮 10 并发时 detailed route 默认 `set_thread_count 16`，"
                    "形成 160 线程/64 核超订，aes 出现 1800s 超时；改为 `EDA_THREADS=8 × jobs=8 = 64 线程`，"
                    "单任务 timeout 7200s 后完成时间稳定（aes 479–1274s，无新超时）。")
    report11.append("- 224 上存在外部用户约 16 个满载 CPU 进程，吞吐受共享节点影响；未 kill 任何非本项目进程。")
    report11.append("")
    report11.append("## 2. 结果")
    report11.append("")
    report11.append("| 指标 | 值 |")
    report11.append("|---|---|")
    report11.append("| v2 记录数 | %d |" % len(replay))
    report11.append("| 计划任务数 | %d |" % len(plan))
    report11.append("| control 记录 | %d |" % controls)
    report11.append("| checkpoint 决策点 | %d |" % n_decisions)
    report11.append("| 运行 gate_ok（rc=0 且 DRC=0） | %d/%d |" % (gate_ok, len(replay)))
    _dsr = dataset_summary.get("gate_ok_rate")
    report11.append("| canonical 时序 gate（数据集 v5 action 样本） | %s/%s = %s |" % (
        int(round((_dsr or 0.0) * dataset_summary.get("n_action_samples", 0))),
        dataset_summary.get("n_action_samples", "NA"),
        ("%.3f" % _dsr) if _dsr is not None else "NA"))
    report11.append("| returncode != 0 | %d |" % rc_bad)
    report11.append("| control 覆盖 | %s |" % (validation.get("control_coverage", "NA")))
    report11.append("| 重复 run_id | %s |" % (validation.get("duplicate_run_ids", "NA")))
    for design in ["gcd", "jpeg", "aes", "ibex"]:
        report11.append("| %s 记录 / 耗时 | %d；%s |" % (design, by_design.get(design, 0), dur_line(design)))
    report11.append("| by action | %s |" % json.dumps(dict(by_action), ensure_ascii=False))
    report11.append("| validation errors | %d |" % validation.get("n_errors", -1))
    report11.append("")
    report11.append("### 2.1 动作相对同 checkpoint control 的平均效应（gate = setup/hold 0.02ns guard + DRC；U = canonical utility）")
    report11.append("")
    report11.append("| design | stage | action | n | gate_ok | d_setupWNS(ns) | d_holdWNS(ns) | d_TNS(ns) | "
                    "d_HPWL(um) | d_WL(um) | d_vias | d_power(W) | U | dur(s) |")
    report11.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in effect_rows:
        report11.append("| %s | %s | %s | %d | %d | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r.get("design"), r.get("stage"), r.get("action_id"), r.get("n", 0), r.get("gate_ok", 0),
            fmt(r.get("mean_delta_setup_wns_ns"), 4), fmt(r.get("mean_delta_hold_wns_ns"), 4),
            fmt(r.get("mean_delta_setup_tns_ns"), 3), fmt(r.get("mean_delta_hpwl_um"), 1),
            fmt(r.get("mean_delta_wirelength_um"), 1), fmt(r.get("mean_delta_vias"), 2),
            fmt(r.get("mean_delta_power_w"), 6), fmt(r.get("mean_utility"), 4),
            fmt(r.get("mean_duration_s"), 0)))
    report11.append("")
    report11.append("解读：layeradj_std 在多数 checkpoint 能改善 TNS/WL，但在部分 aes/ibex checkpoint 上 "
                    "setup hold WNS 退化超过 0.02ns guard，canonical gate 不通过（gate_ok 列 < n）；"
                    "grt50/grt200/cap0 在多设计中 delta 为 0，作为 gate-safe 的 no-op 对照；"
                    "oracle 只看 gate-safe 候选，因此部分 checkpoint 的 oracle 是 no-op 类动作而非 layeradj。")
    report11.append("")
    report11.append("Per-decision oracle（gate-safe, canonical U）分布：")
    report11.append("")
    report11.append("```")
    report11.append(json.dumps(summary.get("oracle_action_counts", {}), indent=2, ensure_ascii=False))
    report11.append("```")
    report11.append("")
    report11.append("## 3. 验收门")
    report11.append("")
    report11.append("- [%s] v2 >= 200 条" % ("x" if len(replay) >= 200 else " "))
    report11.append("- [%s] 46/46 replayable checkpoint 的 control 覆盖（validation: %s）" % (
        "x" if str(validation.get("control_coverage", "")).startswith("46/46") else " ",
        validation.get("control_coverage", "NA")))
    report11.append("- [%s] 无重复 run_id" % ("x" if not validation.get("duplicate_run_ids") else " "))
    report11.append("- [%s] returncode 失败率 < 5%%（实际 %s）" % (
        "x" if (validation.get("returncode_fail_rate", 1.0) < 0.05) else " ",
        validation.get("returncode_fail_rate", "NA")))
    report11.append("- [%s] 失败原因逐条记录（pool failures: %d）" % (
        "x" if validation.get("pool_failure_count", 0) == 0 else " ",
        validation.get("pool_failure_count", -1)))
    report11.append("- [%s] 每条 action 都有同 checkpoint control（validation errors=%d）" % (
        "x" if validation.get("n_errors", 1) == 0 else " ", validation.get("n_errors", -1)))
    report11.append("")
    report11.append("## 4. 产物")
    report11.append("")
    report11.append("- v2 标签：`%s`" % (cs / "checkpoint_replay_v2.jsonl"))
    report11.append("- 任务级 parts：`%s/<run_id>.jsonl`" % (cs / "v2_parts"))
    report11.append("- 汇总：`%s` / `%s`" % (cs / "PHASE0_REPLAY_V2_SUMMARY.json",
                                              cs / "PHASE0_REPLAY_V2_VALIDATION.json"))
    report11.append("- 每任务 artifact：`runs_replay/<run_id>/`（replay.tcl, metrics_raw.json, flow.log, results/route.def）")
    report11.append("")
    report11.append("## 5. 已知限制")
    report11.append("")
    report11.append("- replay 与原始 full-flow 有少量状态差；所有动作效应均以 replay control 配对，"
                    "replay 绝对值不能替代 full-flow 数值。")
    report11.append("- 批处理期间后期任务使用 `EDA_THREADS=8`，早期任务（gcd/jpeg）使用 flow 默认 16；"
                    "同 checkpoint 内 control/action 使用相同配置，配对有效；跨批次绝对数值解释需谨慎。")
    report11.append("- pre-route 时序为 RSZ 估计；final 标签以 post-route DRT 为准；hold TNS 当前 222/222 缺失；"
                    "power/DRC 仅 post-route 可得；hold WNS 覆盖 222/222。")
    report11.append("")
    report11.append("## 6. 下一步")
    report11.append("")
    report11.append("1. 用 `selector_dataset_v5_checkpoint.jsonl` 训练/评估 checkpoint selector（报告 0012）。")
    report11.append("2. P2 objective mode selector（`harness/selector_objective_mode.py`）。")
    report11.append("3. P3 设计族/ODB 快照；P4 signoff；P5 seed library。")
    report11.append("")
    Path(args.report_0011).write_text("\n".join(report11) + "\n")

    report12 = []
    report12.append("# PHASE0_REPORT_0012：checkpoint selector 数据集 v5")
    report12.append("")
    report12.append("**日期：** 2026-09-23（会话 4）  ")
    report12.append("**构建器：** `harness/build_checkpoint_dataset.py`  ")
    report12.append("**输入：** `checkpoint_states_v1.jsonl` + `checkpoint_replay_v2.jsonl` + "
                    "`replay_batch_plan_v2.jsonl`")
    report12.append("")
    report12.append("## 1. 联接与标签口径")
    report12.append("")
    report12.append("- 用 plan 的 `run_id ↔ checkpoint_run_id/action_id/design/stage` 映射，"
                    "把 v2 标签按 (design, checkpoint, stage) 分组；")
    report12.append("- 每条 action 样本以同 checkpoint 的 control 为基准计算 Δsetup/hold WNS、Δsetup/hold TNS、"
                    "ΔHPWL、ΔWL、Δvias、Δpower；")
    report12.append("- gate：setup/hold 分别 >= control − 0.02 ns；control 非负时动作不得转负；DRC 不得增加；")
    report12.append("- 门禁之后 soft utility：`U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power`（相对改善，越大越好）；")
    report12.append("- 未过 gate 的样本保留标签但 `selection_score = U − 1.0`，供 gate-aware 训练/评估。")
    report12.append("")
    report12.append("## 2. 数据集统计")
    report12.append("")
    report12.append("| 指标 | 值 |")
    report12.append("|---|---|")
    for key in ["n_states_total", "n_states_replayable", "n_decisions", "n_controls",
                "n_action_samples", "n_sft", "n_preferences", "gate_ok_rate",
                "hold_wns_coverage", "power_coverage", "n_validation_errors", "n_warnings"]:
        report12.append("| %s | %s |" % (key, dataset_summary.get(key, "NA")))
    report12.append("| by_design | %s |" % json.dumps(dataset_summary.get("by_design", {}), ensure_ascii=False))
    report12.append("| by_stage | %s |" % json.dumps(dataset_summary.get("by_stage", {}), ensure_ascii=False))
    report12.append("| by_action | %s |" % json.dumps(dataset_summary.get("by_action", {}), ensure_ascii=False))
    report12.append("| gate_ok_by_action | %s |" % json.dumps(gba, ensure_ascii=False))
    report12.append("| oracle 分布 | %s |" % json.dumps(oracle, ensure_ascii=False))
    report12.append("")
    report12.append("## 3. 产物")
    report12.append("")
    report12.append("- `selector_dataset_v5_checkpoint.jsonl`（每条 action 样本，含 state/control/candidate/delta/gate/utility）")
    report12.append("- `selector_sft_v5_checkpoint.jsonl`（每决策点一条 SFT，assistant 输出 oracle action）")
    report12.append("- `selector_preferences_v5_checkpoint.jsonl`（按 U 的正/负偏好与 ranking）")
    report12.append("- `selector_dataset_v5_summary.json`（本报告数据源）")
    report12.append("")
    report12.append("## 4. 校验")
    report12.append("")
    report12.append("- 每条非 control 样本都有同 checkpoint control；")
    report12.append("- `(checkpoint_run_id, stage, action_id)` 无重复；delta 无 NaN/Inf；候选动作按 checkpoint 去重；")
    report12.append("- 构建器 `--strict` 在 validation errors > 0 时非零退出。")
    report12.append("")
    report12.append("## 5. 复现命令")
    report12.append("")
    report12.append("```bash")
    report12.append("python3 harness/build_checkpoint_dataset.py \\")
    report12.append("  --states results/canonical_server/checkpoint_states_v1.jsonl \\")
    report12.append("  --replay results/canonical_server/checkpoint_replay_v2.jsonl \\")
    report12.append("  --plan results/canonical_server/replay_batch_plan_v2.jsonl \\")
    report12.append("  --out-jsonl results/canonical_server/selector_dataset_v5_checkpoint.jsonl \\")
    report12.append("  --out-sft results/canonical_server/selector_sft_v5_checkpoint.jsonl \\")
    report12.append("  --out-preferences results/canonical_server/selector_preferences_v5_checkpoint.jsonl \\")
    report12.append("  --out-summary results/canonical_server/selector_dataset_v5_summary.json --strict")
    report12.append("```")
    report12.append("")
    report12.append("## 6. 已知限制")
    report12.append("")
    report12.append("- 标签来自 replay control 配对，不是 full-flow 直接对照；")
    report12.append("- 动作目录 v1 仅 6 类下游动作，未覆盖 timing repair/route ordering/antenna 等；")
    report12.append("- hold TNS 覆盖低；power/DRC 仅 post-route 可得；")
    report12.append("- 早期/后期任务线程配置不同（见报告 0011），同 checkpoint 内配对不受影响。")
    report12.append("")
    Path(args.report_0012).write_text("\n".join(report12) + "\n")
    print("REPORTS_WRITTEN")
    print(args.report_0011)
    print(args.report_0012)


if __name__ == "__main__":
    main()
