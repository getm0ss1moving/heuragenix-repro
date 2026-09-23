# HANDOFF_SESSION4_INPROGRESS — P0 批量 replay 进行中（会话 4）

> **状态（2026-09-23 02:00）：已完成。** P0 222 条 replay、P1 数据集 v5 均已验收；最终接替入口 `HANDOFF_SESSION4_NEXT.md`。以下为运行中进行时记录，保留作历史与复现证据。


**时间：** 2026-09-22 22:10（北京时间）
**定位：** 会话 4 正在执行的 P0 批量 checkpoint replay；若本会话中断，按本文件接续即可，不必重读历史。
**上游：** `HANDOFF_SESSION3_NEXT.md`（P0 计划与口径）；有冲突以本文件 + 服务器/本地最新产物为准。

## 1. 当前状态一句话

P0 批量 replay **正在服务器 224 的 tmux `hapr_pool` 中运行**（jobs=8，EDA_THREADS=8，单任务 timeout=7200s）。截至 2026-09-22 23:30：v2=136 条（gcd 88/88 均 23s + jpeg 48/48 均约 800-1600s），pending=86（aes 50 + ibex 36）；首轮 aes control 曾因旧 1800s 超时失败，已通过重启池自动重排。**性能根因**：`flow/flow_param.tcl` 的 detailed route 默认 `set_thread_count 16`，旧 jobs=10 时 160 线程 / 64 核严重超订；现改为 `EDA_THREADS=8 × jobs=8 = 64 线程`。224 上另有外部用户 `yangjia` 约 16 个满载 python 进程，勿动。

## 2. 关键路径与文件

| 对象 | 路径（本地 / 224 `/data/dzy/heura_repr/eda`） |
|---|---|
| 任务计划 | `results/canonical_server/replay_batch_plan_v2.jsonl`（222 条） |
| 已生成标签（汇总） | `results/canonical_server/checkpoint_replay_v2.jsonl`（池每完成一条追加） |
| 任务级记录（断点续跑） | `results/canonical_server/v2_parts/<run_id>.jsonl` |
| 失败清单 | `results/canonical_server/replay_batch_v2_failures.tsv` |
| 池运行日志 | `logs/session4_pool.log`（224） |
| 并行池工具 | `harness/run_replay_pool.py` |
| 批量校验 | `harness/validate_replay_v2.py` |
| P1 数据集构建 | `harness/build_checkpoint_dataset.py` |
| v2 汇总表 | `harness/summarize_replay_v2.py` |
| P2 objective mode 模块 | `harness/selector_objective_mode.py`（离线已测：gcd HPWL_first→pad_2、power_first→density_035、balanced/timing_first→density_025） |
| 收尾一键脚本 | `scripts/remote/session4_finalize_224.sh` |

## 3. 断点续跑命令（有密码由 harness secrets 提供；禁止把密码写入任何文件/回复）

本地检查进度：

```bash
cd /Users/duanzeyu/Desktop/文献
source _harness/scripts/lib.sh && load_secrets && export SSHPASS="$HEURA_SSH_PASSWORD"
bash _harness/scripts/ssh_run.sh 224 'tail -5 /data/dzy/heura_repr/eda/logs/session4_pool.log; grep -c run_id /data/dzy/heura_repr/eda/results/canonical_server/checkpoint_replay_v2.jsonl; pgrep -x openroad | wc -l'
```

若 tmux 池不在但仍有 pending，重新拉起（幂等、会跳过已完成 run_id）：

```bash
bash _harness/scripts/ssh_run.sh 224 'tmux new-session -d -s hapr_pool "cd /data/dzy/heura_repr/eda && export HEURA_EDA_BASE=/data/dzy/heura_repr/eda && export EDA_THREADS=8 && python3 harness/run_replay_pool.py --plan results/canonical_server/replay_batch_plan_v2.jsonl --out-jsonl results/canonical_server/checkpoint_replay_v2.jsonl --parts-dir results/canonical_server/v2_parts --failures results/canonical_server/replay_batch_v2_failures.tsv --seed-jsonl results/canonical_server/checkpoint_replay_v2_smoke.jsonl --seed-jsonl results/canonical_server/checkpoint_replay_pilot.jsonl --jobs 8 --timeout 7200 > logs/session4_pool.log 2>&1; echo POOL_EXIT_\$? >> logs/session4_pool.log"'
```

修复坏记录/重跑失败：**重跑同一条命令即可**。池启动时会扫描 v2 与 parts，剔除 `returncode != 0` 或重复记录并重新调度。

## 4. 池完成后的一键收尾（224，约 1–2 分钟）

```bash
bash _harness/scripts/ssh_run.sh 224 'cd /data/dzy/heura_repr/eda && export HEURA_EDA_BASE=/data/dzy/heura_repr/eda && tmux new-session -d -s hapr_finalize "bash scripts/remote/session4_finalize_224.sh"; echo FINALIZE_STARTED'
# 轮询：logs/session4_finalize.log 出现 FINALIZE_DONE
```

收尾脚本依次执行：retry/compact → `validate_replay_v2.py`（硬门）→ `build_checkpoint_dataset.py --strict` 生成 `selector_dataset_v5_checkpoint.jsonl` / SFT / preferences / summary → `session_status.py`。

## 5. 验收门（沿用会话 3 handoff）

- v2 >= 200 条；46/46 replayable checkpoint 有 control 配对；无重复 run_id；
- returncode 失败率 < 5%，失败逐条记录；每条 action delta 与同 checkpoint control 配对；
- 写 `results/PHASE0_REPORT_0011_BATCH_REPLAY_V2.md`、`PHASE0_REPORT_0012_CHECKPOINT_DATASET_V5.md`，更新 `results/canonical_server/README.md` 与 `_harness/CHANGELOG.md`；
- 回拉 `checkpoint_replay_v2.jsonl`、`selector_dataset_v5_*`、summary、failures 到本地 canonical dir。

## 6. 收尾后的下一步（P2+）

- P2 objective mode selector：按 `PHASE0_ORACLE_SENSITIVITY` 显式输出 `objective_mode ∈ {timing_first, HPWL_first, power_first, balanced}`，评估 mode 准确率 + 条件 regret + gate 通过率；
- P3 设计族/ODB（向 `phase0.DESIGNS` 加拥塞/宏密集设计，checkpoint 存 ODB）；
- P4 signoff（DRC/LVS/STA + hold TNS）；P5 seed library。

## 7. 已知注意

- 224 上外部用户 `yangjia` 有 16 个 ~100% CPU 的 python 进程；**不要 kill 任何非本项目的进程**。有 tmux 与 openroad 进程时先 `pgrep -x openroad -a` 确认属于 `runs_replay`。
- 池每任务独立 artifact dir，`checkpoint_replay.py` 启动时会清空同名 run dir，因此同一 run_id 不能并发；不要启动两条池处理同一 plan。
- 不要使用旧口径产物（0003–0005、selector_dataset_v3）。
