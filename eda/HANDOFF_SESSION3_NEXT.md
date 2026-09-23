# HANDOFF_SESSION3_NEXT — EDA 布局布线流程与数学建模创新（会话 3 → 下一会话）

**日期：** 2026-09-22 晚
**定位：** 当前任务的最新接替入口；只读本文件 + 跑两条离线命令，即可接续，不必重读全部历史
**上一版交接：** `NEXT_SESSION_HANDOFF.md`、`HANDOFF.md`（历史状态仍有效，冲突时以本文件 + `results/canonical_server/` 最新产物为准）

## 0. 下一会话第一条命令（直接复制）

```bash
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
python3 harness/smoke_test.py        # 期望 SMOKE_TEST_PASS
python3 harness/session_status.py    # 离线快照：46 个可 replay checkpoint、v2=0
python3 harness/plan_replay_batch.py --design gcd --action-ids control,layeradj_std,grt200 --limit 6 \
  --plan-out results/canonical_server/replay_batch_plan_smoke.jsonl
```

预期：`states_replayable=46`、`planned=6`、`skip_done=0`。若 smoke 不通过或状态数不符，先读 `docs/METRIC_CONVENTIONS.md` 与 `results/canonical_server/README.md`，不要继续远程步骤。

## 1. 任务定位与当前一句话状态

把 HeurAgenix 的“启发式演化 + 在线选择”迁移到 EDA 布局布线（HA-PR）。Phase 0（gcd/aes/jpeg/ibex 全 flow、指标口径两轮修复、服务器 224 canonical 重算）已完成；当前处在 Phase 0 收尾 → Phase 1 前置，**唯一阻塞项是批量 checkpoint replay：把 46 个可 replay checkpoint × 动作目录跑成 200–1000 条 `(state, action, delta)` 标签**。

方法底座：`../09_EDA布局布线_新流程与数学建模_报告v1.md`、`../10_完整数学建模体系_EDA布局布线与测试_v1.md`；实现与数据落点：`harness/`、`results/canonical_server/`。

## 2. 当前权威状态（已完成，不要重做）

| 项 | 状态 / 路径 |
|---|---|
| Phase 0 四设计 | gcd / aes / jpeg / ibex 全 flow 完成 |
| 指标口径 | setup/hold WNS、power、DRC、instance、HPWL 两轮修复；规范 `docs/METRIC_CONVENTIONS.md`；旧报告 0003–0005 作废 |
| 服务器 224 canonical | 21 个旧 run 迁移/重算 + 14 个缺 DEF 候选补跑；权威 `results/canonical_server/`；报告 `PHASE0_REPORT_0008_SERVER_RECOMPUTE.md` |
| 新 oracle | gcd→density_025（weighted/TNS-first，HPWL-first→pad_2、power-first→density_035）；aes→pad_2；jpeg→layeradj；ibex→pad_2 |
| API selector | dsv4-flash 3/4 与 weighted oracle 一致；gcd 为近邻分歧 |
| 蒸馏数据集 | `selector_dataset_v4.*` 已生成；v3 作废 |
| checkpoint 状态卡 | `checkpoint_states_v1.jsonl` 共 69 条；其中 46 条可 replay（post-GP 23 条、post-CTS 23 条） |
| replay 原型 | `checkpoint_replay_v1.jsonl` 5 条 gcd；机制已跑通（报告 0010） |
| 旧产物 | `results/legacy_wrong_metrics/`；禁止引用 |

46 个可 replay checkpoint = 4 设计 × 两阶段，每个 checkpoint 对应一个已有 run 的 DEF 快照。每个 checkpoint 必须先跑 control，动作 delta 只与**同 checkpoint control**配对。

## 3. P0（最高优先）：批量 checkpoint replay

### 3.1 本轮新增/沿用的工具

| 文件 | 用途 |
|---|---|
| `config/replay_actions_v1.json` | 10 个动作（control 优先）；含 design defaults，与默认值重复的动作自动跳过 |
| `harness/plan_replay_batch.py` | 状态卡 + 动作目录 → 可续跑计划；支持 `--limit` / `--design` / `--stages` / `--action-ids` / `--write-script` / `--execute`；默认 dry-run |
| `harness/checkpoint_replay.py` | 单条 replay（已跑通，不改语义） |
| `harness/session_status.py` | 离线盘点标签数、control 覆盖、失败数 |
| `scripts/sync_and_recompute_224.sh` | 新增 `SKIP_RECOMPUTE=1` 轻量同步；rsync 已纳入 `config/` |

本地已验收（2026-09-22）：
- `states_replayable=46`；
- 推荐首轮 6 动作组合 `control,layeradj_std,grt50,grt200,slew0,cap0` 生成 **222 条**任务；
- 全 10 动作生成 **406 条**任务；`--limit` 小样、resume（已存在 run_id 自动跳过）、生成脚本 `bash -n` 均通过。

### 3.2 服务器 224 执行步骤

1. **只读探测**（凭据只从 `_harness/secrets/servers.env` 读取，禁止把密码值写入任何文件、报告或回复）：

```bash
cd /Users/duanzeyu/Desktop/文献
bash _harness/scripts/check_harness.sh --remote
bash _harness/scripts/ssh_run.sh 224 'df -h /data; nvidia-smi -L 2>/dev/null; tmux ls 2>/dev/null || true'
```

2. **同步新文件（不触发重算）**：

```bash
source /Users/duanzeyu/Desktop/文献/_harness/scripts/lib.sh
load_secrets
export SSHPASS="$HEURA_SSH_PASSWORD"    # 只在当前 shell，不落盘
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
SKIP_RECOMPUTE=1 PULL_BACK=0 bash scripts/sync_and_recompute_224.sh
```

3. **远程确认**：

```bash
cd /Users/duanzeyu/Desktop/文献
bash _harness/scripts/ssh_run.sh 224 'cd /data/dzy/heura_repr/eda && export HEURA_EDA_BASE=/data/dzy/heura_repr/eda && python3 harness/session_status.py | head -40'
```

4. **小样 smoke（gcd，4 条，约 1–2 分钟）**，在 224 的 tmux 里：

```bash
tmux new -s hapr_smoke
cd /data/dzy/heura_repr/eda
export HEURA_EDA_BASE=/data/dzy/heura_repr/eda
OUT=results/canonical_server/checkpoint_replay_v2_smoke.jsonl
python3 harness/plan_replay_batch.py --design gcd --stages post_global_place \
  --action-ids control,layeradj_std --limit 4 --out-jsonl "$OUT" \
  --plan-out results/canonical_server/replay_smoke_plan.jsonl
python3 harness/plan_replay_batch.py --design gcd --stages post_global_place \
  --action-ids control,layeradj_std --limit 4 --out-jsonl "$OUT" \
  --plan-out results/canonical_server/replay_smoke_plan.jsonl --execute
grep -c '"gate_ok": true' "$OUT"
```

验收：4 条记录、4 条 `gate_ok=true`；layeradj 相对同 checkpoint control 的 ΔTNS 方向与报告 0010 一致（gcd 为正）。

5. **pilot 测各设计时长（24 条，覆盖 jpeg/aes/ibex 的 post-GP）**：

```bash
python3 harness/plan_replay_batch.py --design jpeg,aes,ibex --stages post_global_place \
  --action-ids control,layeradj_std \
  --out-jsonl results/canonical_server/checkpoint_replay_pilot.jsonl \
  --write-script results/canonical_server/replay_pilot.sh
bash results/canonical_server/replay_pilot.sh
```

6. **首轮全量（推荐 222 条）**，tmux 常驻 + 断点续跑：

```bash
tmux new -s hapr_replay
cd /data/dzy/heura_repr/eda
export HEURA_EDA_BASE=/data/dzy/heura_repr/eda
python3 harness/plan_replay_batch.py \
  --action-ids control,layeradj_std,grt50,grt200,slew0,cap0 \
  --out-jsonl results/canonical_server/checkpoint_replay_v2.jsonl \
  --write-script results/canonical_server/replay_batch_v2.sh
bash results/canonical_server/replay_batch_v2.sh
```

- 重跑同一条命令即续跑：生成脚本按输出 JSONL 里的 `run_id` 跳过已完成项；
- 失败项落到 `results/canonical_server/replay_batch_v2_failures.tsv`；重试前删掉对应失败记录行，再重跑脚本；
- gcd 单条约 16 s（v1 实测）；aes/jpeg/ibex 以 pilot 实测为准，再决定是否把 222 扩到 406（全 10 动作：重跑一次 planner + 脚本即可，已完成项自动跳过）。

7. **回拉 + 验收**：

```bash
source /Users/duanzeyu/Desktop/文献/_harness/scripts/lib.sh
load_secrets
export SSHPASS="$HEURA_SSH_PASSWORD"
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
RSYNC_RSH="sshpass -e ssh -p 224 -o StrictHostKeyChecking=accept-new"
rsync -av -e "$RSYNC_RSH" \
  shiliangliang@202.121.181.105:/data/dzy/heura_repr/eda/results/canonical_server/checkpoint_replay_v2.jsonl \
  results/canonical_server/
python3 harness/session_status.py
```

**验收门（缺一不可）：**
- `session_status.py` 显示 v2 ≥200 条、control 覆盖 46/46 可 replay checkpoint；
- 无重复 run_id；失败率 <5%，失败原因逐条记录；
- 所有动作 delta 均由同 checkpoint control 配对计算；
- 写 `results/PHASE0_REPORT_0011_BATCH_REPLAY_V2.md`，记录节点=224、日期、工具、口径版本、实际条数与失败清单，并更新 `results/canonical_server/README.md`。

### 3.3 已知限制

- replay 恢复与原始 full-flow 有少量状态差（gcd WNS/TNS 差约 0.008 ns / 1.4 ns）；动作效应只用 replay control 配对，不能用 replay 数值替代 full-flow；
- pre-route 时序是 RSZ 估计，只用于排序；最终标签以 post-route DRT 为准；
- power/DRC 只在 post-route 有；hold TNS 目前普遍缺失；
- 224 是 CPU 节点（GPU0 故障），按 CPU 队列顺序跑；目标盘剩余 <50GB 停写；
- 不要 kill 225/231 上的 HeurAgenix 复现任务。

## 4. P1：checkpoint selector 数据集（P0 完成后第一件事）

新建 `harness/build_checkpoint_dataset.py`：
- 输入：`checkpoint_states_v1.jsonl` + `checkpoint_replay_v2.jsonl` + `replay_batch_plan_v2.jsonl`（用 plan 里的 `run_id ↔ checkpoint_run_id / action_id` 映射连接）；
- 每条样本以同 checkpoint 的 control 为基准，计算 Δsetup/hold WNS、ΔTNS、ΔHPWL、Δvias、ΔWL、Δpower、gate 是否通过；
- gate 规则：setup/hold 分别 ≥ control−0.02 ns；control 非负时动作不得转负；DRC 不增；
- 软效用沿用 `HANDOFF.md`：门禁之后 `U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power`；
- 输出：`selector_dataset_v5_checkpoint.jsonl`、SFT/偏好版、`selector_dataset_v5_summary.json`；报告写 `PHASE0_REPORT_0012_CHECKPOINT_DATASET_V5.md`；
- 校验：每条 action 都有匹配 control、无缺失字段、delta 有限、动作去重；写完后跑 `session_status.py` 复点。

## 5. P2：objective mode selector

- 依据 `PHASE0_ORACLE_SENSITIVITY.{json,md}`：gcd 的 oracle 依赖 policy（weighted/TNS-first→density_025、HPWL-first→pad_2、power-first→density_035），aes/jpeg/ibex 稳定；
- 在 `selector_v0.py` 或新模块中显式输出 `objective_mode ∈ {timing_first, HPWL_first, power_first, balanced}`，oracle 按 mode 条件化；
- 评估改为 mode 预测准确率 + 条件 regret + gate 通过率；不再宣称唯一 oracle。

## 6. P3–P5（P0/P1/P2 之后依次推进）

- **P3 设计族/ODB**：向 `phase0.DESIGNS` 增加拥塞型/宏密集设计（如 spm 等），并为 checkpoint 保存 ODB 快照（`write_db`），减少 replay 状态差；
- **P4 signoff**：verifier 接 DRC（KLayout/Magic）、LVS（Netgen）、STA（OpenSTA + SPEF）、hold TNS，形成 L2/L3 门禁；
- **P5 seed library**：按 `../10_完整数学建模体系_EDA布局布线与测试_v1.md` §11，30–60 候选 → F0/F1/F2/F3 多保真筛选 → K=6–10 种子库。

## 7. 口径红线（必须遵守）

| 项 | 规则 |
|---|---|
| setup WNS | `DRT::worst_slack_max`，signed，越大越好 |
| hold WNS | `DRT::worst_slack_min`，signed，越大越好 |
| timing gate | setup/hold 分别 ≥ baseline−0.02 ns；baseline 非负时不得转负 |
| power | OpenLane `power_*_uW` 列实际是 W，不要除以 1e6 |
| DRC | canonical = max(KLayout, Magic)（有 signoff）或 detailed-route 总数，不混加子计数 |
| instance | `instance_count` 用 `synth_cell_count`；`total_cell_count` 单列 |
| HPWL | `hpwl_um`（含端口）为规范；`hpwl_no_ports_um` 对照；`hpwl_origin_um` 仅回归 |
| checkpoint replay | `read_libraries → read_def → read_sdc`，不可先 `link_design` |
| 旧产物 | 不用 0003–0005 的 WNS/HPWL/power/DRC；不用 `selector_dataset_v3` |

## 8. 路径索引（全部为绝对路径）

```text
工作区/交接
  /Users/duanzeyu/Desktop/文献/_harness/README.md
  /Users/duanzeyu/Desktop/文献/heura_repro/NEXT_SESSION_HANDOFF.md
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/NEXT_SESSION_HANDOFF.md
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/HANDOFF.md
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/HANDOFF_SESSION3_NEXT.md   ← 本文件
执行/工具
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/harness/plan_replay_batch.py
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/harness/checkpoint_replay.py
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/harness/session_status.py
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/config/replay_actions_v1.json
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/scripts/sync_and_recompute_224.sh
口径/报告
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/docs/METRIC_CONVENTIONS.md
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/docs/RUNBOOK.md
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/results/canonical_server/README.md
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/results/PHASE0_REPORT_0008_SERVER_RECOMPUTE.md
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/results/PHASE0_REPORT_0009_CHECKPOINT_STATES_v1.md
  /Users/duanzeyu/Desktop/文献/heura_repro/eda/results/PHASE0_REPORT_0010_CHECKPOINT_REPLAY_v1.md
方法
  /Users/duanzeyu/Desktop/文献/heura_repro/09_EDA布局布线_新流程与数学建模_报告v1.md
  /Users/duanzeyu/Desktop/文献/heura_repro/10_完整数学建模体系_EDA布局布线与测试_v1.md
```

## 9. 会话 3 交付清单（本轮）

- 新建 `config/replay_actions_v1.json`：10 个可执行动作 + design defaults 去重规则；
- 新建 `harness/plan_replay_batch.py`：batch replay 规划器（dry-run / filter / limit / resume / write-script / execute），本地已通过编译、dry-run、resume、`bash -n`；
- 新建 `harness/session_status.py`：离线接替状态快照（46 replayable、v2 标签数、control 覆盖、失败数）；
- 本文件 `HANDOFF_SESSION3_NEXT.md`；更新两个 `NEXT_SESSION_HANDOFF.md` 与 `AGENTS.md` 指针；`_harness/CHANGELOG.md` 追加；
- `scripts/sync_and_recompute_224.sh` 新增 `SKIP_RECOMPUTE=1` 轻量同步并纳入 `config/`；
- 未执行远程任务：本轮只做接替指引，未登录 224、未启动 replay。

**已知不完美：**
- 动作目录 v1 仍是启发式子集，未覆盖 timing repair / route ordering / antenna 等下游 skill；
- 全量 406 条的机时未实测，仅 gcd v1 有 16 s/条参考；
- `--execute` 未在 224 上实跑，只在本地做了 dry-run；生成脚本已具备 resume + 失败落盘，但首跑必须走 smoke + pilot。

## 10. 下一会话最小闭环

```bash
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
python3 harness/smoke_test.py
python3 harness/session_status.py
python3 harness/plan_replay_batch.py --design gcd --action-ids control,layeradj_std,grt200 --limit 6 \
  --plan-out results/canonical_server/replay_batch_plan_smoke.jsonl
# 然后按 §3.2：只读探测 → 轻量同步 → tmux smoke → pilot → 222 条首轮 → 回拉 → PHASE0_REPORT_0011
```

**任务继承判定：** 新会话能跑通上述三条命令、说清 46 个可 replay checkpoint 与 control 配对规则、并明确 P0 目标是 222/406 条后，即视为完成继承。
