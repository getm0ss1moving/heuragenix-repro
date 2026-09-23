# PHASE0_REPORT_0008：服务器 224 canonical 重算报告 v1

**执行节点：** 2026-09-22，端口 224（thinklab-105-224），项目 `/data/dzy/heura_repr/eda`  
**范围：** WNS/HPWL/power/DRC/instance 口径修复后的服务器重算与候选补跑  
**状态：** 已完成；本报告是当前 EDA Phase 0 的权威数字版本。旧报告 0003–0005 的 WNS/HPWL/power/DRC 数字作废。

---

## 1. 本次执行内容

1. 将本地修复后的 `harness/ docs/ scripts/ results/canonical/` 同步到 224。
2. 对 21 个旧 run 执行 `migrate_legacy_metrics.py --runs-dir runs --in-place`，把旧 timing 字段迁移成 canonical setup/hold。
3. 对已有 DEF 的 run 执行 `recompute_metrics.py`，重算 HPWL/线长/via/power 等。
4. 对 14 个缺 DEF 的 run 补跑 flow（gcd 9 个 + aes 5 个），使用相同 run_id 与 overrides；新 `phase0.py/lef_def.py` 直接产出 canonical 指标和 DEF snapshot。
5. 全量再跑 `recompute_metrics.py`，统一 23 个 run 的指标字段。
6. 按 `config/dataset_runs.json` 重建 canonical 候选表、stats、selector、dataset v4。
7. `cleanup_legacy.py --apply` 把 48 个旧口径产物移入服务器 `results/legacy_wrong_metrics/`。
8. 将 `results/canonical_server/`、关键 `runs/**/metrics.json` 与日志拉回本地。

## 2. HPWL 解析正确性验证

新 `lef_def.py` 的 pin-offset HPWL（含 `( PIN port )` 与换行 continuation）与 OpenROAD detailed-placement 日志一致：

| design | 本 harness `def_route.hpwl_um` | OpenROAD DPL log（legalized） | 偏差 |
|---|---|---|---|
| gcd base | 13117.700 | 13075.7 | +0.32% |
| jpeg base | 1,996,141.315 | 1,994,903.3 | +0.06% |
| ibex base | 1,217,880.171 | 1,217,355.6 | +0.04% |
| aes base | 1,227,554.093 | 待补日志核对 | — |

旧 parser 的 gcd/jpeg/ibex HPWL（7423.9 / 1,875,375 / 929,652）明显偏低，是因为漏掉了换行 pin 与顶层端口；这些旧值已废弃。

## 3. 四设计 canonical baseline

| design | setup_wns_ns | hold_wns_ns | setup_tns_ns | route HPWL_um | logic cells | total cells | power_W |
|---|---|---|---|---|---|---|---|
| gcd | -0.6333 | +0.4842 | -15.58 | 13117.700 | 250 | — | 0.000967 |
| aes | -1.8613 | -0.1463 | -289.19 | 1,227,554.093 | 17210 | — | 0.0424 |
| jpeg | -1.0944 | +0.0402 | -129.90 | 1,996,141.315 | 45634 | — | 0.159 |
| ibex | -5.2052 | -0.1259 | -299.05 | 1,217,880.171 | 15696 | — | 0.0364 |

## 4. 新 oracle / selector 结果

| design | 旧 oracle | 新 oracle | 变化原因 |
|---|---|---|---|
| gcd | pad_2 | **density_025** | 新 HPWL 加入顶层端口/换行 pin 后，pad_2 的 HPWL 优势仍大，但 density_025 的 setup TNS 从 -15.58 改善到 -10.63；gate-only 软效用 `0.5 HPWL + 0.4 |TNS| + 0.1 power` 下 density_025 胜出 |
| aes | pad_2 | pad_2 | 不变 |
| jpeg | layeradj | layeradj | 不变（pad_2/density_040 因 hold 转负被 gate 拒绝） |
| ibex | pad_2 | pad_2 | 不变 |

naive rule（首选 pad_2）在 gcd 上的 gate-aware regret 为 **0.0571**，jpeg 为 **0.7904**（jpeg 仍是最能体现“必须显式写 timing gate”的案例）。

## 5. 产物

服务器：

- `results/canonical_server/{gcd,aes,jpeg,ibex}_candidates.json`
- `results/canonical_server/PHASE0_STATS_4designs_server.{json,md}`
- `results/canonical_server/PHASE0_SELECTOR_4designs_server.{json,md}`
- `results/canonical_server/selector_dataset_v4.jsonl`、`selector_sft_v4.jsonl`、`selector_preferences_v4.jsonl`、`selector_dataset_v4_summary.json`
- `results/legacy_wrong_metrics/`（旧口径产物，含 MANIFEST.txt）

本地镜像：

- `results/canonical_server/`（上面整套）
- `runs/<run_id>/{metrics,meta,state_card,verify}.json` + `flow.log`
- `logs/rerun_missing_224.log`、`recompute_metrics_224_v2.log`、`rebuild_canonical_224.log`、`cleanup_legacy_224.log`

## 6. 下一步

1. dsv4-flash API selector 已补跑（见 §7）：3/4 与 oracle 一致；gcd 需做 utility/oracle 敏感性分析或明确优先目标。
2. 把 `PHASE0_REPORT_0006/0007` 与 0008 合并为论文可用的方法+实验口径章节；主表引用 0008。
3. 扩设计族与 checkpoint（post_global_place/post_cts/post_grt），继续 dataset v4 扩样。
4. 接 DRC/LVS/STA（L2/L3）与 hold TNS 提取。

## 7. dsv4-flash canonical prompt API selector（2026-09-22 补跑）

用 `results/canonical_server/` 四张候选表 + canonical gate prompt，本地调用 dsv4-flash：

| design | oracle | dsv4-flash | API regret | naive rule | rule regret |
|---|---|---|---|---|---|
| gcd | density_025 | density_035 | 0.0562 | pad_2 | 0.0571 |
| aes | pad_2 | pad_2 | 0.0 | pad_2 | 0.0 |
| jpeg | layeradj | layeradj | 0.0 | pad_2 | 0.7904 |
| ibex | pad_2 | pad_2 | 0.0 | pad_2 | 0.0 |

- 3/4 设计与 oracle 一致；jpeg 正确避开 hold 违例的 pad_2/density_040，说明显式 timing gate prompt 生效。
- gcd 的 API 选择 density_035：setup/hold 双 safe、HPWL 优于 density_025，但 setup TNS 略差；这是 gate-only utility 权重（0.5 HPWL / 0.4 |TNS| / 0.1 power）下的近邻决策。后续应做 utility/oracle 敏感性分析，或对该设计明确采用 lexicographic/目标优先级。
- API 产物：`PHASE0_SELECTOR_4designs_server_api.{json,md}`。

## 8. Oracle 敏感性分析（解决 gcd 分歧）

用 `harness/oracle_sensitivity.py` 在 gate-safe 候选上比较不同 utility policy：

| design | weighted v2 | equal v2 | old 4-item | lex HPWL | lex TNS | lex power |
|---|---|---|---|---|---|---|
| gcd | density_025 | density_025 | density_025 | **pad_2** | density_025 | density_035 |
| aes | pad_2 | pad_2 | pad_2 | pad_2 | pad_2 | density_040 |
| jpeg | layeradj | layeradj | layeradj | layeradj | layeradj | layeradj |
| ibex | pad_2 | pad_2 | pad_2 | pad_2 | pad_2 | pad_2 |

**结论：**
- aes/jpeg/ibex 的 oracle 在所有合理 policy 下稳定；gcd 是唯一强 policy-dependent 的设计（density_025 vs pad_2 vs density_035 都在 gate-safe Pareto 前沿）。
- API selector 选 density_035，恰好是 power-first 选择；当前 weighted utility 选 density_025（TNS 权重大）；HPWL-first 选 pad_2。
- 因此 gcd 不应宣称“唯一 oracle”。Phase 0 报告建议同时给 weighted/lex-HPWL 两个口径；Phase 1 应让 selector 显式输出 objective mode（timing_first / HPWL_first / power_first），oracle 按 mode 条件化。
- 产物：`PHASE0_ORACLE_SENSITIVITY.{json,md}`。

## 9. 后续进展（2026-09-22）

- `harness/oracle_sensitivity.py` 已跑：gcd 是 policy-dependent（weighted/TNS-first→density_025；HPWL-first→pad_2；power-first→density_035），aes/jpeg/ibex 稳定；产物 `PHASE0_ORACLE_SENSITIVITY.{json,md}`。
- `harness/checkpoint_states.py` 已跑：从 23 个 run 的 post_global_place/post_cts/post_route DEF 抽取 **69 条无标签状态卡**；产物 `checkpoint_states_v1.jsonl`，摘要 `checkpoint_states_v1.summary.json`；报告 `PHASE0_REPORT_0009_CHECKPOINT_STATES_v1.md`。
- 下一步：checkpoint replay 生成 `(state, action, delta)` 标签，扩到 200–1000 条，并接 L3 signoff。
