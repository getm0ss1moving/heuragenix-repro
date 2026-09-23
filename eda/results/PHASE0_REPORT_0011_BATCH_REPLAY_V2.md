# PHASE0_REPORT_0011：批量 checkpoint replay v2

**执行节点：** 224 thinklab-105-224  
**日期：** 2026-09-23（会话 4）  
**工具：** `harness/plan_replay_batch.py` + `harness/run_replay_pool.py` + `harness/checkpoint_replay.py`（OpenROAD read_libraries → read_def → read_sdc，续跑 post-GP / post-CTS 剩余 flow）  
**口径：** `docs/METRIC_CONVENTIONS.md`（setup WNS=DRT::worst_slack_max，hold WNS=DRT::worst_slack_min，power 单位 W，DRC=detailed-route 总数）

## 1. 执行配置与关键变更

- 计划：4 设计 × 2 stage × 首轮 6 动作（control, layeradj_std, grt50, grt200, slew0, cap0；与设计默认值重复的动作自动跳过），共 222 条任务。
- 控制配对：每个 checkpoint 先跑 control，动作 delta 只与同 checkpoint control 配对；不能跨 checkpoint 或跨 stage 比较。
- 断点续跑：每任务独立 `results/canonical_server/v2_parts/<run_id>.jsonl`，池重启时扫描 v2/parts 跳过已完成、剔除 `returncode != 0` 记录。
- **性能修复（重要）：** 首轮 10 并发时 detailed route 默认 `set_thread_count 16`，形成 160 线程/64 核超订，aes 出现 1800s 超时；改为 `EDA_THREADS=8 × jobs=8 = 64 线程`，单任务 timeout 7200s 后完成时间稳定（aes 479–1274s，无新超时）。
- 224 上存在外部用户约 16 个满载 CPU 进程，吞吐受共享节点影响；未 kill 任何非本项目进程。

## 2. 结果

| 指标 | 值 |
|---|---|
| v2 记录数 | 222 |
| 计划任务数 | 222 |
| control 记录 | 46 |
| checkpoint 决策点 | 46 |
| 运行 gate_ok（rc=0 且 DRC=0） | 222/222 |
| canonical 时序 gate（数据集 v5 action 样本） | 157/176 = 0.892 |
| returncode != 0 | 0 |
| control 覆盖 | 46/46 |
| 重复 run_id | [] |
| gcd 记录 / 耗时 | 88；88 条, mean 23s, median 24s, max 31s |
| jpeg 记录 / 耗时 | 48；48 条, mean 969s, median 950s, max 1569s |
| aes 记录 / 耗时 | 50；50 条, mean 878s, median 900s, max 1355s |
| ibex 记录 / 耗时 | 36；36 条, mean 638s, median 651s, max 930s |
| by action | {"control": 46, "layeradj_std": 46, "grt50": 46, "grt200": 46, "cap0": 14, "slew0": 24} |
| validation errors | 0 |

### 2.1 动作相对同 checkpoint control 的平均效应（gate = setup/hold 0.02ns guard + DRC；U = canonical utility）

| design | stage | action | n | gate_ok | d_setupWNS(ns) | d_holdWNS(ns) | d_TNS(ns) | d_HPWL(um) | d_WL(um) | d_vias | d_power(W) | U | dur(s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aes | post_cts | grt200 | 5 | 5 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 896 |
| aes | post_cts | grt50 | 5 | 5 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 909 |
| aes | post_cts | layeradj_std | 5 | 0 | 0.0997 | -0.0361 | 14.965 | 0.0 | -6848.6 | -4809.40 | -0.000480 | 0.0236 | 564 |
| aes | post_cts | slew0 | 5 | 5 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 885 |
| aes | post_global_place | grt200 | 5 | 5 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 961 |
| aes | post_global_place | grt50 | 5 | 5 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 998 |
| aes | post_global_place | layeradj_std | 5 | 2 | 0.0465 | -0.0220 | 12.910 | 0.0 | -5495.8 | -4515.60 | -0.000280 | 0.0200 | 651 |
| aes | post_global_place | slew0 | 5 | 1 | -0.1682 | -0.0044 | -43.010 | -9854.0 | 3433.2 | -123.60 | -0.000120 | -0.0633 | 1002 |
| gcd | post_cts | grt200 | 11 | 11 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 23 |
| gcd | post_cts | grt50 | 11 | 11 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 23 |
| gcd | post_cts | layeradj_std | 11 | 11 | -0.0069 | 0.0034 | 0.547 | 0.0 | -50.2 | -8.55 | -0.000001 | 0.0129 | 22 |
| gcd | post_global_place | grt200 | 11 | 11 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 24 |
| gcd | post_global_place | grt50 | 11 | 11 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 23 |
| gcd | post_global_place | layeradj_std | 11 | 11 | 0.0031 | 0.0034 | 0.564 | 0.0 | -28.8 | -2.00 | -0.000000 | 0.0139 | 23 |
| ibex | post_cts | cap0 | 3 | 3 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 595 |
| ibex | post_cts | grt200 | 3 | 3 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 607 |
| ibex | post_cts | grt50 | 3 | 3 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 635 |
| ibex | post_cts | layeradj_std | 3 | 1 | 0.1189 | -0.0504 | 27.008 | 0.0 | -5657.7 | -2941.00 | -0.000267 | 0.0409 | 455 |
| ibex | post_cts | slew0 | 3 | 3 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 591 |
| ibex | post_global_place | cap0 | 3 | 3 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 700 |
| ibex | post_global_place | grt200 | 3 | 3 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 718 |
| ibex | post_global_place | grt50 | 3 | 3 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 714 |
| ibex | post_global_place | layeradj_std | 3 | 0 | 0.1312 | -0.0487 | 29.763 | 0.0 | -4733.0 | -2691.67 | -0.000200 | 0.0407 | 533 |
| ibex | post_global_place | slew0 | 3 | 1 | 0.1246 | 0.0016 | -9.817 | 1953.7 | 4213.7 | 337.00 | -0.000067 | -0.0224 | 743 |
| jpeg | post_cts | cap0 | 4 | 4 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 1056 |
| jpeg | post_cts | grt200 | 4 | 4 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 997 |
| jpeg | post_cts | grt50 | 4 | 4 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 909 |
| jpeg | post_cts | layeradj_std | 4 | 4 | 0.0850 | 0.0136 | 9.177 | 0.0 | -2787.2 | -396.00 | -0.001000 | 0.0353 | 863 |
| jpeg | post_cts | slew0 | 4 | 4 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 1020 |
| jpeg | post_global_place | cap0 | 4 | 4 | -0.0008 | -0.0030 | -1.999 | 0.2 | -193.5 | -117.50 | 0.000000 | -0.0070 | 968 |
| jpeg | post_global_place | grt200 | 4 | 4 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 990 |
| jpeg | post_global_place | grt50 | 4 | 4 | 0.0000 | 0.0000 | 0.000 | 0.0 | 0.0 | 0.00 | 0.000000 | 0.0000 | 1036 |
| jpeg | post_global_place | layeradj_std | 4 | 4 | 0.0633 | 0.0112 | 6.138 | 0.0 | -3197.5 | -548.50 | -0.001000 | 0.0231 | 1017 |
| jpeg | post_global_place | slew0 | 4 | 4 | 0.0042 | -0.0010 | -1.339 | -6.7 | -62.0 | -111.25 | 0.000000 | -0.0053 | 986 |

解读：layeradj_std 在多数 checkpoint 能改善 TNS/WL，但在部分 aes/ibex checkpoint 上 setup hold WNS 退化超过 0.02ns guard，canonical gate 不通过（gate_ok 列 < n）；grt50/grt200/cap0 在多设计中 delta 为 0，作为 gate-safe 的 no-op 对照；oracle 只看 gate-safe 候选，因此部分 checkpoint 的 oracle 是 no-op 类动作而非 layeradj。

Per-decision oracle（gate-safe, canonical U）分布：

```
{
  "aes/post_cts/grt200": 5,
  "aes/post_global_place/grt200": 3,
  "aes/post_global_place/layeradj_std": 2,
  "gcd/post_cts/grt200": 3,
  "gcd/post_cts/layeradj_std": 8,
  "gcd/post_global_place/grt200": 1,
  "gcd/post_global_place/layeradj_std": 10,
  "ibex/post_cts/cap0": 2,
  "ibex/post_cts/layeradj_std": 1,
  "ibex/post_global_place/cap0": 3,
  "jpeg/post_cts/layeradj_std": 4,
  "jpeg/post_global_place/layeradj_std": 4
}
```

## 3. 验收门

- [x] v2 >= 200 条
- [x] 46/46 replayable checkpoint 的 control 覆盖（validation: 46/46）
- [x] 无重复 run_id
- [x] returncode 失败率 < 5%（实际 0.0）
- [x] 失败原因逐条记录（pool failures: 0）
- [x] 每条 action 都有同 checkpoint control（validation errors=0）

## 4. 产物

- v2 标签：`results/canonical_server/checkpoint_replay_v2.jsonl`
- 任务级 parts：`results/canonical_server/v2_parts/<run_id>.jsonl`
- 汇总：`results/canonical_server/PHASE0_REPLAY_V2_SUMMARY.json` / `results/canonical_server/PHASE0_REPLAY_V2_VALIDATION.json`
- 每任务 artifact：`runs_replay/<run_id>/`（replay.tcl, metrics_raw.json, flow.log, results/route.def）

## 5. 已知限制

- replay 与原始 full-flow 有少量状态差；所有动作效应均以 replay control 配对，replay 绝对值不能替代 full-flow 数值。
- 批处理期间后期任务使用 `EDA_THREADS=8`，早期任务（gcd/jpeg）使用 flow 默认 16；同 checkpoint 内 control/action 使用相同配置，配对有效；跨批次绝对数值解释需谨慎。
- pre-route 时序为 RSZ 估计；final 标签以 post-route DRT 为准；hold TNS 当前 222/222 缺失；power/DRC 仅 post-route 可得；hold WNS 覆盖 222/222。

## 6. 下一步

1. 用 `selector_dataset_v5_checkpoint.jsonl` 训练/评估 checkpoint selector（报告 0012）。
2. P2 objective mode selector（`harness/selector_objective_mode.py`）。
3. P3 设计族/ODB 快照；P4 signoff；P5 seed library。

