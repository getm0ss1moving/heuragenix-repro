> **WNS 口径勘误（2026-09-22）**：本报告中的 "WNS" 字段实际为 `DRT::worst_slack_min`（hold slack），不是 setup WNS；setup WNS 应使用 `DRT::worst_slack_max`。请以 `docs/METRIC_CONVENTIONS.md` 和 `results/PHASE0_REPORT_0006_WNS_FIX.md` 为准。本报告的 timing gate / regret / 效用数值需按 canonical 口径重算。

# Phase 0 报告 v5：ibex 加入 + timing guard + 四设计 selector

日期：2026-09-22 ｜ 节点：224（本项目工作端口）｜ 设计：gcd / aes / jpeg / ibex ｜ OpenLane spm、pin-offset HPWL、L0/L1 verifier、蒸馏数据集 v3

## 0. 结论

- 第 4 个设计族 ibex（15.7k insts）baseline 276.8 s：HPWL 929,652 µm、WNS −0.126 ns、TNS −299.05 ns、DRC/ant=0；pad_2 HPWL −14.6%、WNS +0.029（改善）、TNS +67.1 ns；density_040 HPWL −13.4%、WNS −0.061（恶化）、TNS +97.1 ns。
- 加入 timing guardband（WNS ≥ baseline −0.02 ns，且不允许把非负 WNS 变成负）后：jpeg 的 pad_2/density_040 都因破坏 setup 被淘汰，oracle=layeradj（唯一 timing-safe）；gcd/aes/ibex oracle=pad_2。
- dsv4-flash selector 在 prompt 明确 timing gate 后，四个设计全部与 oracle 一致（regret=0）；此前无 gate 时 jpeg 误选 pad_2（regret 0.7264）。固定 rule（永远 pad_2）在 jpeg 上同样吃 regret 0.7264。
- 蒸馏数据集 v3：4 设计、16 个 state-candidate、4 条 SFT、4 条 POR 偏好记录；已具备接 Qwen LoRA/GRPO 的数据格式，但样本量仍远小于训练需求（目标 200–1000 条），需先扩 checkpoint/设计族。

## 1. ibex 候选明细

| variant | gate | HPWL_um | ΔHPWL | WNS_ns | ΔWNS | TNS_ns | ΔTNS | power_W | sec |
|---|---|---|---|---|---|---|---|---|---|
| base | True | 929652 | +0.0% | -0.1259 | +0.0000 | -299.05 | +0.0 | 0.0364 | 276.8 |
| density_040 | True | 805510 | -13.4% | -0.1870 | -0.0611 | -201.98 | +97.1 | 0.0347 | 291.5 |
| pad_2 | True | 793709 | -14.6% | -0.0972 | +0.0288 | -231.96 | +67.1 | 0.0345 | 326.1 |

## 2. 四设计 stats（bootstrap 95% CI，含 timing-unsafe 候选）

| candidate | n | ΔHPWL | ΔHPWL CI | ΔTNS_ns | ΔTNS CI | ΔWNS_ns | Δpower | Δruntime |
|---|---|---|---|---|---|---|---|---|
| density_040 | 4 | -12.9% | [-195673.2, -34165.1] | +52.51 | [16.72, 84.66] | -0.015 | -3.8% | +18.1% |
| pad_2 | 4 | -14.4% | [-207961.0, -37859.9] | +47.88 | [17.30, 70.65] | -0.022 | -3.9% | +20.1% |
| layeradj | 1 | +0.0% | [0.0, 0.0] | +1.28 | [1.28, 1.28] | +0.004 | +0.0% | +1.0% |
| grt_200 | 2 | +0.0% | [0.0, 0.0] | +0.00 | [0.00, 0.00] | +0.000 | +0.0% | +8.3% |

注意：上表是跨全部设计的边际统计，未先过 timing guard；部署时应先过滤 timing-unsafe 候选再比较。

## 3. 四设计 selector（timing gate 显式写入 prompt）

| design | candidates | oracle(timing-safe) | rule(pad2) regret | dsv4-flash LLM | LLM regret | random mean regret |
|---|---|---|---|---|---|---|
| aes | 5 | pad_2 | 0.0 | pad_2 | 0.0 | 0.1467 |
| gcd | 8 | pad_2 | 0.0 | pad_2 | 0.0 | 0.0453 |
| ibex | 3 | pad_2 | 0.0 | pad_2 | 0.0 | 0.0983 |
| jpeg | 4 | layeradj | 0.7264042399461953 | layeradj | 0.0 | 0.2233 |

## 4. 蒸馏数据集 v3

| 项 | 值 |
|---|---|
| n_designs | 4 |
| n_candidates | {"gcd": 7, "aes": 4, "jpeg": 3, "ibex": 2} |
| oracles | {"gcd": "pad_2", "aes": "pad_2", "jpeg": "layeradj", "ibex": "pad_2"} |
| n_sft | 4 |
| utility_spec | 0.4*d_hpwl + 0.3*d_abs_tns + 0.2*d_wns + 0.1*d_power; 先过 timing guardband (WNS>=base-0.02ns 且不新增 violation) |

产物：`results/selector_dataset_v3.jsonl`（状态-候选-结果）、`selector_sft_v3.jsonl`（chat SFT）、`selector_preferences_v3.jsonl`（POR 正/负集）、`selector_dataset_v3_summary.json`；方法文档 `docs/DISTILLATION_DATASET.md`。

## 5. 判断与下一步

- timing guard 是必须的：没有它，LLM 会用 jpeg 的 setup violation 换 HPWL/TNS；有了它，LLM 能与规则/oracle 一致。
- `pad_2` 仍是小/中设计（gcd/aes/ibex）的最佳候选；`layeradj` 是 jpeg 这类“baseline 已 timing-tight”设计的保守选项；`density_040` 在 HPWL/TNS 上强但会破坏 jpeg setup。
- 蒸馏到 Qwen 前必须先扩数据：checkpoint 续跑（post_global_place/post_cts/post_grt）、更多设计族、每状态多候选；目标 200–1000 条 state-candidate。
- 下一步：实现 checkpoint 续跑 runner / 用现有 runs 扩 SFT；等 GPU 空闲再跑 Qwen LoRA + GRPO（CA-POR + EDA-CPR + gate/cost）。

