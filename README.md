# HeurAgenix 复现工作区

- `01_文献阅读报告_HeurAgenix.md`：论文精读报告，含方法流程图、实验设计、数据库/大模型/训练方法、论文与代码差异。
- `02_复现清单_HeurAgenix.md`：可执行清单，含服务器选卡、代码 freeze、数据 curation、Table 5 复现、离线数据构建、GRPO+POR/CPR 训练、Table 3/4/Figure 9 评测、可选 B/C 档。
- `04_EDA迁移与Skill自进化设计建议.md`：把 HeurAgenix 的演化+选择迁移到 EDA 布局布线：契约化 Skill、守卫/回滚、多保真验证、dsv4-flash 选择与演化、skill 成效量化协议、EDA 突破方向与落地路线。
- `05_算法生成与在线筛选备选路线.md`：除 Skill 自进化外的算法生成路线（BO/GP/QD/RL/LLM/自动调度）与在线筛选路线（ISAC/bandit/BO/racing/RL/LLM），以及 EDA 场景下的对比实验矩阵。
- `06_八条算法生成路线详解.md`：对 05 中 8 条算法生成路线逐条详解（定位/类比、最小流程、参数、EDA 落地、适用范围与前置条件、常见坑、验收标准），并附横向对比、学习顺序与术语速查。
- `07_术语概念与学习路线指南.md`：为 05/06 中的英文术语提供零基础说明、类比、最小例子、学习资源链接、20 小时学习计划与中英术语速查表。
- `08_自进化框架突破方向建议.md`：明确不做模型训练主贡献，从流程机制层面提出 8 个突破方向：反事实 credit assignment、多粒度多保真演化、正确性优先契约演化、QD archive/课程、元进化、跨阶段协同、表示共同演化、可复用 benchmark 与协议。
- `09B_一页报告_新流程与数学建模.md`：09 的一页速览版，含四段流程、BMF-CSMDP 四个核心公式、5 条创新点与 H1–H5 实验假设，适合快速拍板。
- `10_完整数学建模体系_EDA布局布线与测试_v1.md`：Phase 0 前数学定稿。六层体系 L0 对象 / L1 阶段物理模型 / L2 质量与测试 / L3 BMF-CSMDP / L4 多保真 / L5 信用学习演化 / L6 统计测试；含 HPWL/密度/MCF/option Bellman/机会约束/LCB/CA-POR+EDA-CPR 完整定义、可声明性质、实现映射与 Phase 0 P0-1..P0-11 测试设计。 §11 追加种子启发式发现/筛选/组库（六类来源 + 多保真筛选 + 覆盖/多样性 + Phase 0 具体参数）。
- `10B_数学建模一页速览.md`：10 的一页速览版。
- `eda/`：Phase 0 布局布线 harness（OpenROAD 2022 + sky130hd；工作节点 224，其他窗口勿抢占；234 备份）。已完成 WNS/power/DRC/instance/HPWL 两轮口径审计、gcd/aes/jpeg/ibex 四设计、L0/L1 verifier、selector/stats、数据集 v4。**2026-09-22 已在 224 完成 canonical 重算与 14 个缺 DEF 候选补跑**，权威结果 `eda/results/canonical_server/`，报告 `eda/results/PHASE0_REPORT_0008_SERVER_RECOMPUTE.md`；旧口径与本地 pre-server 产物在 `eda/results/legacy_wrong_metrics/`。接管入口：`eda/HANDOFF.md`、`eda/docs/METRIC_CONVENTIONS.md`、`eda/docs/RUNBOOK.md`。
- 配套图：`../_bilingual/diagram/eda_math_model.pdf`（A1）：六层模型 × 阶段公式 × 测试协议三合一。
- `09_EDA布局布线_新流程与数学建模_报告v1.md`：面向 EDA 布局布线的新流程清单（Phase O 离线准备 / R 在线执行 / E 门控演化 / D 部署蒸馏）+ 新数学建模 BMF-CSMDP（契约化 option 半 MDP、预算约束、多保真 LCB、跨阶段势函数/反事实信用、CA-POR + EDA-CPR），并给出实验假设与 Phase 0 MVP 建议。
- 配套图：`../_bilingual/diagram/eda_pr_flow.pdf`（A1 一张）：新流程 × 阶段图与门禁 × 核心公式三合一。
- `19_补充报告_最新对话增量_v1.md`：2026-09-23 09:33 最新对话增量——2h 口径、TSP 测试集实为 13 实例、Figure8 9 个干净实例 avg 4.601%（gr666/pr1002/pr2392 停跑、pcb442 timeout 排除）、B 档三 seed reasoning 收口、P1A 失败原因、论文 vs 复现差距表、当前任务快照与 TODO。
- `evidence/paper_facts.json`：核对过的事实：commit hash、训练超参、split、参考 upper_bound、seed/eval 对照表。
- 本地参考文本：`../heuragenix_en.md`、`../heuragenix_bi.md`。
- 本地数据/代码侦察副本：`/tmp/heura_data`（HF 数据）、`/tmp/heura_check`（GitHub 完整历史 clone）。
- 原 PDF：`../自进化算法相关/2/2506.15196v2.pdf`；中英对照 PDF：`../_bilingual/out/heuragenix_中英对照.pdf`。

**当前状态：** HeurAgenix 复现按 A 档推进（服务器 225、项目 `/data/dzy/heura_repr`）；mathematical modeling 10/10B + A1 图已交付；EDA Phase 0 已完成 gcd/aes/jpeg/ibex 四设计、WNS/power/DRC/instance/HPWL 口径修复，并已在服务器 224 完成 canonical 重算/补跑/清理；权威结果 `eda/results/canonical_server/` 与 `eda/results/PHASE0_REPORT_0008_SERVER_RECOMPUTE.md`，新 oracle 为 gcd→density_025、aes→pad_2、jpeg→layeradj、ibex→pad_2，数据集 v4 已生成。下一步：canonical API selector（dsv4-flash）、扩设计/checkpoint、L2/L3 signoff；详见 `eda/HANDOFF.md`。
