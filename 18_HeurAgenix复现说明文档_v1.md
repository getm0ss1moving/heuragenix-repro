# HeurAgenix 复现说明文档 v1（2026-09-22）

> 定位：面向“论文方法理解 + 复现过程交代 + 数据/baseline 对比 + 未复现内容说明”的完整说明。
> 状态：A 档 k=0、Table5、231 k=10 子集、TTS stop 诊断、B 档三 seed reasoning、Figure8 DeepSeek 替代版 9 个干净实例均已完成；P1A 论文口径 Table4 待确认；gr666/pr1002/pr2392 已按用户指令停跑（见 §4.5）。

---

## 1. 论文主要内容

### 1.1 问题设定
HeurAgenix 是一个 LLM 驱动的超启发式框架，解决组合优化（TSP/CVRP/MKP/JSSP/MaxCut）。它不直接生成解，而是从启发式池 H 中在线选择启发式并执行：
- 阶段一（离线）：启发式演化，把种子启发式 H_seed 演化成更强的 H_evolved；
- 阶段二（在线）：选择器 π 根据当前状态 z 从 H 中选择启发式，配合 test-time scaling（TTS）评测候选，连续执行 M=5 步，循环直到解完整且无改进。
评价指标为最优性 gap：
```
gap = (v - v_u) / v_u * 100      (最小化问题)
```
其中 v 是所得解目标值，v_u 是已知最优/最好已知值。

### 1.2 数学建模
论文把启发式选择建模成有限时域序列决策问题（MDP/半 MDP 形式）。核心方程（Eq.1）：
```
V(z, 0) = C(S_z)                              # t=0，终止，返回当前解代价
Q(z, H, t) = V( T^M(z, H), t-1 )              # 在 z 执行 H 共 M 步后的动作价值
V(z, t) = min_{H∈H} Q(z, H, t)                # 最优值函数
π*(z, t) = argmin_{H∈H} Q(z, H, t)            # 最优选择器
```
- N：最大启发式调用次数；
- M：每次选择后连续执行的步数，论文全实验 M=5；
- t：剩余决策次数，t=0 即终止。

**TTS（Monte-Carlo 估值）**：直接枚举未来不可行，论文用轻量 rollout 估计 Q：
```
对每个候选 H ∈ H'：
  1. 从当前状态 z 连续执行 H 共 M 步 → 中间状态 z'
  2. 从 z' 出发，随机选启发式直到完成，重复 T 次
  Q̂_H = (1/T) * Σ_{i=1..T} terminal_cost_i
选 Ĥ = argmin_H Q̂_H，执行 Ĥ 共 M 步
```
- 论文求解设置：M=5，Monte-Carlo search times T=10，单实例最长 2h，问题状态上下文长度 1000。

**双奖励微调（POR + CPR）**：由于 rollout 数量有限，Q̂ 带噪，论文提出双奖励：
- POR（Preference-based Outcome Reward，偏好结果奖励）：把当前状态所有启发式的 Q 降序排序，按被选启发式的排名 ℓ 给奖励，压缩正集/负集内部差距，放大两组间的间隔：
```
λ = rank(z, Ĥ, {Q_H})
         ⎧ R_p * (1 - (ℓ-1)/n_pos),                         1 ≤ ℓ ≤ n_pos
R_POR =  ⎨ -R_n * ((ℓ - n_pos)/(n_neg - n_pos)),   n_pos < ℓ ≤ n_neg
         ⎩ -R_L,                                           n_neg < ℓ ≤ n
```
- CPR（Context-Perception Reward，上下文感知奖励）：奖励模型对当前问题状态（problem/state/algorithm type/cost 等卡片）的正确感知：
```
R_CPR(z, ẑ) = Σ_i [ I(ẑ_i = z_i) * R_i^+  -  I(ẑ_i ≠ z_i) * R_i^- ]
```
released code 中的 CPR 不是逐特征数值回归，而是让模型输出结构化卡片（problem card / state card / algorithm type card / cost card），再按卡片匹配给奖励。
- 总奖励：`R = λ_POR * R_POR + λ_CPR * R_CPR + λ_base * R_base`，用 GRPO + LoRA 微调 Qwen2.5-7B-Instruct-1M。

### 1.3 阶段一：启发式演化（Algorithm 1）
```
Step 1 基本解生成：在 D_evo 上运行 H_seed，得到轨迹 S 和代价 C(S)
Step 2 对比解生成：最多 P 次扰动；每次随机选操作子集 K（|K|/N=0.1），把 O_k 替换为 O'_k 后 rollout；
       若 C(S') < C(S)，进入候选改动集合 M
Step 3 关键操作定位：对每个改动单独替换，计算 Δ_k = C(S) - C(S^k)，k* = argmax Δ_k
Step 4 LLM 提取演化策略：E = LLM_evolve(H_seed, z_k*, O_k*, O'_k*)，让 LLM 解释为何 O'_k* 更好
Step 5 迭代精炼：H_0 = H_seed；最多 T_max=5 轮；p_i = evaluate(H_i, D_val)；H_{i+1} = LLM_refine(H_i, E, p_i)；
       无提升则早停
输出 H_evolved
```
参数：演化实例 20，验证实例 7，P=1000，|K|/N=0.1，T_max=5，每种 LLM 方法统一 2000 次 API call 预算。

**released code 的工程化差异**：`HeuristicEvolver` 并非逐字实现 Algorithm 1。它先用 perturbation heuristic 生成 positive trajectory、用 basic seed 生成 negative trajectory，然后让 LLM “identify bottlenecks”、提出操作、生成 suggestion，再用 code generator + validation 迭代 refine。最终产物仍是“从 seed 演化出的新启发式代码”。复现中必须记录这一差异。

### 1.4 阶段二：在线选择流程
```
当前状态 z
  → Step 1 LLM filter：H' = LLM_filter(z, H)，把池子缩小到最多 3 个候选
  → Step 2 TTS：对每个 H ∈ H' 做 T 次随机完成 rollout，估计 Q̂_H
  → Step 3 选 Ĥ = argmin Q̂_H，连续执行 M=5 步
  → 解完整且无进一步提升则停止，否则回到 Step 1
```
LLM 模式的 API call 数约为 `ceil(N/M)+2`；论文用 GPT-4o/o3/DeepSeek-R1 作为在线选择器，同时提供微调 Qwen2.5-7B 的轻量版本。

### 1.5 论文实验设置
- 模型：演化与在线选择用 GPT-4o-2024-11-20；对比选择器 OpenAI o3、DeepSeek-R1；微调底座 Qwen2.5-7B-Instruct-1M。
- 数据集：TSP（TSPLIB）、CVRP、MKP、JSSP、MaxCut；训练实例 20、验证实例 7、测试实例各问题若干。
- baseline：GLS、ACO、OR-Tools、EoH+GLS、ReEvo+GLS、ReEvo+ACO、QICSA、PSO、GWO、CirCut、VNSPR 等；不涉及模型更新的 baseline 可用论文数字，涉及模型更新的需同步重跑。
- 硬件：GNU/Linux + Intel Xeon + 4×NVIDIA RTX A6000 48G；每个测试实例最长 2h。

---

## 2. 复现过程

### 2.1 代码与冻结
- 核心代码 freeze：`f9ec60f`（paper 分支，演化与在线选择框架）；
- 训练代码 freeze：历史 commit `6e4fc66` 的 `src/training/*` + 数据收集器；
- 主工作目录：`repo/HeurAgenix_paper`（f9ec60f）、`repo/HeurAgenix_train`（6e4fc66）。
- 复现中修复的 released-code 问题（均记录为偏差）：
  1. 定时评测脚本相对路径导致空跑 → 绝对路径；
  2. `evolve_heuristic.py` 使用 `args.evolution_dir/validation_dir` 但 argparse dest 是 `evolution_data/validation_data`；
  3. `-pt` 被解析为 float，`range()` 报错 → type=int；
  4. `evolution_single` 异常分支返回未定义变量 → locals 检查返回 `[]`；
  5. `refine_heuristic` 对 None 先 `.split` 崩溃 → 加 None 检查；
  6. `SingleHyperHeuristic.run` 无步数上限 → 遇到持续返回 operator 的启发式会死循环，已加 `2N` 上限；
  7. DeepSeek API 客户端无请求超时（部分运行卡住的潜在原因）。

### 2.2 数据与启发式池
- 训练数据按 released code 规则重建：离线 `(z, H, Q_H)` 数据 1109 条；
- 演化数据：TSP `train_data` 20 个实例、`validation_data` 7 个实例；
- 池口径先用 P2：Appendix E 确定性基础启发式 + 3 个 released evolved（`_2opt_89aa`、`_3opt_e75b`、`simulated_annealing_e625`）；
- Table5 确定性复现：354 run，落盘 `table5_full_corrected.csv`。

### 2.3 模型训练
- 底座：Qwen2.5-7B-Instruct-1M，4bit NF4；
- LoRA rank 32，Paged AdamW 8bit，LR 1e-6，cosine + warmup 0.1，BF16；
- 两个变体：
  - dual（POR+CPR）GRPO LoRA：训练完成，final_lora 324MB，runtime 约 14.2h；
  - vanilla GRPO LoRA：训练完成，final_lora 324MB，runtime 约 12.2h；
- 训练数据为重建的 1109 条，非论文精确数据，且只训练 1 epoch。

### 2.4 评测执行
- A 档 k=0：3 选择器 × 13 TSPLIB 实例，动态队列 8 worker / 4 GPU，2h/实例上限，产物 `results/eval_full/parts/`；
- k=10：在 231 上实现 spawn 多进程 + dill 的 parallel TTS（每 evaluator 16 TTS workers），先跑 n≤225 的 8 实例 × 3 选择器；
- TTS stop 口径对照：实现 `completion / fixed2n / improvement` 三种口径，并做单 rollout 基准与 kroB200 复核；
- B 档 DeepSeek 演化：独立仓库 `HeurAgenix_reason`，用 `deepseek-chat`（non-reasoning）与 `deepseek-flash`（reasoning，max_tokens=32768）分别演化 TSP 三种子；固定 2N+1 步、180s/实例评测演化产物。

### 2.5 运行环境
- 225：4×RTX3090；A 档 k=0、B 档演化、stop 诊断；
- 231：3×RTX4090（GPU1/2/3 可用）+ 64 核；k=10 parallel TTS，Qwen 权重放 NAS 并用 symlink；
- 224：用户另一实验节点，禁止使用。

---

## 3. 与论文的不同点及原因

| 差异 | 论文 | 本复现 | 原因/影响 |
|---|---|---|---|
| LLM API | GPT-4o-2024-11-20 | DeepSeek v4.1 flash（deepseek-chat / deepseek-flash） | 无 Azure/GPT-4o key，按用户决策替换；影响演化/在线选择质量与成本 |
| 训练数据 | 论文私有精确数据 | released code 规则重建 1109 条 | 论文未发布精确数据；直接导致选择器质量差距 |
| 启发式池 | Appendix 全池（可能 P1/P2/P3） | 先用 P2 | 用户决定先 P2 再校准；P2 局部搜索强度有限（`_2opt` 实测无改进，`_3opt` 300 次才到 21490） |
| TTS stop 口径 | 正文 §3.3 until-completion；附录 D improvement-stop；released code fixed2n | 旧默认 completion（完整解跳过 rollout），后改可配置三口径 | 论文三处口径不一致，导致 TTS 分数并列/锁死与 k10 结论变化 |
| k=10 主协议 | 论文用 k=10 作为求解设置 | 主表用 k=0；k=10 只跑 n≤225 子集 | fixed2n/improvement 下 kroB200 单 rollout 109s/54.7s，2h 内不可行；released CLI 默认 b=0 |
| 2h 限制 | 每个测试实例最多 2h（熔断上限） | 沿用 2h；dual/vanilla pr2392 用 nearest_insertion 兜底 | 论文 2h 不是完整协议时长；兜底属工程补全 |
| 演化算法 | Algorithm 1 的 Δ_k 替换流程 | released `HeuristicEvolver` 的 bottleneck/suggestion/refine 工程实现 | released code 与论文描述不完全一致，需按代码口径复现 |
| 硬件/并行 | 4×A6000 + Xeon，TTS 多进程 | 4×3090 / 3×4090，自研 parallel TTS | 时间与并发不可直接比较 |
| 模型更新类 baseline | EoH/ReEvo 等统一重跑 | 暂未重跑（按用户决策，模型更新类需同步更新） | 当前只做 HeurAgenix 自身复现 |
| 重复实验 | 每实验 3 次 | 多为 1 次 | 无方差估计，结论应视为方向性 |

---

## 4. 数据、baseline 与结果对比

### 4.1 Table5（演化阶段，确定性结果）
- 本仓库数据：354 run；问题覆盖 TSP/CVRP/MKP/JSSP/MaxCut；seed/evolved 配对；gap 按实例上界计算。
- 本仓库聚合（全 seed 平均）：
```
TSP      seed 20.04 → evolved  9.11
CVRP     seed 45.22 → evolved 33.25
MKP      seed 18.13 → evolved  5.25
JSSP     seed 159.39 → evolved 28.92
MaxCut   seed 37.06 → evolved 6.35
```
- 与论文代表性数字对比：论文 TSP NN 24.59→9.06，本仓库 seed NN 24.79→released evolved NN 8.75，同量级吻合；pr152 六个启发式与论文逐项一致；JSSP `most_work_remaining_df20` 27.986 vs 论文 27.99；TSP farthest 8.55 vs 论文 9.67；CVRP 新旧代码一致但与论文表有系统性偏差。
- 原因判断：farthest/CVRP 偏差来自 evolved 池版本/论文表格口径不同（released code 可复现，论文表格大概率使用另一版未公开的 evolved 文件），不是评测公式问题。

### 4.2 Table3/4（微调选择器，k=0 口径）
| 指标 | 论文 | 本复现 k=0 | 差异主因 |
|---|---|---|---|
| dual 平均 gap | 0.59 | 12.287 | k=10→k=0、重建数据、P2 池弱、训练不充分 |
| vanilla GRPO | 4.39 | 13.098 | 同上 |
| raw Qwen | 5.01 | 13.787 | 同上 |
- 本复现 k=0 内部：dual 平均最好（12.287），但 raw 在 pr152(6.22)、a280(10.90)、gr666(13.02) 反超；dual/vanilla 的 pr2392 触 2h 熔断兜底。
- 说明：论文用 k=10 + GPT-4o 级在线监督，本复现是 k=0 + 重建数据，数量级差异合理，不能据此声称论文结果错误。

### 4.3 k=10 vs k=0（n≤225 的 8 实例）
| 选择器 | k=0 | k=10 (completion 口径) |
|---|---|---|
| dual | 11.375 | 12.474 |
| vanilla | 12.527 | 14.456 |
| raw | 14.353 | 13.517 |
- k=10 明显变好：pr152 3.96 vs 9.06，kroA150 5.87 vs 11.85，kroC100 4.71 vs 9.67，bier127 9.03 vs 16.65；
- k=10 变差/异常：kroB200 36.24 vs 10.38（completion 口径 skip-on-complete 锁死局部最优，improvement 口径重跑 16.89，仍差于 k=0），kroA100/kroB100/tsp225 小幅变差；
- 结论：completion 口径 k=10 总体无净增益；TTS 效果高度依赖 stop 口径、实例和随机轨迹。

### 4.4 B 档 DeepSeek 演化（固定 2N+1 步）
| 族 | seed | released evolved | DeepSeek chat | DeepSeek reasoning | reasoning n |
|---|---|---|---|---|---|
| farthest | 14.522 | **8.283** | 9.361 | **8.039** | 8/13 |
| cheapest | 19.786 | 9.307 | 21.020 | **6.090** | 12/12 |
| nearest | 24.794 | **8.747** | 16.288 | **4.134** | 12/12 |
- 结论：三个 seed 上 reasoning 均不差于 released evolved；nearest/cheapest 优势明显，farthest 优势很小且 5 个大实例 180s 只走 1 步 INCOMPLETE。
- 属方向性优势，非显著性结论；产物 `evidence/b_reason_*_final.json`、`evidence/b_evolved_vs_released_test13.csv`、doc15。

### 4.5 Figure8 TSP（DeepSeek reasoning 替代版，9 个干净实例）
- 2026-09-23 09:30 用户指令停跑 gr666/pr1002/pr2392；pcb442 因 7500s timeout（result.txt 为超时前最后一轮完整解）排除；主表采用 9 个干净实例。
- 每个实例独立 value/gap，不做“全部取平均”替代。

| instance | value | gap % | upper bound |
|---|---|---|---|
| kroA100.tsp | 21828.0 | 2.566 | 21282 |
| kroA150.tsp | 27873.0 | 5.086 | 26524 |
| kroB100.tsp | 22236.0 | 0.429 | 22141 |
| kroB200.tsp | 30412.0 | 3.312 | 29437 |
| kroC100.tsp | 21714.0 | 4.651 | 20749 |
| bier127.tsp | 125358.0 | 5.982 | 118282 |
| tsp225.tsp | 4295.0 | 9.594 | 3919 |
| a280.tsp | 2790.0 | 8.181 | 2579 |
| pr152.tsp | 74866.0 | 1.607 | 73682 |

- 辅助平均 gap = **4.601%（n=9）**；论文基线 HeurAgenix 0.50%。
- 产物：`results/fig8_tsp_225/Figure8_TSP_report.md`、`Figure8_TSP_9instances.csv`、`summary_9instances.json`；本地 `evidence/fig8_tsp_225/`。

### 4.6 baseline 数据使用说明
- 不涉及模型更新的 baseline（GLS/ACO/OR-Tools 等）：可按用户决策引用论文数字，本轮未重跑；
- 涉及模型更新的 baseline（EoH/ReEvo 等）：论文口径要求同步重跑/更新，本轮未执行，最终报告将标注为“未复现”；
- 闭源选择器（GPT-4o/o3/R1）的 Table3：未调用 API，未复现，B 档用 DeepSeek 做了替代性探索。

---

## 5. 未能复现的内容及原因

1. **Table3 闭源 LLM 在线选择**：需要 GPT-4o/o3/DeepSeek-R1 API，未获得/未授权，且 API 成本高。
2. **Table6 / Figure8 在线 API 选择（GPT-4o 原版）**：未调用 GPT-4o；已完成 DeepSeek reasoning 替代版 Figure8 9 个干净实例（§4.5），GPT-4o 原版 Table6 未复现。
3. **Figure9 完整预算曲线**：未跑 k=0/1/2/4/8/10 全曲线；当前只有 stop 口径诊断与少量 k10 结果。
4. **CVRP/MKP/JSSP/MaxCut 的 B 档演化**：DeepSeek 演化只跑了 TSP 三个种子；其他问题未跑。
5. **C 档模型更新类 baseline**：EoH/ReEvo 等未同步重跑。
6. **完整 k=10 全矩阵**：fixed2n/improvement 口径在 n≥200 单 rollout 分钟级，2h 内不可行；只有 n≤225 的 completion 口径 24 run + kroB200 的 improvement 诊断。
7. **3 次重复与方差**：论文每个求解实验 3 次，本复现多为 1 次，尚无标准差。
8. **论文私有资产**：精确训练数据、完整 evolved 池、prompt 版本未公开，无法完全对齐。
9. **Figure8 13/13 与大实例**：gr666/pr1002/pr2392 已停跑，pcb442 timeout 排除，未取得 13/13。
10. **EDA 迁移 Phase 0**：属于项目后续方向，等用户拍板。

---

## 6. 复现产物索引
- `01` 文献精读报告、`02` 复现清单、`03` 执行决策记录；
- `04–10` EDA 迁移与数学建模系列；
- `11` 评测协议与偏差记录 v1、`12` Table5 汇总、`13` Table3/4 k=0 报告、`14` TTS stop 口径诊断、`15` B 档 DeepSeek 对比、`16` k10 vs k0 子集、`17` 总报告 v2、`18` 本说明文档、`19_补充报告_最新对话增量_v1.md`；
- 数据：`evidence/eval/k0_combined.csv`、`evidence/eval/k10_subset.csv`、`evidence/b_evolved_vs_released_test13.csv`、`evidence/fig8_tsp_225/*`、`results/eval_full/*`；
- 服务器：225 `/data/dzy/heura_repr`；231 第二评测节点；224 禁用。

## 7. 历史：reasoning nearest watcher（已完成）
- 历史状态：225 上 `b_reason_nearest_neighbor_f91d` watcher `watch_b_nearest` 曾每 2 分钟轮询；最终结果见 §8。
- 触发条件：日志出现最终 `[[evolved.py, improvement]]` → 自动按固定 2N+1 步跑 12 实例 → 与 released（8.747）/chat（16.288）比较 → 输出 `results/b_reason_nearest_final.json`；
- 保护：2h 无新 dump 标记 STALLED 退出；进程消失但无最终行标记 PROCESS_GONE_NO_FINAL；
- 完成后本说明文档补一行最终结论，并更新 doc15/doc17。

---

## 8. 补充：reasoning nearest 最终结果（2026-09-23 00:10）
- 新 API key 更新后，reasoning nearest 的最终 evolved heuristic 为 `nearest_neighbor_aac7.py`；
- 12 个 TSPLIB 实例平均 gap = **4.134**，对比 released evolved nearest 8.747、DeepSeek chat nearest 16.288；
- 判定：`reasoning_better_than_released`；pr2392 因 180s 单实例超时未纳入 12 实例平均；
- farthest reasoning 新 key 重跑也已完成（n=8，avg 8.039，released 8.283/chat 9.361，verdict=reasoning_better_than_released）；至此 B 档三 seed 均收口。
