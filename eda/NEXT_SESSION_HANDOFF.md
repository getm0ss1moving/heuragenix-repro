# NEXT SESSION HANDOFF — HA-PR EDA（EDA 线程详细执行指引）

> **会话 4 最终接替入口（2026-09-23）：** 先读 `HANDOFF_SESSION4_NEXT.md`（P0 222 条 replay + P1 数据集 v5 已完成验收，含 P2–P5 下一步）；会话 3 计划见 `HANDOFF_SESSION3_NEXT.md`，本文件保留详细历史状态。

**日期：** 2026-09-22 晚  
**适用对象：** 下一个接手 EDA 线程的对话/窗口  
**一句话任务：** 把 HeurAgenix 的“演化 + 在线选择”迁移到 EDA 布局布线（HA-PR）；Phase 0 已完成，当前进入 Phase 1 前置——checkpoint replay 生成标签、checkpoint selector 数据与 objective mode。

---

## 0. 新会话的第一步

按顺序读：

1. 本文件 `eda/NEXT_SESSION_HANDOFF.md`
2. `eda/docs/METRIC_CONVENTIONS.md`（指标口径，必须遵守）
3. `eda/docs/RUNBOOK.md`（运行/同步/重算命令）
4. `eda/results/PHASE0_REPORT_0008_SERVER_RECOMPUTE.md`、`0009_CHECKPOINT_STATES_v1.md`、`0010_CHECKPOINT_REPLAY_v1.md`
5. `../10_完整数学建模体系_EDA布局布线与测试_v1.md`（方法与 Phase 0 P0-1..P0-11）

快速自检：

```bash
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
python3 harness/smoke_test.py      # 期望 SMOKE_TEST_PASS
```

---

## 1. 已完成、不要重做

- Phase 0：gcd / aes / jpeg / ibex 四设计全 flow、pin-offset HPWL、L0/L1 verifier、selector/stats。
- 两轮指标口径修复：WNS setup/hold、power 单位、DRC 去重、instance_count、HPWL 解析（含 `( PIN port )`/换行 pin）。
- 服务器 224 canonical 重算：21 个旧 run 迁移/重算 + 14 个缺 DEF 候选补跑；HPWL 新解析与 OpenROAD DPL 偏差 ≤0.32%。
- dsv4-flash API selector：aes/jpeg/ibex 与 weighted oracle 一致；gcd 为近邻分歧。
- oracle 敏感性分析：gcd 依赖 objective mode；aes/jpeg/ibex 稳定。
- checkpoint 状态卡 v1：69 条（4 设计 × post-GP/post-CTS/post-route，无标签）。
- checkpoint replay v1 原型：5 条 gcd 标签（post-GP/post-CTS，base 与 layeradj），机制已跑通。
- 旧口径产物已归档到 `results/legacy_wrong_metrics/`；`selector_dataset_v3` 废弃。

**权威结果目录：** `eda/results/canonical_server/`

---

## 2. 下一步任务（按优先级）

### P0：批量 checkpoint replay，目标 200–1000 条标签

> 批量执行已就绪：用 `harness/plan_replay_batch.py` 生成 222 条首轮 / 406 条全量、可续跑计划；步骤与验收门见 `HANDOFF_SESSION3_NEXT.md` §3。

**机制：** `harness/checkpoint_replay.py`

```text
read_libraries → read_def(<checkpoint>.def) → read_sdc
→ 续跑 post_global_place / post_cts 之后剩余 flow
→ 注入 downstream action（layer adjustment / congestion / slew/cap margin 等）
→ 记录最终 canonical 指标
```

**baseline checkpoint 路径（服务器 `/data/dzy/heura_repr/eda` 下）：**

| design | post_global_place DEF | post_cts DEF |
|---|---|---|
| gcd | `runs/phase0_sweep_0002_base/results/gcd_sky130hd_global_place.def` | `runs/phase0_sweep_0002_base/results/gcd_sky130hd_cts.def` |
| aes | `runs/aes_baseline_0001/results/aes_sky130hd_global_place.def` | `runs/aes_baseline_0001/results/aes_sky130hd_cts.def` |
| jpeg | `runs/jpeg_baseline_0001/results/jpeg_sky130hd_global_place.def` | `runs/jpeg_baseline_0001/results/jpeg_sky130hd_cts.def` |
| ibex | `runs/ibex_baseline_0001/results/ibex_sky130hd_global_place.def` | `runs/ibex_baseline_0001/results/ibex_sky130hd_cts.def` |

**动作目录（示例，后续可扩）：**

```json
{"global_routing_layer_adjustments": [["met1",0.4],["met2",0.4],["met3",0.3],["met4",0.3],["met5",0.2]]}
{"global_route_congestion_iterations": 50}
{"global_route_congestion_iterations": 200}
{"slew_margin": 0}
{"slew_margin": 20}
{"cap_margin": 0}
```

**单条命令模板：**

```bash
cd /data/dzy/heura_repr/eda
export HEURA_EDA_BASE=/data/dzy/heura_repr/eda
python3 harness/checkpoint_replay.py \
  --design gcd --stage post_global_place \
  --checkpoint-def runs/phase0_sweep_0002_base/results/gcd_sky130hd_global_place.def \
  --run-id replay_gcd_pgp_base \
  --action '{}' \
  --out-jsonl results/canonical_server/checkpoint_replay_v2.jsonl
```

**批量要求：**
- 每个 `(design, stage)` 先跑一条 replay baseline（`--action '{}'`），动作效应与它配对比较。
- 用 tmux 后台顺序跑 + `nice 10`；脚本路径用绝对路径；产物轮询。
- 目标 200–1000 条；以 4 设计 × 2 stage × 8–15 动作作为第一轮。
- 跑完 `rsync` 回本地 `results/canonical_server/checkpoint_replay_v2.jsonl`。

**重要校准：** replay baseline 与原始 full-flow baseline 有少量状态差（gcd WNS/TNS 差约 0.008 ns / 1.4 ns）；**动作 delta 只能用同 stage replay baseline 配对**，不要直接替代 full-flow 数值。

### P1：构建 checkpoint selector 数据集（新脚本）

建议新文件：`harness/build_checkpoint_dataset.py`

- 输入：`checkpoint_states_v1.jsonl` + `checkpoint_replay_v2.jsonl`
- 每个 `(design, stage)` 以 replay baseline 为 control，计算动作的 Δsetup/hold WNS、ΔTNS、ΔHPWL、Δvias、ΔWL、Δpower、gate_safe。
- 输出：`results/canonical_server/selector_dataset_v5_checkpoint.jsonl` + SFT/偏好版。
- 注意：pre-route timing 是 RSZ 估计，仅用于排序；最终标签以 post-route DRT 为准。

### P2：objective mode selector

- 已有 `PHASE0_ORACLE_SENSITIVITY.{json,md}`：gcd 是 policy-dependent。
- 扩展 `selector_v0.py` 或新增 selector：prompt 显式要求输出 `objective_mode`（timing_first / HPWL_first / power_first / balanced），oracle 按 mode 条件化。
- 评估指标：mode 预测准确率 + 条件 regret；不再宣称唯一 oracle。

### P3：扩展设计族 / 保存 ODB checkpoint

- 当前只有 gcd/aes/jpeg/ibex；需要拥塞型、宏密集设计族。
- 可在 224 添加 OpenLane 中其他设计（如 spm 等）到 `phase0.DESIGNS` 与 `flow/`。
- 为减少 replay 状态差，建议后续阶段保存 ODB 快照（不只 DEF）；`phase0.py` 里可扩展 `write_db`。

### P4：L2/L3 signoff

- 现状 verifier 只有 L0/L1（overlap/row/boundary/net/fixed/netlist hash）。
- 需接 DRC（Magic/KLayout）、LVS（Netgen）、STA（OpenSTA + SPEF）、hold TNS。
- 当前 hold_tns 普遍缺失；post-route DRT 已有 setup WNS/TNS。

### P5：Phase 1 seed library

按 `10` §11：30–60 候选 → F0/F1/F2/F3 多保真筛选 → 覆盖/多样性/可演化性 → K=6–10 种子库。

---

## 3. 服务器与环境

| 项 | 值/路径 |
|---|---|
| 本地代码镜像 | `/Users/duanzeyu/Desktop/文献/heura_repro/eda` |
| 服务器 EDA 工作目录 | `/data/dzy/heura_repr/eda` |
| 工作节点 | 224（thinklab-105-224）；234 备份；225/231 是 HeurAgenix 复现，不要动 |
| 工具 | OpenROAD 2022（`tools/openroad/bin/openroad`）、sky130hd flow |
| 认证 | 密码不落盘；支持 `export SSHPASS=...` + `sshpass -e`，或 `ssh-copy-id` 配公钥 |
| 同步/重算脚本 | `scripts/sync_and_recompute_224.sh`（支持 SSHPASS，含回拉） |

同步示例：

```bash
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
export SSHPASS='...'    # 不要写入文件
bash scripts/sync_and_recompute_224.sh
```

常用 remote 命令：

```bash
sshpass -e ssh -p 224 shiliangliang@202.121.181.105 \
  "cd /data/dzy/heura_repr/eda && export HEURA_EDA_BASE=/data/dzy/heura_repr/eda && \
   python3 harness/smoke_test.py && \
   python3 harness/checkpoint_replay.py --help"
```

---

## 4. 口径与坑（必须遵守）

| 项 | 规则 |
|---|---|
| setup WNS | `DRT::worst_slack_max`，signed，越大越好；≥0 满足 |
| hold WNS | `DRT::worst_slack_min`，signed，越大越好；≥0 满足 |
| timing gate | setup/hold 分别 ≥ baseline−0.02 ns；baseline 非负时不得转负 |
| power | OpenLane `power_*_uW` 列实际是 W；不要除以 1e6 |
| DRC | canonical = max(KLayout, Magic)（有 signoff）或 detailed-route 总数；不要把子计数与总数混加 |
| instance | `instance_count` 用 `synth_cell_count`（逻辑单元），`total_cell_count` 单列 |
| HPWL | 三口径：`hpwl_um`（含端口，规范）、`hpwl_no_ports_um`（对照 OpenLane global）、`hpwl_origin_um`（旧回归） |
| checkpoint replay | `read_libraries → read_def → read_sdc`；**不可先 link_design**（Chip already exists） |
| replay 对比 | 动作效应必须与同 stage replay baseline 配对；replay 与 full-flow 有状态差 |
| 旧产物 | 不要用 `PHASE0_REPORT_0003–0005` 的 WNS/HPWL/power/DRC；`selector_dataset_v3` 已废弃 |

---

## 5. 关键文件索引

| 用途 | 路径 |
|---|---|
| EDA 详细状态 | `eda/HANDOFF.md` |
| 指标口径 | `eda/docs/METRIC_CONVENTIONS.md` |
| 运行手册 | `eda/docs/RUNBOOK.md` |
| checkpoint replay | `eda/harness/checkpoint_replay.py` |
| checkpoint 状态卡 | `eda/harness/checkpoint_states.py` |
| oracle 敏感性 | `eda/harness/oracle_sensitivity.py` |
| WNS/TNS 口径模块 | `eda/harness/metrics_schema.py` |
| OpenLane 指标规则 | `eda/harness/metric_rules.py` |
| selector | `eda/harness/selector_v0.py` |
| 旧数据迁移/重算/清理 | `eda/harness/migrate_legacy_metrics.py`、`recompute_metrics.py`、`cleanup_legacy.py` |
| 离线自检 | `eda/harness/smoke_test.py` |
| 服务器同步 | `eda/scripts/sync_and_recompute_224.sh` |
| 权威结果 | `eda/results/canonical_server/` |
| 阶段报告 | `eda/results/PHASE0_REPORT_0008/0009/0010*.md` |
| 数学建模方法 | `10_完整数学建模体系_EDA布局布线与测试_v1.md` |
| 新流程报告 | `09_EDA布局布线_新流程与数学建模_报告v1.md`、`09B_...md` |

---

## 6. 新会话建议的第一条实际动作

1. `python3 harness/smoke_test.py` 确认口径模块正常。
2. 看 `results/PHASE0_REPORT_0010_CHECKPOINT_REPLAY_v1.md`，再决定批量 replay 的动作目录。
3. 用 `scripts/sync_and_recompute_224.sh` 同步最新 harness（如本地有改动）。
4. 在 224 上用 tmux 启动批量 replay，目标 `checkpoint_replay_v2.jsonl`。
5. 批量完成后写 `build_checkpoint_dataset.py`，接 P1/P2。
