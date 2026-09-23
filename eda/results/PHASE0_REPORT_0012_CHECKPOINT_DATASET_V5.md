# PHASE0_REPORT_0012：checkpoint selector 数据集 v5

**日期：** 2026-09-23（会话 4）  
**构建器：** `harness/build_checkpoint_dataset.py`  
**输入：** `checkpoint_states_v1.jsonl` + `checkpoint_replay_v2.jsonl` + `replay_batch_plan_v2.jsonl`

## 1. 联接与标签口径

- 用 plan 的 `run_id ↔ checkpoint_run_id/action_id/design/stage` 映射，把 v2 标签按 (design, checkpoint, stage) 分组；
- 每条 action 样本以同 checkpoint 的 control 为基准计算 Δsetup/hold WNS、Δsetup/hold TNS、ΔHPWL、ΔWL、Δvias、Δpower；
- gate：setup/hold 分别 >= control − 0.02 ns；control 非负时动作不得转负；DRC 不得增加；
- 门禁之后 soft utility：`U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power`（相对改善，越大越好）；
- 未过 gate 的样本保留标签但 `selection_score = U − 1.0`，供 gate-aware 训练/评估。

## 2. 数据集统计

| 指标 | 值 |
|---|---|
| n_states_total | 69 |
| n_states_replayable | 46 |
| n_decisions | 46 |
| n_controls | 46 |
| n_action_samples | 176 |
| n_sft | 46 |
| n_preferences | 46 |
| gate_ok_rate | 0.8920454545454546 |
| hold_wns_coverage | 1.0 |
| power_coverage | 1.0 |
| n_validation_errors | 0 |
| n_warnings | 0 |
| by_design | {"gcd": 66, "jpeg": 40, "aes": 40, "ibex": 30} |
| by_stage | {"post_global_place": 88, "post_cts": 88} |
| by_action | {"grt200": 46, "grt50": 46, "layeradj_std": 46, "cap0": 14, "slew0": 24} |
| gate_ok_by_action | {"cap0": "14/14", "grt200": "46/46", "grt50": "46/46", "layeradj_std": "33/46", "slew0": "18/24"} |
| oracle 分布 | {"layeradj_std": 29, "grt200": 12, "cap0": 5} |

## 3. 产物

- `selector_dataset_v5_checkpoint.jsonl`（每条 action 样本，含 state/control/candidate/delta/gate/utility）
- `selector_sft_v5_checkpoint.jsonl`（每决策点一条 SFT，assistant 输出 oracle action）
- `selector_preferences_v5_checkpoint.jsonl`（按 U 的正/负偏好与 ranking）
- `selector_dataset_v5_summary.json`（本报告数据源）

## 4. 校验

- 每条非 control 样本都有同 checkpoint control；
- `(checkpoint_run_id, stage, action_id)` 无重复；delta 无 NaN/Inf；候选动作按 checkpoint 去重；
- 构建器 `--strict` 在 validation errors > 0 时非零退出。

## 5. 复现命令

```bash
python3 harness/build_checkpoint_dataset.py \
  --states results/canonical_server/checkpoint_states_v1.jsonl \
  --replay results/canonical_server/checkpoint_replay_v2.jsonl \
  --plan results/canonical_server/replay_batch_plan_v2.jsonl \
  --out-jsonl results/canonical_server/selector_dataset_v5_checkpoint.jsonl \
  --out-sft results/canonical_server/selector_sft_v5_checkpoint.jsonl \
  --out-preferences results/canonical_server/selector_preferences_v5_checkpoint.jsonl \
  --out-summary results/canonical_server/selector_dataset_v5_summary.json --strict
```

## 6. 已知限制

- 标签来自 replay control 配对，不是 full-flow 直接对照；
- 动作目录 v1 仅 6 类下游动作，未覆盖 timing repair/route ordering/antenna 等；
- hold TNS 覆盖低；power/DRC 仅 post-route 可得；
- 早期/后期任务线程配置不同（见报告 0011），同 checkpoint 内配对不受影响。

