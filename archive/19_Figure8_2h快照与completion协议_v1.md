# Figure8 2h 快照与 completion 双阶段协议 v1（2026-09-23）

## 结论
- 当前 225 上 `rerun_fig8_missing`（gr666/pr1002/pr2392）**不是 2h 熔断版**：`/tmp/run_fig8_one_225.sh` 没有 `timeout`，目标是跑到自然结束。
- 按用户 2026-09-23 新要求：不 2h kill；在 2h 先获取一次数据，再在 completion 自然结束时保存一次。
- 231 的 `farthest_eval_231`（`/tmp/eval_one_nearest.py`）按实例 `signal.alarm(180)`，**满足 2h 上限**。

## 当前运行快照
- 225 parent PID：9270（start 2026-09-23 08:34:43）。
- 2h 时刻：2026-09-23 10:34:43。
- Watcher tmux：`fig8_2h_capture`，脚本 `/tmp/fig8_2h_capture_watcher.sh 9270`。
- 2h 输出目录：`/data/dzy/heura_repr/results/fig8_tsp_225/snapshot_2h/`
  - 每实例：`result.txt` / `best_result_*.txt` / 最新 `step_*.txt` / `parameters.txt` / `<inst>.json`
  - 汇总：`summary_2h.json`、`PROCESS_INFO.txt`
  - 若 2h 时还没有完成第一个 selection round，数值为 `null`，但中间 LLM dump 仍会保存。
- completion 输出目录：`/data/dzy/heura_repr/results/fig8_tsp_225/final_completion/`
  - 每实例 completion capture、`summary_completion.json`、`PROCESS_INFO.txt`
  - 另复制 `summary.json`、`Figure8_TSP_report_completion.md`
- 双阶段对照报告：`/data/dzy/heura_repr/results/fig8_tsp_225/Figure8_TSP_report_2h_completion.md`

## 关键脚本（服务器）
- `/tmp/capture_fig8_two_phase.py`
- `/tmp/combine_fig8_two_phase.py`
- `/tmp/report_fig8_two_phase.py`
- `/tmp/fig8_2h_capture_watcher.sh`

## 说明
- 当前 completion = released `LLMSelectionHyperHeuristic` 主循环自然结束（`selection_round * M <= 2n`），TTS 内部 rollout 为 completion/no-improvement 口径。
- 早前 10 个实例来自旧 campaign，其中 pcb442/gr666/pr1002/pr2392 曾在 7500s 触发 rc=124；本轮 3 个大实例不再 2h kill。
- 结果回拉和文书更新等 watcher 完成后进行。

## 2026-09-23 09:23 运行正确性检测与修复
- 已确认 225 上运行中的 Figure8 进程 cwd 全部是 `/data/dzy/heura_repr/repo/HeurAgenix_paper`，不违反 `search_file` 依赖 cwd 的约束。
- 发现并修复：`combine_fig8_two_phase.py` 原先只扫描顶层 `*.tsp.json`，但 capture 实际写到 `<dest>/<inst>/<inst>.tsp.json` 嵌套目录；已改为递归 `**/*.tsp.json`，并在测试快照上验证能读到 3 行。
- 修复 final combine 输出为 `summary_completion_combined.json`，避免覆盖 capture 生成的 `summary_completion.json`。
- watcher 增加 parent 变 zombie / 出现 `MISSING_REPORT_DONE` 时的退出判断，避免 `kill -0` 卡住。
- 已重启 watcher：tmux `fig8_2h_capture`（09:23:07），target 仍为 2026-09-23 10:34:43。
- capture 解析已在已完成实例 kroA100 上验证：result=21828.0，best=21828.0。
- 231 farthest_eval 已于 08:58:57 完成，13 实例每实例 alarm 180s，满足 2h；verdict reasoning_farthest_avg 8.0387 / released 8.2829 / chat 9.3607。
- 225 当前 3 个大实例仍在第一个 selection round 的 TTS 阶段（仅 step_0，TTS worker CPU 45–51%），所以 2h 快照可能数值为 null；watcher 会保留 step/参数/进程/磁盘证据。

## 2026-09-23 09:33 停跑与 9 实例报告
- 09:30 按用户指令停跑 gr666/pr1002/pr2392 三个超长实例：kill 进程组 9270 + tmux `fig8_2h_capture` / `rerun_fig8_missing`；无 completion 值。
- 同时排除 pcb442（7500s timeout，result.txt 为超时前最后一轮完整解），整理其他 9 个干净实例。
- 逐实例结果写入 `results/fig8_tsp_225/Figure8_TSP_report.md`（每个实例独立 value/gap，不合并成单一平均值）。
- 辅助产物：`Figure8_TSP_9instances.csv`、`summary_9instances.json`；9 实例平均 gap 4.601%，论文基线 0.50%。
- 本地回拉目录：`heura_repro/evidence/fig8_tsp_225/`。
