# HeurAgenix Table 3/4 复现报告（k=0 口径）v1（2026-09-22）

## 0. 结论摘要
- A 档 k=0 评测 3 选择器 × 13 TSPLIB 实例全部完成（39/39），产物 `results/eval_full/k0_combined.csv`。
- 本仓库口径平均 gap：**dual 12.287 / vanilla 13.098 / raw 13.787**。
- 与论文 Table 3/4（dual 0.59、vanilla GRPO 4.39、raw 5.01）差距很大，主因是 **用 k=0 代替论文的 TTS k=10 主协议**，叠加“训练数据按 released code 规则重建（1109 条）”和 P2 池局部搜索强度有限；不能直接与论文数字对齐。
- k=0 下 dual 平均最好，但 raw 在多个实例反超（pr152/a280/gr666），说明当前微调选择器尚未形成论文所述的全面优势。

## 1. 评测协议（k=0）
- 代码：`eval_selector_tsp.py`（k=0 模式，无 TTS）
- 模型：raw = Qwen2.5-7B-Instruct-1M base；vanilla = vanilla GRPO LoRA；dual = POR+CPR LoRA（final_lora）
- pool：P2（11 个确定性基础启发式 + 3 个 released evolved：`_2opt_89aa`,`_3opt_e75b`,`simulated_annealing_e625`）
- 每轮：模型输出卡片+最多 3 候选 → 直接取第一候选 → 连续执行 M=5 步；
  - 轮数上限 `int(2*construction_steps/5)`，与 released code 的 `selection_round*M <= 2N` 一致
  - 未完成且第一候选是 refinement 时强制换 construction
  - 完解后连续 10 轮无改进停止
- 单实例 2h 熔断；熔断时若未完成，用 nearest_insertion 补完成并标 `fallback_complete=true`
- 解码：temperature 0.7 / top-p 0.95 / max_new_tokens 512；4bit NF4

## 2. 逐实例结果（gap %，越低越好）
| instance | dual | vanilla | raw |
|---|---|---|---|
| kroA100 | 14.33 | 12.91 | 12.27 |
| kroA150 | 11.85 | 12.01 | 13.47 |
| kroB100 | **7.07** | 6.37 | 19.01 |
| kroB200 | **10.38** | 13.33 | 16.19 |
| kroC100 | 9.67 | 17.35 | 20.19 |
| bier127 | 16.65 | 10.45 | 13.72 |
| tsp225 | **11.99** | 20.11 | 13.75 |
| a280 | 12.87 | 15.12 | **10.90** |
| pcb442 | **13.46** | 13.48 | 14.42 |
| gr666 | 15.08 | 14.06 | **13.02** |
| pr152 | 9.06 | 7.69 | **6.22** |
| pr1002 | 10.82 | **10.69** | 11.16 |
| pr2392 | **16.49**† | 16.69† | **14.91** |
| **平均** | **12.287** | 13.098 | 13.787 |

† dual/vanilla pr2392 触 2h 熔断，用 nearest_insertion 补完成（tl=true, fb=true）；raw pr2392 完整 540 轮、未兜底。

## 3. 与论文对照
| 指标 | 论文 | 本复现（k=0 口径） | 差异主因 |
|---|---|---|---|
| dual 平均 gap | 0.59 | 12.287 | k=10→k=0、重建数据、P2 局部搜索 |
| vanilla GRPO 平均 | 4.39 | 13.098 | 同上 |
| raw Qwen 平均 | 5.01 | 13.787 | 同上 |
| 论文 Table 3 闭源 LLM | GPT-4o 0.61 / O3 0.39 / R1 0.45 | 未在本轮范围 | 需 B 档 API 选择结果 |

## 4. 231 上 k=10 平行 TTS 的部分结果（截至 2026-09-22 17:00，9/24）
| instance | dual k=10 | dual k=0 | 说明 |
|---|---|---|---|
| pr152 | **3.96** | 9.06 | k=10 明显更好 |
| kroA150 | **5.87** | 11.85 | k=10 明显更好 |
| kroC100 | **4.71** | 9.67 | k=10 明显更好 |
| bier127 | **9.03** | 16.65 | k=10 明显更好 |
| tsp225 | 13.37 | 11.99 | 略差 |
| kroA100 | 15.06 | 14.33 | 略差 |
| kroB100 | 11.54 | 7.07 | 变差 |
| kroB200 | **36.24** | 10.38 | 异常变差，需复核 |
| **dual 平均** | 12.474 | 12.287 | 无净增益 |

vanilla 目前仅 kroA150 完成：k=10 24.98 vs k=0 12.01，明显更差（单样本）。
结论：k=10 结果高度依赖实例与 TTS 噪声，**不能直接声称 TTS 有效或无效**；需等剩余任务完成并复核 kroB200 异常。

## 5. 已知偏差（必须在最终报告声明）
1. 主协议 k=10 在 n≥442 无法在 2h 内完成（rollout 单核实测 pcb442 341s、gr666 1523s、pr2392 小时级），A 档主表采用 k=0；
2. dual/vanilla pr2392 使用 nearest_insertion 兜底完成；
3. rollout 停止口径尚未锁定：正文 until-completion / 附录 improvement-stop / released code 固定 2N；本 k=0 与 k=10 当前均为 until-completion（release 近似）；
4. 训练数据为 released code 规则重建，非论文精确数据；
5. 推理解码沿用论文 temperature/top-p，但 max_new_tokens=512 与论文 768 略有差异。

## 6. 产物与复现命令
- 合并 CSV：`/data/dzy/heura_repr/results/eval_full/k0_combined.csv`（本地 `evidence/eval/k0_combined.csv`）
- 分片：`results/eval_full/parts/{mode}__{instance}.json`；合并脚本 `repo/combine_parts.py`
- k=10 平行产物：231 `results/eval_full/parts_k10/`（`eval_selector_tsp_par.py --tts-workers 16`）
- 启动/监控：`run_eval_queue.sh`（225 k=0）、`run_eval_k10_par_231.sh`（231 k=10）

## 7. 下一步
1. 231 跑完 k=10 的 vanilla/raw；复核 kroB200 异常（独立重跑）；
2. stop 口径对照：until-completion / improvement-stop / fixed-2N；
3. B 档 DeepSeek reasoning vs chat 的最终 improvement 对照；
4. 将本报告升级为 v2（加入完整 k=10、B 档、Figure 9）。
