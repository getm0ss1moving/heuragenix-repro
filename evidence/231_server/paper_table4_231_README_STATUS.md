# paper_table4_231 状态说明（2026-09-23 09:40）

## 任务
论文口径 Table4：`raw / vanilla / dual` × 8 个 TSP 实例（kroC100、kroA100、kroB100、bier127、kroA150、tsp225、kroB200、a280）。
- `k=10`（`--tts-budget 10`）
- `--rollout-stop completion`（论文 until-completion 口径）
- `--time-limit 0`（不 2h 截断）
- `--fallback-complete 0`
- `--max-new-tokens 768`

## 运行
- 主脚本：`/tmp/dzy_p1a/run_p1a_231_v2.sh`（setsid/nohup 启动，PID 24707）
- 监控脚本：`/tmp/dzy_p1a/watch_p1a_231.sh`（PID 25025，每 4 分钟写 `p1a_watch.log`）
- 固定 GPU：`CUDA_VISIBLE_DEVICES=2`（进程内 cuda:0），不碰他人 GPU

## 当前进度（09:40 快照）
- `parts/` 已有：`raw__kroC100.tsp.json`、`raw__kroA100.tsp.json`
- 当前运行：`raw__kroB100.tsp`
- 目标：24 parts（3 mode × 8 instance）

## 目录布局
- `parts/`：每实例 JSON 分片，断点续跑依据（存在且非空则 skip）
- `logs/`：当前 run 的单实例日志
- `logs/failed_first_run_20260923_0839/`：08:39 首跑失败日志归档
- `smoke/`：09:22–09:24 冒烟结果
- `p1a_watch.log`：watcher 进度与最终汇总
- `table4_p1a_summary.csv`：24/24 后由 watcher 自动生成

## 完成后检查
    tail -20 .../p1a_watch.log
    wc -l .../table4_p1a_summary.csv
