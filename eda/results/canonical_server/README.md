# canonical_server：服务器 224 重算后的权威结果

本目录是 2026-09-22/23 在端口 224（`thinklab-105-224`）完成 WNS/HPWL/power/DRC/instance 口径修复与 checkpoint replay 批量标签后得到的 canonical 结果。

## 1. Phase 0 canonical 结果

| 文件 | 内容 |
|---|---|
| `gcd_candidates.json` / `aes_candidates.json` / `jpeg_candidates.json` / `ibex_candidates.json` | 按 `config/dataset_runs.json` 重建的候选表 |
| `PHASE0_STATS_4designs_server.{json,md}` | 新口径 paired stats |
| `PHASE0_SELECTOR_4designs_server.{json,md}` | random/rule/oracle selector（未调 API） |
| `PHASE0_SELECTOR_4designs_server_api.{json,md}` | dsv4-flash canonical prompt API selector（3/4 与 oracle 一致） |
| `selector_dataset_v4.jsonl` / `selector_sft_v4.jsonl` / `selector_preferences_v4.jsonl` | canonical 蒸馏数据集 v4（flow-start） |
| `selector_dataset_v4_summary.json` | v4 摘要 |
| `PHASE0_ORACLE_SENSITIVITY.{json,md}` | 不同 utility policy 下的 oracle 敏感性 |

## 2. checkpoint replay v2（会话 4，P0）

| 文件 | 内容 |
|---|---|
| `checkpoint_states_v1.jsonl` + `.summary.json` | post-GP/post-CTS/post-route 无标签状态卡（69 条，46 条可 replay） |
| `checkpoint_replay_v1.jsonl` | v1 原型 5 条 gcd（历史） |
| `checkpoint_replay_v2.jsonl` | **权威批量标签：222 条 = 46 checkpoint × control + 176 动作样本**，全部 rc=0 / DRC=0，control 覆盖 46/46 |
| `v2_parts/<run_id>.jsonl` | 每任务独立记录（断点续跑用） |
| `PHASE0_REPLAY_V2_SUMMARY.{json,md}` | 动作相对同 checkpoint control 的 paired 效应表 |
| `PHASE0_REPLAY_V2_VALIDATION.json` | 验收校验：records/control 覆盖/重复/失败/门禁 |
| `replay_batch_plan_v2.jsonl` | 222 条任务计划（run_id ↔ checkpoint/action 映射） |

配置要点（报告 0011）：首轮曾因 detailed-route 默认 `set_thread_count 16` × 10 并发导致 160 线程/64 核超订和 aes 1800s 超时；改为 `EDA_THREADS=8 × jobs=8` + timeout 7200s 后无新超时。224 为共享节点（外部用户负载存在），但未 kill 任何非本项目进程。

## 3. checkpoint selector 数据集 v5（会话 4，P1）

| 文件 | 内容 |
|---|---|
| `selector_dataset_v5_checkpoint.jsonl` | **176 条 (checkpoint, action, delta, gate, U) 标签**，每条与同 checkpoint control 配对 |
| `selector_sft_v5_checkpoint.jsonl` | 46 条 SFT（每决策点一条，assistant 输出 gate-safe oracle action） |
| `selector_preferences_v5_checkpoint.jsonl` | 46 条偏好（正/负样本 + ranking） |
| `selector_dataset_v5_summary.json` | 46 决策点、gate_ok 率 0.892、oracle 分布（layeradj 29 / grt200 12 / cap0 5）、0 校验错误 |

口径：setup/hold ≥ control − 0.02 ns 且 baseline 非负不转负、DRC 不增；门禁后 `U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power`。

## 4. P2 objective mode（会话 4，离线部分）

| 文件 | 内容 |
|---|---|
| `PHASE0_OBJECTIVE_MODE_SELECTOR.{json,md}` | 4 设计 × 4 objective mode 的条件化 oracle；gcd 复现敏感性（HPWL_first→pad_2、power_first→density_035、balanced/timing_first→density_025），aes/jpeg/ibex 稳定 |
| 工具 | `harness/selector_objective_mode.py`（LLM 评估需加 API key，未执行） |

## 5. 配套报告

- `../PHASE0_REPORT_0008_SERVER_RECOMPUTE.md`（canonical 重算）
- `../PHASE0_REPORT_0009_CHECKPOINT_STATES_v1.md`（checkpoint 状态卡）
- `../PHASE0_REPORT_0010_CHECKPOINT_REPLAY_v1.md`（replay 原型）
- `../PHASE0_REPORT_0011_BATCH_REPLAY_V2.md`（P0 批量 222 条）
- `../PHASE0_REPORT_0012_CHECKPOINT_DATASET_V5.md`（P1 数据集 v5）

旧结果和本地 pre-server 版本已归档到 `../legacy_wrong_metrics/`，禁止用于报告/训练/selector/论文；`selector_dataset_v3` 废弃。

**会话 4 状态：** P0（222 条 replay）与 P1（v5 数据集）已完成并验收；下一步 P2 LLM mode 评估、P3 设计族/ODB、P4 signoff、P5 seed library，入口 `../../HANDOFF_SESSION4_NEXT.md`。
