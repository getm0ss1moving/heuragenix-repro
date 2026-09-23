# HA-PR / EDA 布局布线 Phase 0 交接文档

**更新时间：** 2026-09-23（会话 4 完成 P0/P1）  
**交接对象：** 下一个继续本任务的会话（避免从零读全部上下文）  
**会话 4 最终交接：** `HANDOFF_SESSION4_NEXT.md`（P0 222 条、P1 v5 已完成并验收）；以下 Phase 0 历史仍有效。

**先读顺序：** 本文件 → `docs/METRIC_CONVENTIONS.md` → `docs/RUNBOOK.md` → `results/PHASE0_REPORT_0006_WNS_FIX.md`、`results/PHASE0_REPORT_0007_METRIC_AUDIT_v1.md` → 根目录 `10_完整数学建模体系_EDA布局布线与测试_v1.md`。

---

## 1. 任务是什么

把 HeurAgenix 的“启发式演化 + 在线选择”迁移到 EDA 布局布线，形成 HA-PR 框架：契约化 skill/option、多保真评估、verifier 门禁、selector 与后续自进化。当前已进入 **Phase 0 实跑**：在 OpenLane 1 / OpenROAD 2022 + sky130hd 上跑 4 个设计（gcd/aes/jpeg/ibex），验证 HPWL 口径、verifier、selector、统计协议、timing gate。

## 2. 当前状态（截至本次交接）

- Phase 0 已完成 4 个设计：gcd、aes、jpeg、ibex；覆盖 floorplan→placement→cts→route 全 flow。
- 已实现：pin-offset HPWL（`harness/lef_def.py`）、OpenLane spm ingest（`harness/openlane_ingest.py`）、L0/L1 verifier（`harness/verifier.py`）、selector v0（`harness/selector_v0.py`）、paired stats（`harness/stats.py`）、蒸馏数据集构建（`harness/build_selector_dataset.py`）。
- **发现并修复 WNS 口径错误：** 旧代码把 `DRT::worst_slack_min`（hold slack）当作 WNS；真正 setup WNS 是 `DRT::worst_slack_max`。修复见 `harness/metrics_schema.py`、`docs/METRIC_CONVENTIONS.md`。
- **dsv4-flash canonical API selector 已跑**：3/4 与 oracle 一致；jpeg 正确避开 hold 违例；gcd 选 density_035（regret≈0.056，接近 oracle density_025）。
- **2026-09-22 已在 224 完成服务器 canonical 重算**：21 个旧 run 迁移/重算 + 14 个缺 DEF 候选补跑；权威结果 `results/canonical_server/`，报告 `results/PHASE0_REPORT_0008_SERVER_RECOMPUTE.md`。本地 pre-server 的 `*_wnsfix*` 与 `canonical/` 已移入 `results/legacy_wrong_metrics/`。
- 第二批指标审计又修复：OpenLane power 列实际是 W（旧 bug 差 1e6）、DRC 不再重复相加、instance_count 改用逻辑单元数、HPWL 修正 `( PIN port )`/换行 pin 并拆出 `hpwl_no_ports_um`；新增 `harness/metric_rules.py`、`harness/recompute_metrics.py`、`harness/cleanup_legacy.py`。
- 旧报告 `PHASE0_REPORT_0003/0004/0005` 的 “WNS” 数值不再可信，已加勘误横幅；最终数字需在服务器用新 harness 重跑/重算后出 v2。
- 服务器重算已实际跑通，关键产物与 run 日志已拉回本地；HPWL 新解析器与 OpenROAD DPL 日志在 gcd/jpeg/ibex 上偏差 ≤0.32%。

## 3. 关键结论（新口径，本地数据重算）

| design | setup_wns_ns | hold_wns_ns | setup_tns_ns | 新 oracle | 旧 oracle |
|---|---|---|---|---|---|
| gcd | -0.6333 | +0.4842 | -15.58 | **density_025** | pad_2 |
| aes | -1.8613 | -0.1463 | -289.19 | pad_2 | pad_2 |
| jpeg | -1.0944 | +0.0402 | -129.90 | layeradj | layeradj |
| ibex | -5.2052 | -0.1259 | -299.05 | pad_2 | pad_2 |

- gcd 的新 oracle 变为 density_025：新 HPWL（含端口/换行 pin）加上 gate-only utility `0.5 HPWL + 0.4 |TNS| + 0.1 power` 后，density_025 的 setup TNS 优势胜出；aes/jpeg/ibex oracle 不变。
- jpeg：pad_2/density_040 的 setup 改善，但把 hold 从非负变成负，按新规则被拒绝；layeradj 是唯一 setup/hold 双 safe，oracle 不变。
- 新 selector 的 gate-aware regret：jpeg 下 naive rule（pad_2）≈0.785；旧报告 0.7264 是用错误 WNS 软项算出来的，不应再引用。
- 软效用已改为 gate 之后只比 HPWL/TNS/power：`U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power`；WNS 只做硬门禁。

## 4. 代码/文件地图

本地（Mac，代码与报告镜像）：
```
/Users/duanzeyu/Desktop/文献/heura_repro/eda/
  harness/            # 控制面代码（phase0/verifier/selector/stats/dataset/ingest/migration）
  docs/               # METRIC_CONVENTIONS.md, RUNBOOK.md, DISTILLATION_DATASET.md
  results/            # 报告、selector/stats/dataset 产物
  openlane_runs/      # 本地 OpenLane slim 产物 + ingest 结果
  pdk/                # sky130A LEF
  scripts/            # 早期运行脚本
```
服务器（真正跑 flow）：`/data/dzy/heura_repr/eda/`，包含 `tools/openroad`、`flow/`、`runs/`、`reference/`、`results/`。  
同步提示：本次修复后的 `harness/*.py`、`docs/*`、`results/canonical_server/*`、`results/*wnsfix*`、`results/PHASE0_REPORT_0006*` 需要 rsync 到服务器 224 后再在服务器重建。

**同步脚本：** 在本地 `eda/` 下执行 `bash scripts/sync_and_recompute_224.sh`（会提示 ssh/rsync 凭据，不落盘），脚本会同步修复后 harness/docs/报告，在 224 上依次执行 smoke test、migrate、recompute、cleanup，并把重算结果拉回本地。

> 本会话本地环境无 224 的 SSH publickey/password（`ssh -o BatchMode=yes` 被拒），因此未直接登录服务器；服务器重算必须由有凭据的会话/用户执行上面的脚本。

执行节点约定：
- **224（thinklab-105-224）是本 EDA 任务的工作节点**；其他窗口不要抢占。
- 234 仅作备份；225/231 属于 HeurAgenix 复现训练/评测，不要动。
- 如果 224 不可用，先同步文件到 234，再按 RUNBOOK 跑；结论里必须记录实际节点。

## 5. 下一步（按优先级）

1. **服务器 canonical 重算 + dsv4-flash API selector + oracle 敏感性：已完成**（见 `PHASE0_REPORT_0008` §7–9）；3/4 与 oracle 一致，gcd 是 policy-dependent（weighted/TNS-first→density_025，HPWL-first→pad_2，power-first→density_035）；Phase1 selector 建议显式输出 objective mode。
2. **蒸馏数据集 v4 + checkpoint 状态卡 v1 + checkpoint replay v1 原型：已完成**（4 设计/16 候选/4 SFT/POR + 69 条无标签状态卡 + 5 条 gcd replay 标签）；下一步批量 replay（4 设计 × 2 stage × 动作目录，目标 200–1000 条），并接入 checkpoint selector dataset。
3. **旧报告勘误：0003–0005 仅历史**；最终结论以 0008 与 `results/canonical_server/` 为准。
4. **扩展设计/checkpoint**：`checkpoint_replay.py` 已实现 post-GP/post-CTS 续跑并验证；下一步批量 replay + 增加拥塞型/宏密集设计族，把数据从 `flow_start` 扩到多决策点。
5. **verifier L2/L3**：接入 DRC/LVS/STA（Magic/Netgen/OpenSTA）与 hold TNS 提取；当前 hold_tns 普遍缺失。
6. **Phase 1**：按 `10` §11 构建 seed library（30–60 候选 → F0/F1/F2/F3 → K=6–10），再进入演化。
7. **不要做的**：不要用旧报告里的 “WNS” 做 gate/训练标签；不要把 signed WNS/TNS 的百分比变化当主要结论；不要在未同步新 harness 的节点上跑新实验。

## 6. 交接检查清单

- [ ] 已读 `docs/METRIC_CONVENTIONS.md`，能说出 setup WNS 与 hold WNS 的源键。
- [ ] 已确认 `harness/metrics_schema.py` 是新代码唯一口径入口。
- [ ] 已在目标节点同步修复后的 harness。
- [ ] 已用 `migrate_legacy_metrics.py --audit` 检查 setup/hold 字段无 missing。
- [ ] 已用 `recompute_metrics.py` 重算 DEF HPWL/线长/via/power，并核对 power 不再有 1e6 量级错误。
- [ ] 旧口径产物已 `cleanup_legacy.py --apply` 移入 `results/legacy_wrong_metrics/`。
- [x] 服务器 224 canonical 重算/补跑/清理已完成，产物已拉回 `results/canonical_server/`。
- [ ] 已跑 `python3 harness/smoke_test.py`，确认 canonical 口径模块工作正常。
- [ ] 运行 selector 时明确记录：模型、prompt、timing convention、guard bands、软效用。
- [ ] 新报告记录实际执行节点、日期、工具 commit、PDK、WNS 口径。
