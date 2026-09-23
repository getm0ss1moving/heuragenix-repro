# 从 HeurAgenix 迁移到 EDA 布局布线：Skill 自进化 + 可验证在线选择（设计建议稿 v0.1）

**日期：** 2026-09-20  
**配套材料：** `01_文献阅读报告_HeurAgenix.md`、`02_复现清单_HeurAgenix.md`、`03_执行决策记录_20260920.md`  
**API 口径：** 按 `03` 的决策，DeepSeek v4.1 flash（请求名 `deepseek-chat`，下称 dsv4-flash）承担“演化 proposer + 在线 selector”两个角色；如后续有更强的 DeepSeek reasoner 或本地 Qwen 蒸馏模型，可作为 reviewer/L3 代码合成/低成本推理的替代。

---

## 0. 结论先行（TL;DR）

1. **HeurAgenix 可直接迁移的是“双层结构”**：离线启发式演化（外层）+ 在线启发式选择（内层）。  
   不能直接照搬的是它隐含的四个低成本假设：状态廉价、动作是短序列、transition 廉价确定、terminal cost 精确且正确性由问题编码天然保证。EDA/芯片布局布线恰恰相反：一次 flow 至少分钟到小时级，signoff 昂贵，正确性是独立硬约束。
2. **把“启发式”重定义为 Skill = 带契约的可执行 option**。  
   一个 skill 不是一段 prompt 或一句策略，而是：`适用状态谓词 + 参数 + 受限可执行体（Tcl/Python/DSL）+ 前置检查 + 后置不变式 + 预估效果 + 代价模型 + 单测 + 历史证据 + fallback`。只有这种对象才能被 A/B 量化、门控晋升和回滚。
3. **让 LLM 做它最擅长的（状态理解、策略选择、参数/权重/触发条件/组合与停止），不要让它直接输出坐标、路径或版图几何**。  
   几何/数值搜索交给 DREAMPlace、OpenROAD、OpenLane、SA/QP 等底层求解器；LLM 是 hyper-heuristic 的“指挥”。
4. **正确性不能靠 LLM 保证，靠“契约 + 检查器 + 快照/回滚 + signoff 门禁”保证。**  
   性能提升也不能承诺“确定性提升”；工程上可做到两件事：
   - **点态不劣化**：同一设计上，候选 skill 只有通过门禁且优于基线才被接受，否则回滚/走基线（需要重复计算或 canary 机制）。
   - **分布上稳定改进**：在留出设计族上用配对实验 + 置信下界（LCB）做晋升，而不是看单次最好结果。
5. **建议的总体架构（三层 + 双循环）：**
   - **Skill Runtime**：skill 库、适用性判断、沙箱执行、契约检查、快照/回滚。
   - **Verifier Stack**：L0 schema/静态检查 → L1 快速不变量/连接性/合法性 → L2 局部 flow canary（如 global route + DRC）→ L3 全 flow signoff（DRC/LVS/STA with SPEF，PPA）。
   - **Selector/Evolver**：dsv4-flash 在线选 skill；同时作为 mutator 提出参数/触发条件/组合扰动，经 verifier 过滤后进入 skill 库。
   - **Experience Bank**：按设计族、状态特征、skill 版本记录 Q̂、真实效果、失败模式、成本，供检索与统计晋升/退役。
6. **落地顺序建议：**  
   ① 参数/阈值/顺序进化（L1）→ ② 触发条件/组合/停止条件进化（L2）→ ③ 受限 DSL/代码结构进化（L3）。  
   目标阶段：先 standard-cell placement 的合法化/时序修复，再全局布线 RRR，再做跨阶段联合 PPA。  
   先 OpenLane1 + sky130A 的 `spm` 等小设计打通度量，再扩到 ORFS / OpenLane 多设计族。
7. **对“skill 能否确定提升”的直接回答：**  
   在开放 EDA flow 中，**严格确定性提升不可证**（LLM 采样、工具版本/噪声、状态分布漂移都存在）。  
   可交付的是三层更强的声明：**可复现（同 checkpoint/seed/版本结果一致）→ 局部可验证（同一状态配对 A/B 的因果效应 + 置信区间）→ 部署可控（shield/rollback 保证不劣化，canary+shadow 保证上线风险有界）**。  
   统计上要达到“稳定”，用配对设计 + 分层 bootstrap/序贯置信序列，晋升条件示例：`LCB(Δ_composite) > 0` 且 `UCB(correctness_violation) < ε` 且成本未超预算；不满足的 skill 只能停留在 candidate。

---

## 1. 为什么不能直接套用 HeurAgenix 的实例结构

HeurAgenix 的抽象是：`z`(状态) → `H`(启发式) → `O`(一步操作) → `T`(确定性转移) → `C(S)`(终点代价)，并且有便宜的 Monte-Carlo TTS 来估 `Q(z,H)`。EDA 布局布线的情况：

| 维度 | HeurAgenix 假设 | EDA 现实 | 迁移对策 |
|---|---|---|---|
| 状态 | 低维特征 + 部分解 | DEF/ODB 快照、网表图、时序/拥塞/版图状态，高维异构 | **状态卡（LLM 用）+ 图/向量特征（surrogate/Q 网络用）双表示** |
| 动作/启发式 | 有限启发式池中的函数 `Z→O` | 工具参数、策略调度、局部搜索模板、跨阶段 flow 选择，动作空间巨大 | **Skill = 类型化 option**，仅暴露少量参数和组合接口 |
| 转移 | 单步、便宜、确定 | 一次 placement/route 分钟~小时，工具版本/seed 有噪声 | **checkpoint/snapshot + 子进程隔离 + 配对重放 + seed 冻结** |
| 终点代价 | 一次 rollout 即可得精确 cost | 最终 PPA/DRC/STA 昂贵；HPWL/overflow 是代理 | **多保真：L0~L3 验证栈 + 代理校准 + 主动 signoff 采样** |
| 正确性 | 由问题编码保证（TSP 路径一定成环） | 重叠、连通性、DRC、LVS、时序约束是独立硬门槛 | **契约/守卫/回滚；LLM 不碰 netlist 与几何合法性** |
| 监督密度 | 可跑大量 TTS | signoff 采样稀少 | **离线 checkpoint replay/反事实评估；顺序决策用带噪偏好监督（POR 思路）** |
| 反馈形式 | 标量 gap | 多目标向量（timing/power/area/DRC/runtime）且有约束 | **约束多目标：feasibility gate + hypervolume/Pareto 改进 + CVaR 风险** |

---

## 2. 统一形式化：带守卫的约束 option MDP（EDA 版）

### 2.1 状态与动作

```
s ∈ S：  一个可恢复的 flow checkpoint
         s = (stage, odb_snapshot, netlist_graph, state_card, metric_summary, budget)

a：      一个 skill 的调用 option
         a = (skill_id, θ, h)
         skill_id：技能库条目（见 §3）
         θ：连续/离散参数（density、weight、order、batch size…）
         h：horizon/停止条件（执行到事件/步数/时间预算，替代 HeurAgenix 的固定 M=5）

T(s,a)： shield( apply_skill(s, a) )
         apply_skill 调 OpenROAD/OpenLane 等工具
         shield 由 §3.4 的契约检查器实现；不通过则 rollback 或走 fallback
```

### 2.2 奖励与目标

建议 reward 是**向量**而不是标量：

```
r(s,a) = [
  gate_feasible,          # 0/1：硬约束是否全通过
  ΔWNS, ΔTNS,             # timing（越大越好，放在约束或目标里）
  -ΔPower, -ΔArea,        # PPA（归一化后）
  -ΔWirelength, -ΔOverflow,
  -Runtime, -LLM_cost, -APICalls
]
```

目标（约束 MDP 视角）：

```
maximize    E[ U(quality_vector) ]           （建议 U 用 hypervolume / 约束加权效用）
subject to  P(gate_violation) ≤ ε            （正确性 chance constraint）
            Runtime ≤ B, APICalls ≤ B_api
```

- **硬约束（gate）**：placement 的重叠/越界/固定对象被改动、routing 的连通性/DRC/LVS/容量；任一失败直接拒绝该 skill 执行结果。
- **软目标**：timing/power/area/wirelength/overflow。建议先用字典序/约束法，不要一上来把 PPA 揉成一个不透明的加权和。
- **尾部风险**：对最差 case 用 CVaR 或 `worst-case improvement` 作为晋升门槛，防止“平均好但个别设计爆炸”。

### 2.3 双循环

```
外层（慢、贵、稀疏）：
  skill 库演化：LLM 基于对比轨迹提出 L1/L2/L3 扰动 → verifier 过滤 → 候选 skill
                → 留出设计族配对评估 → 达到晋升门槛才进入主库

内层（快、便宜、稠密）：
  在线选择：dsv4-flash / 蒸馏 selector 读 state card + skill cards
            → 输出候选 (skill_id, θ, h) → 廉价 TTS/代理估值 → shield 执行
            → 记录 (s,a,r,Q̂,真实结果) 进 Experience Bank
```

与 HeurAgenix 的对应关系：

| HeurAgenix | EDA 迁移版 |
|---|---|
| Problem state z | stage checkpoint + 双表示状态卡 |
| Heuristic H | 契约化 Skill/option |
| `T^M(z,H)` 固定 M 步 | option 执行到触发停止条件；必要时可做成 macro-action |
| Monte-Carlo TTS 估 Q | 代理模型 + 局部 canary + 少量真 rollout；多保真估值 |
| 启发式池 H | 带版本/统计/适用域的 Skill Library |
| Algorithm 1 演化 | 对比正/负轨迹找关键操作 → LLM 生成策略/参数/结构扰动 → verifier 验证 |
| POR+CPR 微调 | 状态卡正确性 reward（CPR 类）+ 候选排序偏好 reward（POR 类）的蒸馏 |
| Table 6 在线选择 | dsv4-flash 或蒸馏模型选 skill；工业指标看最终 signoff |

---

## 3. Skill 的定义、Schema 与安全执行

### 3.1 定义

**Skill 是一个带版本的可执行 option；它有明确的适用条件、参数域、后置不变式和失败 fallback。**  
它的价值不在“prompt 写得好”，而在“可重复执行 + 可度量 + 可回滚”。

一个 skill 至少包含 10 个字段：

| 字段 | 说明 |
|---|---|
| `id / version` | 版本化；同一 id 不同版本可 A/B |
| `stage` | floorplan / placement / cts / global_route / detailed_route / signoff |
| `applicability(s)` | 输入状态谓词：如“global route overflow>2%”“存在 timing violation” |
| `params` | JSON Schema：类型、范围、枚举、默认值 |
| `implementation` | 受限执行体：OpenROAD Tcl 模板 / allowlist Python API / 自定义 DSL；**不允许任意 shell** |
| `preconditions` | 执行前状态检查和资源检查 |
| `postconditions/invariants` | 硬/软约束：如“无重叠”“连通性 100%”“WNS 退化 ≤ guardband” |
| `effect_model` | 廉价预测 `Δmetric`（代理或历史统计）及不确定性 |
| `cost_model` | 预估 runtime / CPU / API calls / 显存 |
| `tests & evidence` | 单测/属性测试、历史 A/B 结果、置信区间、失败模式、provenance |

### 3.2 示例 A：placement 的合法化 skill

```yaml
id: place.legalize.order_aware
version: 1.0.0
stage: placement
applicability: "global placement 已跑完，存在 overlap 或 row 非法"
params:
  max_displacement_um: {type: float, range: [0.0, 5.0], default: 1.0}
  order: {type: enum, values: [left_to_right, density_desc, wns_first], default: wns_first}
  preserve_wns: {type: bool, default: true}
implementation:
  type: openroad_tcl
  body: |
    # 示意：顺序策略由参数控制，具体命令以 f9ec60f/OpenLane 版本 help 为准
    set_placement_padding -masters ... 
    detailed_placement
    check_placement
preconditions:
  - "fixed macro / IO 未被改动"
postconditions:
  - "no overlaps"
  - "all instances row-legal"
  - "HPWL increase <= 2%"
  - "WNS degradation <= 5 ps else fallback"
fallback: "restore checkpoint; run baseline legalizer"
evidence: "见 experience/place_legalize_order_aware.jsonl"
```

### 3.3 示例 B：global routing 的 RRR/参数 skill

```yaml
id: route.global.rrr_congestion_batch
version: 0.3.0
stage: global_route
applicability: "global route overflow > 1% 且 runtime 预算足够"
params:
  overflow_trigger: {type: float, range: [0.0, 5.0], default: 1.0}
  max_iters: {type: int, range: [1, 20], default: 3}
  layer_adjustment: {type: list[float], default: [0.1, 0.1, 0.05]}
  cost_shaping: {type: enum, values: [uniform, congestion_penalty, critical_first], default: congestion_penalty}
implementation:
  type: python_allowlist
  api: [openroad.grt.ripup, openroad.grt.reroute, openroad.grt.global_route]
preconditions: ["GRT 数据存在，layout 连通性可读"]
postconditions:
  - "overflow 相比执行前下降"
  - "全部 net 连通"
  - "无新增 DRC"
fallback: "restore GR checkpoint; 使用 baseline global_route"
```

### 3.4 三级进化：从安全到开放

| 级别 | 演化对象 | 风险 | 建议顺序 |
|---|---|---|---|
| L1 | 参数、权重、阈值、顺序 | 低 | 第一批做 |
| L2 | 触发条件、skill 组合、停止/fallback 策略 | 中 | 第二批 |
| L3 | 新算子结构、受限 DSL/AST 代码、复杂控制流 | 高，必须沙箱+静态检查+形式化/单测 | 最后，且有足够 verifier 后再做 |

**关键建议：** 在 EDA 里不要一开始让 LLM 直接生成任意 Python/Tcl 并执行。先把「参数化模板 + 允许的 API 列表 + 组合」做出来，L1/L2 通常就能拿到大部分收益，且错误面可控。L3 用受限 DSL，所有生成代码必须通过 `compile + AST allowlist + 单元/属性测试 + 小设计 canary`。

### 3.5 守卫与回滚（保证“正确性不打折”的核心）

每个 stage 执行前保存 ODB/DEF checkpoint；skill 执行后依次过检查：

```
L0 静态：schema、参数范围、API allowlist、seed/超时
L1 快检：parse/连通性/重叠/row 合法/层规则/资源容量/简单 ERC
L2 canary：局部流程或部分 net/局部区域跑通（如若干条 net 的 GR+DR）
L3 signoff：完整 DRC/LVS/STA（含 SPEF）、功耗/面积、时序 corner
```

任一硬检查失败 → **restore checkpoint + 记录失败**；质量退化但硬检查通过 → **不晋升，diff 存档；生产中由 fallback 接管**。  
这样系统在**已验证指标集**上可以做到点态不劣化；对未见设计的泛化仍由统计门控管理。

### 3.6 EDA 正确性不变量清单（初版）

| 阶段 | 必须守住的不变量 |
|---|---|
| placement | netlist 不变；fixed macro/IO 不动；无重叠；在 die/core 内；row/site 合法；density/blockage 约束满足；不引入非法布置 |
| floorplan/macro | 形状/朝向/通道合法；halo/blockage 不冲突；电源规划预留；设计规则间距 |
| CTS | 时钟拓扑合法；skew/latency 在门限内；不产生新 DRC；buffer 合法 |
| global routing | 100% 连通；overflow/容量约束；层方向/轨道合法；via 规则；天线规则可不恶化 |
| detailed routing | 无短路/开路；DRC=0（目标）；via/enclosure 规则；时序/串扰不恶化超出 guardband |
| signoff | DRC/LVS/ERC 通过；STA 在 corner 下满足或退化有界；版图与网表一致 |

> 如果暂时只做 physical-only 优化，netlist/HDL 不进 LLM 的动作空间，可以先把“逻辑功能正确性”风险隔离；这也是建议的默认边界。

---

## 4. 如何量化 skill 的成效（重点一）

### 4.1 先分清三种“提升”，避免概念混淆

| 声明 | 测量对象 | 方法 | 能给出什么 |
|---|---|---|---|
| 可复现 | 同 checkpoint/seed/prompt/工具版本，同 skill 的输出是否稳定 | 重复运行/固定 seed/版本冻结 | “可重复”，不等于“有提升” |
| 局部因果效应 | 同一个状态 s，用 skill vs 基线分别走完后续 flow 的差异 | **配对 A/B + checkpoint replay** | `δ_k(s)` 的均值/分布 |
| 部署/群体效应 | 分布 μ 上 `π_base⊕skill` vs `π_base` | 留出设计族上的配对实验 | 统计提升及置信区间 |

推荐数值定义：

```
局部效应：  δ_k(s) = U( Flow_rest(s, k, freeze_policy) ) - U( Flow_rest(s, baseline, freeze_policy) )
条件效应：  Δ_k = E_{s~μ_k}[ δ_k(s) ]
部署效应：  Δ_deploy = E_{design~D_test}[ J(π_skill) - J(π_base) ]
其中 U 是经过 gate 的 PPA 效用（见 4.3），μ_k 是“skill 被选中且适用”的状态分布
```

### 4.2 实验协议：checkpoint replay + 配对 A/B

1. **固定变量**：同一 design、同一 PDK、同一工具版本、同一 seed、同一机器/负载窗口；LLM 版本与 prompt hash 入日志。
2. **checkpoint**：在 `floorplan/place/global_route` 后保存 ODB/DEF；测试某个 skill 时从同一 checkpoint 恢复，分别跑 `baseline` 与 `skill`，其余阶段用**冻结的参考策略**走完。
3. **配对**：同一 (design, checkpoint, seed) 下的 baseline 和 skill 是配对样本；跨设计用分层 bootstrap，先按 design 聚合再按 family。
4. **随机化/平衡**：多 skill 的 A/B 顺序随机；同一组实验尽量同一时段跑，减少机器/温度/网络影响。
5. **预算对齐**：baseline 消耗的时间/rollout/API token 与 skill 一致；否则比较不公平。
6. **留出原则**：用于演化/提示设计的 design 不能作为最终测试；最好按 **design family / 规模 / 结构** 切分，而不是同设计随机 instance（EDA 中随机实例切分容易高估泛化）。
7. **重复次数**：选择类实验每状态重复 G=5~12 次；最终设计级实验每设计 ≥3 seeds；初始阶段 10~20 个设计、每设计 3 seeds，按 pilot 方差决定是否扩样。

### 4.3 指标与综合分数

**第一层：正确性门禁（gate，不可交易）**

- placement：`overlap=0, row-legal=1, 固定对象未变, netlist hash 未变`
- routing：`connectivity=100%, DRC=0, overflow≤baseline, LVS/ERC pass`
- STA：`WNS/TNS` 不低于 baseline - guardband；corner 覆盖按项目要求

**第二层：质量向量（每个设计归一化后比较）**

- `ΔWNS`, `ΔTNS`（ps，或相对改进）
- `ΔPower`（mW，internal/leakage/total 分开）
- `ΔArea`（um² 或相对）
- `ΔWirelength/ΔVia`
- `ΔOverflow`, `ΔDRC`
- `ΔRuntime`, `ΔAPICalls`, `ΔToken`
- 方差/最差 case（CVaR 或 P90 loss）

**第三层：综合效用（建议从简到繁）**

- 方案 A（首版，最稳）：**字典序**：先 gate，再保证所有指标不劣化的前提下，按约定顺序优化（例如 WNS→TNS→power→area→runtime）。
- 方案 B：**约束归一化加权**：把各指标相对 baseline 的改进做鲁棒归一化（median/MAD 或分位数），权重只作排序参考。
- 方案 C（推荐研究版）：**Hypervolume Improvement (HVI)**：在 PPA 目标空间构造 Pareto 前沿（WNS/TNS、power、area、runtime），用相对 baseline 前沿的超体积改进作为 quality 奖励；HVI 天然处理多目标，不需要拍权重。

> 不要用 HPWL 单独作为最终奖励：它是代理，容易 reward hacking。HPWL 可以进 reward 的 shaping 项，但门禁和最终验收必须落到 signoff/metrics.csv 的真实指标。

### 4.4 统计推断与晋升门槛

- **配对检验**：跨设计用 paired bootstrap / Wilcoxon signed-rank；不是对 decision 级样本做检验（会有相关性）。
- **分层 bootstrap**：design → seed → decision 三层；报均值和 95% CI。
- **序贯决策**：用置信序列（confidence sequence）支持“边跑边停”，避免反复看 p 值。
- **晋升条件示例**（可调）：
  1. 正确性：在 ≥N 个留出设计上 gate 全通过；`UCB(P(gate fail)) < 1%`。
  2. 质量：`LCB(Δ_composite) > 0`，且任一单项指标相对基线恶化不超过阈值。
  3. 成本：平均 runtime/token 超支 ≤ 预算；P95 超时 ≤ 门限。
  4. 可复现：同条件 3/3 次重跑结果在容差内。
  5. 泛化：至少跨 2 个 design family，而不是单一设计。
- **不显著怎么办**：标记为 `inconclusive` 而不是“无提升”；记录样本量和置信区间宽度，决定是否扩样。这能防止“小样本恰好变好 → 上线 → 翻车”。

### 4.5 消融：把“skill 的功劳”拆开

至少做 6 组、预算对齐的消融：

```
B0: baseline flow
B1: + 随机从 skill 库里选（测“库本身有没有用”）
B2: + dsv4-flash selector（测“LLM 选择有没有用”）
B3: + selector + TTS 候选估值（测“搜索/rollout 有没有用”）
B4: B3 + L1/L2 演化出的 skill（测“自进化有没有用”）
B5: B3 + 蒸馏本地 selector（测“API 模型 vs 本地模型”）
```

每组在同一组留出设计上跑配对实验，报告 `Δ vs B0` 的置信区间。这样可以精确回答“skill 的提升到底来自库、LLM、TTS 还是进化”。

### 4.6 “确定性提升”到底怎么表述

- **同状态、同版本、同 seed**：skill 本身可确定性执行；但这只是可复现。
- **对某设计、某 flow**：若候选必须通过“最终 signoff 更优或 gate 更稳”才被采用，否则回滚 baseline，则可以得到**相对于该设计的点态不劣化**（代价是要跑候选 + 可能并行跑 baseline）。
- **对未见设计分布**：无法证明确定提升；用 LCB/UCB 做统计声明，并保留 fallback。工程上把这叫“**高概率稳定改进 + 有界风险**”。
- **对 skill 的局部效果**：某些 skill 可以在线验证（例如合法化后 overlap 必减、连通性必增），这类可以给“**certified improvement**”的强声明；PPA 类目标一般不能便宜地证明，只能统计。

---

## 5. dsv4-flash 的角色、Prompt 与工程细节

### 5.1 角色分工

| 角色 | 频率 | 建议模型/策略 | 输出 |
|---|---|---|---|
| 在线 skill selector | 每决策点（多） | dsv4-flash，temperature 0~0.3，JSON schema，n candidates | `{skill_id, params, horizon, rationale, fallback}` |
| TTS/候选评估 | 每决策点 | 代理模型或局部真实 rollout，不是 LLM | `Q̂(s,a)` 及不确定性 |
| 演化 proposer（L1/L2） | 每轮演化（少） | dsv4-flash，多候选 + 对比正负轨迹 | `{扰动类型, 参数/触发/组合, 测试, 预期效果}` |
| L3 代码合成 | 很少 | 强模型优先；dsv4-flash 至少多采样 + verifier 过滤 | 受限 DSL 代码 + 单测 |
| reviewer/critic | 可选 | 强模型或同一模型第二次调用 | 风险提示；**不替代工具验证** |
| 最终裁决 | 永远 | OpenROAD/OpenLane/STA/DRC/LVS 检查器 | 客观结果 |

### 5.2 Prompt 结构（建议固定模板）

```
[system]
你是 EDA flow 的 hyper-heuristic selector。只允许从下面 skill 卡中选择。
必须输出 JSON；不能输出坐标、DEF 片段或 shell。

[state card]
stage / legality / key metrics / top congested gcells / critical endpoints /
constraints / previous actions and effects / remaining budget / uncertainty

[skill cards]
id / version / applicability / params schema / cost / historical effect stats /
risk flags / fallback

[budget]
max_steps, max_runtime, max_api_calls

[output JSON schema]
{ "skill_id": ..., "params": {...}, "horizon": "...", "why": "...", "fallback": "..." }
```

### 5.3 为什么要这样设计

- **状态卡**解决 LLM 上下文窗口问题：不塞完整 DEF/log，而是给结构化摘要（图特征另有向量表示给 surrogate）。
- **skill cards**把选择空间压缩到可审计的少量选项；避免 LLM 幻觉出不存在的工具命令。
- **JSON schema + allowlist**让解析失败可检测；失败重试或退回检索/基线。
- **TTS 不交给 LLM 拍脑袋**：LLM 提议候选，代理/真 rollout 给 Q̂，最后按 Q̂ + 风险选。
- **不确定性**：让 selector 输出置信度或由 Q̂ 方差给出；低置信时自动升级到更多 rollout 或走 baseline。

### 5.4 缓存、成本与版本

- `state_hash + skill_library_version + model_version` 作为缓存 key；同状态重复决策直接复用。
- 批量/并发建议沿用现有约束：分批 + 3 并发 + 每批落盘（`03` 已验证），避免限流和丢结果。
- 记录每次调用的 model 版本、日期、prompt hash、token 数、输出；API 模型会漂移，必须能回归测试。
- 做 20~50 条固定 eval prompt，作为“模型漂移监控”；parse rate/selection accuracy 下降就切 distilled 或回滚 prompt。

### 5.5 蒸馏到本地模型（把 HeurAgenix 的 Qwen 路线接到 EDA）

- 先用 dsv4-flash 跑探索/标注，收集 `(state_card, skill_set, Q̂, 真实结果)`。
- 训练/微调本地 Qwen 7B（或 14B）selector：
  - **POR 类**：对候选 skill 的 Q 排序做偏好奖励（正集/负集），抗 rollout 噪声。
  - **CPR 类**：状态卡字段预测正确性（stage、legality、congestion level、timing severity），即“看懂状态”奖励。
  - 可选 vanilla GRPO 作为消融，对应 HeurAgenix Table 4 的对照。
- 比较“dsv4-flash API vs 本地小模型”在留出设计上的部署效应与 token 成本；这是把论文框架推到 EDA 的自然延伸。

---

## 6. 在现有框架下稳定提升 LLM“设计能力”的机制

这里的“设计能力”建议拆成三层来优化，否则容易把“模型权重能力”和“系统工具能力”混在一起：

| 层级 | 提升手段 | 验证方式 |
|---|---|---|
| 表现层（LLM 输出） | 结构化动作空间、skill cards、few-shot 轨迹、状态卡 | parse rate、action validity、top-k recall |
| 决策层（选择/组合） | Experience Bank 检索、上下文 bandit、TTS、校准/弃权 | regret、Q 校准误差、决策成功率 |
| 系统层（最终 PPA/正确性） | verifier、guard/rollback、多保真评估、skill 演化 | signoff PPA、DRC/LVS、跨设计 LCB |

具体机制：

1. **动作抽象/可供性（affordance）**：LLM 只输出 skill id + 参数 + horizon；几何/数值由底层求解器完成。  
   EDA 的经验是：LLM 直接输出坐标/路径的成功率低且难验证，而“选择工具策略/参数”稳定得多。
2. **状态卡工程**：把 DEF/ODB 转成固定 schema 的摘要：stage、legality、面积/密度/利用率、WNS/TNS、top critical endpoints/paths、congestion hot spots、macro/IO、最近动作及效果、剩余预算。  
   再加一个给 surrogate 的图/向量表示（node/edge feature、HPWL、pin density），形成双表示。
3. **经验库（Experience Bank）**：每个 `(design family, stage, state cluster, skill version)` 存：被选中次数、成功/失败、平均 Δ、方差、最差案例、runtime、失败模式。  
   给 selector 检索“相似状态的 Top-K 成功案例”和“需要避开的坑”。这是“逐步学习”的主要载体，即使模型权重不变。
4. **多保真反馈**：L0 static → L1 cheap checker → L2 canary → L3 signoff；把代理误差显式建模（不确定性），不确定时升级保真度。  
   不建议在 L1 代理上训练后直接上 L3，必须留审计样本。
5. **课程与恢复数据**：先在简单设计/局部子问题教学，再加入人为退化状态（重叠、拥塞、时序差），教授 recovery skill/fallback；对应 HeurAgenix 的 stochastic trajectory 思路。  
   EDA 版：stochastic 轨迹 = 故意选非最优 skill 进入坏状态，然后要求 selector 用修复 skill 救回，且修复后仍满足 gate。
6. **过程奖励**：除最终 PPA 外，奖励“动作合法、契约通过、状态卡判断正确、及时回退、成本低”。  
   CPR 的 EDA 版可以直接对状态卡字段（stage/legality/congestion/timing severity）做监督；POR 用于 skill 候选排序。
7. **校准与弃权**：selector 输出 Q̂ 与置信度；用 conformal prediction / 温度校准；低置信时选择“多跑 TTS / 基线 skill / 请求更强模型”。  
   校准误差本身是一个可优化指标（ECE、coverage）。
8. **shadow/canary 上线**：新 skill 先 shadow 执行（不影响生产），与 baseline 并行比较；通过后再进入主库。生产中保留 rollback 与 kill switch。
9. **回归测试集**：固定一组设计 × 阶段 × 指标，任何 skill/model/prompt 版本变更都跑；防止“改 A 好、改 B 坏”。
10. **版本与 provenance**：所有东西都可追溯：design hash、tool commit、PDK 版本、skill 版本、prompt、模型日期、seed、运行时。  
    LLM 生成的内容必须带来源，方便审计与科学复现。
11. **防 reward hacking**：HPWL/预测拥塞/代理时序都可能被优化坏；用 signoff 真实指标、随机审计、最差 case 约束、多目标 HVI 来降低风险。
12. **边界控制**：第一阶段只改 physical implementation，不改 RTL/netlist；这能隔离功能正确性风险。等 verifier 成熟后再考虑逻辑/算法级演化。

---

## 7. EDA 领域的突破口（重点二）

下面按“最容易证明价值 → 最有研究新意”排序。

### 7.1 突破点 A：自进化的修复/合法化 skill（correctness-first）

**为什么：** RL/生成式/启发式方法普遍面临“生成后不合法”的问题（重叠、拥塞、DRC、连通性）。行业真正的痛点是 **repair/legalization**，而不是再生成一个略有不同的布局。  
**做法：**

- Placement 修复 skill：overlap 消除、row/site 合法化、macro halo/blockage 修复、时序 guardband 调整、密度/拥塞 relief。
- Routing 修复 skill：RRR 调度、DRC violation 修复、antenna 修复、via 优化、局部重布顺序。
- 这些 skill 的 gate 清晰（合法性/连通性/DRC），适合做“certified improvement”。
- 演化目标：在**修复成功率、修复后 PPA、runtime** 上做 Pareto 提升。

### 7.2 突破点 B：层次化 option + 跨阶段协同

- EDA 天然分层：floorplan → placement → CTS → global route → detailed route。每层 status/skill/目标不同。
- 把 HeurAgenix 的单层选择器升级为 **hierarchical selector**：高层选阶段策略/预算，低层选具体 skill。
- 关键研究点：**跨阶段 credit assignment**。placement 的一个 skill 可能当时 HPWL 好，但 route 后 overflow 爆炸；需要把 placement 的 reward 与 global route 的真实反馈耦合（类似 PRNet 的 coarse HPWL→router WL 过渡）。
- 实践：先在 placement checkpoint 上选 skill，但奖励用“继续跑 GRT 后的 overflow + 最终 WNS”的短程代理；这比只看 HPWL 稳。

### 7.3 突破点 C：约束多目标 + 尾部风险优化

- 芯片 PPA 是天然多目标：timing / power / area / wirelength / runtime / DRC risk。
- 用 **feasibility-gated hypervolume** 作为质量分数，用 **CVaR** 控制最差设计；用约束 MDP chance constraint 约束 DRC/LVS/时序违例概率。
- LLM 的职责：选择目标优先级、约束阈值、Lagrangian 权重/guardband，而不是直接优化几何。
- 可以把“设计目标配置”本身 skill 化：`timing_first`、`power_first`、`area_recovery`、`routability_first`，让 selector 按设计状态切换。

### 7.4 突破点 D：多保真 surrogate + 不确定性驱动的主动 signoff

- 训练图网络/树模型预测：placement 后的 GRT overflow、route 后 DRC risk、WNS/TNS、power/area。
- 关键不是预测准，而是**知道什么时候不准**：conformal prediction/ensemble variance；不确定就 upgrade 到 L2/L3。
- 这能显著降低 skill 评估成本，让“演化 + 选择”闭环可行。  
  发表点：**uncertainty-aware multi-fidelity skill evaluation for EDA hyper-heuristics**。

### 7.5 突破点 E：反事实 checkpoint replay + 设计族泛化

- 每次 flow 在各阶段存 checkpoint；对同一个 checkpoint 可重放多个 skill/selector，构成天然的反事实数据集。
- 用 replay 训练 selector/evolver，比在线随机探索便宜 1~2 个数量级。
- **按 design family 划分 train/test**（控制逻辑、数据通路、存储、宏密集、拥塞严重等），报告跨族泛化，而不是同设计随机 instance。  
  这是比“在 TSPLIB 上刷 gain”更接近 EDA 真实价值的评测协议。

### 7.6 突破点 F：先优化“工具使用/flow 调参”，再演化算法代码

- EDA 工具本身有很多启发式和参数：OpenROAD 的 density/init/wirelength coefficient、layer adjustment、congestion iterations、RRR 策略、detailed route effort 等。
- 先让 LLM **自进化 tool-use policy**（什么时候跑哪个 tool、用什么参数、迭代几次），这比让 LLM 重写 placement 算法更可行、也更接近工业痛点。
- 有稳定收益后，再进入 L3：在受限 DSL 中演化新算子。这样风险/收益曲线更健康。

### 7.7 建议的初始 skill 池（每阶段 5~8 个）

| 阶段 | 候选 skill |
|---|---|
| Placement | 全局布局 density/wirelength coef 调度；macro floorplan/region/SA 策略；legalize 顺序/effort/guardband；timing-driven 权重/endpoint 优先；congestion-aware spreading |
| CTS | buffer 策略/规格选择；clock tree 拓扑/约束调度（先只做参数级） |
| Global Route | net ordering（criticality/congestion/pin density）；layer adjustment/偏好；cost shaping/via 权重；congestion iterations；RRR 批选择与 rip-up 顺序 |
| Detailed Route | effort/iteration 调度；DRC repair 顺序；via/antenna 修复调度；局部重布策略 |
| Flow/全局 | 阶段顺序/预算分配；何时 repair timing；何时升级 signoff 保真度 |

### 7.8 可发表的贡献点（如果这条线要做成论文）

1. **Verification-guided skill self-evolution**：带契约、门控晋升、signoff-in-the-loop 的 LLM 自进化框架。
2. **Contract-based hyper-heuristic for EDA**：状态卡 + skill option + 守卫回滚，解决 LLM 在 EDA 中不可信的问题。
3. **Counterfactual checkpoint replay evaluation**：可复用的 EDA skill 因果评估协议。
4. **Chance-constrained multi-objective PPA optimization**：HVI + CVaR + LLM 权重调度。
5. **Distilling a flash LLM into a local selector**：把 HeurAgenix 的 POR+CPR 微调搬到 EDA 状态卡上，报告跨设计泛化。

---

## 8. 落地路线与交付物（建议）

### Phase 0（1~2 周）：度量与闭环骨架

- 建 EDA harness：OpenLane1 + sky130A，跑通 `spm` + `gcd` 等 2~3 个小设计，保存各阶段 checkpoint（ODB/DEF）和 metrics。
- 定义 state card schema、skill schema、verifier L0/L1 接口。
- 实现 3 个 placement skill（参数级）+ 3 个 routing skill（参数级）的**空壳**：先保证可执行、可回滚、可记录。
- 验收：baseline 重复 3 次指标一致；skill 调用后可恢复 checkpoint；日志含 version/seed/metrics。

### Phase 1（2~3 周）：量化协议 + dsv4-flash 选择

- 固定 10~20 个设计/checkpoint，做 baseline vs 单 skill 的配对实验。
- 实现 dsv4-flash selector（3 个候选 skill）与 Experience Bank；跑 “随机选择 / LLM 选择 / oracle 选择” 三档。
- 验收：给出每个 skill 的 `δ_k` 分布、selector 的 top-k recall/regret、以及一版统计报告。
- 关键产出：**“skill 到底有没有用、多大用、在什么状态有用”的第一份数据。**

### Phase 2（3~4 周）：L1/L2 自进化 + 门控晋升

- 用对比正/负轨迹让 dsv4-flash 提出参数/触发/组合扰动；verifier 过滤；留出设计族评估。
- 跑 20~50 轮演化，记录 mutation 成功率、晋升率、被淘汰原因。
- 产出：skill 库版本 + 晋升记录 + 演化成功率报告。

### Phase 3（3~4 周）：Routing 与跨阶段

- 加入 GRT RRR/overflow/congestion skill；从 placement 奖励过渡到“GRT 后 overflow / 最终 WNS”。
- 对比单阶段 opt 与跨阶段 co-opt。
- 产出：placement→routing 的联合 PPA 结果。

### Phase 4（2~4 周）：L3 代码进化 + 蒸馏

- 受限 DSL/allowlist 下尝试结构化 skill 合成；严格 sandbox + 单测 + canary。
- 收集数据蒸馏本地 Qwen selector，对比 API vs local。
- 产出：设计文档、代码、数据、报告、可复现命令；如果目标论文，整理成方法+实验章节。

**每一阶段的共同要求：**
- 每个结果带 `meta.json`（design/tool commit/PDK/skill version/prompt/seed/runtime）。
- 每一个被宣称的提升都附：样本量、置信区间、gate 通过率、最差 case、成本。

---

## 9. 风险与反模式

| 风险/反模式 | 后果 | 对策 |
|---|---|---|
| 让 LLM 直接执行任意代码/命令 | 不可控、不可复现、安全风险 | allowlist + sandbox + schema + 超时 + 资源限制 |
| 只测 selector 准确率，不测最终 PPA | 指标好看、芯片变差 | 双层指标：决策指标 + signoff 指标 |
| 只看平均提升，不看最差 case | 个别设计失败 | UCB 失败率、CVaR、P90 worst-case |
| 用 HPWL/代理指标做最终奖励 | reward hacking | signoff gate；代理只用于候选筛选/排序 |
| 同设计随机切分 train/test | 高估泛化 | 按 design family / 规模 / 结构留出 |
| 样本量不足就宣布成功 | 不能复现 | 预注册实验协议 + 置信区间 + 序贯检验 |
| 工具版本/LLM 版本漂移 | 结果不可复现 | 版本冻结 + prompt hash + meta.json |
| skill 库膨胀、旧 skill 污染选择 | 选择质量下降 | 版本化、定期退役、experience bank 统计 |
| 修改 netlist/RTL 做物理优化 | 功能正确性风险 | 第一阶段禁止；需要时用等价性检查/LVS |
| 只优化一个阶段 | 局部最优、下游爆炸 | 跨阶段 reward、阶段 checkpoint replay |
| API 成本/延迟失控 | 无法规模化 | 缓存、批处理、TTS 早停、本地蒸馏、fallback |

---

## 10. 需要拍板的决策项（建议默认值）

| # | 决策 | 建议默认 | 说明 |
|---|---|---|---|
| 1 | 先做 placement 还是 routing？ | **placement：legalize + timing/congestion refine** | 容易构造 checkpoint，验证快 |
| 2 | 工具链 | **OpenLane1 + sky130A（本地/服务器）**，控制层逐步转到 OpenROAD Python API | 现有 `eda-101/tools` 已跑通 |
| 3 | 初始 skill 等级 | **L1 参数级**，L2 紧随，L3 最后 | 降低不可验证风险 |
| 4 | 模型分工 | **dsv4-flash = selector + L1/L2 proposer**；L3/最终 review 用更强模型（如有） | 成本/能力平衡 |
| 5 | 正确性门禁 | **DRC/LVS/STA + 设计不变式**；第一阶段不碰 netlist | 与用户“正确性优先”一致 |
| 6 | 综合目标 | **gate + HVI（timing/power/area/runtime）**，首版先用字典序 | 避免拍脑袋权重 |
| 7 | 评测规模 | **10~20 设计 × 3 seeds** 起步，按 pilot 方差扩样 | 先证明度量协议可靠 |
| 8 | 是否蒸馏本地模型 | **先 API 打通、后蒸馏** | 对应 HeurAgenix Qwen 路线 |
| 9 | 是否允许 L3 代码演化 | **verifier 成熟后再说** | 否则容易产生不可控失败 |
| 10 | 项目命名/路径 | 建议新目录 `heura_repro/eda/` 或独立 `heura-eda/`，与 TSP 复现分开 | 数据/代码/结果隔离 |

---

## 11. 一页总结

- **迁移核心**：把 HeurAgenix 的“启发式池 + 在线选择”升级为“**契约化 skill 库 + 守卫执行 + 多保真验证 + 双层进化/选择**”。
- **LLM 定位**：做状态理解、skill 选择、参数/条件/组合演化；不做几何输出、不做最终正确性裁决。
- **正确性**：靠契约、检查器、checkpoint/rollback 和 signoff gate；不靠 LLM“更小心”。
- **成效量化**：三层声明（可复现 / 局部因果 / 群体部署）+ checkpoint replay 配对 A/B + 分层 bootstrap + 晋升门槛 + 消融。
- **EDA 突破点**：self-evolving repair skills、hierarchical options/跨阶段 co-opt、约束多目标 HVI+CVaR、多保真不确定性与反事实 replay、先工具使用后算法代码、design-family 泛化。
- **最快的验证路径**：OpenLane/spm 上先做 3 个参数级 skill，用 dsv4-flash 选，配对跑 10~20 个 checkpoint；只要能把“skill 的 δ_k 分布 + selector regret + signoff PPA”稳定测出来，后面演化才有科学依据。
