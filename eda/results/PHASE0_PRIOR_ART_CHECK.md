# PHASE0 PRIOR ART CHECK — checkpoint selector / composite action 查重

**日期：** 2026-09-23  **执行：** 本地 macOS，arXiv API + Crossref + OpenAlex（DBLP / Semantic Scholar 限流未完成）
**目的：** 在投入 composite-action PoC 之前，确认「checkpoint 级决策 / stage-aware flow tuning / gate-aware 多目标 selector / layeradj 时序预算换 HPWL」是否已有他人成果。
**原始命中：** `results/prior_art/arxiv_round1.json`、`arxiv_round2.json`、`arxiv_key_abstracts.json`

---

## 1. 结论（先行）

**重叠率高，建议不把 composite-action PoC 当作新颖性实验。** 我们的高层框架已经被 2025–2026 年多篇工作覆盖：

- **stage-aware + checkpoint 复用 + 阶段局部决策 + post-route 评估** → AgenticPD (2026) 基本完整覆盖；
- **stateful / evidence-gated / runtime-aware 的 LLM flow tuning** → StateTune (2026) 覆盖；
- **LLM 迭代调 OpenROAD/ASAP7/SKY130HD flow 参数并对比 BO** → ORFS-agent (2025) 覆盖；
- **多目标/mode-first tuning（power-first、非支配排序、无人工权重）** → POET (2026) + preference-conditioned MORL 系列覆盖；
- **timing 约束下的 ECO/repair 组合优化（含 Pareto 与最小扰动）** → IR-Aware ECO Timing RL (2024) 及 ISPD/ICCAD 大量 timing-driven optimization 工作覆盖。

按你的规则「重复率高则不需要再进行这个实验」——**composite-action PoC 可以不做**（若要用于内部标签质量改进，只能定位为工程验证，不构成方法创新）。

## 2. 候选点 vs 最接近工作

| 我们的候选点 | 最接近工作 | 重叠度 | 判断 |
|---|---|---|---|
| checkpoint replay + stage-aware 动作选择 + 阶段局部 agent | **AgenticPD** arXiv:2607.04758 (2026)：stage-aware agentic PD QoR，Judge Agent + 阶段专家 agent，复用 intermediate checkpoints 从先前状态分支，post-route signoff 评估 | **高** | 高层框架已被覆盖 |
| stateful/evidence-gated/runtime-aware 的 flow tuning | **StateTune** arXiv:2608.23601 (2026)：typed persistent optimization memory、evidence-gated、EHVI-guided runtime-aware promotion、Cadence 工业 flow | **高** | 思想已被覆盖 |
| LLM 迭代调 EDA flow 参数 | **ORFS-agent** arXiv:2506.08332 (2025)：LLM agent 调 ORFS；ASAP7/SKY130HD；比 BO 省 40% 迭代；wirelength/clock period/co-opt 改善 | **高** | 选型器思路已被覆盖 |
| composite action（ECO/repair + placement/route 联合，时序约束预算） | **IR-Aware ECO Timing RL** arXiv:2402.07781 (2024)：RL+拉格朗日松弛做 gate sizing ECO，delay-power Pareto，最小化 placement 扰动；以及大量 timing-driven placement / layer assignment 工作 | **中-高** | 组合优化 + ECO 是成熟方向 |
| objective-mode conditioned oracle（mode-first PPA） | **POET** arXiv:2603.19333 (2026)：power-first LLM 进化调优，非支配排序+层级内 power 优先，无需手调权重；**preference-conditioned MORL** 2026 多篇 | **中** | 方法族已存在，EDA 实例化属增量 |
| gate-first（WNS 仅作 hard guard）+ 多目标 selector | 约束 MDP / safe RL / timing-driven optimization 文献；项目内 09/10 文档已引用 Altman 1999 等 | **中** | 常规受限优化，不是新方法 |
| checkpoint 级 paired `(state, action, Δmetric)` 数据集 + 可复现开源 harness | 未检索到完全同名工作；但 AgenticPD 的 checkpoint 分支机制接近 | **中/低** | 可作为 benchmark/评测协议贡献，需全文查重后再定 |

## 3. 关键工作摘要（原文摘录）

- **AgenticPD (2607.04758)**：“…Instead of re-running the full flow after every trial, AgenticPD is organized around the stage boundaries of the physical design flow, where a Judge Agent navigates the search and stage-specialized agents make local decisions within their own stage using stage-local tools… the system can branch from prior intermediate states and reuse checkpoints to continue the optimization procedure, and every candidate is evaluated at the post-route signoff.”
- **StateTune (2608.23601)**：“…reformulates LLM-assisted EDA tuning as a closed-loop, state-carrying process. Its optimizer state is a typed, evidence-gated persistent optimization memory… an EHVI-guided, runtime-aware promotion policy ranks quick-stage candidates… Evaluated on a Cadence industrial flow…”
- **ORFS-agent (2506.08332)**：“…LLM-based iterative optimization agent that automates parameter tuning in an open-source hardware design flow… improvements over standard Bayesian optimization… up to 1.0%/1.3%/2.7%… using 40% fewer iterations.”
- **IR-Aware ECO Timing RL (2402.07781)**：“…integrates IR-drop-aware timing analysis and ECO timing optimization using RL… gate sizing… moves the Pareto front of the delay-power tradeoff… reduces perturbation to placement.”
- **POET (2603.19333)**：“…LLM-driven evolutionary mechanism with non-dominated sorting, power-first intra-level ranking, and proportional survivor selection to steer the search toward the low-power region of the Pareto front without manual weight tuning.”
- **Preference-conditioned MORL（2026 多篇）**：把 preference/mode 作为策略条件训练，覆盖 Pareto 前沿——与 objective_mode selector 同族。

## 4. 残余可能的新颖点（需全文精读确认）

1. **checkpoint 粒度的配对标签协议**：从 post-GP/post-CTS DEF replay，同 checkpoint control 配对，canonical setup/hold gate，产出可训练的 `(state, action, ΔHPWL/WL/via/TNS/power)` 数据集；AgenticPD 有 checkpoint 分支但没有强调配对标签/数据集。
2. **objective-mode 条件化 + gate-first 的 EDA oracle 评估协议**（mode 预测准确率、条件 regret、gate 通过率）——方法族已有，EDA 实例化可能只是增量。
3. **可复现开源 harness**（OpenROAD 224、固定 freeze、失败重试、报告自动化）——工程/benchmark 价值，而非算法创新。

## 5. 建议

- **不启动 composite-action PoC 作为研究实验**；若为了标签质量仍要做，定位为工程验证。
- 若目标是对外论文/方法章：先做一次**系统全文查重**（DBLP/Scopus + DAC/ICCAD/TCAD/ISPD/ASPDAC 近 5 年），重点看 AgenticPD、StateTune、ORFS-agent、ChatEDA 系列的 related work，再决定做「复现对比」还是寻找真空。
- 项目可转的策略：把 HA-PR 定位为 **open reproducible checkpoint-level benchmark + gate-aware/objective-mode 评测协议**，用现有方法（stage-aware search / preference-conditioned selector）作 baseline，而不是新算法。

## 6. 检索记录与局限

- arXiv 查询：flow tuning physical design、hyper-heuristic EDA、LLM physical design、checkpoint RL design flow、multi-objective PPA、Bayesian optimization EDA、preference/mode-conditioned RL、ECO ML、OpenROAD tuning 等 20+ 条。
- Crossref：flow tuning OpenROAD、hyper-heuristic EDA、timing guardband optimization、checkpoint chip design 等 6 条；命中 METRICS2.1/Flow Tuning (ICCAD 2021)、OpenROAD-Assistant (MLCAD 2024) 等。
- OpenAlex：LLM EDA flow tuning 命中 ChatEDA (TCAD 2024)、ChipNeMo 等。
- **局限**：DBLP API 持续 429/500、Semantic Scholar 429 未完成；Crossref/OpenAlex 对工程会议覆盖有限；以上均为标题/摘要级判断，尚未做全文精读与引用网络追溯。
