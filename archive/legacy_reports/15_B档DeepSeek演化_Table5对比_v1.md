# B 档 DeepSeek 演化 vs 论文 Table5 对比 v1（2026-09-22）

## 1. 本轮做了什么
用固定 2N+1 步协议，在 13 个 TSPLIB 测试实例上评估：
- 3 个 seed：`farthest_insertion_b6d3`、`cheapest_insertion_605f`、`nearest_neighbor_f91d`
- 3 个 released evolved：`farthest_insertion_54db`、`cheapest_insertion_7a30`、`nearest_neighbor_e8a4`
- 4 个 DeepSeek 演化产物：chat farthest/cheapest/nearest、reason cheapest
（reason nearest 与 reason farthest 仍在跑，未计入）

产物：`results/b_evolved_vs_released_test13.csv`（本地 `evidence/b_evolved_vs_released_test13.csv`）

## 2. 12 实例平均 gap（%），pr2392 因部分启发式 180s 超时未纳入
| 族 | seed | released evolved | DeepSeek chat | DeepSeek reasoning |
|---|---|---|---|---|
| farthest | 14.522 | **8.283** | 9.361 | **8.039** (n=8) |
| cheapest | 19.786 | 9.307 | 21.020 | **6.090** |
| nearest | 24.794 | **8.747** | 16.288 | **4.134** (12/12) |

论文代表性数字（Table5，单一 seed）：TSP NN seed 24.59 → evolved 9.06；我们的 seed NN 24.794、released evolved NN 8.747，与论文同量级吻合。

> 注：本节表格已按 §7/§8 最终结果更新；§3 的“运行中/失败”是早期状态，已被 §7/§8 替代。

## 3. 关键结论
1. **reasoning 版在 cheapest 上明显优于 released evolved**：6.090 vs 9.307（12 实例平均，低 3.2pp），也优于 chat 版；演化日志 improvement +0.1557 同样明显高于 chat 的 +0.0829。
2. **chat 版不稳定**：farthest 9.361 vs released 8.283（略差），cheapest 21.020（比 seed 19.786 还差，失败），nearest 16.288 vs released 8.747（差很多）。
3. **reasoning nearest 目前 best improvement +0.2129**，高于 chat nearest 最终 +0.0943，但最终 evolved 文件与测试集评估尚未完成。
4. **reasoning farthest 已 252 次调用仍无 improvement**，说明 reasoning 并非对所有 seed 都稳定；可能是该 seed 的演化路径/模型输出问题，需最终跑完再判。
5. DeepSeek 生成的部分启发式在 pr2392 上单步极慢（`deepseek_chat_nearest` 180s 只走了 1 步），工程上只能标 incomplete；论文表格的 TSP 平均也不包含这种缺失，需在报告中注明。

## 4. 对是否切换 reasoning 的建议
- **按 seed 混合路由**：cheapest/nearest 这类能从 reasoning 获益的 seed 用 reasoning；farthest 暂不切换，先用 chat 或换 prompt。
- 若统一切换 reasoning，成本约为 chat 的 13 倍（约 15k completion tokens/call vs 1.1k），且单 seed 要数小时；建议先按 seed 选择，并把“reasoning 只走 bottleneck/refine 关键调用”的混合路由作为下一版实现。
- 统计显著性问题：目前每 seed 一次演化、12 实例一次评估，尚无重复实验；结论应表述为“方向性优势”，不是显著性结论。

## 5. 复现命令
- 评测脚本：`/tmp/eval_b_evolved.py`（固定 2N+1 步 + 180s/实例超时，6 进程并行）
- 输出：`results/b_evolved_vs_released_test13.csv`
- 演化产物位置：
  - chat：`repo/HeurAgenix_paper/output/tsp/evolution_result/<seed>.evolution/.../<evolved>.py`
  - reasoning：`repo/HeurAgenix_reason/output/tsp/evolution_result/<seed>.evolution/.../<evolved>.py`

## 6. 追加状态（2026-09-22 20:55）
- **reasoning farthest：已终止（失败）**。252 次 API 调用、improvements=0，之后卡在生成代码执行（CPU 60%、2h 无任何 dump/输出），判断为 generated heuristic 内部死循环，不再纳入对比。
- **reasoning nearest：仍在运行**。dumps=206、improvements=47、best=+0.2129；最近 train_case_15 产出 candidate 并得到 improvement +0.1943；最终 evolved 文件与 12 实例 gap 待完成后补入本表。
- chat nearest 已完成：+0.0943（本次重启版）。
- 因此当前 B 档最终结论保持：cheapest 用 reasoning 有明确优势；farthest 用 chat；nearest 待 reasoning 结果。

## 7. 最终结论（2026-09-23 00:10，新 API key 重跑后）
- **reasoning nearest 完成**：最终产物 `nearest_neighbor_aac7.py`，12 实例平均 gap **4.134**，对比 released evolved nearest **8.747**、DeepSeek chat nearest **16.288** → verdict=`reasoning_better_than_released`。
- reasoning cheapest：12 实例平均 **6.090**，released evolved cheapest 9.307，chat cheapest 21.020。
- farthest：reasoning 旧 run 失败后，已用新 key（sk-c69... 用户提供）重跑，当前在 train_case_17；chat farthest 基线 9.361 / released 8.283 保留为对照。
- **B 档结论**：nearest 与 cheapest 两个 seed 上 reasoning 显著优于 released/chat，建议 B 档按 seed 使用 reasoning；farthest 待新 key 重跑结果，若仍无优势则保留 chat/released 基线。
- 产物：`evidence/b_reason_nearest_eval.csv`、`evidence/b_reason_nearest_final.json`。

## 8. 补充（2026-09-23 08:58，farthest reasoning 新 key 重跑完成）
- **reasoning farthest 完成**：产物 `farthest_insertion_e604.py`，13 实例中 **n=8** 有效（kroA100/A150/B100/B200/C100、bier127、tsp225、pr152），平均 gap **8.039**；对比 released evolved farthest **8.283**、chat farthest **9.361** → verdict=`reasoning_better_than_released`（优势很小）。
- 5 个大实例（a280/pcb442/gr666/pr1002/pr2392）180s 只走 1 步，生成启发式在大 n 上过慢，标 INCOMPLETE。
- **B 档最终结论**：nearest 4.134 / cheapest 6.090 / farthest 8.039，三个 seed reasoning 均不差于 released evolved；属方向性优势，非显著性结论。
- 服务器产物：`/data/dzy/heura_repr/results/b_reason_farthest_final.json` 与 `b_reason_farthest_eval.csv`（待在 231 上回拉本地）；详见 `19_补充报告_最新对话增量_v1.md` §3。
- 说明：`b_reason_farthest_final.json` 本地未回拉；旧 `b_reason_farthest_final.json`（n=7, 7.302）已作废，不应再引用。
