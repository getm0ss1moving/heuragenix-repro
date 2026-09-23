# 231 节点任务整理（2026-09-23 09:40）

- hostname：`think4proj-105-232`，5×RTX4090，64 核。
- 根盘 `/` 与 `/data` 共用 `/dev/sda1`，余量约 **5.0G（99%）**；大文件只走 `/mnt/nas-new`（余 16T）。
- 项目目录：`/data/dzy/heura_repr`；模型软链到 `/mnt/nas-new/dzy/heura_repr_models`。

## 运行中
| 任务 | PID | 状态 |
|---|---|---|
| P1A 论文口径 Table4 v2 | 24707 + watcher 25025 | raw 已落 2/8（kroC100、kroA100），当前 raw kroB100；后续 vanilla/dual 共 24 parts |
- 输出：`/data/dzy/heura_repr/results/paper_table4_231/`
- 详细：`paper_table4_231/README_STATUS.md`

## 已完成
| 任务 | 产物 |
|---|---|
| farthest reasoning eval | `results/b_reason_farthest_final.json`、`b_reason_farthest_eval.csv`（reasoning n=8 avg 8.039 / released 8.283 / chat 9.361） |
| k10 completion 口径子集 | `results/eval_full/parts_k10/`（24/24）、`results/eval_full/k10_subset.csv`；stop 口径为 completion，后续需重标或重跑 |
| Table5 全量 | `results/table5_full_corrected.csv`（354 run） |

## 历史/归档
| 目录/文件 | 处理 |
|---|---|
| `results/paper_table4_231/logs/failed_first_run_20260923_0839/` | 08:39 首跑失败日志已从 `logs/` 移入归档，避免与 v2 混淆 |
| `results/fig8_tsp/` | 2026-09-23 02:07 的 Figure8 小日志，已被 225 主 campaign 取代；保留但不再更新 |
| `results/eval_full/parts_k10/` | k10 completion 口径子集，保留供重标对照 |

## 常用只读检查
    bash _harness/scripts/ssh_run.sh 231 'tail -20 /data/dzy/heura_repr/results/paper_table4_231/p1a_watch.log'
    bash _harness/scripts/ssh_run.sh 231 'ls -l /data/dzy/heura_repr/results/paper_table4_231/parts | tail'
    bash _harness/scripts/ssh_run.sh 231 'df -h / /mnt/nas-new'

## 纪律
1. 不 kill 他人 GPU 任务；当前 P1A 固定 231 的 GPU2（进程内 cuda:0）。
2. 根盘只剩约 5G，不在 `/data` 写大模型/大日志；大文件走 `/mnt/nas-new`。
3. P1A 输出 JSON 很小，落盘到 `results/paper_table4_231/` 可接受，但不要新增全量日志刷屏。
