# Figure 8 TSP 复现报告（9 个干净实例，逐实例）

- 生成时间：2026-09-23 09:33:18
- 2026-09-23 09:30 按用户指令停止 gr666/pr1002/pr2392 三个超长实例；这三个不纳入本报告。
- pcb442 曾在 7500s 触发 timeout，result.txt 为超时前最后一轮完整解；为保持口径干净，也不纳入 9 实例主表，单列在排除区。
- 每个实例单独报告自己的 value/gap；平均 gap 仅作辅助，不替代逐实例值。
- 协议：DeepSeek V4.1 Flash(reasoning) 替代 GPT-4o；pool_fig8（11 基础 + 3 released evolved，共 14）；在线选择 n=2.0, m=5, c=3, b=10；TTS stop=补全后首次无提升即停；单实例 2h 上限。

## 逐实例结果
| instance | value | gap % | upper bound | source |
|---|---|---|---|---|
| kroA100.tsp | 21828.0 | 2.566 | 21282 | result.txt |
| kroA150.tsp | 27873.0 | 5.086 | 26524 | result.txt |
| kroB100.tsp | 22236.0 | 0.429 | 22141 | result.txt |
| kroB200.tsp | 30412.0 | 3.312 | 29437 | result.txt |
| kroC100.tsp | 21714.0 | 4.651 | 20749 | result.txt |
| bier127.tsp | 125358.0 | 5.982 | 118282 | result.txt |
| tsp225.tsp | 4295.0 | 9.594 | 3919 | result.txt |
| a280.tsp | 2790.0 | 8.181 | 2579 | result.txt |
| pr152.tsp | 74866.0 | 1.607 | 73682 | result.txt |

## 辅助平均
- 9 实例平均 gap = 4.601% (n=9)
- 论文 Figure8 TSP HeurAgenix 基线 = 0.50%，GLS=3.93%，EoH+GLS=1.93%，ReEvo+GLS=0.98%。

## 被排除实例
| instance | value | gap % | 状态 |
|---|---|---|---|
| pcb442.tsp | 54527.0 | 7.362 | 7500s timeout, 不纳入主表 |
| gr666.tsp |  |  | 2026-09-23 09:30 用户指令停跑，无完成轮 |
| pr1002.tsp |  |  | 2026-09-23 09:30 用户指令停跑，无完成轮 |
| pr2392.tsp |  |  | 2026-09-23 09:30 用户指令停跑，无完成轮 |

## 产物
- summary_9instances.json: 逐实例 value/gap/upper_bound/source + 辅助平均
- Figure8_TSP_9instances.csv: 同上，便于下游使用
- 本文件 Figure8_TSP_report.md：逐实例报告
