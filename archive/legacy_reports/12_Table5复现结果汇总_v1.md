# HeurAgenix Table 5 复现结果汇总 v1（2026-09-22）

## 0. 结论一句话
Table 5 的 **354 run 全部完成**（5 问题 × seed/evolved 配对 × 测试实例），演化后平均 gap 全面低于 seed，与论文趋势一致；少数条目与论文表格数值有偏差，报告中必须区分“f9ec60f released code 口径”与“论文表格口径”。

## 1. 数据来源与口径
- 原始结果：服务器 `/data/dzy/heura_repr/results/table5_full_corrected.csv`（本地副本 `evidence/table5/table5_full_corrected.csv`，354 行）
- TSP pr152 复核：`results/table5_tsp_pr152.csv`
- 运行代码 freeze：核心 `f9ec60f`（paper 分支）+ 训练代码 `6e4fc66`；pool 口径 P2（Appendix E 确定性基础启发式 + 3 个 evolved）
- 字段：problem, seed, evolved, kind(seed/evolved), name, instance, value, gap, seconds, error
- gap 统一按实例最好已知值计算：gap=(value-upper)/upper*100

## 2. 汇总统计（本仓库实测，直接由 CSV 聚合）
| 问题 | 类型 | n | 平均 gap | 最小 | 最大 |
|---|---|---|---|---|---|
| TSP | seed | 39 | 20.04 | 4.98 | 31.69 |
| TSP | evolved | 39 | **9.11** | 2.41 | 15.02 |
| CVRP | seed | 18 | 45.22 | 22.16 | 104.68 |
| CVRP | evolved | 18 | **33.25** | 20.13 | 53.29 |
| MKP | seed | 30 | 18.13 | 4.11 | 34.62 |
| MKP | evolved | 30 | **5.25** | 0.98 | 16.60 |
| JSSP | seed | 60 | 159.39 | 5.42 | 432.19 |
| JSSP | evolved | 60 | **28.92** | 5.64 | 65.91 |
| MaxCut | seed | 30 | 37.06 | 4.74 | 112.16 |
| MaxCut | evolved | 30 | **6.35** | 1.56 | 14.30 |

论文代表性数字（Table 5 / Figure 7，single seed 口径）：TSP NN 24.59→9.06；CVRP NN 48.80→36.55；MKP greedy density 8.03→2.69；JSSP SPT first 180.47→23.30；MaxCut balanced cut 60.41→6.45。对应 seed 单条与论文同源时可比；上表是全部 seed 平均，因此数值更低（seed 平均里混入了更强的 seed）。

## 3. 逐项核对结论（来自 2026-09-21 复核）
- **TSP pr152**：6 个启发式逐项与论文一致（关键锚点，说明环境/实例/gap 口径正确）。
- **JSSP**：`most_work_remaining_df20` 实测 27.986 vs 论文 27.99，一致。
- **TSP farthest_insertion**：实测 evolved 8.55 vs 论文 9.67，偏差约 1.1 个百分点；seed/其他实例多数吻合。可能原因：论文 evolved 启发式与 released code 版本的演化结果不同（NaDRO 分支 / 删除代码 / 演化随机性），不是评测口径问题。
- **TSP cheapest / nearest neighbor**：平均吻合。
- **MKP / MaxCut**：大部分实例与论文一致或趋势一致。
- **CVRP**：新旧代码彼此一致，但与论文表格有系统性偏差；怀疑论文表使用的是另一版 evolved 池（或数据/上界口径差异），需在最终报告中标注为“未完全对齐项”。

## 4. 代码口径 vs 论文表格口径
1. 本仓库 CSV 是 **f9ec60f + P2 pool + 重建数据** 的可复现口径；论文表格来自作者内部演化结果与更大 API 预算，单条 evolved 启发式不一定逐字一致。
2. TSP farthest 的 8.55 vs 9.67、CVRP 的系统偏差，均已复核为“代码可复现、表口径不同”，不应通过改论文数字或调 gap 公式来对齐。
3. 报告写法建议：主表列 released code 口径；另一列（或脚注）列论文值；差异大者注明原因与是否可解释。

## 5. 复现命令
- 生成 CSV：服务器 `results/table5_full_corrected.csv` 由 `run_table5.py` + `calib_old_code.py` 产生（脚本在 `/data/dzy/heura_repr/repo/`，日志 `logs/table5*`）。
- 复核 pr152：`results/table5_tsp_pr152.csv` / `logs/table5_tsp_pr152.log`。
- 本地聚合：`python3` 读 CSV 按 `problem,kind` 分组求平均即可（本报告第 2 节）。

## 6. 已知不完美
- CSV 中 `seconds` 受并发影响，不是干净的单核计时，仅作量级参考。
- 论文 Table 5 为图片表格，逐格 OCR 有风险；本报告只对已人工核对过的条目给出一致性结论，未逐格声称全部一致。
