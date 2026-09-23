# 从 HeurAgenix 到 EDA 布局布线：新流程清单与数学建模报告（v1.0）

**日期：** 2026-09-21  
**依据文献：** Wang et al., *HeurAgenix: Leveraging LLMs for Solving Complex Combinatorial Optimization Challenges*，arXiv:2506.15196v2（§2.1、§3.1–3.3、Eq.(1)、Algorithm 1、TTS、POR/CPR）。  
**配套材料：** `01_文献阅读报告_HeurAgenix.md`（原文公式逐条转写）、`04_EDA迁移与Skill自进化设计建议.md`（契约化 skill / 守卫 / 多保真）、`05–08`（算法生成路线与突破方向）。  
**关系说明：** `04–08` 解决"机制层面怎么迁移"；本文解决"**EDA 布局布线版的新流程长什么样、数学上如何统一建模、如何证明每一步的提升逻辑**"。数学建模**不是另起炉灶**，而是把 HeurAgenix 的 Eq.(1)（V/Q/π*）、Algorithm 1（演化）、POR/CPR（选择器训练）改造成适配 EDA 的版本，并明确标出哪些是原式转写、哪些是 EDA 新增。

> **更新（2026-09-21）：** 完整、严格的数学规格已单独立稿为 `10_完整数学建模体系_EDA布局布线与测试_v1.md`（含布局/布线/signoff 物理模型、测试统计协议、Phase 0 P0-1..P0-11）。本文与 10 如有冲突，以 10 为准；本文保留为迁移流程与核心公式的导览。

---

## 0. 一页速览（TL;DR）

**框架名：HA-PR（HeurAgenix for Placement & Routing）——面向布局布线的契约化层次超启发式框架。**

**一句话：** 把 HeurAgenix 的"启发式池 + 单层在线选择 + 廉价 rollout"，升级成"**阶段图上的契约化 option 半 MDP + 多保真预算分配 + 跨阶段信用分配 + 双层自进化**"；LLM 只做状态理解、阶段/技能选择与技能演化，几何和正确性交给工具、代理模型与验证器。

**新流程清单（四段式）：**

| 段 | 名称 | 做什么 | 关键产物 |
|---|---|---|---|
| **O** | 离线准备（Offline） | 建 checkpoint、状态卡、技能卡、验证栈、代理模型、经验库 | 可复现的 harness + 初始 skill 库 |
| **R** | 在线执行（Runtime） | 在阶段图上做预算约束的 option 选择；契约 shield 执行；回滚/fallback | flow 轨迹 + PPA + 每次决策记录 |
| **E** | 自进化（Evolution） | 反事实定位关键决策 → LLM 提出 skill 变异 → 多保真评估 → 门控晋升 | 版本化 skill 库 + 晋升/退役记录 |
| **D** | 部署/蒸馏（Deploy，可选） | 把在线选择器蒸馏到本地小模型；shadow/canary/回滚 | 低成本 selector + 上线风险边界 |

**新数学建模（一个总模型 + 三个子系统）：**

1. **总模型：BMF-CSMDP**（Budgeted Multi-Fidelity Constrained Semi-MDP with Contract Shield，带契约 shield 的预算约束多保真半马尔可夫决策过程）。  
   - 与 HeurAgenix Eq.(1) 的区别：状态从"低维问题状态"→"工具 checkpoint"，动作从"启发式"→"带参数与停止条件的 option"，转移从"确定单步"→"shielded 工具转移 + 变时长"，目标从"单标量终点代价"→"多目标效用 + 硬约束 + 预算"。
2. **价值估计：多保真 LCB + 自适应升保真**（解决 EDA 评估太贵、TTS 不可直接套用）。
3. **信用分配：势函数 shaping + 反事实重放/Shapley 近似**（解决跨阶段影响延迟到 routing/signoff）。
4. **演化与选择器：双层进化 + CA-POR + 序数/gate 版 CPR**（解决 skill 成本异构、EDA 状态是序数特征、安全性关键）。

**四个最核心的公式（后文 §3 给出完整定义）：**

- **Option Bellman（内层选择）：**  
  $$Q(s,\omega)=\mathbb{E}\big[\,r(s,\omega,s')+\gamma^{\rho(\omega)}V(s')\,\big],\qquad V(s)=\max_{\omega\in\Omega_{\mathrm{adm}}(s)}Q(s,\omega)$$
- **预算约束多目标目标函数（外层）：**  
  $$\max_{\pi}\ \mathbb{E}\Big[\textstyle\sum_j \gamma^{\rho_j}\Delta U(s_j,s_{j+1})\Big]\quad \text{s.t.}\ \Pr(\text{gate 失败})\le\delta_{\text{fail}},\ \ \sum_j \rho_j\le B_{\text{time}},\ \ \sum_j c^{\text{api}}_j\le B_{\text{api}}$$
- **多保真选择分数（在线决策用）：**  
  $$\mathrm{Score}(s,\omega)=\mathrm{LCB}_{1-\alpha}\big[\Delta U(s,\omega)\big]-\lambda_c\,\hat c(s,\omega)-\lambda_r\,\mathrm{UCB}_{1-\alpha}\big[P_{\text{fail}}(s,\omega)\big]$$
- **跨阶段势函数 shaping（把 routing 后果提前告诉 placement）：**  
  $$r_{\text{train}}(s,\omega,s')=r_{\text{PPA}}(s,\omega,s')+\gamma^{\rho}\Phi(s')-\Phi(s),\qquad
  \Phi(s)=-\big(\lambda_1\widehat{OF}_{\text{route}}(s)+\lambda_2\widehat{TNS}_{\text{post-route}}(s)+\lambda_3\widehat{DRC}(s)\big)$$

**预期收益（待实验验证，不是承诺）：**

| 机制 | 预期改善 | 对应指标 |
|---|---|---|
| 契约 shield + 硬 gate | 搜索不再浪费在非法解上；点态不劣化可通过回滚保证 | gate 通过率↑、无效评估次数↓ |
| 多保真 LCB + 自适应升保真 | 同 tool-hour 预算下评估更多候选 | time-to-target↓、HPWL/overflow/WNS 改善 |
| 跨阶段 shaping + 反事实信用 | 减少"HPWL 好但布线爆炸"的近视决策 | post-route overflow↓、WNS/TNS↓、DRC↓ |
| CA-POR（成本感知偏好奖励） | selector 学会珍惜昂贵工具调用 | 单位预算 PPA 效用↑、API/tool 调用↓ |
| EDA-CPR（序数状态 + gate 预测） | 状态理解更准，跨设计族泛化更稳 | selector regret↓、top-k recall↑、最差族改善 |
| 双层演化 + 门控晋升 | skill 库持续进化且风险有界 | LCB(ΔU)>0 的 skill 数↑、CVaR↓ |

**明确不做：** LLM 不输出坐标/DEF/路径几何；不做任意 shell 执行；第一阶段不改 RTL/netlist；不以"训练更大的模型"为主贡献。

---

## 1. 为什么 HeurAgenix 不能直接照搬到布局布线

HeurAgenix 的核心假设（§2.1、§3.1–3.3）：

- 状态 $z$：实例与部分解的高层抽象；
- 启发式 $H:\mathcal{Z}\to\mathcal{O}$，单步转移 $z_{t+1}=T(z_t,O_t)$，同一启发式执行 $M=5$ 步记为 $T^M(z,H)$；
- 最小化目标（Eq.1）：$Q(z,H,t)=V(T^M(z,H),t-1)$，$\pi^\star=\arg\min Q$；
- Monte-Carlo TTS 估计 $\hat Q_H=\frac1T\sum_t C(S_t)$，便宜、可重复、终点代价精确；
- 演化 Algorithm 1：正/负轨迹对比 → 单点反事实定位关键操作 $k^\star=\arg\max_k \Delta_k$ → LLM 提炼演化策略 → 迭代精修；
- 选择器训练：离线 $(z,H,Q_H)$，POR 处理带噪排序，CPR 对齐状态感知，GRPO 微调。

这五条在 EDA 布局布线中分别失效或需要改造：

| # | HeurAgenix 假设 | EDA 布局布线现实 | HA-PR 的改造（创新点编号） |
|---|---|---|---|
| 1 | 状态便宜、低维 | ODB/DEF/网表/时序/拥塞高维异构；LLM 上下文装不下 | **双表示状态**：LLM 读结构化 state card，代理模型读图/向量特征（I1） |
| 2 | 动作是短序列、固定 $M$ 步 | 一次工具调用分钟~小时；合法化/布线迭代次数因状态而异 | **契约化 option**：$(skill\_id,\theta,\tau)$，停止条件/预算由 option 自带（I1/I2） |
| 3 | 转移单步、确定、廉价 | 工具版本/seed 有噪声；一次 transition 有随机时长与成本 | **shielded 半 MDP**：变时长 $\rho$、成本进状态、配对重放降噪（I3） |
| 4 | 终点代价一次 rollout 可得 | signoff 昂贵；HPWL/overflow 是代理，可能 reward hacking | **多保真估值**：F0–F3 + LCB + 不确定时升保真（I3） |
| 5 | 正确性由问题编码天然保证 | 重叠、连通性、DRC、LVS、STA 是独立硬门槛 | **契约 + gate + chance constraint + rollback**；LLM 不碰几何合法性（I2） |
| 6 | 单目标、单阶段 | PPA 多目标；placement 决策影响 routing/signoff | **HVI + CVaR + 跨阶段 shaping + 反事实信用**（I4） |
| 7 | 启发式池同质、成本接近 | legalize 秒级 vs 全 flow 小时级，成本差 3–4 个数量级 | **成本感知选择**：CA-POR 按"单位成本 LCB 效用"排序（I5） |
| 8 | 一个池子服务所有实例 | 设计族异构（控制/数据通路/存储/宏密集/拥塞严重） | **阶段条件 + 设计族条件 skill 库 + QD archive**（I5） |

> **一句话结论：** HeurAgenix 的"演化 + 选择"双层结构可以保留；必须替换的是它的四个低成本假设——状态廉价、动作短、转移确定廉价、正确性免费。HA-PR 的流程和数学建模都围绕这四个替换展开。

---

## 2. 新流程清单（可执行版）

### 2.0 总体流程：三库 + 双循环 + 验证栈

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryTextColor':'#000000','textColor':'#000000','lineColor':'#333333'}}}%%
flowchart TD
    subgraph O[Phase O 离线准备]
      O1[工具链/设计冻结] --> O2[baseline + 全阶段 checkpoint]
      O2 --> O3[指标 / gate / 归一化 / 参考点]
      O3 --> O4[state card schema + 图特征]
      O4 --> O5[skill schema + 初始 skill 库]
      O5 --> O6[验证栈 L0–L3 + shield/rollback]
      O6 --> O7[多保真评估器 + surrogate 校准]
      O7 --> O8[Experience Bank + meta 日志]
      O8 --> O9[按 design family 切分 train/val/test]
    end

    subgraph R[Phase R 在线执行 · 内循环]
      R1[构建状态卡 s] --> R2[selector 提候选 H']
      R2 --> R3[硬过滤: 适用性 / 预算 / 前置]
      R3 --> R4[多保真估值: LCB / UCB]
      R4 --> R5[选 argmax 综合分数]
      R5 --> R6[契约 shield 下执行 + 快照]
      R6 --> R7{gate 全通过?}
      R7 -- 否 --> R8[回滚 + fallback + 记录失败]
      R7 -- 是 --> R9[更新 checkpoint / Q̂ / Experience Bank]
      R9 --> R10{终止 / 无改进 / 预算尽?}
      R10 -- 否 --> R1
      R10 -- 是 --> R11[signoff + 输出 PPA + 完整轨迹]
      R8 --> R10
    end

    subgraph E[Phase E 自进化 · 外循环]
      E1[收集正/负轨迹] --> E2[对齐差异决策点]
      E2 --> E3[反事实重放 Δ / Shapley → 关键决策]
      E3 --> E4[构造演化 prompt: 证据 + 契约]
      E4 --> E5[LLM 提 L1/L2/L3 变异候选]
      E5 --> E6[静态 / 单测 / canary 过滤]
      E6 --> E7[多保真评估 + 跨设计族验证]
      E7 --> E8{LCB(ΔU) > 0 且 UCB(违规) < ε?}
      E8 -- 是 --> E9[晋升: 加入 skill 库 / 归档]
      E8 -- 否 --> E10[存为失败样本 / 不晋升]
    end

    V[验证栈 L0→L3<br/>门禁 · 回滚 · 审计] -.横切.-> R
    V -.横切.-> E
    O --> R
    R9 -.轨迹与统计.-> E1
    E9 -.新 skill 版本.-> R2
    R11 -.signoff 真实标签.-> O7

    style O fill:#eef,stroke:#55a,color:#000000;
    style R fill:#efe,stroke:#5a5,color:#000000;
    style E fill:#fef6e0,stroke:#c8871a,color:#000000;
    style V fill:#f5f5f5,stroke:#888,color:#000000;
```

### 2.1 Phase O：离线准备（9 步）

| 步 | 功能 | 产物 | 验收标准 |
|---|---|---|---|
| O1 | 冻结工具链与设计：OpenLane1/OpenROAD + PDK + 设计集；记录 commit/版本 | `env.lock`、design 清单 | 版本可追溯；同一命令两次运行结果一致 |
| O2 | 跑 baseline 全 flow，在每个阶段后存 DEF/ODB checkpoint + metrics | `checkpoints/`、`baseline_metrics.csv` | ≥2 个小设计全阶段跑通；baseline 重复 3 次指标在容差内 |
| O3 | 定义每阶段指标、硬 gate、归一化、参考点 $r$ | `metrics_spec.yaml`、`gates.yaml` | 每个指标都有方向、量纲、baseline、容差、是否 gate |
| O4 | 定义 state card schema 与图/向量特征 | `state_card.schema.json`、特征 extractor | 同一 checkpoint 生成确定性卡片；LLM 可读、字段无歧义 |
| O5 | 定义 skill schema，实现首批 L1 参数级 skill（含契约、单测、fallback） | `skills/*.yaml`、测试 | 每个 skill 可独立执行、可回滚、有前置/后置检查 |
| O6 | 建验证栈 L0–L3 与 shield/rollback | `verifier/`、`shield.py` | 故意注入非法状态能被 L1 拦下；回滚后 checkpoint 字节级一致 |
| O7 | 建多保真评估器 + surrogate（代理），并在审计集上校准 | `fidelity.py`、`surrogate/`、校准报告 | 代理误差有置信区间；高保真审计样本不被代理替代 |
| O8 | 建 Experience Bank 与统一日志 | `experience.db`、`meta.json` schema | 每次决策可追溯 design/tool/prompt/seed/runtime |
| O9 | 按 design family（控制/数据通路/存储/宏密集/拥塞型）切 train/val/test | `splits.json` | 同一设计族不跨 train/test；test 冻结后不再改 |

### 2.2 Phase R：在线执行（9 步）

| 步 | 功能 | 关键动作 | 失败处理 |
|---|---|---|---|
| R1 | 构建状态 $s$ | 读 checkpoint；生成 state card + 图特征；读剩余预算 $b$ | checkpoint 损坏 → 拒绝启动 |
| R2 | 生成候选 | LLM/dsv4-flash/蒸馏 selector 读 state card + skill cards，输出 $(skill\_id,\theta,\tau,fallback)$ 的 Top-$K$ | parse 失败 → 重试 1 次 → 退回检索/基线 |
| R3 | 硬过滤 | 适用性谓词、前置条件、参数范围、剩余预算、许可证/allowlist | 无候选 → 走 fallback / 终止该阶段 |
| R4 | 多保真估值 | 对候选估计 $\Delta U$、成本、失败率；按不确定性决定升保真 | 高不确定性 → 升一档或弃权 |
| R5 | 选择 | $\arg\max \mathrm{Score}(s,\omega)$（见 §3.6） | 全部 Score<0 → 不执行，直接进入下一阶段 |
| R6 | 执行 | 快照 → sandbox 执行 tool Tcl/Python（带超时/资源限制）→ shield 检查 | 执行异常/超时 → 回滚 + fallback |
| R7 | 后置检查 | L1 不变式；按需 L2 canary；记录真实 $\Delta$ | gate 失败 → 回滚，标记 skill 失败次数 +1 |
| R8 | 更新 | 更新 checkpoint、Experience Bank、surrogate、预算 | 日志缺失 → 该样本不进训练集 |
| R9 | 终止 | 到达 signoff / 无正收益 / 预算耗尽 / 触发 kill switch | 提前终止也输出当前最优合法解 |

### 2.3 阶段图、每阶段 gate 与候选 skill 池

**阶段图：** `floorplan → global_placement → legalization → CTS → global_route → detailed_route → signoff`。允许跳跃（如 physical-only 可跳过 CTS）、回退（DR 失败回 GR）和迭代（timing repair → placement/CTS），因此是**有向图而非固定链**。

| 阶段 | checkpoint 内容 | 主要指标 | 硬 gate（示例） | 候选 skill（每阶段 5–8 个） |
|---|---|---|---|---|
| floorplan | DEF/ODB + macro/IO 约束 | 面积、通道、halo 冲突 | 固定 IO/macro 合法；blockage/halo 不冲突；在 die 内 | macro 区域/朝向策略、通道预留、power planning 预留、density budget 分配 |
| global placement | 全局坐标 + density | HPWL、density overflow、时序代理 | 固定对象不动；在 core 内；netlist hash 不变；density ≤ 上限 | density/wirelength 权重调度、timing-driven 权重、endpoint 优先级、congestion-aware spreading、region 约束 |
| legalization | row/site 合法坐标 | overlap、位移、HPWL 变化 | overlap=0；row-legal=1；固定对象不动；HPWL 恶化 ≤ guardband | 合法化顺序（WNS-first/density-first）、padding/effort、时序 guardband、局部 swap |
| CTS | 时钟树 | skew、latency、clock DRC | 拓扑合法；skew/latency 在门限；无新增 DRC | buffer 规格/策略、拓扑约束、target skew 调度（先 L1 参数级） |
| global route | GRT 结果 + overflow map | overflow、wirelength、connectivity | 100% 连通；层方向/轨道合法；overflow ≤ baseline+guardband | net ordering（criticality/congestion/pin density）、layer adjustment、cost shaping、RRR 批策略、congestion iterations |
| detailed route | 详细布线结果 | DRC、via、short/open、runtime | DRC=0（或 ≤ 严格阈值）；无短路/开路；天线不恶化 | effort/iteration 调度、DRC repair 顺序、via/antenna 修复、局部重布 |
| signoff | GDS + SPEF + 时序报告 | DRC/LVS/STA/power/area | DRC=0、LVS pass、ERC pass、各 corner STA 不劣化超过 guardband | 最终验收；不执行演化类 skill；只允许回退 |

**初始 skill 池建议（与 `04` §7.7 一致，这里补上"契约后置条件"口径）：** 每个 skill 都必须声明 `postconditions`（如"overflow 下降""WNS 退化 ≤ 5 ps""无新增 DRC"）；不满足则自动回滚，该次执行按失败样本入库。

### 2.4 Phase E：自进化（8 步）

| 步 | 功能 | 数学/机制 | 产物 |
|---|---|---|---|
| E1 | 收集轨迹 | 从 Experience Bank 取同一状态族下的正/负轨迹对 | $(s_i,a_i,\Delta U_i)$ 数据集 |
| E2 | 对齐与差异定位 | 找出少数决策位置不同的候选集 $\mathcal{D}$ | 差异决策列表 |
| E3 | 反事实信用 | 单点重放估计 $\delta_i$；必要时 Shapley 近似 $\phi_i$（§3.8） | 关键决策 $i^\star$ 及其证据 |
| E4 | 构造演化 prompt | 输入：skill 契约 + 正/负动作 + $\delta^\star$ + 失败模式 + 约束 | evolution prompt（含 JSON schema） |
| E5 | LLM 提变异 | L1 参数/阈值 → L2 触发条件/组合/停止 → L3 受限 DSL/结构 | 候选 skill（含测试与预期效果） |
| E6 | 快速过滤 | schema + AST/allowlist + 单测 + 小设计 canary | 通过过滤的候选 |
| E7 | 多保真评估 | F0→F3 递进；跨 ≥2 个 design family；配对 A/B | 候选的 $\Delta U$ 分布与成本 |
| E8 | 晋升/退役 | 接受条件：$\mathrm{LCB}(\Delta U)>0 \wedge \mathrm{UCB}(\text{违例})<\varepsilon \wedge$ 成本在预算内 | 新版本入库；失败样本入"避坑库"；低效 skill 退役 |

### 2.5 验证栈 L0–L3（横切所有阶段）

| 层 | 检查内容 | 成本 | 失败动作 |
|---|---|---|---|
| L0 | JSON schema、参数范围、allowlist、超时、资源、seed | 极低 | 拒绝执行，记录 parse/static error |
| L1 | 快速不变式：重叠=0、row-legal、连通性、固定对象未动、netlist hash、容量/层规则 | 低 | 回滚；skill 计一次失败 |
| L2 | canary：局部区域/部分 net 的 GR+DR，或"placement + GRT"子 flow | 中 | 回滚；降级到更保守 skill |
| L3 | signoff：DRC/LVS/ERC、STA（含 SPEF）、power/area、多 corner | 高 | 回滚；该 skill 不进生产库，只作研究样本 |

**原则：** L0/L1 必须 100% 每次通过；L2 按风险触发（新 skill、参数超出历史范围、代理不确定）；L3 用于最终验收和演化晋升，不做每步在线评估。

### 2.6 交付物与分阶段验收

| 阶段 | 时间（建议） | 交付物 | 验收 |
|---|---|---|---|
| Phase 0 | 1–2 周 | harness + checkpoint + schema + 6 个 L1 skill + L0/L1 验证 | baseline 可重复；skill 可执行/可回滚/可记录 |
| Phase 1 | 2–3 周 | dsv4-flash selector + Experience Bank + 配对实验报告 | 每个 skill 的 $\delta_k$ 分布 + selector regret + gate 通过率 |
| Phase 2 | 3–4 周 | 反事实信用 + 多保真 + L1/L2 演化 | 固定预算下优于随机/BO 基线；晋升记录完整 |
| Phase 3 | 3–4 周 | routing skill + 跨阶段 shaping | placement→routing 联合指标优于单阶段优化 |
| Phase 4 | 2–4 周 | L3 受限代码演化 + 本地蒸馏 selector | API vs 本地对比；成本下降、质量不劣化 |

---

## 3. 新数学建模：BMF-CSMDP（带契约 shield 的预算约束多保真半 MDP）

> **建模总思路：** HeurAgenix 的 Eq.(1) 本质是一个"单层、确定、无约束、终点可精确评估"的有限步 MDP。HA-PR 把它扩展成：
> 1. **半 MDP / option**：一动作 = 一段工具执行，时长与成本随机（§3.3–3.4）；
> 2. **约束 MDP**：硬 gate + 机会约束 + 预算约束（§3.5–3.6）；
> 3. **多保真观测**：Q 不能精确测，只能在若干保真度下带偏、带噪估计（§3.7）；
> 4. **跨阶段层次结构**：阶段策略与技能策略分层，用势函数把下游后果前移（§3.8）；
> 5. **双层自进化**：内层学选择器，外层学 skill 库（§3.9–3.10）。

### 3.1 记号总表

| 符号 | 含义 |
|---|---|
| $g\in\mathcal{G}$ | 阶段：floorplan / global placement / legalization / CTS / GRT / DR / signoff |
| $d$ | 设计（网表 + 约束 + PDK） |
| $x_g$ | 阶段 $g$ 的物理实现状态（DEF/ODB + 工具中间数据） |
| $m_g$ | 阶段指标向量（HPWL、density、overflow、WNS/TNS、DRC、power、area…） |
| $b=(b_{\text{time}},b_{\text{api}},b_{\text{tool}})$ | 剩余预算 |
| $\xi_g$ | 工具随机性（seed、并行、版本） |
| $s=(g,d,x_g,m_g,b,h)$ | 完整状态；$h$ 为历史摘要（最近动作/效果/失败模式） |
| $\sigma(s)$ | 给 LLM 的状态卡（结构化摘要） |
| $\varphi(s)$ | 给代理/策略网络的图/向量表示 |
| $k$ | skill id（技能库条目） |
| $\theta$ | skill 参数 |
| $\tau$ | option 的停止条件/horizon（步数、事件、时间预算） |
| $\omega=(k,\theta,\tau)$ | 一个 option（执行单元） |
| $C_k=(\mathrm{Pre}_k,\mathrm{Post}_k,\mathrm{Inv}_k,\mathrm{Fallback}_k,\mathrm{Cost}_k)$ | skill 契约 |
| $A_k(s)\in\{0,1\}$ | 适用性谓词 |
| $\mathcal{F}(s)$ | 该阶段的合法状态集合（无重叠、连通、DRC=0 等） |
| $G(s)=1[x\in\mathcal{F}(s)]$ | 硬 gate 指示函数 |
| $\rho(\omega)$ | option 实际消耗（时间/工具调用/token） |
| $c(\omega)$ | option 成本（标量或向量） |
| $U(s)$ | 质量效用（HVI、字典序或加权，见 §3.5） |
| $\Delta U(s,\omega)=U(s')-U(s)$ | 单步效用改进 |
| $\hat Q_l,\hat\sigma_l$ | 保真度 $l$ 下的价值估计与标准差 |
| $\Phi(s)$ | 下游感知势函数（routing/signoff 代理） |
| $l\in\{F0,F1,F2,F3\}$ | 保真度层级（静态→代理→子 flow→signoff） |

### 3.2 状态：checkpoint + 双表示

**状态本体是 checkpoint：**
$$
s=(g,d,x_g,m_g,b,h),\qquad x_g=\mathrm{Checkpoint}(g,d),\; m_g=\mathrm{Metrics}(x_g)
$$

这是与 HeurAgenix 最大的一处差异：HeurAgenix 的 $z$ 是低维实例特征 + 部分解；EDA 的 $s$ 是高维版图对象。因此采用**双表示**：

1. **LLM 状态卡** $\sigma(s)$：固定 schema 的结构化摘要，例如
   $$
   \sigma(s)=\big(\underbrace{g}_{\text{阶段}},\underbrace{\text{legality}}_{\text{合法类}},\underbrace{\text{density overflow}}_{\text{序数 0–4}},\underbrace{\text{congestion severity}}_{0–4},\underbrace{\text{timing severity}}_{0–4},\underbrace{\text{budget class}}_{\text{充足/紧/尽}},\underbrace{\text{recent actions}}_{\text{最近 3 次动作/效果}}\big)
   $$
   其中"序数"字段不是简单正确/错误，而是 **0–4 等级**（这是 §3.10 CPR 扩展的前提）。
2. **代理向量/图表示** $\varphi(s)$：网表超图 + 单元/线网特征（pin density、net degree、坐标、层、拥塞图、时序关键度），供 surrogate / Q 网络使用。

**状态卡构造原则：** 只放决策相关字段；所有字段可机读、可验证、有确定性 extractor；失败模式（上次动作为何失败）必须进状态卡，这对应 HeurAgenix 的 stochastic trajectory 思想。

### 3.3 动作：契约化 option skill

**定义（EDA 版 option）：**
$$
\omega=(k,\theta,\tau),\qquad 
k\in\mathcal{K},\;\theta\in\Theta_k,\;\tau\in\mathcal{T}_k
$$
其中 $\tau$ 替代 HeurAgenix 固定 $M=5$：可以是"执行到 overflow 收敛/最多 $n$ 次/最多 $t$ 秒/事件触发停止"。这直接解决"固定步数在 EDA 中不合理"的问题。

**skill 契约**是安全迁移的关键：
$$
C_k=(\mathrm{Pre}_k,\mathrm{Post}_k,\mathrm{Inv}_k,\mathrm{Fallback}_k,\mathrm{Cost}_k,\mathrm{Evidence}_k)
$$
- $\mathrm{Pre}_k$：前置谓词（如"GRT 数据存在""global placement 已完成""剩余预算 ≥ 2×P50 成本"）；
- $\mathrm{Post}_k$：后置条件（如"overflow 相比执行前下降""HPWL 恶化 ≤ 2%""无新增 DRC"）；
- $\mathrm{Inv}_k$：执行期间必须保持的不变式（fixed macro 不动、netlist hash 不变、连通性不破）；
- $\mathrm{Fallback}_k$：失败时走哪条基线；
- $\mathrm{Cost}_k$：成本模型（runtime、tool calls、API token 的分布）；
- $\mathrm{Evidence}_k$：历史 A/B 统计、置信区间、失败模式、provenance。

**适用与可负担集合：**
$$
\Omega_{\mathrm{adm}}(s)=\{\omega=(k,\theta,\tau): A_k(s)=1,\ \mathrm{Pre}_k(s)=1,\ \mathbb{E}[\rho(\omega)]\le b_{\text{time}},\ \mathbb{E}[c_{\text{api}}(\omega)]\le b_{\text{api}}\}
$$

> **与 HeurAgenix 的对应：** 原 $H$ 是"状态→操作"的函数；这里 $\omega$ 是"状态→（参数化工具策略 + 停止条件）"的 option。LLM 的动作空间从"选一个启发式"变成"选一个可验证的 option"，并可以对 $\theta,\tau$ 做参数化搜索。

### 3.4 转移：工具执行 + 契约 shield（半 MDP）

**裸执行：** 在状态 $x$ 下调用 skill：
$$
\tilde x'=\mathrm{Exec}_k(x,\theta;\xi_g)+\text{工具噪声}
$$
裸执行可能产生非法结果，因此定义 **shield 算子**：
$$
\mathcal{S}_k(s,\tilde x')=
\begin{cases}
s^+=(g',\tilde x',m',b-c(\omega),h') & \text{若 } \mathrm{Post}_k,\mathrm{Inv}_k,\;G(s^+)\text{ 全部通过}\\
s & \text{否则回滚（记录失败，可选执行 } \mathrm{Fallback}_k\text{）}
\end{cases}
$$

**概率转移（半 MDP，变时长）：**
$$
P\big(s',\rho\,\big|\,s,\omega\big)=\Pr\big(\mathcal{S}_k(s,\mathrm{Exec}_k(x,\theta))=s',\ \rho(\omega)=\rho\big)
$$
其中 $\rho$ 是随机时长/成本；$\gamma^{\rho}$ 表示每单位成本/时间的折扣（可用 $\gamma\in(0,1]$ 或显式预算约束替代）。

**option Bellman（核心公式 1，Eq.(1) 的 EDA 版）：**
$$
Q(s,\omega)=\mathbb{E}\Big[\,r(s,\omega,s')+\gamma^{\rho(\omega)}V(s')\ \Big|\ s,\omega\Big],
\qquad
V(s)=\max_{\omega\in\Omega_{\mathrm{adm}}(s)}Q(s,\omega)
$$
终止条件：$V(s_{\text{signoff}})=U(s_{\text{signoff}})$；当无正收益 option 或预算耗尽时停止。

**两层层次结构（可选但推荐）：**
- 高层阶段策略 $\pi_{\text{high}}(g'\,|\,g,s)$：决定下一个跑哪个阶段、是否回退/重复、预算如何在阶段间分；
- 低层技能策略 $\pi_{\text{low}}(\omega\,|\,g,s)$：在阶段 $g$ 内选 skill 与参数。
- 由 options framework（Sutton–Precup–Singh, 1999），半 MDP 的 option 可以嵌套，因此阶段本身可以视为 macro-option；这给"placement↔routing 迭代"提供了严格表示，而不是把整个 flow 当成一条固定链。

### 3.5 EDA 指标、gate 与效用

#### 3.5.1 阶段指标（写出真正要优化的量）

**Placement：**
$$
\mathrm{HPWL}(x)=\sum_{e\in E}\Big[\max_{p\in e}x_p-\min_{p\in e}x_p+\max_{p\in e}y_p-\min_{p\in e}y_p\Big]
$$
$$
\mathrm{OF}_{\text{den}}(x)=\frac{\sum_{b\in B}\max\{0,D_b(x)-C_b\}}{\sum_{b\in B}C_b},
\qquad
D_b(x)=\sum_i \mathrm{area}(i)\cdot\mathrm{overlap}_{i,b}(x),\quad C_b=\rho_{\text{target}}A_b
$$

**Routing（全局布线 overflow）：** 对每个 3D g-cell/layer 边 $e$，记需求 $d_e(x)$、容量 $c_e$：
$$
\mathrm{OF}_{\text{route}}(x)=\frac{\sum_e\max\{0,d_e-c_e\}}{\sum_e c_e},
\qquad
\mathrm{MOF}(x)=\max_e\frac{\max\{0,d_e-c_e\}}{c_e}
$$

**时序：**
$$
\mathrm{WNS}_{\text{setup}}(x)=\min_{p\in\Pi}\mathrm{slack}^{\text{setup}}_p,\qquad
\mathrm{WNS}_{\text{hold}}(x)=\min_{p\in\Pi}\mathrm{slack}^{\text{hold}}_p,\qquad
\mathrm{TNS}_{\text{setup}}(x)=\sum_{p\in\Pi}\min\{0,\mathrm{slack}^{\text{setup}}_p\},
\qquad
\mathrm{slack}_p=T_{\text{req},p}-T_{\text{arr},p}
$$

**DRC / via / power：** $N_{\text{drc}}(x)$（signoff 必须为 0）、$N_{\text{via}}(x)$、$P_{\text{total}}=P_{\text{dyn}}+P_{\text{leak}}$。

**WNS 口径（v1.1）：** setup WNS 用 `DRT::worst_slack_max`，hold WNS 用 `DRT::worst_slack_min`，二者均为 signed、越大越好；详细口径与工程实现见 `10_完整数学建模体系...v1.md` §3.1 与 `eda/docs/METRIC_CONVENTIONS.md`。


#### 3.5.2 归一化与 gate

设基线 $y_i^{\text{base}}$、方向 $\sigma_i\in\{+1,-1\}$（+1 越大越好）、尺度 $s_i$（IQR 或基线绝对值的鲁棒估计）：
$$
\tilde y_i(s)=\sigma_i\,\frac{y_i(s)-y_i^{\text{base}}}{s_i}
$$
硬 gate：
$$
G(s)=\prod_{c\in\mathcal{C}_{\text{stage}}}\mathbb{1}[F_c(s)=1],
\qquad
\mathcal{F}(s)=\{x:\text{所有 }F_c\text{ 通过}\}
$$
例如 placement 阶段：$F=\{$无重叠、row-legal、fixed 对象未动、netlist hash 不变、density ≤ 上限$\}$；routing 阶段：$F=\{$100% 连通、层规则、overflow ≤ baseline+guardband、DRC ≤ 阈值$\}$。

#### 3.5.3 效用 $U$：从标量到 HVI + 尾部风险

三种可用定义（建议首版用 A，研究版用 C）：

**A. 字典序（最稳）：** 先 gate，再按 $\tilde y_1\succ\tilde y_2\succ\cdots$ 比较。无权重争议，但表达力弱。

**B. 约束加权：** $U_w(s)=\sum_i w_i\tilde y_i(s)$，其中权重由 LLM selector 按设计状态选（如 timing_first / routability_first / power_recovery 模式）。

**C. 超体积改进（推荐研究版）：** 以基线可行点集 $Y_{\text{base}}$ 与参考点 $r$（悲观方向）为参照：
$$
\Delta U_{\mathrm{HV}}(s,\omega)=\mathrm{HV}\big(Y_{\text{base}}\cup\{\tilde y(s')\};r\big)-\mathrm{HV}\big(Y_{\text{base}};r\big)
$$
HVI 天然处理 timing/power/area/runtime 的多目标权衡，不需要拍权重。

**尾部风险（约束而非奖励）：** 设 $L=-\Delta U$ 为效用损失：
$$
\mathrm{CVaR}_{\alpha}(L)=\mathbb{E}\big[L\,\big|\,L\ge \mathrm{VaR}_{\alpha}(L)\big]
$$
用 $\mathrm{CVaR}_{\alpha}\le \rho_{\text{risk}}$ 约束"平均好但个别设计爆炸"的 skill。

### 3.6 外层目标：约束预算 MDP

**完整目标（核心公式 2）：**
$$
\max_{\pi}\ \mathbb{E}_{d\sim\mathcal{D},\;s_0\sim\mu_d}\Big[\sum_{j=0}^{K-1}\gamma^{\rho_j}\Delta U(s_j,s_{j+1})\Big]
$$
$$
\text{s.t.}\quad
\Pr\big(\exists j:\ G_3(s_{j+1})=0\big)\le\delta_{\text{fail}}
\quad\text{（signoff 硬约束机会约束）}
$$
$$
\sum_j\rho_j\le B_{\text{time}},\qquad
\sum_j c^{\text{api}}_j\le B_{\text{api}},\qquad
\sum_j c^{\text{tool}}_j\le B_{\text{tool}}
$$
$$
\omega_j\in\Omega_{\mathrm{adm}}(s_j),\qquad s_{j+1}=\mathcal{S}_{\omega_j}(s_j,\mathrm{Exec}_{\omega_j}(x_j))
$$

其中 $G_3$ 是 L3 signoff gate；在线 L0/L1 gate 由 shield 保证，L3 只抽样评估，所以才需要机会约束。

**拉格朗日/primal-dual 视角（把约束变成可调代价）：**
$$
\max_{\pi}\min_{\lambda,\mu\ge0}\ \mathbb{E}\Big[\sum_j\gamma^{\rho_j}\Delta U_j\Big]
-\lambda\Big(\sum_j\rho_j-B_{\text{time}}\Big)
-\mu\Big(\Pr(G_3=0)-\delta\Big)
$$
工程上用 primal-dual 更新 $\lambda,\mu$，或直接在候选评分中加成本/风险惩罚。

**在线决策用的实用分数（核心公式 3）：**
$$
\mathrm{Score}(s,\omega)=
\underbrace{\mathrm{LCB}_{1-\alpha}\big[\Delta U(s,\omega)\big]}_{\text{性能下界}}
-\lambda_c\,\frac{\hat c(s,\omega)}{\max(b_{\text{time}}-b_{\text{min}},\epsilon_b)}
-\lambda_r\,\underbrace{\mathrm{UCB}_{1-\alpha}\big[P_{\text{fail}}^{L3}(s,\omega)\big]}_{\text{风险上界}}
$$
选择：
$$
\omega^\star=\arg\max_{\omega\in\Omega_{\mathrm{adm}}(s)}\mathrm{Score}(s,\omega)
$$
**解释：** 性能用下界（保守），成本按剩余预算归一化（贵动作要显著更好才值得做），失败风险用上界（安全优先）。这三项正是 HeurAgenix 原 TTS 的 $\hat Q_H$ 所没有的。

**与 HeurAgenix 的差异：** 原 Eq.(1) 的 $\min Q$ 只处理"期望终端代价"；这里把"多目标效用、成本、风险、预算"拆开，并用 LCB/UCB 显式表达不确定性。注意：**这不是把 PPA 揉成一个不透明加权和**，而是字典序/HVI + 约束的形式。

---
### 3.7 多保真价值估计与预算分配（解决"评估太贵"）

**保真度层级：**

| 层级 | 评估内容 | 典型成本 | 偏差/方差 | 用途 |
|---|---|---|---|---|
| F0 | schema、单测、静态检查、单位换算 | ≈0 | 无随机性 | 硬过滤 |
| F1 | 代理模型/快速 checker：HPWL、density、拥塞代理、连通性 | 秒级 | 偏差大、方差小 | 大规模粗筛 |
| F2 | 子 flow：placement+GRT，或局部 canary | 分钟级 | 中等偏差 | 候选排序 |
| F3 | 全 flow signoff：DRC/LVS/STA(with SPEF)/power | 小时级 | 偏差最小、方差最大 | 晋升与最终验收 |

**观测模型：**
$$
\tilde Q_l(s,\omega)=Q(s,\omega)+b_l(s,\omega)+\varepsilon_l,\qquad
\mathbb{E}[\varepsilon_l]=0,\quad \mathrm{Var}(\varepsilon_l)=\frac{\sigma_l^2}{n_l}
$$
其中 $b_l$ 是保真度偏差（proxy gap），$n_l$ 是该候选在保真度 $l$ 上的评估次数。

**保守估计（LCB）：**
$$
\mathrm{LCB}_{1-\alpha}^{\,l}(s,\omega)
=\hat Q_l(s,\omega)-\hat b_l^{\max}(s,\omega)
-z_{1-\alpha}\frac{\hat\sigma_l(s,\omega)}{\sqrt{n_l}}
$$
$\hat b_l^{\max}$ 是代理偏差的悲观上界（用审计集校准）；不确定就自动升保真，而不是硬信代理。

**升保真规则（racing / Hyperband 思想）：**
$$
\mathrm{Promote}(l\to l+1)\iff
\mathrm{LCB}_{1-\alpha}^{\,l}(s,\omega)\ge \tau_l
\ \wedge\ \text{剩余预算够跑 }F_{l+1}
\ \wedge\ \hat\sigma_l>\sigma_{\text{target}}
$$
首版可用简单规则：F0 全过 → F1 保留 top 30% → F2 保留 top 5–10 个 → F3 只对最终决策/晋升候选做。

**预算分配问题（研究版）：**
$$
\max_{\{n_l\}}\ \Pr\big(\text{选出的候选是真实最优}\big)
\quad\text{s.t.}\quad \sum_l n_l c_l\le B
$$
可用 OCBA（Optimal Computing Budget Allocation）或贝叶斯优化中的 Expected Improvement / Value of Information 近似：
$$
\mathrm{VOI}_l\approx\frac{\partial\,\mathbb{E}[\text{最终选择质量}]}{\partial n_l}\Big/c_l
$$
优先给"能改变当前决策 + 单位成本信息量大"的保真度加样本。

**与 HeurAgenix 的差异：** 原 TTS 用一个固定小 rollout 数对所有启发式做无偏平均；EDA 版不能"无偏地便宜"，只能用**带偏、带噪、成本异构**的多保真估计 + 显式不确定性。这是从"Monte-Carlo TTS"到"fidelity-aware decision-making"的升级。

### 3.8 跨阶段信用分配：势函数 shaping + 反事实重放

#### 3.8.1 下游感知势函数

定义状态势函数（由 surrogate 估计下游后果）：
$$
\Phi(s)=-\Big(\lambda_1\widehat{OF}_{\text{route}}(s)
+\lambda_2\widehat{\mathrm{TNS}}_{\text{post-route}}(s)
+\lambda_3\widehat{\mathrm{DRC}}(s)
+\lambda_4\widehat{\mathrm{MOF}}(s)\Big)
$$
**训练用 reward（核心公式 4）：**
$$
r_{\text{train}}(s,\omega,s')=
\underbrace{r_{\text{PPA}}(s,\omega,s')}_{\text{本阶段真实效用}}
+\underbrace{\gamma^{\rho}\Phi(s')-\Phi(s)}_{\text{势函数 shaping}}
$$
**理论依据：** 对任意只依赖状态的势函数 $\Phi$，势函数 shaping（potential-based reward shaping, Ng et al. 1999）不改变最优策略；因此它注入的是"信用传播加速"，不是"篡改目标"。  
**EDA 注意事项：** $\Phi$ 是估计值，若乐观估计会被 reward hacking；工程上用**悲观势函数** $\Phi^-=\hat\Phi-\kappa\hat\sigma_\Phi$，并把 $\Phi$ 对应的真实指标（GRT overflow、post-route WNS、DRC）保留在 L3 审计中验证。

#### 3.8.2 反事实重放

HeurAgenix Algorithm 1 Step 3 对操作 $k$ 做单点替换：
$$
\Delta_k=C(S)-C(S^{(k)}),\qquad k^\star=\arg\max_k\Delta_k
$$
EDA 版在**同一 checkpoint** 上做：
$$
\delta_i=U\big(\mathrm{Replay}(s_i,a_i^+;\pi_{\text{freeze}})\big)
-U\big(\mathrm{Replay}(s_i,a_i^-;\pi_{\text{freeze}})\big)
$$
其中 $a_i^+$ 是正轨迹的决策、$a_i^-$ 是负轨迹的决策，$\pi_{\text{freeze}}$ 是冻结的后续策略（保证因果对照）；$U$ 是经过 gate 的最终效用。  
若差异位置可能交互（非可加），用 Shapley 值近似。为避免组合爆炸，用组合数形式写权重：
$$
\phi_i=\sum_{S\subseteq\mathcal{D}\setminus\{i\}}
\frac{1}{n\binom{n-1}{|S|}}\Big[v(S\cup\{i\})-v(S)\Big],
\qquad v(S)=U(\text{按 }S\text{ 替换决策后的重放})
$$
其中 $n=|\mathcal{D}|$，$\binom{n-1}{|S|}$ 是二项系数；该权重与经典的阶乘归一化 Shapley 权重等价。实践中：先用单点重放筛 top-$m$，再对 top-$m$ 做分组/两两交互检查，得到关键决策：
$$
i^\star=\arg\max_i |\hat\phi_i|\quad\text{或}\quad \arg\max_i |\delta_i|
$$
把 $(s_{i^\star},a_{i^\star}^-,a_{i^\star}^+,\hat\phi_{i^\star},\text{契约},\text{失败模式})$ 作为演化 prompt 的核心证据。**创新点：** 把 HeurAgenix 的"操作级反事实"提升为"checkpoint 级、带交互修正、面向昂贵延迟反馈"的信用分配。

### 3.9 双层自进化：外层学 skill 库，内层学 selector

设技能库 $\mathcal{S}=\{\omega_1,\dots,\omega_K\}$，选择器参数为 $\theta$。

**内层（快）：**
$$
\theta^\star(\mathcal{S})=\arg\max_\theta\ \mathbb{E}_{s\sim d_{\pi_\theta}}\Big[\sum_j\gamma^{\rho_j}\Delta U_j(\mathcal{S})\Big]
\quad\text{s.t. shield/gate 全通过}
$$
**外层（慢、贵）：**
$$
\max_{\mathcal{S}\subset\Omega}\ \mathcal{J}_{\text{outer}}(\mathcal{S})
=\mathbb{E}_{d\sim\mathcal{D}_{\text{val}}}\Big[J\big(\mathrm{Flow}_{\pi_{\theta^\star(\mathcal{S})}}(d)\big)\Big]
$$
$$
\text{s.t.}\quad
\Pr\big(G_3=0\big)\le\delta_{\text{fail}},\qquad
|\mathcal{S}|\le K,\qquad
\mathrm{Cost}(\mathcal{S})\le B_{\text{evo}}
$$
其中 $J$ 是 signoff 后的 PPA 效用（字典序/HVI）；约束保证"加入新 skill 不能把正确性风险放大"。

**演化算子：**
$$
\mathcal{M}_{\text{LLM}}:\ (\mathcal{S},\ \text{evidence})\longrightarrow
\{\omega'_1,\omega'_2,\dots\}
$$
三级变异：
- **L1：** 参数/阈值/权重/顺序 $(k,\theta)\to(k,\theta')$；
- **L2：** 触发条件/组合/停止/fallback $(k,\tau)\to(k',\tau')$；
- **L3：** 受限 DSL / AST 结构变异（必须过静态 allowlist + 单测 + canary）。

**晋升判据（门控演化）：**
$$
\mathrm{Accept}(\omega')=1\iff
\mathrm{LCB}_{1-\alpha}\big[\Delta U(\omega')\big]>0
\ \wedge\
\mathrm{UCB}_{1-\alpha}\big[P^{L3}_{\text{fail}}(\omega')\big]<\varepsilon
\ \wedge\
\hat c(\omega')\le B_{\text{skill}}
$$
不满足的候选：**不删除**，存入失败/避坑库（negative archive），避免选择器反复踩同一个坑。

**(可选) Quality-Diversity archive：** 按行为描述子 $b(\omega)$（如"优化目标侧重：timing/routability/power" + "适用状态：density 高/拥塞高/时序差"）维护多样化档案：
$$
\max_{\mathcal{A}}\ \sum_{\omega\in\mathcal{A}}q(\omega)+\lambda_{\text{div}}\mathrm{Div}(\mathcal{A})
$$
防止 skill 库收敛到少数同质策略，提升跨设计族适应性。

### 3.10 选择器学习：CA-POR + EDA-CPR

**离线数据（checkpoint replay 收集）：**
$$
\mathcal{D}_{\text{offline}}=\big\{\big(\sigma(s_i),\ \{\omega\},\ \widehat{\Delta U},\ \hat c,\ \hat P_{\text{fail}},\ y^{L3}\big)\big\}
$$
包括两类轨迹：**greedy**（每步选当前最好 option）与 **stochastic**（故意选次优/随机，制造坏状态让模型学恢复）。EDA 版 stochastic 轨迹可以直接**人为注入重叠、拥塞、时序恶化**，要求 selector 学会用修复 skill 救回且最终过 gate。

#### 3.10.1 CA-POR：成本感知的偏好结果奖励

HeurAgenix 的 POR 按 rollout 分数 $Q_H$ 排名；但 EDA 中不同 skill 的成本差 3–4 个数量级——按原始效用排名会偏爱昂贵 skill。**先定义"单位成本、扣风险后的 LCB 效用"作为排名分数：**
$$
\varrho(s,\omega)=\frac{\mathrm{LCB}_{1-\alpha}[\Delta U(s,\omega)]-\lambda_r\mathrm{UCB}_{1-\alpha}[P_{\text{fail}}(s,\omega)]}{\hat c(s,\omega)+\epsilon_c}
$$
按 $\varrho$ 降序排名，$\omega$ 排第 $\ell$ 位。

**正/负集合数据驱动定义（这是对论文 POR 手工阈值 $n_{pos},n_{neg}$ 的改进）：**
$$
n_{\text{pos}}(s)=\max\Big\{n:\ \forall \ell\le n,\ \mathrm{LCB}[\Delta U_{(\ell)}]-\lambda_r\mathrm{UCB}[P_{\text{fail},(\ell)}]>0\Big\},
\qquad
n_{\text{neg}}(s)=\min\Big\{n:\ \forall \ell\ge n,\ \mathrm{UCB}[\Delta U_{(\ell)}]-\lambda_r\mathrm{LCB}[P_{\text{fail},(\ell)}]<0\Big\}
$$
即"风险调整后统计显著为正"的放进正集，"显著为负"的放进负集，剩下的进错误/不确定区。这样阈值随设计状态和样本量自适应，而不是固定超参。

**分段奖励：**
$$
R_{\text{CA-POR}}(s,\omega)=
\begin{cases}
R_p\left(1-\dfrac{\ell-1}{n_{\text{pos}}}\right), & 1\le\ell\le n_{\text{pos}}\\[2mm]
-R_n\left(\dfrac{\ell-n_{\text{pos}}}{n_{\text{neg}}-n_{\text{pos}}}\right), & n_{\text{pos}}<\ell\le n_{\text{neg}}\\[2mm]
-R_L, & n_{\text{neg}}<\ell\le n
\end{cases}
$$
直觉与 HeurAgenix 一致：正集内部压缩差异（抗估值噪声），正负边界保留大跳变（强梯度），错误区固定惩罚；但**排名指标换成了"单位成本 LCB 效用 − 风险"，阈值换成统计量**。

#### 3.10.2 EDA-CPR：序数状态 + gate 预测

状态卡字段分三类：类别型 $Cat$（阶段、动作类型、预算档）、序数型 $Ord$（density 严重度、拥塞严重度、时序严重度、overflow 档、失败严重度）、二值型 $Bin$（是否合法、是否连通、是否发生过 gate 失败）。

HeurAgenix CPR 的指示函数奖励：
$$
R_{\text{CPR}}=\sum_{i=1}^m\Big[\mathbb{I}(\hat z_i=z_i)R_i^+-\mathbb{I}(\hat z_i\ne z_i)R_i^-\Big]
$$
**EDA 版扩展为：**
$$
R_{\text{EDA-CPR}}
=\sum_{i\in Cat}\Big[\mathbb{I}(\hat z_i=z_i)R_i^+-\mathbb{I}(\hat z_i\ne z_i)R_i^-\Big]
+\sum_{j\in Ord}\Big[R_j^+-\kappa_j\,|\hat z_j-z_j|\Big]
+\sum_{k\in Bin}\Big[\mathbb{I}(\hat b_k=b_k)R_k^+-\mathbb{I}(\hat b_k\ne b_k)R_k^-\Big]
$$
序数项允许"差一档"给部分分，符合"density 严重度 3 vs 4"这种只差一档的情况；同时保持对严重错判的强惩罚。所有标签都可由 checkpoint 真实 metrics 自动生成（不依赖人工标注）。

**额外加入 gate 预测与成本校准奖励（安全/预算关键）：**
$$
R_{\text{gate}}=R_g^+\mathbb{I}(\hat g=g)-R_g^-\mathbb{I}(\hat g\ne g),
\qquad
R_{\text{cost}}=-\big|\log(\hat c+1)-\log(c+1)\big|
$$

**总奖励与训练：**
$$
R_{\text{total}}
=\lambda_{\text{POR}}R_{\text{CA-POR}}
+\lambda_{\text{CPR}}R_{\text{EDA-CPR}}
+\lambda_gR_{\text{gate}}
+\lambda_cR_{\text{cost}}
+\lambda_{\text{fmt}}R_{\text{fmt}}
$$
$$
\max_\theta\ \mathbb{E}_{z\sim\mathcal{D}_{\text{offline}}}\ \mathbb{E}_{a\sim\pi_\theta(\cdot|z)}\big[R_{\text{total}}(z,a)\big]
$$
用 **GRPO**（组内相对优势）：
$$
\hat A^{(g)}=R_{\text{total}}^{(g)}-\frac{1}{G}\sum_{g'=1}^{G}R_{\text{total}}^{(g')}
$$
同一状态采 $G$ 条 heuristic/参数序列，组内比较；这与 HeurAgenix 的训练流程兼容，只是奖励项换成了 EDA 版。

### 3.11 与 HeurAgenix 公式的对应关系

| HeurAgenix 原方法 | HA-PR 新模型 | 变更类型 | 为什么更适合 EDA |
|---|---|---|---|
| 状态 $z$：低维问题状态 | $s=(g,d,x_g,m_g,b,h)$：checkpoint + 双表示 | 扩展 | 高维版图无法塞进 LLM；checkpoint 可重放 |
| 启发式 $H:\mathcal{Z}\to\mathcal{O}$ | 契约化 option $\omega=(k,\theta,\tau)$ | 替换/扩展 | 工具参数、停止条件、成本、回滚都需要显式建模 |
| 固定 $M=5$ 步 | option 时长 $\rho(\omega)$ 随机，停止条件可学习 | 扩展 | EDA 中固定步数不合理 |
| $\min Q$（Eq.1） | constrained semi-MDP option Bellman | 等价转写+约束扩展 | 目标从标量代价变为多目标效用 + 硬约束 + 预算 |
| Monte-Carlo TTS 平均 | 多保真 LCB/UCB + 自适应升保真 | 替换 | signoff 昂贵，代理有偏，不能假装无偏 |
| Alg.1 单操作 $\Delta_k$ | checkpoint 级反事实 $\delta_i$ + Shapley $\phi_i$ | 等价转写+扩展 | 影响延迟到 routing，需显式 credit |
| POR（固定 $n_{pos},n_{neg}$） | CA-POR：成本感知排名 + 统计显著阈值 | 扩展 | skill 成本异构；阈值不该手拍 |
| CPR（指示函数） | EDA-CPR：类别 + 序数 + gate + 成本校准 | 扩展 | EDA 状态多为序数，安全/成本字段关键 |
| GRPO 微调 | 同 GRPO，奖励项增加 gate/cost | 保留+扩展 | 训练流程可复用，风险/成本进入学习信号 |
| 演化 = LLM 读正负轨迹 | 演化 = 反事实证据 + 契约 + 多保真门控晋升 | 扩展 | 防止错误归因和"越改越不安全" |

### 3.12 公式来源与准确性声明（防止把"示意"当原文）

- **原式转写（保真）：** Eq.(1) 的 $V(z,t)$、$Q(z,H,t)=V(T^M(z,H),t-1)$、$\pi^\star=\arg\min Q$；Algorithm 1 的 $\Delta_k$、$k^\star$；POR 的分段线性结构；CPR 的指示函数结构；TTS 的 $\hat Q_H=\frac1T\sum_t C(S_t)$。
- **EDA 扩展（本文新增）：** shield 算子 $\mathcal{S}_k$；半 MDP 的 $\gamma^\rho$ 与 option Bellman；预算约束与机会约束；LCB/UCB 分数；多保真观测模型与升保真规则；势函数 shaping $\gamma^\rho\Phi(s')-\Phi(s)$ 及悲观修正；Shapley credit；双层演化目标与晋升判据；CA-POR 的"单位成本 LCB"排序与统计阈值；EDA-CPR 的序数与 gate/成本项。
- **明确标为"示意"的公式：** HPWL/density/overflow/WNS/TNS 是标准 EDA 指标定义（非本文创新，用于统一口径）；$\Phi(s)$ 的线性形式和权重是工程示意，实际应通过 surrogate 学习和校准；LCB 的正态近似是首版工程近似，样本少时建议用 bootstrap/序贯置信序列。

---

## 4. 简单报告说明（面向拍板）

### 4.1 我们提出了什么（5 句话）

1. **流程上：** 把 HeurAgenix 的"演化 + 选择"升级为 **Phase O 离线准备 → Phase R 在线 shielded 执行 → Phase E 门控演化 → Phase D 部署/蒸馏** 的四段式闭环；阶段图为 placement/routing 的可回退有向图，而不是固定链。
2. **表示上：** 状态用 **checkpoint + 双表示**（LLM 状态卡 + 代理图特征）；动作从"启发式函数"变成 **带参数、停止条件、成本、契约的 option**；LLM 不输出几何。
3. **数学上：** 用 **BMF-CSMDP** 统一描述"预算约束 + 硬 gate + 多保真评估 + 多目标效用"下的布局布线决策，给出 option Bellman、机会约束、LCB/UCB 选择分数三个核心公式。
4. **信用分配上：** 用 **下游感知势函数 shaping + checkpoint 反事实重放/Shapley** 解决"placement 好坏要到 routing/signoff 才知道"的延迟反馈问题。
5. **学习与演化上：** 把 POR/CPR 改成 **CA-POR（成本感知 + 统计阈值）** 与 **EDA-CPR（序数状态 + gate/成本预测）**；外层用 **LCB(ΔU)>0 且 UCB(违规)<ε** 的门控判据做 skill 晋升。

### 4.2 为什么能提升 EDA 适配性

| EDA 适配难点 | HA-PR 对应机制 | 可在哪个指标上验证 |
|---|---|---|
| LLM 不懂版图几何 | 只输出 skill id + 参数 + horizon；几何交给工具 | parse rate、非法动作率、gate 通过率 |
| 工具执行贵、状态高维 | checkpoint + 状态卡摘要 + 代理图特征 | LLM token 数、状态卡可读性/字段准确率 |
| 一次评估分钟~小时 | 多保真 LCB + 自适应升保真 | time-to-target、单位预算评估候选数 |
| 正确性是硬红线 | 契约 shield + L0–L3 验证栈 + 回滚 | gate 通过率、非法解浪费次数、L3 失败率 |
| 设计族异构 | 阶段条件 + 设计族条件 skill 库 + QD archive | 跨族泛化、最差族指标 |
| 动作成本异构 | CA-POR 按"单位成本 LCB 效用"排序 | 单位 tool-hour 的 PPA 改进、API 成本 |
| 状态是序数/多档 | EDA-CPR 序数奖励 + gate/cost 预测 | selector regret、top-k recall、校准误差 |

### 4.3 为什么可能提升最终优化效果

| 机制 | 因果链 | 期望看到的最终指标 |
|---|---|---|
| 契约 shield | 非法解在 L0/L1 被挡掉，搜索预算集中在合法空间 | 无效评估次数↓、gate 通过率↑ |
| 多保真 LCB | 同预算下评估/晋升更多候选；不确定时升保真防止代理欺骗 | 同 tool-hour 的 HPWL/overflow/WNS 更优；time-to-target↓ |
| 跨阶段 shaping | placement 阶段就感知 GRT overflow/post-route 时序；减少近视 | post-route overflow↓、WNS/TNS↓、DRC↓ |
| 反事实信用 | 演化只改真正影响最终结果的决策，样本效率高 | 达到目标质量所需评估次数↓、晋升率↑ |
| HVI + CVaR | 多目标不揉权重；约束最差设计不爆炸 | 超体积改进↑、最差族/最差 seed 不退化 |
| CA-POR + EDA-CPR | selector 学会珍惜昂贵调用、读懂序数状态 | selector top-1 regret↓、单位预算效用↑、跨族稳定性↑ |

**重要边界（必须写进论文/报告）：** 以上是"机制 → 期望指标"的假设，不是已证实结论。严格"确定性提升"在开放 EDA flow 中不可证；可证明的是：
- **点态不劣化**：候选 skill 必须通过 gate 且优于冻结基线才被采用，否则回滚（需要配对评估/fallback）。
- **统计提升**：在留出设计族上报告配对 LCB 和置信区间（默认 `LCB(Δ_composite)>0`）。
- **风险有界**：`UCB(P(gate fail)) < ε` 与 CVaR 约束。

### 4.4 实验设计与验收（把 claim 变成可测命题）

**五个可证伪假设：**

| 编号 | 假设 | 对照 | 主指标 | 验收门槛（示例） |
|---|---|---|---|---|
| H1 | 契约 shield + option 流程比无约束流程更适配 EDA | random skill / 静态最佳 skill | gate 通过率、单位 tool-hour 效用 | gate 通过率 ≥ 99%；非法解浪费次数下降 > 50% |
| H2 | 多保真 LCB 比单保真/固定 rollout 更省评估预算 | 固定 F3 / 固定比例 | time-to-target、同预算候选数 | 同预算下 `LCB(ΔU)` 提升；time-to-target 下降 > 20% |
| H3 | 跨阶段 shaping 减少 placement 近视 | HPWL-only reward | post-route overflow、WNS/TNS、DRC | overflow 与 WNS 配对 LCB > 0 |
| H4 | CA-POR + EDA-CPR 优于 vanilla GRPO 与原始 POR | vanilla GRPO / raw Q selection | selector regret、top-k recall、最终 PPA | top-1 regret 下降；跨族不劣化 |
| H5 | 反事实信用 + 门控演化优于随机/LLM 直接读日志 | random mutation / LLM bottleneck | 达到目标质量所需评估次数、晋升率 | 同预算下 time-to-target 下降；gate 违例不增加 |

**Baselines：**

- B0：OpenROAD/OpenLane 默认 flow；
- B1：从 skill 库随机选；
- B2：静态最佳 skill（在 train 上调好，固定使用）；
- B3：BO / bandit / ISAC 调度（预算对齐）；
- B4：HeurAgenix 风格 raw TTS（无多保真、无成本、无风险项）；
- B5：HA-PR w/o cross-stage shaping；
- B6：HA-PR 完整版；
- B7：API selector vs 蒸馏本地 selector（成本/质量对照）。

**评测协议：**

1. 按 design family 切分 train/val/test（控制、数据通路、存储、宏密集、拥塞型至少 5 类）；test 冻结。
2. 每个设计 ≥3 seeds；同一 (design, checkpoint, seed) 做配对 A/B；预算对齐（相同 tool-hour/API token）。
3. 统计：先按 design 聚合再按 family 分层 bootstrap，报 95% CI；用序贯置信序列支持"边跑边停"。
4. 报告：均值、中位数、最差族、CVaR、失败案例；禁止只报最好 run。
5. 消融：B0→B6 逐项加机制，明确每项贡献。

**综合验收（Phase 1 过关线）：**

- baseline 同一命令重复 3 次指标在容差内；
- 至少 1 个 skill 在 ≥2 个设计族上 `LCB(ΔU) > 0`；
- selector 的 top-1 regret 显著低于随机/原始 TTS；
- 所有留出设计 gate 通过率不下降；
- 所有结果有 `meta.json`（design/tool commit/PDK/skill version/prompt/seed/runtime）。

### 4.5 最小可执行 Phase 0（1–2 周，建议立刻做）

1. **工具链：** OpenLane1 + sky130A，先跑 `spm`、`gcd`；按阶段存 ODB/DEF checkpoint。
2. **指标与 gate：** 每阶段定义 3–5 个指标 + 硬门禁（可直接沿用 §2.3 表）。
3. **6 个 L1 skill：** placement 3 个（density/wirelength 权重、timing-driven 权重、legalize 顺序）、routing 3 个（net ordering、layer adjustment、RRR 批策略），全部带契约、单测、fallback。
4. **验证栈 L0/L1：** 先实现 schema 检查 + 重叠/row-legal/连通性/固定对象检查 + 回滚；L2/L3 用现成 flow。
5. **Selector v0：** dsv4-flash + 3 候选；同时跑 random / oracle 两档作为上下界。
6. **数据规模：** 10–20 个 checkpoint × 3 seeds；记录 state card、动作、真实 Δ、成本、gate 结果。
7. **产出：** skill 的 $\delta_k$ 分布、selector regret/top-k recall、gate 通过率、复现命令与日志。

> 只有 Phase 0 的数据证明"skill 有效且能被稳定测量"，Phase 1 之后的反事实/多保真/演化才值得投入。这也是与 HeurAgenix 复现（A 档）并行的最小验证路径。

### 4.6 风险与对策

| 风险 | 后果 | 对策 |
|---|---|---|
| LLM 幻觉出不存在/不安全的命令 | 执行失败或破坏状态 | 只允许 skill id + 参数；allowlist + schema + sandbox + 超时 + 回滚 |
| 代理指标被 reward hacking | 代理变好、signoff 变差 | 代理只做筛选；L3 审计；悲观势函数；随机审计样本 |
| 多保真预算失控 | 评估成本爆炸 | 硬预算 + racing/early stop + 缓存 + 分层晋升 |
| 工具/seed 噪声导致归因错误 | 把噪声当提升 | 配对重放、同 checkpoint、固定 seed/版本、重复 ≥3 次 |
| 设计族过拟合 | 平均好、最差族崩 | 按 family 切分；报告最差族；QD archive + 跨族晋升 |
| skill 库膨胀/旧版本污染 | selector 质量下降 | 版本化 + Experience Bank 统计 + 定期退役 |
| contract 过严导致无候选 | flow 停滞 | 预留 fallback；先保守后放松；放松必须重新过 L2/L3 |
| PPA 权重拍脑袋 | 结论不可信 | 优先字典序/HVI；权重只作排序参考并做敏感性分析 |
| 反事实重放本身昂贵 | credit 计算不可行 | 单点重放 + 分组/Shapley 近似；只在关键 checkpoint 做 |
| API 模型版本漂移 | 结果不可复现 | 记录 model/date/prompt hash；固定 eval set；必要时蒸馏本地 |
| 修改 netlist/RTL 引入功能风险 | 正确性红线失守 | 第一阶段只做 physical implementation；禁止改 netlist |

### 4.7 需要拍板的默认值（建议直接采用）

| # | 决策 | 建议默认 | 理由 |
|---|---|---|---|
| 1 | 先 placement 还是 routing | **placement：legalize + timing/congestion refine** | checkpoint 好构造、验证快、与 HeurAgenix 复现并行 |
| 2 | 工具链 | **OpenLane1 + sky130A**，控制层逐步转 OpenROAD Python API | `eda-101/tools` 已跑通 |
| 3 | 初始 skill 等级 | **L1 参数级**；L2 紧随；L3 等 verifier 成熟 | 风险/收益曲线最健康 |
| 4 | 模型分工 | **dsv4-flash = selector + L1/L2 proposer**；L3/review 用更强模型（如有） | 成本/能力平衡 |
| 5 | 正确性门禁 | **DRC/LVS/STA + 阶段不变式**；第一阶段不改 netlist | 正确性优先 |
| 6 | 综合目标 | **gate + HVI**；首版字典序，研究版 HVI + CVaR | 避免不透明加权 |
| 7 | 评测规模 | **10–20 设计 × 3 seeds** 起步，按 pilot 方差扩样 | 先证明测量协议可靠 |
| 8 | 多保真 | **F0–F3 四档 + LCB/UCB**；F2 用 placement+GRT | 直接对准评估贵的痛点 |
| 9 | 蒸馏本地模型 | **先 API 打通、后蒸馏** | 与 HeurAgenix Qwen 路线一致 |
| 10 | 目录 | 建议 `heura_repro/eda/` 或独立 `heura-eda/`，与 TSP 复现隔离 | 代码/数据/结果不混 |

---

## 5. 参考资料

1. Wang et al. *HeurAgenix: Leveraging LLMs for Solving Complex Combinatorial Optimization Challenges*, arXiv:2506.15196v2. （§2.1 问题定义；§3.1 Algorithm 1；§3.2 Eq.(1)+TTS；§3.3 POR/CPR+GRPO）
2. 本项目 `01_文献阅读报告_HeurAgenix.md`（公式逐条转写与论文/代码差异）
3. 本项目 `04_EDA迁移与Skill自进化设计建议.md`（契约 skill、验证栈、统计协议）
4. 本项目 `05–08`（算法生成/筛选路线、术语、突破方向）
5. Sutton, Precup, Singh. *Between MDPs and semi-MDPs: A framework for temporal abstraction in reinforcement learning*, AIJ 1999.（option / semi-MDP）
6. Ng, Harada, Russell. *Policy invariance under reward transformations: Theory and application to reward shaping*, ICML 1999.（势函数 shaping）
7. Altman. *Constrained Markov Decision Processes*, 1999.（约束 MDP / 机会约束）
8. Rockafellar, Uryasev. *Optimization of Conditional Value-at-Risk*, 2000.（CVaR）
9. Zitzler, Thiele. *Multiobjective evolutionary algorithms: a comparative case study and the strength Pareto approach*, 1999.（hypervolume）
10. Li et al. *Hyperband: A novel bandit-based approach to hyperparameter optimization*, JMLR 2018.（多保真/racing）
11. Chen et al. *Optimal Computing Budget Allocation*（OCBA）相关工作。（多保真样本分配）
12. Shapley. *A value for n-person games*, 1953.（Shapley credit）
13. OpenROAD / OpenLane / DREAMPlace 官方文档与论文（工具链与指标口径）。

---

## 附录 A：状态卡示例（state_card.json）

```json
{
  "design": {"name": "spm", "family": "datapath", "pdk": "sky130A", "die_um": [0, 0, 1200, 1200]},
  "stage": "global_route",
  "checkpoint": {"id": "spm_gr_seed0", "tool_commit": "abc123", "seed": 0},
  "legality": {"overlap": 0, "row_legal": true, "fixed_objects_ok": true, "connectivity": 1.0},
  "metrics": {
    "hpwl_um": 123456.7, "density_overflow": 0.018,
    "route_overflow_pct": 2.31, "max_overflow_pct": 6.4,
    "wns_ps": -42.0, "tns_ps": -180.0, "drc": 0,
    "power_mw": 12.3, "area_um2": 45678.9, "runtime_s": 321.0
  },
  "severity": {"density": 2, "congestion": 3, "timing": 2, "routability": 3, "drc_risk": 1},
  "history": [
    {"action": "gr.layer_adjust", "params": {"m2": 0.1}, "result": "improved", "delta_overflow_pct": -0.4},
    {"action": "gr.net_order", "params": {"mode": "criticality"}, "result": "worse", "delta_overflow_pct": 0.2}
  ],
  "budget": {"time_left_s": 5400, "api_left": 180, "class": "tight"},
  "candidates": ["route.global.rrr_congestion_batch", "route.global.layer_adjust", "route.global.net_order"]
}
```

## 附录 B：skill 卡示例（YAML，placement + routing）

```yaml
- id: place.legalize.order_aware
  version: 1.0.0
  stage: legalization
  applicability: "存在 overlap 或 row 非法"
  params:
    order: {type: enum, values: [wns_first, density_first, left_to_right], default: wns_first}
    max_displacement_um: {type: float, range: [0.0, 5.0], default: 1.0}
    hpwl_guard_pct: {type: float, range: [0.0, 10.0], default: 2.0}
  contract:
    pre: ["global placement checkpoint 可读", "fixed macro/IO 未变"]
    post: ["overlap = 0", "row-legal = true", "HPWL 恶化 <= hpwl_guard_pct", "WNS 退化 <= 5 ps"]
    invariants: ["netlist hash 不变", "fixed objects 未动"]
    fallback: "restore checkpoint + baseline legalizer"
  cost: {runtime_s: {p50: 25, p90: 60}, api_calls: 0}
  implementation: {type: openroad_tcl, allowlist: [detailed_placement, check_placement]}
  evidence: {n_runs: 0, delta_utility_ci: null, failure_modes: []}

- id: route.global.rrr_congestion_batch
  version: 0.3.0
  stage: global_route
  applicability: "route_overflow_pct > 1.0 且预算允许"
  params:
    overflow_trigger_pct: {type: float, range: [0.0, 5.0], default: 1.0}
    max_iters: {type: int, range: [1, 20], default: 3}
    layer_bias: {type: list_float, default: [0.1, 0.1, 0.05]}
    order_mode: {type: enum, values: [criticality, congestion, pin_density], default: congestion}
  contract:
    pre: ["GRT 数据存在", "net 全部连通"]
    post: ["overflow 相比执行前下降", "无新增 DRC", "runtime <= 预算"]
    invariants: ["connectivity = 100%", "layer 方向合法"]
    fallback: "restore GR checkpoint + baseline global_route"
  cost: {runtime_s: {p50: 600, p90: 1800}, api_calls: 0}
  implementation: {type: openroad_python, allowlist: [ripup, reroute, global_route]}
  evidence: {n_runs: 0, delta_utility_ci: null, failure_modes: []}
```

## 附录 C：实验记录示例（meta.json）

```json
{
  "run_id": "20260921_spm_gr_ha_pr_seed0_b6",
  "design": "spm", "design_family": "datapath", "design_hash": "sha256:...",
  "toolchain": {"openroad": "commit/ver", "openlane": "ver", "pdk": "sky130A"},
  "flow": {"start_checkpoint": "spm_gr_seed0", "policy": "HA-PR", "skill_library_version": "v0.3.0"},
  "selector": {"model": "deepseek-chat/deepseek-v4-flash", "prompt_hash": "sha256:...", "temperature": 0.0},
  "seed": 0, "budget": {"time_s": 7200, "api_calls": 200},
  "decisions": [
    {"step": 1, "state_hash": "...", "candidates": ["..."], "chosen": "route.global.rrr_congestion_batch",
     "params": {"max_iters": 3}, "q_lcb": 0.42, "cost_hat_s": 600, "fidelity": "F1", "gate": "pass"}
  ],
  "final": {"gate_l3": "pass", "wns_ps": -35.2, "tns_ps": -120.1, "power_mw": 12.0,
            "area_um2": 45500.0, "wirelength_um": 118000.0, "drc": 0, "runtime_s": 6800},
  "artifacts": {"checkpoints": ["..."], "logs": ["..."], "report": "..."}
}
```

## 附录 D：与 04–08 的关系与下一步

- **`04`**：给出契约化 skill、守卫/回滚、验证栈、统计协议；本文把它升级为**统一数学形式 + 阶段图流程**。
- **`05/06`**：算法生成与在线筛选的备选路线；本文采用其中"多保真 + 反事实 + 门控演化"作为主骨架，其余路线作为消融/备选。
- **`07`**：术语与学习路线；本文出现的 $V/Q$、option、CVaR、HVI、LCB 等可在 `07` 查定义。
- **`08`**：框架突破 A–H；本文选取 A（反事实信用）+ B（多粒度多保真）+ C（正确性门禁）+ F（跨阶段协同）作为第一版主线，其余方向留作后续。
- **下一步（等拍板）：** 若按 §4.5 执行 Phase 0，产出 `harness + checkpoint + 6 skill + selector v0 + 配对报告`；据此再决定是否进入 Phase 1/2。

---

**报告结论一句话：** HeurAgenix 的"演化 + 选择"是很好的骨架，但直接用于布局布线的瓶颈在**状态表示、动作粒度、评估成本、正确性硬约束和跨阶段信用**；HA-PR 用"契约化 option + BMF-CSMDP + 多保真 LCB + 势函数/反事实信用 + CA-POR/EDA-CPR"逐项替换，给出了一条既有数学统一性、又能落到 OpenLane/OpenROAD 实验的迁移路线。
