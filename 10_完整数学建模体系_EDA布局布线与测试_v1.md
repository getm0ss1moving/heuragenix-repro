# EDA 布局布线完整数学建模体系（v1.0）

**副标题：** 面向 HA-PR 流程、签核验证（signoff）与统计测试的统一定义  
**日期：** 2026-09-21  
**关系：** `09_EDA布局布线_新流程与数学建模_报告v1.md` 给出"迁移流程 + 核心模型"；本文给出**完整数学规格**，作为进入 Phase 0 前的最终定稿。`09` 仍可作为一页式导览，公式冲突时以本文为准。  
**范围声明：** 本文覆盖 standard-cell 布局布线（floorplan / global placement / legalization / CTS / global routing / detailed routing / signoff）的连续、组合与约束模型，以及它们的**验证测试与统计测试**要求。DFT/ATPG、模拟/混合信号、3D-IC 只在附录中给扩展接口，不作为首版核心。

---

## 0. 一页速览

### 0.1 这套数学体系由六个层次组成

| 层 | 名称 | 回答什么问题 | 核心对象 |
|---|---|---|---|
| L0 | 设计对象与工艺 | 我们在什么空间上优化 | 网表 $D$、工艺规则 $R$、布局变量、布线图 |
| L1 | 阶段物理模型 | 每个阶段的目标/约束/门禁是什么 | HPWL、density、CTS skew、routing overflow、DRC |
| L2 | 质量与测试基础 | 一个解"多好、合不合法、如何测" | 指标向量 $y$、gate $G$、效用 $U$、HVI、CVaR、测试协议 |
| L3 | 决策核心 BMF-CSMDP | 超启发式在多阶段、预算、硬约束下如何做序贯决策 | state $s$、option $\omega$、shield、Bellman、约束目标 |
| L4 | 多保真与不确定性 | 评估太贵且带噪时如何估计与分配预算 | 偏差 $b_l$、方差 $\sigma_l^2$、LCB/UCB、升保真、VOI/OCBA |
| L5 | 信用分配与学习 | 如何定位关键决策、训练 selector、演化 skill | 反事实 $\delta_i$、Shapley $\phi_i$、势函数 shaping、CA-POR/EDA-CPR、GRPO、双层演化 |
| L6 | 测试与统计协议 | 如何证明"真的有提升、且正确性风险有界" | 配对效应、分层 bootstrap、置信下界、失败率上界、复现记录 |

### 0.2 统一六元组

整套体系可以压成一个元组：

$$
\mathfrak{M}=\big(\underbrace{\mathcal{D},R}_{\text{L0 对象}},\;
\underbrace{\{f_g\}_{g\in\mathcal{G}},\{\mathcal{F}_g\}_{g\in\mathcal{G}}}_{\text{L1 阶段模型+可行集}},\;
\underbrace{U,\mathcal{T}_{\text{test}}}_{\text{L2 质量+测试}},\;
\underbrace{(\mathcal{S},\Omega,P,r,\gamma,\mathcal{B},\delta_{\text{fail}},G_3)}_{\text{L3 决策核心}},\;
\underbrace{\{(b_l,\sigma_l^2,c_l)\}_{l=0}^{L}}_{\text{L4 多保真}},\;
\underbrace{(\Pi,\mathcal{M}_{\text{LLM}},\mathcal{A})}_{\text{L5 策略+演化+档案}}\big)
$$

其中：
- $\mathcal{D}$：设计集合与家族；$R$：PDK/工艺规则；
- $f_g$：阶段 $g$ 的目标函数；$\mathcal{F}_g$：阶段合法状态集；
- $U$：多目标效用；$\mathcal{T}_{\text{test}}$：测试/统计协议；
- $\mathcal{S},\Omega,P,r,\gamma$：状态、option、转移、奖励、折扣；$\mathcal{B}$：预算；$\delta_{\text{fail}}$：允许 L3 失败概率；$G_3$：signoff gate；
- $(b_l,\sigma_l^2,c_l)$：保真度 $l$ 的偏差、方差、成本；
- $\Pi$：selector 策略类；$\mathcal{M}_{\text{LLM}}$：演化算子；$\mathcal{A}$：skill 档案/经验库。

### 0.3 "完整"体现在四个闭合

1. **物理闭合**：每个阶段的变量、约束、目标、合法集 $\mathcal{F}_g$ 都定义；阶段间接口（checkpoint/ODB）明确。
2. **决策闭合**：LLM 的动作空间（option）与工具执行语义、契约、shield、回滚规则一一对应。
3. **统计闭合**：每个"提升"声明都能对应到配对效应估计、置信区间、失败率上界和复现协议。
4. **成本闭合**：每个 option/保真度都有成本模型，并进入预算约束；不做无上限探索。

### 0.4 与 Phase 0 的关系

- 本文档是 Phase 0 的**前置输入**：Phase 0 的每个测试项都能在本文找到对应定义（见 §9）。
- 文档完成后仍**不自动启动** Phase 0；等用户拍板后再建 harness、跑 baseline、实现 skill。
- 若 Phase 0 发现模型与工具现实不符，修改本文并升版本，不回改历史结论。

---

## 1. 设计对象、工艺与状态空间

### 1.1 设计对象

一个设计（design）记为

$$
\mathcal{D}=\big(\mathcal{C},\mathcal{M},\mathcal{I},\mathcal{N},\mathcal{G}_t,\mathcal{Q}\big)
$$

| 符号 | 含义 |
|---|---|
| $\mathcal{C}$ | 标准单元集合；单元 $i$ 有宽 $w_i$、高 $h_i$、面积 $a_i=w_ih_i$、引脚偏移 $\Delta_i=(\Delta x_i,\Delta y_i)$、时序信息 |
| $\mathcal{M}$ | 宏单元/存储器集合；分为固定（fixed）与可移动（movable） |
| $\mathcal{I}$ | IO/pad 集合；通常固定 |
| $\mathcal{N}$ | 线网集合；$n\in\mathcal{N}$ 是超边，$n\subseteq\mathcal{C}\cup\mathcal{M}\cup\mathcal{I}$ |
| $\mathcal{G}_t=(\mathcal{V}_t,\mathcal{A}_t)$ | 时序图：节点为引脚/端口，边为时序弧或线网 |
| $\mathcal{Q}$ | 时序 corner 集合（PVT + RC corner），$q\in\mathcal{Q}$ |

**版面参数：** die 宽 $W$、高 $H$；core 区域 $\Omega_{\text{core}}$；行高 $h_{\text{row}}$；site 宽 $w_{\text{site}}$。

**工艺规则：** $R=(R_{\text{layer}},R_{\text{spacing}},R_{\text{width}},R_{\text{via}},R_{\text{antenna}},R_{\text{density}},\dots)$，由 PDK 给出；signoff 检查器是 $R$ 的可执行实现（Magic/KLayout/OpenSTA/Netgen 等）。

### 1.2 布局变量与几何

**布局状态：**

$$
p=\{(x_i,y_i,o_i)\}_{i\in\mathcal{C}\cup\mathcal{M}},\qquad o_i\in\mathcal{O}
$$

- 引脚坐标：$\pi_i(p)=(\,x_i+\Delta x_i,\;y_i+\Delta y_i\,)$；
- 单元包围盒：$B_i(p)=[x_i,x_i+w_i]\times[y_i,y_i+h_i]$；
- fixed 对象：$p_i\equiv p_i^{0}$（常量）；
- 布局合法集（硬约束）：

$$
\mathcal{F}_{\text{place}}=\Big\{p:\;
\forall i\in\text{fixed},\ p_i=p_i^{0};\;
B_i\subseteq\Omega_{\text{core}};\;
\forall i<j,\ B_i\cap B_j=\varnothing;\;
\text{row/site 合法}\Big\}
$$

**row/site 合法性：** 存在行号 $\rho(i)$ 与 site 号 $\sigma(i)$，使得 $y_i=\rho(i)h_{\text{row}}$、$x_i=\sigma(i)w_{\text{site}}$；对多高单元还需满足连续行覆盖。

### 1.3 布线空间

**全局布线图：**

$$
\mathcal{G}_r=(\mathcal{V}_r,\mathcal{A}_r),\qquad
e=(u,v,l,d)\in\mathcal{A}_r
$$

- $l$：金属层；$d$：走线方向（H/V）；
- $c_e$：边容量（可用轨道数 / 单位长度容量）；
- $\ell_e$：边长（几何长度）；
- via 边：层间切换边 $e_\updownarrow$，带 via 成本 $c_{\text{via}}$；
- 每条边对应一个或一组 g-cell；容量由轨道、层规则、blockage 决定。

**详细布线轨道图：** $\mathcal{G}_{\text{track}}=(\mathcal{V}_{\text{tr}},\mathcal{A}_{\text{tr}})$，节点是轨道上的端点，边是可供一条 net 走线的轨道段；同一轨道段不能被不同 net 占用（或按规则共享）。

### 1.4 阶段、checkpoint 与状态

阶段集合：

$$
\mathcal{G}=\{\text{floorplan},\text{global placement},\text{legalization},\text{CTS},\text{global route},\text{detailed route},\text{signoff}\}
$$

阶段 $g$ 的物理状态 $x_g$（DEF/ODB/工具中间数据）与指标向量 $m_g$ 构成 checkpoint：

$$
x_g=\mathrm{Checkpoint}(g,\mathcal{D}),\qquad m_g=\mathrm{Metrics}(x_g)
$$

完整决策状态（L3 用）：

$$
s=\big(g,\mathcal{D},x_g,m_g,b,h,\xi\big)
$$

| 符号 | 含义 |
|---|---|
| $g$ | 当前阶段 |
| $b=(b_{\text{time}},b_{\text{api}},b_{\text{tool}})$ | 剩余预算 |
| $h$ | 历史摘要（最近动作/效果/失败模式） |
| $\xi$ | 工具随机性（seed、并行、版本漂移） |

**双表示（观测）：**

$$
o=\big(\sigma(s),\varphi(s)\big)
$$

- $\sigma(s)$：给 LLM 的结构化状态卡（阶段、合法性、序数严重度、预算类、最近历史）；
- $\varphi(s)$：给代理模型的图/向量特征（单元、线网、拥塞、时序关键度）。

### 1.5 成本模型

每个 option $\omega$ 的实际消耗是一个随机向量：

$$
\rho(\omega)=\big(\rho_{\text{time}},\rho_{\text{tool}},\rho_{\text{api}},\rho_{\text{mem}}\big)
$$

预算约束（硬）：$\rho(\omega)\le b$ 分量形式。标量成本：
$$
c(\omega)=\lambda_t\rho_{\text{time}}+\lambda_k\rho_{\text{tool}}+\lambda_a\rho_{\text{api}}+\lambda_m\rho_{\text{mem}}
$$
其中 $\lambda$ 由项目按机器/API 价格设定，且进入决策评分（见 §4/§5）。

### 1.6 不确定性来源

| 来源 | 符号 | 处理 |
|---|---|---|
| 工具 seed/并行 | $\xi_{\text{tool}}$ | 固定 seed、配对重放、多次重复 |
| 代理模型误差 | $b_l$ | 审计集校准 + 乐观/悲观界 |
| 统计估计误差 | $\epsilon_l$ | LCB/UCB、bootstrap、序贯置信序列 |
| 模型/API 漂移 | $\xi_{\text{LLM}}$ | 记录 model/date/prompt hash，固定 eval set |
| 设计分布漂移 | $\xi_{\text{design}}$ | 按 family 切分，报告最差族 |

---

## 2. 阶段物理模型：变量、目标、约束与合法集

本节对每个阶段给出 $(\text{变量},\ \text{目标 }f_g,\ \text{约束/合法集 }\mathcal{F}_g,\ \text{主要指标})$。阶段间通过 checkpoint 接口衔接；hyper-heuristic 的动作只改参数/策略，不绕过这些约束。

### 2.1 Floorplan（布局规划）

**变量：** 宏单元位置/朝向 $\{(x_m,y_m,o_m)\}_{m\in\mathcal{M}}$，IO 位置 $\{(x_i,y_i)\}_{i\in\mathcal{I}}$，blockage/region 划分，电源通道预留宽度 $g_{\text{ring}}$，halo 间距 $g_{\text{halo}}$。

**目标（示例）：**
$$
f_{\text{FP}}=\alpha_1 A_{\text{core}}+\alpha_2 \widehat{\mathrm{WL}}_{\text{bbox}}+\alpha_3\sum_m \mathrm{halo\_conflict}(m)+\alpha_4\,\mathrm{channel\_shortage}
$$

**合法集：**
$$
\mathcal{F}_{\text{FP}}=\Big\{B_m\subseteq\Omega_{\text{die}},\;\;
B_m\cap B_{m'}=\varnothing,\;\;
\mathrm{dist}(B_m,B_{m'})\ge g_{\text{halo}},\;\;
\text{IO/pad 合法},\;\;
\text{电源/地通道宽度}\ge g_{\text{ring}}\Big\}
$$

**主要指标：** core/die area、utilization、macro channel 占用、halo 冲突、power-planning 可行性、初始 HPWL 估计。

**skill 参数示例：** macro 区域/朝向策略、通道预留、density budget、blockage 生成。

### 2.2 Global Placement（全局布局）

**变量：** $p=\{(x_i,y_i,o_i)\}$（可允许单元重叠；宏通常固定或受限）。

**目标：**
$$
f_{\text{GP}}(p)=
\underbrace{\alpha_1\mathrm{HPWL}(p)}_{\text{线长}}
+\underbrace{\alpha_2\mathrm{OF}_{\text{den}}(p)}_{\text{密度}}
+\underbrace{\alpha_3\widehat{\mathrm{OF}}_{\text{route}}(p)}_{\text{可布线性/拥塞}}
+\underbrace{\alpha_4\mathrm{TNS}(p)}_{\text{时序}}
+\underbrace{\alpha_5P_{\text{total}}(p)+\alpha_6A_{\text{core}}(p)}_{\text{功耗/面积}}
+\alpha_7\Omega_{\text{region}}(p)
$$

#### 2.2.1 HPWL 与线性化

**精确 HPWL：**
$$
\mathrm{HPWL}(p)=\sum_{n\in\mathcal{N}}\Big[
\max_{i\in n}\big(x_i+\Delta x_i\big)-\min_{i\in n}\big(x_i+\Delta x_i\big)
+\max_{i\in n}\big(y_i+\Delta y_i\big)-\min_{i\in n}\big(y_i+\Delta y_i\big)
\Big]
$$

**线性化（等价转写，便于 LP/QP 求解）：** 对每个 net $n$ 引入 $u_n^x\ge x_i+\Delta x_i$、$l_n^x\le x_i+\Delta x_i$（$y$ 同理），则
$$
\mathrm{HPWL}(p)=\sum_{n\in\mathcal{N}}\big[(u_n^x-l_n^x)+(u_n^y-l_n^y)\big]
$$
最小化会驱使 $u_n^x=\max$、$l_n^x=\min$，因此与原式等价。

#### 2.2.2 密度与密度溢出

将 core 划成 bins $B$，bin $b$ 的面积 $A_b$：
$$
D_b(p)=\frac{1}{A_b}\sum_{i\in\mathcal{C}\cup\mathcal{M}}a_i\cdot \mathrm{overlap}\big(B_i(p),b\big),
\qquad C_b=\rho_{\text{target}}A_b
$$
$$
\mathrm{OF}_{\text{den}}(p)=\frac{\sum_{b\in B}\max\{0,D_b(p)-C_b\}}{\sum_{b\in B}C_b}
$$
$\rho_{\text{target}}$ 是目标利用率（如 0.7–0.85），由 skill 调整。

#### 2.2.3 布线拥塞代理（placement → routing 的桥）

把每个 net 的包围盒按面积均匀摊到它与各 g-cell/边的重叠上，得到估计需求：
$$
\widehat{D}_e(p)=\sum_{n\in\mathcal{N}}
\frac{\big|\,\mathrm{bbox}_n(p)\cap \mathrm{region}(e)\,\big|}{\big|\mathrm{bbox}_n(p)\big|}\cdot \mathrm{pin\_weight}_n,
\qquad
\widehat{\mathrm{OF}}_{\text{route}}(p)=\frac{\sum_e\max\{0,\widehat{D}_e(p)-C_e\}}{\sum_e C_e}
$$
这是 RUDY 类代理的通用形式（具体权重可在 Phase 0 用 GRT 真实 overflow 校准）；它的存在使 placement 阶段能感知 routing 后果。

#### 2.2.4 时序与功耗

时序图 $\mathcal{G}_t$ 上：
$$
a_v=\max_{u\to v}\big(a_u+d_{uv}(p)\big),\qquad
r_v=\min_{v\to w}\big(r_w-d_{vw}(p)\big),\qquad
\mathrm{slack}_v=r_v-a_v
$$
$$
\mathrm{WNS}_{\text{setup}}(p)=\min_v \mathrm{slack}^{\text{setup}}_v,\qquad
\mathrm{WNS}_{\text{hold}}(p)=\min_v \mathrm{slack}^{\text{hold}}_v,\qquad
\mathrm{TNS}_{\text{setup}}(p)=\sum_v\min\{0,\mathrm{slack}^{\text{setup}}_v\}
$$
其中弧延迟 $d_{uv}(p)$ 由单元延迟 + 线网延迟组成；线网延迟可用 Elmore/一阶模型与 $\mathrm{WL}_n(p)$ 近似。

功耗：
$$
P_{\text{dyn}}=\sum_{g}\alpha_g C_g V_{\text{dd}}^2 f,\qquad
P_{\text{leak}}=\sum_g I_{\text{leak},g}V_{\text{dd}},\qquad
P_{\text{total}}=P_{\text{dyn}}+P_{\text{leak}}
$$

#### 2.2.5 合法集

全局布局允许重叠，但仍需：
$$
\mathcal{F}_{\text{GP}}=\Big\{p:\ \forall i\in\text{fixed},p_i=p_i^0;\quad B_i\subseteq\Omega_{\text{core}};\quad
\frac{1}{A_b}D_b(p)\le \rho_{\max}\ \forall b\Big\}
$$
密度上限是软/硬约束可切换项；最终合法化由下一阶段完成。

**主要指标：** HPWL、density overflow、\widehat{OF}_route、WNS/TNS、power、area、runtime。  
**skill 参数示例：** HPWL/density 权重调度、timing 权重、endpoint 优先级、region 约束、spreading 强度。

### 2.3 Legalization（合法化）

**输入：** 全局布局坐标 $p^0$；**变量：** 行/site 分配 $q_i=(\rho_i,\sigma_i)$（等价于合法坐标 $(x_i^q,y_i^q)$）。

**目标：**
$$
f_{\text{LG}}(q)=\sum_{i}\big\|q_i-p_i^0\big\|_2^2
+\lambda_1\mathrm{HPWL}(q)+\lambda_2\max\{0,\mathrm{TNS}(q)-\mathrm{TNS}(p^0)+\epsilon_{\text{guard}}\}
$$

**约束：**
$$
\mathcal{F}_{\text{LG}}=\Big\{q:\ \text{overlap}=0,\ \text{row/site 合法},\ \text{fixed 不变},\ q_i\in\Omega_{\text{core}},\ \text{位移}\le d_{\max}\Big\}
$$
可写成带析取约束的 ILP/分配问题（相邻单元对之间至少一个方向不重叠），工业上用 Abacus/贪心 + 局部交换求解。

**主要指标：** overlap 数、位移总和/最大值、HPWL 变化、WNS 退化、runtime。  
**skill 参数示例：** 合法化顺序（WNS-first / density-first）、padding/effort、时序 guardband、局部 swap 半径。

### 2.4 CTS（时钟树综合）

**变量：** 时钟树拓扑 $T$、buffer 插入位置与规格 $\{s_b\}$、走线层与长度、时钟约束调度。

**延迟与 skew：**
$$
L_k=\sum_{e\in\mathrm{path}(s_0,k)}d_e,\qquad
\mathrm{skew}(T)=\max_{k\in\text{sinks}}L_k-\min_{k\in\text{sinks}}L_k
$$
**目标：**
$$
f_{\text{CTS}}=\lambda_1\mathrm{skew}(T)+\lambda_2\max_k L_k+\lambda_3P_{\text{clk}}+\lambda_4A_{\text{buffer}}+\lambda_5 N_{\text{buf}}
$$
**约束：**
$$
\mathcal{F}_{\text{CTS}}=\Big\{\mathrm{skew}(T)\le S_{\max},\ \max_k L_k\le L_{\max},\ \mathrm{clock\ DRC}=0,\ \text{拓扑合法}\Big\}
$$
**主要指标：** skew、latency、clock DRC、clock power、buffer area。  
**skill 参数示例：** buffer 规格/级数、target skew、拓扑约束、layer 偏好（首版只做 L1 参数级）。

---

## 2（续）. 布线阶段与签核模型

### 2.5 Global Routing（全局布线）

**输入：** 合法布局 + 布线图 $\mathcal{G}_r$；**变量：** 每条 net $n$ 在边 $e$ 上的流量 $f_{n,e}\in\mathbb{Z}_{\ge0}$。

**流守恒：** 对每个 net $n$，选取源点 $s_n$ 与汇点集合 $T_n$，定义供给
$$
b_{n,v}=
\begin{cases}
|T_n|, & v=s_n\\
-1, & v\in T_n\\
0, & \text{否则}
\end{cases}
$$
要求
$$
\sum_{e\in\delta^+(v)}f_{n,e}-\sum_{e\in\delta^-(v)}f_{n,e}=b_{n,v},
\qquad \forall n\in\mathcal{N},\ \forall v\in\mathcal{V}_r
$$
其中 $\delta^+/\delta^-$ 是出/入边集合。多端 net 可通过 Steiner 树或拆成两两路径处理。

**容量与溢出：**
$$
d_e=\sum_{n\in\mathcal{N}}f_{n,e},\qquad
o_e=\max\{0,d_e-c_e\},\qquad
\mathrm{OF}_{\text{route}}=\frac{\sum_e o_e}{\sum_e c_e},\qquad
\mathrm{MOF}=\max_e\frac{o_e}{c_e}
$$

**目标：**
$$
f_{\text{GR}}=\lambda_1\,\sum_{e\in\mathcal{A}_r}\ell_e d_e
+\lambda_2\,\sum_{n,e\in\text{via}}f_{n,e}
+\lambda_3\,\sum_e o_e
+\lambda_4\mathrm{MOF}
+\lambda_5\,\mathrm{TNS}
+\lambda_6\,N_{\text{bend}}
$$
**约束：**
$$
\mathcal{F}_{\text{GR}}=\Big\{\text{流守恒},\ \text{层方向合法},\ \text{via 规则合法},\ \text{overflow}\le \mathrm{OF}_{\max}\Big\}
$$
（全局布线允许受控 overflow，但必须有限；最终 100\% 连通与零 overflow 由详细布线/signoff 保证。）

**求解口径：** 精确 MCF 是 ILP/LP，可对局部子图/小 net 精确解，全局用 Lagrangian 松弛 + 顺序 rip-up & reroute（RRR）、pattern routing；skill 控制 net ordering、layer bias、cost shaping、RRR 批大小与迭代预算。

**主要指标：** overflow（total/max）、wirelength、via、bend、连通率、runtime。  
**skill 参数示例：** net ordering（criticality/congestion/pin density）、layer adjustment、cost shaping、RRR 策略、congestion iterations。

### 2.6 Detailed Routing（详细布线）

**空间：** 轨道图 $\mathcal{G}_{\text{track}}$；每条 net 选一棵 Steiner 树 $T_n\subseteq\mathcal{G}_{\text{track}}$。

**占用变量：**
$$
z_{n,a}=\mathbb{1}[a\in T_n],\qquad a\in\mathcal{A}_{\text{track}}
$$
**连通约束：** $T_n$ 连接 $n$ 的所有端点（Steiner 树约束）。
**独占约束：** 对不能共享的轨道段
$$
\sum_{n}z_{n,a}\le 1,\qquad \forall a\in\mathcal{A}_{\text{track}}
$$
（同 net 可复用；实际工具还会允许同 net 分支共享与层间 via。）

**设计规则（DRC）约束：** 工艺规则可写成一组几何谓词
$$
\Phi_j(\text{geometry})=0,\qquad j=1,\dots,J
$$
覆盖 width、spacing、notch、min-area、via enclosure、end-of-line、density、antenna 等。违反数：
$$
N_{\text{DRC}}=\sum_{j=1}^{J}\#\{\text{violations of }\Phi_j\}
$$

**目标：**
$$
f_{\text{DR}}=\lambda_1\mathrm{WL}+\lambda_2N_{\text{via}}+\lambda_3N_{\text{DRC}}+\lambda_4N_{\text{short/open}}+\lambda_5\,\mathrm{runtime}
$$
**约束：**
$$
\mathcal{F}_{\text{DR}}=\Big\{\text{100\% 连通},\ N_{\text{short/open}}=0,\ N_{\text{DRC}}\le \epsilon_{\text{DR}}\Big\}
$$
（签核要求通常 $N_{\text{DRC}}=0$；优化过程中允许暂时非零作为惩罚，最终必须归零。）

**求解口径：** 网格图上的 Steiner 树 + 冲突消解，工业用 rip-up & reroute、贪心列生成、SAT/ILP 局部精确；skill 控制 effort/iteration 调度、DRC repair 顺序、via/antenna 修复、局部重布。

**主要指标：** DRC、short/open、via、wirelength、antenna ratio、runtime。

### 2.7 Signoff（签核验证）

最终版图 $x_T$ 必须满足一组**不可交易的硬门禁**。定义门禁向量：
$$
G(x_T)=\big(G_{\text{legality}},G_{\text{conn}},G_{\text{DRC}},G_{\text{LVS}},G_{\text{ERC}},G_{\text{STA}},G_{\text{ANT}},G_{\text{IR/EM}}\big)\in\{0,1\}^8
$$

| Gate | 定义 | 典型工具/判据 |
|---|---|---|
| $G_{\text{legality}}$ | placement 合法（overlap=0、row-legal、fixed 不变） | OpenROAD `check_placement` |
| $G_{\text{conn}}$ | 每条 net 100\% 连通 | OpenROAD/GRT/DRT |
| $G_{\text{DRC}}$ | 版图 DRC 违例数 $N_{\text{DRC}}=0$ | Magic/KLayout |
| $G_{\text{LVS}}$ | 版图提取网表与源网表一致 | Netgen |
| $G_{\text{ERC}}$ | 电气规则（浮空、多驱动、闩锁等）通过 | OpenROAD/工具 |
| $G_{\text{STA}}$ | 所有 corner $q\in\mathcal{Q}$ 下 setup WNS $\ge -\epsilon_{\text{STA}}$ 且 hold WNS $\ge -\epsilon_{\text{hold}}$（或设计约束） | OpenSTA + SPEF |
| $G_{\text{ANT}}$ | antenna ratio 不超工艺限值 | OpenROAD/工具 |
| $G_{\text{IR/EM}}$ | IR drop/EM 不超限（若启用） | OpenROAD PDN/EM 分析 |

**总签核可行集：**
$$
\mathcal{F}_{\text{signoff}}=\{x_T:\ G(x_T)=\mathbf{1}\},\qquad
G_3(x_T)=\prod_{c}G_c(x_T)
$$
只有 $G_3=1$ 的 flow 结果才被计为"成功样本"；否则进入回滚/失败档案。

### 2.8 阶段接口与 checkpoints

| 阶段 | 输入 | 输出 checkpoint | 主要指标 | 硬门禁（阶段内） |
|---|---|---|---|---|
| floorplan | 网表 + 约束 | DEF/ODB（macro/IO） | area、channel、halo | fixed/IO 合法、通道不冲突 |
| global placement | floorplan | 全局坐标 | HPWL、density、拥塞代理、时序代理 | fixed 不变、core 内、density 上限 |
| legalization | 全局布局 | row/site 合法坐标 | overlap、位移、HPWLΔ | overlap=0、row-legal、HPWL guard |
| CTS | 合法布局 | 时钟树 | skew、latency、clock DRC | 拓扑合法、skew/latency 门限 |
| global route | CTS/布局 | GRT 结果 | overflow、WL、via、连通 | 连通、层规则、overflow 上限 |
| detailed route | GRT | 详细布线 | DRC、short/open、via、runtime | DRC=0、无 short/open |
| signoff | DR | GDS/SPEF/报告 | DRC/LVS/STA/power/area | 见 2.7 全通过 |

---

## 3. 质量、约束与测试基础模型

本节回答两个问题：**"一个 flow 结果有多好？"** 与 **"怎么测才算数？"** 它是 L3 决策模型的效用与约束来源。

### 3.1 指标向量

> **WNS/TNS 口径修正（v1.1，2026-09-22）**：`WNS` 必须区分 setup 与 hold。本文约定：setup WNS = max-delay（setup）分析的最差 slack（OpenROAD 源键 `DRT::worst_slack_max`）；hold WNS = min-delay（hold）分析的最差 slack（`DRT::worst_slack_min`）；二者均为 signed 值，越大越好，负值表示违例。setup TNS = setup 负 slack 之和（`DRT::tns_max`）。旧文档/旧 harness 曾把 `worst_slack_min`（hold）当作 WNS，该口径已废弃；工程实现与测试口径见 `heura_repro/eda/docs/METRIC_CONVENTIONS.md` 与 `harness/metrics_schema.py`。 其他指标（power 单位、DRC 去重、instance_count、HPWL 含/不含端口三口径）见该文档 §8–9 与 `harness/metric_rules.py`。

对最终状态 $s_T$（或其阶段快照）定义质量向量：

$$
y(s_T)=\big(
\mathrm{WNS}_{\text{setup}},\ \mathrm{WNS}_{\text{hold}},\ \mathrm{TNS}_{\text{setup}},\ -P_{\text{total}},\ -A_{\text{core}},\ -\mathrm{WL},\ -N_{\text{via}},\ -\mathrm{OF},\ -N_{\text{DRC}},\ -\mathrm{runtime},\ -\mathrm{cost}
\big)
$$

统一约定：**每个分量越大越好**（因此功耗/面积/线长/违例/成本前面加负号）。若需要区分动态/漏电功耗、setup/hold 时序，则扩展为多分量。

### 3.2 归一化与方向

对每个分量 $i$，给定基线 $y_i^{\text{base}}$、方向 $\sigma_i\in\{+1,-1\}$（+1 越大越好）、鲁棒尺度 $s_i$（如基线 IQR 或 $\max(|y_i^{\text{base}}|,\epsilon)$）：

$$
\tilde y_i(s)=\sigma_i\frac{y_i(s)-y_i^{\text{base}}}{s_i}
$$

$\tilde y_i>0$ 表示在该指标上优于基线。归一化的目的：让多目标的数值尺度可比，同时保持"相对基线"的可解释性。

### 3.3 门禁函数

每个阶段定义合法集 $\mathcal{F}_g$（见 §2），门禁指示：

$$
G_g(s)=\mathbb{1}\big[x_g\in\mathcal{F}_g\big]\in\{0,1\}
$$

整条 flow 的硬门禁：

$$
G_{\text{flow}}(s_T)=\prod_{g\in\mathcal{G}}G_g(s_g)\cdot G_3(s_T)
$$

其中 $G_3$ 是 §2.7 的 signoff gate。**任何 $G_{\text{flow}}=0$ 的样本在统计上按失败处理，不进入性能均值。**

### 3.4 效用 $U$：从字典序到超体积

**定义 3.1（字典序效用）** 给定优先级排列 $\pi_U$，定义
$$
U_{\text{lex}}(s)=\big(G_{\text{flow}}(s),\tilde y_{\pi_U(1)}(s),\tilde y_{\pi_U(2)}(s),\dots\big)
$$
按字典序比较。最稳、无权重争议，适合 Phase 0。

**定义 3.2（加权效用）**
$$
U_w(s)=\sum_i w_i\tilde y_i(s),\qquad w_i\ge0
$$
权重可由 selector 按设计状态选择（timing_first / routability_first / power_first 等模式），但必须做敏感性分析。

**定义 3.3（超体积改进 HVI）** 取参考点 $r$（被所有候选支配），基线点集 $Y_{\text{base}}$，候选点 $y'$：
$$
\Delta U_{\mathrm{HV}}(y')=\mathrm{HV}\big(Y_{\text{base}}\cup\{y'\};r\big)-\mathrm{HV}\big(Y_{\text{base}};r\big)
$$
其中 $\mathrm{HV}(Y;r)=\Lambda\big(\bigcup_{y\in Y}[r,y]\big)$，$\Lambda$ 为 Lebesgue 测度。HVI 同时考虑多目标支配关系，不依赖人工权重。

**定义 3.4（尾部风险 CVaR）** 令损失 $L=-\Delta U$（或某个指标的退化），
$$
\mathrm{VaR}_{\alpha}(L)=\inf\{\ell:\Pr(L\le\ell)\ge\alpha\},\qquad
\mathrm{CVaR}_{\alpha}(L)=\mathbb{E}\big[L\,\big|\,L\ge \mathrm{VaR}_{\alpha}(L)\big]
$$
等价优化形式：
$$
\mathrm{CVaR}_{\alpha}(L)=\min_{t\in\mathbb{R}}\Big\{t+\frac{1}{1-\alpha}\mathbb{E}\big[(L-t)^+\big]\Big\}
$$
CVaR 作为约束：$\mathrm{CVaR}_{\alpha}\le \rho_{\text{risk}}$，控制"平均好但个别设计爆炸"。

### 3.5 测试集与数据划分

**测试协议参数：**

| 符号 | 含义 | 建议 |
|---|---|---|
| $\mathcal{D}_{\text{train}}$ | 演化/调参用设计 | 按家族分层 |
| $\mathcal{D}_{\text{val}}$ | 候选晋升用设计 | 与 train 不同设计 |
| $\mathcal{D}_{\text{test}}$ | 最终报告用设计 | 冻结后不再改 |
| $K$ | 每设计 seed 数 | ≥3 |
| $N_{\text{family}}$ | design family 数 | 控制/数据通路/存储/宏密集/拥塞型 ≥5 |

**切分原则：** 同一设计族不跨 train/test；报告最差族结果；禁止用 test 反馈调参。

### 3.6 配对因果效应

对同一设计 $d$、同一 checkpoint、同一 seed $k$，用候选策略 $\pi$ 与基线 $\pi_0$ 各跑一次冻结后续 flow：

$$
\delta_{d,k}(\pi)=U\big(s_T(\pi,d,k)\big)-U\big(s_T(\pi_0,d,k)\big)
$$

设计级效应与总体效应：
$$
\delta_d(\pi)=\frac{1}{K}\sum_{k=1}^{K}\delta_{d,k}(\pi),\qquad
\Delta(\pi)=\mathbb{E}_{d\sim\mathcal{D}_{\text{test}}}\big[\delta_d(\pi)\big]
$$

这是**配对设计**，可消掉设计难度带来的大部分方差。仅当两侧都 $G_{\text{flow}}=1$ 时 $\delta$ 进入性能统计；否则记入失败率统计。

### 3.7 统计推断与晋升判据

**分层 bootstrap：** 先按 design 聚合，再按 family 重采样；得到 $\hat\Delta$ 的分布与置信区间。  
**置信下界：**
$$
\mathrm{LCB}_{1-\alpha}(\Delta)=\hat\Delta-z_{1-\alpha}\widehat{\mathrm{SE}}_{\text{boot}}
$$
**失败率上界（Wilson 型）：** $\hat p=\frac{1}{N}\sum_{d,k}\mathbb{1}[G_{\text{flow}}=0]$，
$$
\hat p_{\text{UCB}}=\frac{\hat p+\frac{z^2}{2N}+z\sqrt{\frac{\hat p(1-\hat p)}{N}+\frac{z^2}{4N^2}}}{1+\frac{z^2}{N}},\qquad z=z_{1-\alpha}
$$
**样本量粗估（配对连续指标）：**
$$
N\approx\frac{(z_{1-\alpha}+z_{1-\beta})^2\sigma_\delta^2}{\Delta^2}
$$
按 design 内相关性（ICC）放大。  
**序贯决策：** 用 anytime-valid 置信序列（confidence sequence）支持"边跑边停"，避免重复检验导致的假阳性膨胀。  
**晋升判据（默认）：**
$$
\mathrm{Promote}(\pi)=1\iff
\mathrm{LCB}_{1-\alpha}(\Delta)>0
\ \wedge\
\hat p_{\text{UCB}}<\epsilon_{\text{fail}}
\ \wedge\
\overline{\mathrm{cost}}\le B_{\text{unit}}
$$
不满足则标为 `inconclusive`（而非"无提升"），记录样本量与 CI 宽度。

### 3.8 布局布线测试的基本要求

| 测试层 | 检查内容 | 工具/方式 | 通过标准 |
|---|---|---|---|
| T0 输入/记录 | 版本、schema、seed、参数范围、allowlist、超时 | 脚本断言 + `meta.json` | 100% 可追溯 |
| T1 布局合法性 | overlap、row-legal、fixed 不变、netlist hash 不变、density | OpenROAD `check_placement` / 自研 checker | 全通过 |
| T2 连通性 | 每条 net 100\% 连通；无 floating | OpenROAD / 图算法 | 全通过 |
| T3 快速签核 | GRT overflow、局部 DRC、时序代理 | OpenROAD / 代理 | 不超 guardband |
| T4 详细签核 | DRC=0、LVS、ERC、antenna、STA 多 corner | Magic/KLayout/Netgen/OpenSTA | $G_3=1$ |
| T5 性能 | WNS/TNS、power、area、WL、via、runtime、cost | 指标 CSV | 进入效用统计 |
| T6 可复现 | 同版本/seed/输入重复运行；结果容差 | 重复运行 + hash | 指标差 $\le\epsilon_{\text{rep}}$ |
| T7 统计测试 | 配对效应、LCB、失败率 UCB、最差族 | bootstrap / 置信序列 | 满足晋升判据 |
| T8 回归 | 新 skill/model/prompt 不破坏已有测试集 | 固定 regression set | 无退化 |

**基准数据集建议（Phase 0 起）：** placement 可用 ISPD 2005/2006 或 OpenLane 内置设计；routing 可用 ISPD 2007/2008 或 OpenROAD 的 GRT 测试集；首版建议 OpenLane1 + sky130A 的 `spm`/`gcd` 打通，再扩到更多 family。  
**DFT/ATPG 说明：** 若后续纳入 scan chain/test point，需在 §2 额外加 scan 顺序/长度平衡约束，并把 test wirelength 作为额外目标；首版不纳入核心设计。

---

## 4. 决策核心：BMF-CSMDP 完整定义

**名称：** Budgeted Multi-Fidelity Constrained Semi-Markov Decision Process with Contract Shield（带契约 shield 的预算约束多保真半马尔可夫决策过程）。  
**定位：** 把 §2 的物理阶段模型与 §3 的质量/测试模型统一成一个序贯决策问题；HA-PR 的 selector、演化、验证协议都是它的算法实例。

### 4.1 元组

$$
\mathfrak{C}=\big(\tilde{\mathcal{S}},\ \Omega,\ P,\ r,\ \gamma,\ \mathcal{B},\ \delta_{\text{fail}},\ \mu_0,\ G_3,\ \mathcal{F}\big)
$$

| 符号 | 含义 |
|---|---|
| $\tilde{\mathcal{S}}$ | 预算增广状态空间：$\tilde s=(s,b)$ |
| $\Omega$ | option/skill 集合 |
| $P$ | 受 shield 约束的转移核 |
| $r$ | 标量奖励（由多目标效用与成本导出） |
| $\gamma$ | 折扣因子（$\gamma\in(0,1]$；预算约束存在时可用 $\gamma=1$） |
| $\mathcal{B}$ | 预算上限（时间/工具/API） |
| $\delta_{\text{fail}}$ | 允许的 L3 signoff 失败概率上界 |
| $\mu_0$ | 初始 checkpoint 分布 |
| $G_3$ | signoff gate 指示 |
| $\mathcal{F}$ | 各阶段合法集（见 §2） |

### 4.2 预算增广状态

$$
\tilde s=(g,\mathcal{D},x_g,m_g,b,h,\xi),\qquad b=(b_{\text{time}},b_{\text{api}},b_{\text{tool}})
$$

同 §1.4；其中 $b$ 随 option 消耗递减。为便于理论分析，假设所有成本有界且离散步长有限，则 $\tilde{\mathcal{S}}$ 在预算维度可离散化。

### 4.3 Option（契约化 skill）

$$
\omega=(k,\theta,\tau),\qquad
k\in\mathcal{K},\ \theta\in\Theta_k,\ \tau\in\mathcal{T}_k
$$

- $k$：skill id（工具策略、参数模板、局部搜索、修复动作、阶段调度）；
- $\theta$：连续/离散参数；
- $\tau$：停止条件/horizon（迭代次数、overflow 阈值、时间预算、事件触发）。

**契约：**
$$
C_k=(\mathrm{Pre}_k,\mathrm{Post}_k,\mathrm{Inv}_k,\mathrm{Fallback}_k,\mathrm{Cost}_k,\mathrm{Evidence}_k)
$$
**适用与可负担集合：**
$$
\Omega_{\mathrm{adm}}(s)=\Big\{\omega=(k,\theta,\tau):\ A_k(s)=1,\ \mathrm{Pre}_k(s)=1,\ \mathbb{E}[\rho(\omega)]\le b\Big\}
$$

### 4.4 Shield（契约守卫）

裸执行结果 $\tilde x'=\mathrm{Exec}_k(x,\theta;\xi)$。shield 算子：

$$
\mathcal{S}_k(s,\tilde x')=
\begin{cases}
s^+=\big(g',\tilde x',m',b-c(\omega),h'\big), & \text{若 }\mathrm{Post}_k,\mathrm{Inv}_k,G_{g'}(s^+)\text{ 全通过}\\[1mm]
s\ \text{（回滚）}, & \text{否则（可先执行 }\mathrm{Fallback}_k\text{）}
\end{cases}
$$

**约定：** L0/L1 检查永远在 shield 内执行；L2 canary 可按风险触发；L3 signoff 不在线执行，其残余失败由 §4.7 的机会约束控制。

### 4.5 转移核（半 MDP，变时长）

$$
P\big(s',\rho\,\big|\,s,\omega\big)
=\Pr\Big(\mathcal{S}_k\big(s,\mathrm{Exec}_k(x,\theta;\xi)\big)=s',\ \rho(\omega)=\rho\Big)
$$

- $\rho$ 是随机时长/成本；$\gamma^{\rho}$ 对长动作做折扣；
- 若使用预算硬约束，可令 $\gamma=1$，由 $\sum\rho\le B$ 与状态中的 $b$ 处理；
- 工具随机性 $\xi$ 通过固定 seed、重复运行与配对设计管理。

### 4.6 奖励：从多目标到标量

**单步效用增量：**
$$
\Delta U(s,s')=U(s')-U(s)
$$
其中 $U$ 可取 §3.4 的字典序/HVI/加权效用（HVI 为研究版推荐）。  
**标量奖励：**
$$
r(s,\omega,s')=\Delta U(s,s')-\lambda_c\,c(\omega)-\lambda_f\,\mathbb{1}\big[G_{g'}(s')=0\big]+\underbrace{\gamma^{\rho}\Phi(s')-\Phi(s)}_{\text{可选：跨阶段势函数 shaping（§6.2）}}
$$
**说明：** $-\lambda_f$ 是软惩罚；真正的硬门禁由 shield + §4.7 约束保证；$\Phi$ 只依赖状态，满足 §6.2 的不变性条件。

若 $U$ 只在 signoff 可精确获得，则在线用代理 $\widehat{\Delta U}$；这直接引出 §5 的多保真估计。

### 4.7 约束与目标

**有限 horizon（或无限 horizon 折扣）目标：**

$$
\max_{\pi}\ J(\pi)=\mathbb{E}_{\mu_0,\pi}\left[\sum_{j=0}^{K-1}\gamma^{\rho_j}r(s_j,\omega_j,s_{j+1})\right]
$$

**约束：**
$$
\Pr\Big(\exists j\in\{1,\dots,K\}:\ G_3(s_j)=0\Big)\le\delta_{\text{fail}}
\qquad\text{（signoff 机会约束）}
$$
$$
\mathbb{E}\left[\sum_{j=0}^{K-1}\rho_j\right]\le B
\qquad\text{（预算约束，分量形式）}
$$
$$
\omega_j\in\Omega_{\mathrm{adm}}(s_j),\qquad
s_{j+1}=\mathcal{S}_{\omega_j}\big(s_j,\mathrm{Exec}_{\omega_j}(x_j)\big)
$$

**为什么需要机会约束：** L0/L1 能在 shield 内检查的约束不需要概率化；L3 的 DRC/LVS/STA 只能抽样评估，因此必须显式控制其失败概率。

### 4.8 Bellman 方程与最优策略

**option 价值：**
$$
Q^{\star}(s,\omega)=\mathbb{E}\Big[r(s,\omega,s')+\gamma^{\rho(\omega)}V^{\star}(s')\ \Big|\ s,\omega\Big],
\qquad
V^{\star}(s)=\max_{\omega\in\Omega_{\mathrm{adm}}(s)}Q^{\star}(s,\omega)
$$

**终止：** $V^{\star}(s_T)=0$（奖励为效用增量，终端不额外奖励）；或等价的 $V(s_T)=U(s_T)$ 形式。  
**最优策略：** 在可测选择与有界性假设下，存在确定性平稳最优策略
$$
\pi^{\star}(s)\in\arg\max_{\omega\in\Omega_{\mathrm{adm}}(s)}Q^{\star}(s,\omega)
$$
（标准 semi-MDP 结论，参见 Puterman 1994；Sutton–Precup–Singh 1999 的 options framework。）

**层次结构：** 阶段本身可作为 macro-option。设高层策略 $\pi_{\text{high}}$ 选择阶段流转/预算分配，低层策略 $\pi_{\text{low}}$ 在阶段内选 skill；由 options 的可嵌套性，层次结构可"压平"为等价的 option 半 MDP，但显式分层更利于信用分配与实现。

**部分可观测性：** selector 实际只看到观测 $o=(\sigma,\varphi)$，因此工程上按 POMDP 处理：策略 $\pi(\omega\mid o)$，价值估计通过 checkpoint replay 与经验库近似；本文不假设 belief state 可精确计算。

### 4.9 拉格朗日对偶与在线分数

把约束拉格朗日化（$\lambda,\mu\ge0$）：
$$
\min_{\lambda,\mu\ge0}\ \max_{\pi}\ \mathbb{E}\Big[\sum_j\gamma^{\rho_j}r_j\Big]
-\lambda\Big(\mathbb{E}\big[\textstyle\sum_j\rho_j\big]-B\Big)
-\mu\Big(\Pr(G_3=0)-\delta_{\text{fail}}\Big)
$$

工程上对每个候选 $\omega$ 用保守估计：
$$
\widehat{\mathrm{Score}}(s,\omega)
=\mathrm{LCB}_{1-\alpha}\big[\Delta U(s,\omega)\big]
-\lambda_c\,\frac{\hat c(s,\omega)}{\max(b_{\text{time}}-b_{\min},\epsilon_b)}
-\lambda_r\,\mathrm{UCB}_{1-\alpha}\big[P^{L3}_{\text{fail}}(s,\omega)\big]
+\big(\gamma^{\hat\rho}\hat\Phi(s')-\hat\Phi(s)\big)
$$
选择
$$
\omega^{\star}=\begin{cases}
\arg\max_{\omega\in\Omega_{\mathrm{adm}}(s)}\widehat{\mathrm{Score}}(s,\omega), & \text{若最大分数 }>0\\
\text{fallback / 进入下一阶段}, & \text{否则}
\end{cases}
$$
其中 $\lambda_c,\lambda_r$ 可由 primal-dual 在线更新，或按项目预算固定。

### 4.10 与 HeurAgenix Eq.(1) 的关系

- HeurAgenix 的 $V,Q,\pi^{\star}$ 是本模型的特殊情形：单阶段、固定 $M=5$、确定转移、无约束、精确终点代价；
- 本模型新增：预算增广状态、option 变时长、契约 shield、多目标效用、机会约束、多保真观测；
- `09` 中已给对应关系表，本文不再重复，公式冲突时以本文 §4 为准。

---

## 5. 多保真评估与主动资源分配

EDA 的核心困难：真实目标（signoff PPA/DRC）一次评估要分钟到小时，而代理指标（HPWL/overflow）秒级但带偏差。本节把"评估"本身建模为可分配、可校准、可置信的决策资源。

### 5.1 保真度层级

$$
l\in\{F0,F1,F2,F3\}
$$

| 保真度 | 评估对象 | 成本 $c_l$ | 偏差 $b_l$ | 方差 $\sigma_l^2$ |
|---|---|---|---|---|
| F0 | schema/单测/静态检查 | $\approx0$ | 无 | 0 |
| F1 | 代理 + 快速 checker：HPWL、density、拥塞代理、连通性 | 秒级 | 大 | 小 |
| F2 | 子 flow：placement+GRT，或局部 canary | 分钟级 | 中 | 中 |
| F3 | 全 flow signoff：DRC/LVS/STA(SPEF)/power | 小时级 | 最小 | 大 |

**约定：** F3 是"真实目标"的唯一权威；F0–F2 只用于筛选、排序与升保真决策，不能作为最终晋升依据。

### 5.2 观测模型

对任意 option $\omega$ 在状态 $s$ 下的真实（F3）增益 $\Delta U(s,\omega)$，保真度 $l$ 给出观测：

$$
\widetilde{\Delta U}_l(s,\omega)
=\Delta U(s,\omega)+b_l(s,\omega)+\varepsilon_l,\qquad
\mathbb{E}[\varepsilon_l]=0,\quad
\mathrm{Var}(\varepsilon_l)=\frac{\sigma_l^2}{n_l}
$$

- $b_l$ 为保真度偏差（proxy gap）；
- $n_l$ 为该候选在保真度 $l$ 上的评估次数；
- 若代理误差随状态变化，可写成 $b_l(s,\omega)$，并用回归/GP/集成模型估计。

### 5.3 偏差校准与置信上界

在审计集 $\mathcal{A}_{\text{audit}}$ 上同时跑 F_l 与 F3，估计偏差：

$$
\hat b_l=\frac{1}{|\mathcal{A}_{\text{audit}}|}\sum_{a\in\mathcal{A}_{\text{audit}}}
\Big(\widehat{\Delta U}_l(a)-\widehat{\Delta U}_3(a)\Big)
$$

给定置信水平 $1-\alpha_b$，偏差上界：
$$
\beta_l=\big|\hat b_l\big|+t_{1-\alpha_b/2,\,n_a-1}\frac{\hat\sigma_{b_l}}{\sqrt{n_a}}
$$

**原则：** 偏差上界没用审计集校准过的代理，不能进入晋升决策；审计集按 design family 分层。

### 5.4 保守估计（LCB/UCB）

$$
\mathrm{LCB}_{1-\alpha}^{\,l}(s,\omega)
=\widehat{\Delta U}_l(s,\omega)-\beta_l
-z_{1-\alpha}\frac{\hat\sigma_l(s,\omega)}{\sqrt{n_l}}
$$

$$
\mathrm{UCB}_{1-\alpha}^{\,l}(s,\omega)
=\widehat{\Delta U}_l(s,\omega)+\beta_l
+z_{1-\alpha}\frac{\hat\sigma_l(s,\omega)}{\sqrt{n_l}}
$$

- 性能增益用 LCB（保守）；
- 失败概率/风险用 UCB（保守）；
- 当 $\beta_l$ 或 $\hat\sigma_l$ 过大时，不应当用该保真度做最终决策。

### 5.5 预算分配：选多少、在哪档选

**优化问题：**
$$
\max_{\{n_l\}_{l=0}^{L}}\ \mathbb{E}\Big[U\big(\text{最终决策}\big)\Big]
\quad\text{s.t.}\quad
\sum_{l=0}^{L}n_l c_l\le B_{\text{eval}}
$$

**两种实用近似：**

1. **OCBA（Optimal Computing Budget Allocation）：** 以"正确选出最优候选的概率"为目标，按各候选的均值/方差分配样本；适合候选数中等、评估噪声近似正态的情形。
2. **VOI（Value of Information）：**
$$
\mathrm{VOI}_l\approx
\frac{\partial\,\mathbb{E}[\text{最终决策质量}]}{\partial n_l}\Big/c_l
$$
优先给"能改变当前决策 + 单位成本信息量大"的保真度加样本。

**工程默认（Phase 0/1）：** F0 全过 → F1 保留 top 30% → F2 保留 top 5–10 个 → F3 只对最终决策/晋升候选做；每层保留比例可随预算调整。

### 5.6 升保真与 racing 规则

$$
\mathrm{Promote}(\omega:l\to l+1)
\iff
\mathrm{LCB}_{1-\alpha}^{\,l}(s,\omega)\ge \tau_l
\ \wedge\
\text{剩余预算}\ge c_{l+1}
\ \wedge\
\hat\sigma_l>\sigma_{\text{target}}
$$

- $\tau_l$ 是各保真度的晋升阈值（例如 F1 上"代理预测需优于基线至少 $\tau_1$"）；
- 不满足的候选直接淘汰，不浪费 F2/F3；
- 连续淘汰/晋升规则与 Hyperband、successive halving 同源，但阈值由偏差校准与风险约束决定。

### 5.7 代理欺骗（reward hacking）防护

代理指标可能被优化坏，必须加四道防线：
1. **F3 审计：** 随机抽样候选跑完整 signoff，检查代理排序与真实排序的一致性（Spearman/Kendall）；
2. **悲观校正：** 用 $\beta_l$ 与 LCB，不用点估计；
3. **多目标保留：** 代理只用于筛选，最终按 §3.4 的多目标效用与硬门禁判定；
4. **分布监控：** 监控代理误差随状态/设计族漂移，超阈值触发重新校准或降级到高保真。

---

## 6. 信用分配、演化与选择器学习

### 6.1 反事实信用与 Shapley

给定正/负轨迹对，在同一 checkpoint 上固定后续策略 $\pi_{\text{frozen}}$，做单点反事实重放：

$$
\delta_i=U\Big(\mathrm{Replay}\big(s_i,a_i^+;\pi_{\text{frozen}}\big)\Big)
-U\Big(\mathrm{Replay}\big(s_i,a_i^-;\pi_{\text{frozen}}\big)\Big)
$$

若决策间存在交互（非可加），用 Shapley 值：
$$
\phi_i=\sum_{S\subseteq\mathcal{D}\setminus\{i\}}
\frac{1}{n\binom{n-1}{|S|}}\Big[v(S\cup\{i\})-v(S)\Big],
\qquad
v(S)=U\big(\text{按 }S\text{ 替换决策后的重放}\big)
$$
其中 $n=|\mathcal{D}|$；该权重与经典阶乘归一化 Shapley 权重等价。  
**近似流程：** 先用单点 $\delta_i$ 排序取 top-$m$，再对 top-$m$ 做分组/两两交互重放，取
$$
i^{\star}=\arg\max_i|\hat\phi_i|\quad\text{或}\quad\arg\max_i|\delta_i|
$$
把 $(s_{i^{\star}},a^-_{i^{\star}},a^+_{i^{\star}},\hat\phi_{i^{\star}},\text{契约},\text{失败模式})$ 作为演化 prompt 的证据。

### 6.2 势函数 shaping 及其不变性

定义状态势函数（下游后果代理）：
$$
\Phi(s)=-\Big(\lambda_1\widehat{\mathrm{OF}}_{\text{route}}(s)
+\lambda_2\widehat{\mathrm{TNS}}_{\text{post-route}}(s)
+\lambda_3\widehat{N}_{\text{DRC}}(s)
+\lambda_4\widehat{\mathrm{MOF}}(s)\Big)
$$
shaping 奖励：
$$
F(s,s')=\gamma^{\rho}\Phi(s')-\Phi(s)
$$
**命题（Ng et al. 1999）：** 若 $\Phi$ 只依赖状态，则对任意转移与奖励，加入 $F$ 后最优策略不变；因此 shaping 只加速信用传播，不改变最优目标。  
**估计误差处理：** 在线用悲观势函数
$$
\Phi^-(s)=\hat\Phi(s)-\kappa\hat\sigma_\Phi(s)
$$
并在 F3 审计中验证 $\Phi$ 对应的真实指标；若真实指标恶化，降低 shaping 权重或关闭。

### 6.3 双层演化：外层学 skill 库，内层学 selector

**内层：**
$$
\pi^{\star}(\mathcal{L})=\arg\max_{\pi}\ \mathbb{E}\Big[\sum_j\gamma^{\rho_j}r_j\Big]
\quad\text{s.t.}\quad \Pr(G_3=0)\le\delta_{\text{fail}}
$$

**外层：**
$$
\max_{\mathcal{L}\subset\Omega,\ |\mathcal{L}|\le K}\ 
\mathcal{J}_{\text{outer}}(\mathcal{L})
=\mathbb{E}_{d\sim\mathcal{D}_{\text{val}}}\Big[J\big(\mathrm{Flow}_{\pi^{\star}(\mathcal{L})}(d)\big)\Big]
-\lambda_{\text{evo}}\,\mathrm{Cost}(\mathcal{L})
$$
约束：库内每个 skill 通过契约与 L3 审计；$\mathcal{J}_{\text{outer}}$ 用 §3.7 的 LCB 估计。

**演化算子：**
$$
\mathcal{M}_{\text{LLM}}:\ (\mathcal{L},\text{evidence})\to\{\omega'_1,\dots\}
$$
三级变异：
- L1：参数/阈值/权重/顺序；
- L2：触发条件/组合/停止/fallback；
- L3：受限 DSL/AST 结构。

**接受判据（门控晋升）：**
$$
\mathrm{Accept}(\omega')=1\iff
\mathrm{LCB}_{1-\alpha}(\Delta U(\omega'))>0
\ \wedge\
\mathrm{UCB}_{1-\alpha}\big(P^{L3}_{\text{fail}}(\omega')\big)<\varepsilon
\ \wedge\
\hat c(\omega')\le B_{\text{skill}}
$$
不通过的候选进入负档案（negative archive），用于避免重复踩坑。可选 QD 档案：

$$
\max_{\mathcal{A}}\ \sum_{\omega\in\mathcal{A}}q(\omega)+\lambda_{\text{div}}\mathrm{Div}(\mathcal{A})
$$

### 6.4 Selector 离线数据集

通过 checkpoint replay 收集：
$$
\mathcal{D}_{\text{offline}}=\Big\{\big(o_i,\{\omega\},\widehat{\Delta U},\hat c,\hat P_{\text{fail}},G_3\big)\Big\}
$$
两类轨迹：
- **greedy：** 每步选当前最优 option；
- **stochastic：** 故意选次优/随机，或人为注入 overlap/拥塞/时序恶化状态，要求 selector 用修复 skill 救回并最终过 $G_3$。

### 6.5 CA-POR：成本感知偏好奖励

**排名分数（单位成本、扣风险后的 LCB）：**
$$
\varrho(s,\omega)=\frac{\mathrm{LCB}_{1-\alpha}[\Delta U(s,\omega)]-\lambda_r\mathrm{UCB}_{1-\alpha}[P_{\text{fail}}(s,\omega)]}{\hat c(s,\omega)+\epsilon_c}
$$
按 $\varrho$ 降序，$\omega$ 排第 $\ell$ 位。  
**统计阈值（数据驱动，替代手工 $n_{pos},n_{neg}$）：**
$$
n_{\text{pos}}(s)=\max\Big\{n:\forall\ell\le n,\ 
\mathrm{LCB}[\Delta U_{(\ell)}]-\lambda_r\mathrm{UCB}[P_{\text{fail},(\ell)}]>0\Big\}
$$
$$
n_{\text{neg}}(s)=\min\Big\{n:\forall\ell\ge n,\ 
\mathrm{UCB}[\Delta U_{(\ell)}]-\lambda_r\mathrm{LCB}[P_{\text{fail},(\ell)}]<0\Big\}
$$
**分段奖励：**
$$
R_{\text{CA-POR}}(s,\omega)=
\begin{cases}
R_p\left(1-\dfrac{\ell-1}{n_{\text{pos}}}\right), & 1\le\ell\le n_{\text{pos}}\\[2mm]
-R_n\left(\dfrac{\ell-n_{\text{pos}}}{n_{\text{neg}}-n_{\text{pos}}}\right), & n_{\text{pos}}<\ell\le n_{\text{neg}}\\[2mm]
-R_L, & n_{\text{neg}}<\ell\le n
\end{cases}
$$

### 6.6 EDA-CPR：状态感知奖励

状态卡字段分为类别型 $Cat$、序数型 $Ord$（density/拥塞/时序/overflow/失败严重度，0–4）、二值型 $Bin$（合法/连通/是否 gate 失败）。

$$
R_{\text{EDA-CPR}}
=\sum_{i\in Cat}\Big[\mathbb{I}(\hat z_i=z_i)R_i^+-\mathbb{I}(\hat z_i\ne z_i)R_i^-\Big]
+\sum_{j\in Ord}\Big[R_j^+-\kappa_j|\hat z_j-z_j|\Big]
+\sum_{k\in Bin}\Big[\mathbb{I}(\hat b_k=b_k)R_k^+-\mathbb{I}(\hat b_k\ne b_k)R_k^-\Big]
$$
**额外安全/成本项：**
$$
R_{\text{gate}}=R_g^+\mathbb{I}(\hat g=g)-R_g^-\mathbb{I}(\hat g\ne g),
\qquad
R_{\text{cost}}=-\big|\log(\hat c+1)-\log(c+1)\big|
$$
**总奖励：**
$$
R_{\text{total}}
=\lambda_{\text{POR}}R_{\text{CA-POR}}
+\lambda_{\text{CPR}}R_{\text{EDA-CPR}}
+\lambda_gR_{\text{gate}}
+\lambda_cR_{\text{cost}}
+\lambda_{\text{fmt}}R_{\text{fmt}}
$$

### 6.7 GRPO 训练目标

对每个状态采 $G$ 条响应，组内相对优势：
$$
\hat A^{(g)}=R_{\text{total}}^{(g)}-\frac{1}{G}\sum_{g'=1}^{G}R_{\text{total}}^{(g')}
$$
最大化带截断的策略比率目标：
$$
\max_\theta\ \mathbb{E}\Big[\frac{1}{G}\sum_g \min\big(\rho_g(\theta)\hat A^{(g)},\ 
\mathrm{clip}(\rho_g(\theta),1-\epsilon,1+\epsilon)\hat A^{(g)}\big)\Big]
$$
$$
\rho_g(\theta)=\frac{\pi_\theta(\omega^{(g)}\mid o)}{\pi_{\theta_{\text{old}}}(\omega^{(g)}\mid o)}
$$
（保留 HeurAgenix 的 GRPO 训练流程，奖励项换成 §6.5/6.6。）

---

## 7. 可声明性质、假设与边界

本节明确：在这套模型下**哪些性质可以证明或声明**，哪些只能统计声明，哪些不能承诺。论文写作必须区分这三类。

### 7.1 假设清单

| 编号 | 假设 | 作用 |
|---|---|---|
| A1 | 阶段合法集 $\mathcal{F}_g$ 的 checker 正确实现 PDK/设计约束 | shield 与 gate 的有效性 |
| A2 | shield 在 accepted transition 前检查 $\mathrm{Post}_k,\mathrm{Inv}_k,G_g$，失败时回滚到字节级一致的 checkpoint | 安全性 |
| A3 | fallback 至少能复现 baseline 的合法结果 | 点态不劣化 |
| A4 | L3 失败概率可由抽样估计，且抽样设计不偏 | 机会约束 |
| A5 | 候选与 baseline 可配对：同设计、同 checkpoint、同 seed、同冻结后续策略 | 因果效应识别 |
| A6 | 第一阶段不修改 RTL/netlist，功能等价性由 LVS 兜底 | 功能正确性隔离 |
| A7 | 工具/PDK/模型版本在实验内冻结并记录 | 可复现性 |

### 7.2 命题（shield 安全性）

**命题 1.** 在 A1、A2 下，对任意策略 $\pi$，从任意合法 checkpoint 出发，若 shield 检查通过才接受，则 flow 中被接受的每个检查点都满足对应阶段的合法集；若某步失败，回滚后仍停留在原合法 checkpoint。  
**证明思路：** 对决策步数归纳。每步 accepted transition 的条件直接包含 $\mathrm{Inv}_k$ 与 $G_g$；失败分支返回同一 $s$，由 A2 保证状态不变。$\square$

**推论 1.1.** 若 fallback 为 baseline 且满足 A3，则最终输出至少有一个满足 L0/L1/阶段 gate 的合法解；L3 残余风险由机会约束单独管理。

### 7.3 命题（点态不劣化）

**命题 2（精确评估版）.** 若对每个设计，策略只在候选最终效用 $U_{\text{cand}}\ge U_{\text{base}}$ 时接受候选，否则执行 baseline，则该设计上的最终效用不低于 baseline。  
**命题 3（带噪评估版）.** 若接受规则改用配对 LCB：$\mathrm{LCB}_{1-\alpha}(U_{\text{cand}}-U_{\text{base}})>0$，则在不满足时回退 baseline 的前提下，"部署结果不劣于 baseline" 以至少 $1-\alpha$ 的概率成立（单次决策；序贯场景用置信序列控制整体 $\alpha$）。

**注意：** 命题 2 的"候选"本身可能比 baseline 差，只是被拒绝；该性质保证的是**部署输出**，不是"每个候选都好"。

### 7.4 命题（势函数 shaping 不变性）

**命题 4.** 若 shaping 项为 $F(s,s')=\gamma^{\rho}\Phi(s')-\Phi(s)$ 且 $\Phi$ 只依赖状态 $s$（不依赖动作、后继或时间），则加入 $F$ 的前后最优策略集合相同（Ng, Harada, Russell 1999）。  
**估计误差推论：** 若使用 $\hat\Phi$ 且 $|\hat\Phi-\Phi|\le\eta$，则在有限状态/动作与有界奖励下，最优值函数的误差可由 $\eta$ 的某个常数倍控制（标准扰动界）；工程上用悲观 $\Phi^-$ 降低乐观误差风险。

### 7.5 统计声明（可发布口径）

| 声明 | 需要的证据 | 不能声明的内容 |
|---|---|---|
| 可复现 | 版本/seed/输入冻结；重复运行容差内 | 不能推出"性能提升" |
| 局部因果 | 同 checkpoint 配对 A/B；冻结后续策略 | 不能直接推全体设计分布 |
| 群体统计提升 | 留出 design family；分层 bootstrap；$\mathrm{LCB}(\Delta)>0$ | 不能声称"每个设计都提升" |
| 风险有界 | 失败率 UCB $<\epsilon$；CVaR 约束；最优/最差族报告 | 不能声称"绝对无 DRC/LVS 失败" |
| 相对最优 | oracle/上界对照、regret 分析 | 不能声称"全局最优" |

### 7.6 明确不能承诺的性质

1. **全局最优**：布局/布线/DRC 约束问题本身 NP-hard，本文所有优化都是启发式近似；
2. **零泛化风险**：未见设计族、工艺节点、工具版本可能退化；
3. **代理一致性**：F1/F2 与 F3 的排序在分布漂移下可能翻转，必须审计与重校准；
4. **LLM 稳定性**：API 模型版本/日期变化可能导致 selector 行为漂移，必须固定 eval prompt 与回归集；
5. **精确因果**：多步决策存在交互效应，单点反事实只是近似，Shapley 也有采样误差；
6. **DFT/ATPG 正确性**：若纳入 scan/test point，需要额外约束与检查（见 §10）。

---

## 8. 数学对象 ↔ 实现落点映射

下表把本文符号映射到建议的目录/文件/工具，作为 Phase 0 建 harness 的对照表。

| 数学对象 | 实现产物 | 路径/工具 |
|---|---|---|
| 设计 $\mathcal{D}$、工艺 $R$ | 设计配置、PDK 版本锁 | `designs/*.def`, `config/*.json`, `env.lock` |
| 阶段 checkpoint $x_g$ | ODB/DEF + 指标 | `checkpoints/<design>_<stage>_s<seed>.odb` |
| 指标 $m_g$ | metrics CSV | `results/metrics/*.csv` |
| 状态卡 $\sigma(s)$ | JSON schema + extractor | `state/state_card.schema.json`, `state/extract.py` |
| 图特征 $\varphi(s)$ | 图/向量导出 | `state/graph_features.py` |
| skill $k$、参数 $\theta$、停止 $\tau$ | YAML skill 卡 | `skills/*.yaml` |
| 契约 $C_k$ | 前置/后置/不变式检查 | `verifier/contracts/*.yaml` |
| shield $\mathcal{S}_k$ | 执行包装器 | `runtime/shield.py` |
| 转移 $P$ | 工具执行 + 快照 | `runtime/executor.py`, `checkpoints/` |
| 预算 $b$ | 运行时/工具/API 计数器 | `runtime/budget.py` |
| 效用 $U$ | 归一化 + HVI/字典序 | `metrics/utility.py` |
| gate $G$ | L0–L3 验证栈 | `verifier/` + OpenROAD/Magic/Netgen/OpenSTA |
| 保真度 $(b_l,\sigma_l^2,c_l)$ | 代理 + 校准 + 成本模型 | `fidelity/estimator.py`, `fidelity/calibration.py` |
| selector $\pi_\theta$ | 在线选择器/蒸馏模型 | `selector/` |
| 经验库 | SQLite/JSONL 经验记录 | `experience/experience.db`, `experience/*.jsonl` |
| 演化算子 $\mathcal{M}_{\text{LLM}}$ | 变异生成 + 验证 | `evolver/` |
| 反事实信用 $\delta_i,\phi_i$ | replay 与 Shapley 近似 | `credit/replay.py`, `credit/shapley.py` |
| 测试协议 $\mathcal{T}_{\text{test}}$ | 配对实验/统计报告 | `eval/protocol.yaml`, `eval/report.py` |
| 运行记录 | `meta.json` | `results/runs/<run_id>/meta.json` |

**建议目录结构（Phase 0 新建，与 TSP 复现隔离）：**
```
heura_repro/eda/
  designs/  config/  checkpoints/  state/  skills/  runtime/
  verifier/  fidelity/  selector/  evolver/  credit/  experience/
  eval/  results/  logs/  docs/
```

---

## 9. Phase 0 测试设计（基于本数学体系）

Phase 0 的目标不是刷 PPA，而是**验证这套数学体系与实现一致**：能测、能复现、能回滚、能校准、能统计。以下 11 个测试全部通过后才进入 Phase 1 的 skill 效力实验。

| 编号 | 测试 | 步骤（摘要） | 通过标准 |
|---|---|---|---|
| P0-1 | 文档—实现一致性 | 每个符号/公式有对应代码/配置；跑 `symbol_check` | 无未定义对象；公式版本号一致 |
| P0-2 | Harness 可复现 | 同设计/seed/工具版本跑 baseline 3 次 | 指标差 $\le\epsilon_{\text{rep}}$；日志/hash 齐全 |
| P0-3 | Shield 安全性 | 注入非法 skill（越界/改 fixed/制造 overlap） | 10/10 被 L1 拦截并字节级回滚 |
| P0-4 | Gate 正确性 | 用手工构造的 known-good/bad 样本验证 L0–L3 | 判定与专家/工具一致；无假阴性 |
| P0-5 | 代理校准 | F1 vs F3 在审计集上的偏差与排序 | 偏差上界有限；Spearman $\ge\rho_0$；否则不许晋升 |
| P0-6 | 配对估计器 | 注入已知 synthetic effect（如指标平移）到 replay 数据 | 估计值覆盖真值；零效应下 type-I 错误 $\le\alpha$ |
| P0-7 | Selector sanity | random / oracle / selector 三档 | random 与 oracle 有可测 gap；selector 不差于 random |
| P0-8 | 演化门控 | 构造 known-bad 与 known-good 候选 skill | bad 不晋升；good 在预算内晋升 |
| P0-9 | 预算核算 | 对比 runtime/tool/API 实际值与记录值 | 误差 $\le$ 容差；超预算自动截断 |
| P0-10 | 可追溯性 | 检查每次运行 `meta.json` | design/tool/PDK/skill/model/prompt/seed 全可查 |
| P0-11 | Skill 效力 pilot | 6 个 L1 skill × 10–20 checkpoint × 3 seeds | 给出 $\delta_k$ 分布、LCB、gate 通过率；至少一个 skill 在 $\ge2$ 族上 LCB>0 |

**Phase 0 退出判据：** P0-1 到 P0-11 全通过；baseline 与 selector 的测量协议稳定；若 P0-11 未出现任何正效应，先校准 skill/代理，不进入 Phase 1 演化。

**Phase 0 报告必须包含：**
- 测试集/设计族清单与冻结版本；
- 每个 skill 的配对效应分布、LCB、失败率 UCB、成本；
- 代理偏差/方差校准曲线与审计结论；
- 系统安全事件（非法动作、回滚、fallback）统计；
- 已知不完美与下一步决策建议。

---

## 10. 适用范围、已知不完美与扩展接口

### 10.1 适用范围

- 数字标准单元设计（OpenLane1 + sky130A 起步）；
- 固定 RTL/netlist 的 physical-only 优化（第一阶段）；
- 布局（floorplan/GP/legalize）、CTS、全局/详细布线、signoff 各阶段的参数/策略/调度级优化；
- 工具为 OpenROAD/OpenLane/Magic/Netgen/OpenSTA 等可控开源工具链。

### 10.2 已知不完美

| 问题 | 影响 | 缓解 |
|---|---|---|
| 布局/布线/DRC 问题 NP-hard | 无全局最优保证 | 只声明启发式/统计改进；用 oracle/上界对照 |
| 代理与 signoff 有 gap | 可能优化错方向 | 偏差校准 + 悲观 LCB + F3 审计 |
| 工具随机性 | 效应估计有噪声 | seed 冻结 + 配对重放 + 重复实验 |
| 多步交互效应 | 单点反事实有偏 | Shapley 近似 + 分组重放；报告近似误差 |
| 设计分布有限 | 泛化不可证 | 按 family 切分；报告最差族；QD 档案 |
| LLM/API 漂移 | 决策不稳定 | 固定 prompt hash/eval set；回归监控；可蒸馏本地模型 |
| 约束/工艺规则不完整 | shield 漏检 | L0–L3 分层 + 审计 + 金标准样本 |
| 成本模型不准 | 预算分配失真 | 实测校准成本分布；在线更新 |

### 10.3 扩展接口

- **DFT/ATPG：** 增加 scan chain 顺序/长度平衡约束、test point 合法性、test wirelength 目标；在 §2.5/2.6 的流模型中把 scan net 作为特殊 net，并增加 $G_{\text{DFT}}$ gate。
- **多 corner/IR/EM/信号完整性：** 扩展 $G_3$ 为向量，增加 $G_{\text{IR}},G_{\text{EM}},G_{\text{SI}}$；效用向量相应扩展。
- **3D-IC/先进节点：** 增加 TSV/hybrid bonding 约束与层间容量；Routing 图变多 die 图。
- **模拟/混合信号：** 增加匹配/对称/寄生约束；布局目标替换为模拟专用指标。
- **多目标偏好学习：** 用人类/设计者反馈学习 $w$ 或效用函数，替代手工权重。

---

## 附录 A. 核心符号总表

| 符号 | 含义 | 首次出现 |
|---|---|---|
| $\mathcal{D}$ | 设计（网表 + 约束 + PDK） | §1.1 |
| $R$ | 工艺规则 | §1.1 |
| $p$ | 布局变量 $(x_i,y_i,o_i)$ | §1.2 |
| $\mathcal{F}_g$ | 阶段 $g$ 合法集 | §1.2–2.7 |
| $G_g,G_3$ | 阶段/signoff gate | §2.7 |
| $\mathcal{G}_r,\mathcal{G}_{\text{track}}$ | 全局/详细布线图 | §1.3 |
| $f_{n,e},o_e$ | 线网流量/边溢出 | §2.5 |
| $N_{\text{DRC}}$ | DRC 违例数 | §2.6 |
| $y,\tilde y,U$ | 指标向量/归一化/效用 | §3.1–3.4 |
| $\Delta U_{\mathrm{HV}}$ | 超体积改进 | §3.4 |
| $\delta,\Delta$ | 配对效应/总体效应 | §3.6 |
| $\mathrm{LCB},\mathrm{UCB}$ | 置信下/上界 | §3.7, §5.4 |
| $s,\omega,C_k$ | 状态/option/契约 | §4.2–4.3 |
| $\mathcal{S}_k$ | shield 算子 | §4.4 |
| $r,\gamma,\rho$ | 奖励/折扣/时长 | §4.5–4.6 |
| $b,B,\delta_{\text{fail}}$ | 预算/预算上界/允许失败率 | §4.2, §4.7 |
| $\mathcal{L}$ | skill 库 | §6.3 |
| $\delta_i,\phi_i$ | 反事实/Shapley 信用 | §6.1 |
| $\Phi,F$ | 势函数/shaping | §6.2 |
| $R_{\text{CA-POR}},R_{\text{EDA-CPR}}$ | 选择器奖励 | §6.5–6.6 |

## 附录 B. 八个核心公式速查

1. **HPWL：** $\sum_n[\max x-\min x+\max y-\min y]$
2. **密度溢出：** $\sum_b\max(0,D_b-C_b)/\sum_b C_b$
3. **全局布线 MCF：** 流守恒 + $\sum_n f_{n,e}\le c_e$ + $\min\sum_e\ell_e d_e+\lambda\sum_e o_e$
4. **option Bellman：** $Q(s,\omega)=\mathbb{E}[r+\gamma^{\rho}V(s')]$，$V(s)=\max_{\Omega_{\text{adm}}}Q$
5. **约束目标：** $\max\mathbb{E}[\sum\gamma^{\rho}r]$ s.t. $\Pr(G_3=0)\le\delta_{\text{fail}}$，$\sum\rho\le B$
6. **在线分数：** $\mathrm{Score}=\mathrm{LCB}(\Delta U)-\lambda_c c/b-\lambda_r\mathrm{UCB}(P_{\text{fail}})$
7. **多保真 LCB：** $\mathrm{LCB}_l=\widehat{\Delta U}_l-\beta_l-z\hat\sigma_l/\sqrt{n_l}$
8. **CA-POR/EDA-CPR：** 单位成本 LCB 排名 + 统计阈值分段的偏好奖励 + 类别/序数/gate/cost 状态感知奖励

## 附录 C. 运行记录 schema（meta.json）

```json
{
  "run_id": "2026xxxx_<design>_<stage>_<policy>_s<seed>",
  "design": {"name": "...", "family": "...", "hash": "sha256:..."},
  "toolchain": {"openroad": "...", "openlane": "...", "pdk": "sky130A", "magic": "...", "netgen": "...", "opensta": "..."},
  "checkpoint": {"id": "...", "stage": "...", "hash": "sha256:..."},
  "policy": {"type": "HA-PR|baseline", "skill_library_version": "...", "selector": {"model": "...", "prompt_hash": "..."}},
  "seed": 0,
  "budget": {"time_s": 0, "api_calls": 0, "tool_calls": 0},
  "decisions": [{"step": 1, "state_hash": "...", "chosen": "...", "params": {}, "fidelity": "F1", "score": 0.0, "gate": "pass"}],
  "final": {"G3": true, "wns": 0.0, "tns": 0.0, "power": 0.0, "area": 0.0, "wirelength": 0.0, "drc": 0, "runtime_s": 0},
  "artifacts": {"checkpoints": [], "logs": [], "reports": []}
}
```

## 附录 D. 参考

1. Wang et al., *HeurAgenix*, arXiv:2506.15196v2（§2.1, §3.1–3.3, Eq.1, Algorithm 1, POR/CPR）。
2. Sutton, Precup, Singh, *Between MDPs and semi-MDPs*, AIJ 1999（options/semi-MDP）。
3. Puterman, *Markov Decision Processes*, 1994（MDP/semi-MDP 最优性）。
4. Ng, Harada, Russell, *Policy invariance under reward transformations*, ICML 1999（势函数 shaping）。
5. Altman, *Constrained Markov Decision Processes*, 1999（约束 MDP/机会约束）。
6. Rockafellar, Uryasev, *Optimization of Conditional Value-at-Risk*, 2000。
7. Zitzler, Thiele, *Multiobjective evolutionary algorithms*, 1999（hypervolume）。
8. Li et al., *Hyperband*, JMLR 2018；Chen et al., OCBA 相关工作。
9. Shapley, *A value for n-person games*, 1953。
10. OpenROAD/OpenLane/Magic/Netgen/OpenSTA 文档；ISPD/ICCAD placement/routing benchmark 说明。
11. 本项目：`01` 精读报告、`04–09` EDA 迁移设计、`09B` 一页版、`eda_pr_flow.pdf` 对照图。

---

**文档结论：** 这套体系把"布局布线的物理模型、质量与门禁、超启发式决策、多保真评估、信用/学习与演化、统计测试"六层闭合起来；只要 Phase 0 的 P0-1 到 P0-11 通过，就可以把本文作为方法章节的数学基础，并进入 Phase 1 的 skill 效力实验。

## 11. 种子启发式（Seed Skill）的发现、筛选与组库

### 11.1 种子是什么：初始 option 集合，而不是"当前最强 skill"

在 HA-PR 中，种子启发式对应一个契约化 option：
$$
\omega_0=(k,\theta,\tau),\qquad C_k=(\mathrm{Pre},\mathrm{Post},\mathrm{Inv},\mathrm{Fallback},\mathrm{Cost},\mathrm{Evidence})
$$
一个种子库（seed library）是
$$
\mathcal{L}_0=\{\omega_1,\dots,\omega_K\}\subset\Omega_0
$$
其中 $\Omega_0$ 是候选种子空间。种子的使命不是"立刻赢"，而是**为后续 Phase E 演化提供安全、可测、可变异、覆盖关键状态的起点**。因此选种应优化"演化后的最终收益"，而不是只优化种子当前表现。

### 11.2 选种问题的形式化

**理想目标（元层选种）：**
$$
\max_{\mathcal{L}_0\subset\Omega_0,\ |\mathcal{L}_0|\le K}
\ \mathbb{E}\Big[\mathcal{J}_{\text{outer}}\big(\mathcal{M}^{(E)}_{\text{LLM}}(\mathcal{L}_0)\big)\Big]
$$
约束：
$$
\forall \omega\in\mathcal{L}_0:\ \mathrm{ContractPass}(\omega)=1,\quad
\Pr\big(G_3=0\mid \omega\big)\le\epsilon_{\text{fail}},\quad
\sum_{\omega\in\mathcal{L}_0}\hat c(\omega)\le B_{\text{seed}}
$$
其中 $\mathcal{M}^{(E)}_{\text{LLM}}$ 是 $E$ 轮演化算子。该目标无法直接计算，所以用代理目标：
$$
\widehat{\mathcal{S}}(\mathcal{L}_0)
=\sum_{\omega\in\mathcal{L}_0}\mathrm{SeedScore}(\omega)
+\lambda_{\text{div}}\mathrm{Div}(\mathcal{L}_0)
$$
**单种子评分：**
$$
\mathrm{SeedScore}(\omega)=
\underbrace{\frac{\mathrm{LCB}_{1-\alpha}[\Delta U(\omega)]-\lambda_r\mathrm{UCB}[P_{\text{fail}}(\omega)]}{\hat c(\omega)+\epsilon_c}}_{\text{单位成本、扣风险的效用下界}}
+\lambda_{\text{cov}}\mathrm{Cov}(\omega)
+\lambda_{\text{ev}}\mathrm{Evolvability}(\omega)
$$
**覆盖度：** 设目标状态被聚类为 $\mathcal{C}_{\text{state}}$，每个簇 $c$ 的权重为 $p_c$：
$$
\mathrm{Cov}(\omega)=\sum_{c\in\mathcal{C}_{\text{state}}}p_c\cdot\mathbb{1}\big[A_\omega(c)=1\big]
$$
**可演化性（Evolvability）：** 参数化程度、失败反馈清晰度、验证风险的组合：
$$
\mathrm{Evolvability}(\omega)=
\frac{1}{3}\Big(\mathbb{1}[\omega\text{ 有可调参数/触发条件}]
+\mathbb{1}[\omega\text{ 有可观测失败模式}]
+\mathbb{1}[\omega\text{ 的风险面可控}]\Big)
$$
**多样性：** 用行为描述子集合的覆盖/熵度量：
$$
\mathrm{Div}(\mathcal{L}_0)=\big|\{b(\omega):\omega\in\mathcal{L}_0\}\big|
\quad\text{或}\quad
\mathrm{Div}(\mathcal{L}_0)=-\sum_{b}p_b\log p_b
$$
若覆盖度按集合覆盖定义，则 $\widehat{\mathcal{S}}$ 具有子模性；用贪心即可得到 $1-1/e$ 近似。**结论：选种是"组合覆盖 + 质量 + 可演化性"问题，不是单指标排序。**

### 11.3 种子来源：六类入口

| 来源 | 具体做法 | EDA 示例 | 风险 |
|---|---|---|---|
| S1 工具原生 | 把 OpenROAD/OpenLane 的默认策略、参数、推荐 recipe 封装为 option | density/WL 权重、layer adjustment、RRR iterations、drc repair effort | 低 |
| S2 经典算法封装 | 经典求解器/算法模板参数化 | SA/QP/ePlace/DREAMPlace、Abacus 合法化、pattern routing、Lagrangian 松弛 | 低–中 |
| S3 文献/竞赛 | 从论文、ISPD/ICCAD benchmark recipe、OpenROAD-flow-scripts 中抽取策略 | timing-driven placement、congestion-aware RRR、via/antenna repair | 中 |
| S4 经验库挖种 | 从 baseline/探索轨迹中做规则/因果挖掘，找"什么状态用什么参数有效" | 高 overflow 时 layer bias；WNS 差时 timing weight | 中 |
| S5 失败驱动修复 | 从失败日志/DRC cluster/overlap 热点反向定义修复 skill | legalize order、DRC repair order、局部重布 | 低（gate 清晰） |
| S6 LLM 生成 | 给工具文档 + 状态卡 + skill schema，只生成 L1 参数/L2 触发组合 | 新的 cost shaping 规则、conditional RRR trigger | 中–高（需 verifier） |
| S7 迁移/贝叶斯优化 | 跨设计族迁移已有种子；参数空间大时用多保真 BO/DOE 拟合 | 从 `gcd` 迁移到 `spm`；GRT 参数搜索 | 低–中 |

**优先顺序建议：** S1/S2/S5（安全、可验证）→ S3/S4（有依据）→ S6（最后、必须过 verifier）→ S7（离线低成本时用）。

### 11.4 行为描述子与状态聚类

选种前先定义两个映射，否则"多样性"和"覆盖"无法计算：

**行为描述子：**
$$
b(\omega)=\big(\text{阶段},\ \text{目标状态簇},\ \text{优化目标侧重},\ \text{成本档},\ \text{风险档},\ \text{参数化类型}\big)
$$
例如：`("global_route", "high_congestion", "overflow_first", "medium", "low", "layer_bias")`。用于判断两个种子是否"在做同一件事"。

**状态聚类：** 用 checkpoint 指标/状态卡特征（density、congestion、timing、legality、design family）聚类成 $\mathcal{C}_{\text{state}}$，例如 8–12 个簇。每个簇应至少有一个种子可作用。

### 11.5 六步筛选流程（与 Phase 0 对齐）

| 步 | 名称 | 做什么 | 产出/对齐 |
|---|---|---|---|
| S1 | 候选池枚举 | 从 §11.3 六类来源收集候选，先写清模板与参数域 | 候选池 $\Omega_0$（30–60 个） |
| S2 | 契约化 + F0 | 每个候选写成 skill 卡：Pre/Post/Inv/Fallback/Cost/Evidence；过 schema/allowlist/单测 | $\Omega_1$，与 P0-1/P0-4 对齐 |
| S3 | F1 多保真筛选 | 在代表状态簇上跑代理/秒级评估，估 $\Delta U$、失败率、成本、适用性；滚动淘汰 | 打分表，与 P0-5 对齐 |
| S4 | 覆盖与多样性过滤 | 按 $b(\omega)$ 去重；用贪婪集合覆盖保证每个关键状态簇/阶段都有种子 | 保覆盖的候选子集 |
| S5 | F2 配对 pilot + F3 审计 | 同 checkpoint/seed 配对 A/B；计算 $\delta$、$\mathrm{LCB}$、失败率 UCB；随机 10% 跑 F3 校准 | 与 P0-6/P0-11/P0-7 对齐 |
| S6 | 组库与冻结 | 解代理目标 $\widehat{\mathcal{S}}(\mathcal{L}_0)$，得到 $K$ 个种子；写入版本化 seed library | $\mathcal{L}_0$ + `seed_library_v0.yaml` + 选择报告 |

**S3 细节：** 先按最便宜保真度筛掉明显不合法/无适用面的候选；对存活者逐级升保真，只有 $\mathrm{LCB}_l\ge\tau_l$ 的候选进入下一档（见 §5.6）。
**S5 细节：** 同 checkpoint、同 seed、同冻结后续策略，候选与 baseline 配对；性能用 $\mathrm{LCB}(\delta)$，风险用 $\mathrm{UCB}(P_{\text{fail}})$，成本进预算。

### 11.6 什么算"合适"：种子合格判据

| 判据 | 门槛（建议） | 说明 |
|---|---|---|
| 安全可执行 | contract pass 100% | 过不了 F0/L1 的一律不要 |
| 状态覆盖 | 每个关键状态簇 ≥1 个种子 | 防止 selector 无 option 可选 |
| 局部效果 | 至少在 1 个簇上 $\mathrm{LCB}(\Delta U)>0$；探索型种子可放宽为均值>0且 CI 跨 0 | 严格种子库与探索种子分开标记 |
| 门控风险 | $\mathrm{UCB}(P_{\text{fail}})<\epsilon$ | 与 signoff 机会约束一致 |
| 成本可控 | 单 seed 与总库成本在 $B_{\text{seed}}$ 内 | 昂贵种子少而精，便宜种子多而广 |
| 可复现 | 同版本/seed 3 次落在容差内 | 否则不能进入配对实验 |
| 可演化性 | 参数化、失败模式可观测、风险面可控 | 决定它值不值得进入 Phase E |
| 行为多样性 | $b(\omega)$ 与已选种子不同 | 用 QD 档案维护，避免同质化 |
| 来源可追溯 | 有来源/版本/provenance | 便于审计和复现 |

**重要区分：** "高质量种子"和"高可演化种子"不是一回事。一个当前 PPA 稍差、但参数清晰、失败模式稳定、适用面广的种子，可能比一个当前最好但不可解释、难以变异的种子更适合做演化起点。

### 11.7 Phase 0 选种落地参数（建议）

| 项 | 建议值 |
|---|---|
| 设计/状态规模 | 10–20 个 checkpoint × ≥3 个 design family × 3 seeds |
| 候选池 | 30–60 个（每阶段 8–12，含修复类 5–10） |
| 状态簇 | 8–12 个（按 density/congestion/timing/legality/family） |
| F1 筛选 | 全候选在每簇代表状态上评估 |
| F2 配对 pilot | 每阶段 top 6–8 个做配对 A/B |
| F3 审计 | 随机 10% 做完整 signoff 校准 |
| 初始种子库 | $K=6$–10：placement 3–5、routing 3–5、CTS/flow 1–2、repair 1–2 |
| 交付物 | `seed_library_v0.yaml`、`seed_evidence.jsonl`、`seed_selection_report.md`、成本预算表 |

### 11.8 从种子到演化：交接规则

1. $\mathcal{L}_0$ 直接作为 Phase E 的初始 skill 库；每个种子带来源、契约、行为描述子、证据。
2. 维护 **QD archive**：新演化出的 skill 若占据新的 $b(\omega)$ 区域，即使当前质量不是最高，也保留为候选。
3. 监控每个种子的 **后代贡献率**：若一个种子的后代长期不晋升，且其覆盖状态已被其他种子覆盖，可退役。
4. 定期重跑 **覆盖检查**：设计分布漂移或新 family 出现时，补种（从 S3/S5/S7 重新挖）。
5. 所有种子/后代/退役记录进 Experience Bank，与 §8 的映射表保持一致。

**一句话总结：** 在 BMF-CSMDP 下找种子，等价于解一个"**带安全与覆盖约束的组合选种问题**"：先从工具原生、经典算法、文献、经验库、失败修复、LLM 生成六类来源构建候选池；再用 F0→F1→F2→F3 多保真筛选、状态簇覆盖、行为多样性和可演化性做组合优化；最后把 $\mathcal{L}_0$ 作为 Phase E 的初始库。

**随机种子（seed）说明：** 本节 "种子" 指 seed heuristic/skill；工具随机种子是 §1.6 的 $\xi_{\text{tool}}$，用于复现和噪声控制，两者不是一回事。
