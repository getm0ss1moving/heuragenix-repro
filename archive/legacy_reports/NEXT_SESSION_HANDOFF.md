# NEXT SESSION HANDOFF — heura_repro 项目级入口

> **会话 4 接替入口（2026-09-23）：** EDA 线程请先读 `eda/HANDOFF_SESSION4_NEXT.md`（P0 222 条 replay + P1 数据集 v5 已完成验收）；会话 3 计划见 `eda/HANDOFF_SESSION3_NEXT.md`；本文件为线程总览。

**日期：** 2026-09-22 晚  
**用途：** 新对话/新窗口先读本文件，再按线程进入对应详细交接，避免重读全部历史。

---

## 0. 项目线程总览

`heura_repro/` 当前有两条并行线程：

| 线程 | 目标 | 当前状态 | 详细入口 |
|---|---|---|---|
| **EDA 线程** | HeurAgenix → EDA 布局布线（HA-PR） | Phase 0 完成；服务器 224 canonical 重算/API selector/sensitivity/checkpoint replay 原型完成；准备批量 checkpoint replay | `eda/NEXT_SESSION_HANDOFF.md` |
| **HeurAgenix 复现线程** | 复现 arXiv:2506.15196v2（Table3/4/5、Fig9、A/B 档） | A 档 k=0 39/39 完成；Table5 完成；B 档三 seed reasoning 收口；Figure8 DeepSeek 替代版 9 个干净实例报告完成（gr666/pr1002/pr2392 停跑，pcb442 timeout 排除）；231 k10 部分完成（需重标口径） | `11`、`13`、`14`、`19_补充报告_最新对话增量_v1.md`；服务器项目 `/data/dzy/heura_repr`（主要用 225，评测用 231） |

---

## 1. 新会话读文件顺序

1. 本文件
2. `eda/NEXT_SESSION_HANDOFF.md`（EDA 执行指引）
3. `eda/docs/METRIC_CONVENTIONS.md`（WNS/power/DRC/HPWL 口径）
4. `eda/docs/RUNBOOK.md`（命令）
5. 复现线程：`11`、`13`、`14` 与 `01/02/03` 报告
6. 方法：`09/09B`、`10/10B` 与 `_bilingual/diagram/` 图

---

## 2. EDA 线程：当前权威状态

- 四设计 gcd/aes/jpeg/ibex 全 flow 完成；两轮指标口径修复完成。
- 服务器 224 canonical 重算：21 旧 run 迁移/重算 + 14 缺 DEF 候选补跑；HPWL 新解析与 OpenROAD DPL 偏差 ≤0.32%。
- 权威结果：`eda/results/canonical_server/`
  - `{gcd,aes,jpeg,ibex}_candidates.json`
  - `PHASE0_STATS_4designs_server.{json,md}`
  - `PHASE0_SELECTOR_4designs_server.{json,md}`（无 API）与 `..._server_api.{json,md}`（dsv4-flash）
  - `PHASE0_ORACLE_SENSITIVITY.{json,md}`
  - `selector_dataset_v4.*`
  - `checkpoint_states_v1.jsonl`（69 条无标签状态卡）
  - `checkpoint_replay_v1.jsonl`（5 条 gcd replay 标签）
- 新 oracle 依赖 objective mode：gcd weighted/TNS-first→density_025、HPWL-first→pad_2、power-first→density_035；aes→pad_2、jpeg→layeradj、ibex→pad_2。
- 旧报告 0003–0005 的 WNS/HPWL/power/DRC 数字作废；旧产物在 `eda/results/legacy_wrong_metrics/`。

### EDA 下一步（执行细节见 `eda/NEXT_SESSION_HANDOFF.md`）

1. 批量 checkpoint replay：4 设计 × {post_global_place, post_cts} × 动作目录，目标 200–1000 条标签，输出 `checkpoint_replay_v2.jsonl`。
2. 新建 `harness/build_checkpoint_dataset.py`：状态卡 + replay 标签 → checkpoint selector 数据集。
3. selector 显式支持 `objective_mode`；oracle 按 mode 条件化。
4. 扩设计族/保存 ODB checkpoint；接 L2/L3 signoff（DRC/LVS/STA）与 hold TNS。
5. 按 `10` §11 构建 Phase 1 seed library。

---

## 3. HeurAgenix 复现线程：当前状态

- A 档无 API：
  - Table5：354 run 已落盘；pr152 逐项一致；JSSP/MKP/MaxCut 大部分吻合；TSP farthest/CVRP 需区分“可复现代码口径 vs 论文表格口径”。
  - k=0 评测：3 选择器 × 13 TSPLIB 实例 39/39 完成（`doc13`、`k0_combined.csv`），平均 gap dual 12.287 / vanilla 13.098 / raw 13.787，与论文 k=10 口径不可直接对比。
  - TTS stop 口径已诊断（`doc14`）：completion 在完整解 0 步是 kroB200 36.24 的根因；fixed2n/improvement 对照。
- B 档：DeepSeek reasoning 三 seed 已收口：nearest 4.134 / cheapest 6.090 / farthest 8.039（n=8），均不差于 released evolved；属方向性优势。
- 231 评测节点：k10 completion 口径 24/24 已完成（需重标或重跑）；P1A 论文口径 Table4 v2 运行中（09:22 启动，raw 3/8，watcher 25025）；farthest eval 已完成。
- 待办：P1A v2 完成后回拉/汇总；doc15/17/18 最终回填已完成；如需显著性再做重复实验；整理 Table5 口径差异。

**服务器路径：** `/data/dzy/heura_repr/`（主节点 225；231 为第二评测节点）。详细命令和日志见 `11/13/14` 文档与项目记忆。

---

## 4. 环境与安全约定

| 项 | 约定 |
|---|---|
| EDA 工作节点 | 224（thinklab-105-224）；其他窗口勿抢占 |
| HeurAgenix 复现 | 225 为主；231 为评测；234 备份 |
| 认证 | 密码不落盘；AI 直连需用户临时提供凭据或用 `export SSHPASS=...` + `sshpass -e`；更安全是配公钥 |
| EDA 同步脚本 | `eda/scripts/sync_and_recompute_224.sh`（支持 SSHPASS，含结果回拉） |
| 远程脚本 | 必须绝对路径；长任务用 tmux + 日志轮询 |
| 旧产物 | 不要引用 0003–0005 的 WNS/HPWL/power/DRC；不要用 `selector_dataset_v3` |

---

## 5. 关键路径索引（本地）

```text
heura_repro/
  01_文献阅读报告_HeurAgenix.md
  02_复现清单_HeurAgenix.md
  03_执行决策记录_20260920.md
  04–08 EDA 迁移机制设计
  09/09B HA-PR 新流程与数学建模
  10/10B 完整数学建模体系
  11 评测协议与偏差记录
  12 Table5 结果汇总
  13 Table3/4 k0 口径报告
  14 TTS stop 口径诊断
  NEXT_SESSION_HANDOFF.md          # 本文件
  eda/
    NEXT_SESSION_HANDOFF.md        # EDA 详细执行指引（新会话先读）
    HANDOFF.md                     # EDA 详细状态与历史
    docs/METRIC_CONVENTIONS.md
    docs/RUNBOOK.md
    harness/                       # 控制面代码
    scripts/                       # 同步与批量脚本
    results/canonical_server/      # EDA 权威结果
    results/legacy_wrong_metrics/  # 旧口径产物（禁止使用）
    runs/                          # 回拉的关键 run 记录
```

---

## 6. 新会话建议的第一条命令

```bash
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
python3 harness/smoke_test.py
cat NEXT_SESSION_HANDOFF.md
```

如果继续 EDA，按 `eda/NEXT_SESSION_HANDOFF.md` §2 的 P0（批量 checkpoint replay）执行；如果继续复现，先看 `11/13/14` 与服务器 `results/eval_full` 最新状态，再决定 Table3/4 v2 与 Figure9。

---

## 7. 会话 5 更新（2026-09-23 09:00）

**先读 `19_补充报告_最新对话增量_v1.md`**（本轮增量：2h 口径、TSP 13 实例、Figure8 9 个干净实例 avg 4.601%、B 档三 seed 收口、P1A 失败原因、论文 vs 复现差距表）。

### 复现线程最新状态
- **Figure8 TSP 最终按 9 个干净实例报告，逐实例 avg gap 4.601%（n=9）**（论文 HeurAgenix 0.50）；gr666/pr1002/pr2392 已按用户指令停跑，pcb442 因 7500s timeout 排除；产物 `results/fig8_tsp_225/Figure8_TSP_report.md`、`Figure8_TSP_9instances.csv`、`summary_9instances.json`，本地 `evidence/fig8_tsp_225/`。
- **B 档 reasoning 三 seed 全部完成**：nearest 4.134 / cheapest 6.090 / farthest 8.039，均不差于 released evolved（8.747 / 9.307 / 8.283）。
- **P1A 论文口径 Table4 v2 已在 231 GPU2 启动**：09:22 起跑，09:54 raw 3/8（kroC100、kroA100、kroB100 已落 parts，当前 raw bier127）；watcher PID 25025，完成后自动生成 `table4_p1a_summary.csv`。首跑失败日志已归档到 `paper_table4_231/logs/failed_first_run_20260923_0839/`；现场说明见 `results/231_STATUS.md` 与 `paper_table4_231/README_STATUS.md`。
- **farthest eval 已完成**：`released 8.283 / chat 9.361 / reasoning 8.039（n=8）`，verdict=reasoning_better_than_released；本地 evidence/ 已有 `b_reason_farthest_final.json` 与 `b_reason_farthest_eval.csv`。

### 命令入口（只读探测）
```bash
bash _harness/scripts/ssh_run.sh 225 "tmux ls; ls -lt /data/dzy/heura_repr/results/fig8_tsp_225/ | head"
bash _harness/scripts/ssh_run.sh 231 "nvidia-smi --query-gpu=index,memory.free --format=csv; ls -lt /data/dzy/heura_repr/results/paper_table4_231/parts/ | head"
```
