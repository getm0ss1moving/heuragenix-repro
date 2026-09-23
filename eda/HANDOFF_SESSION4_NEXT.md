# HANDOFF_SESSION4_NEXT — P0/P1 已完成（会话 4 → 下一会话）

**日期：** 2026-09-23 凌晨（北京时间）
**定位：** 最新接替入口；只读本文件 + 跑三条离线命令即可接续，不必重读历史。
**上游：** `HANDOFF_SESSION3_NEXT.md`（计划）、`docs/METRIC_CONVENTIONS.md`（口径）。

## 0. 下一会话第一条命令（离线验证继承）

```bash
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
python3 harness/smoke_test.py          # 期望 SMOKE_TEST_PASS
python3 harness/session_status.py      # 期望 v2=222、control coverage 46/46
python3 harness/validate_replay_v2.py  # 期望 VALIDATE_REPLAY_V2_PASS
python3 harness/build_checkpoint_dataset.py --strict   # 期望 46 decisions / 176 samples / 0 errors
```

## 1. 一句话状态

**P0 完成：** 4 设计 × 2 stage × 首轮 6 动作，共 **222 条 replay 标签**（46 control + 176 action），全部 rc=0、DRC=0、control 覆盖 46/46、0 重复、0 有效失败；报告 `results/PHASE0_REPORT_0011_BATCH_REPLAY_V2.md`。
**P1 完成：** checkpoint selector 数据集 v5：46 决策点 / 176 action 样本 / 46 SFT / 46 preferences，canonical timing gate 通过率 0.892，oracle 分布 layeradj 29 / grt200 12 / cap0 5，0 校验错误；报告 `results/PHASE0_REPORT_0012_CHECKPOINT_DATASET_V5.md`。
**P2 部分完成：** objective mode 条件化 selector 模块与 4 设计 × 4 mode 离线表已产出（LLM 评估未执行）。

## 2. 权威产物（本地 canonical：`results/canonical_server/`）

| 产物 | 说明 |
|---|---|
| `checkpoint_replay_v2.jsonl` | 222 条 replay 记录（权威） |
| `v2_parts/<run_id>.jsonl` | 每任务独立 part（断点续跑） |
| `PHASE0_REPLAY_V2_VALIDATION.json` | 验收结果：records=222, control=46/46, dup=[], rc_fail=0, retried_ok=[aes_baseline_0001_pgp_control] |
| `PHASE0_REPLAY_V2_SUMMARY.{json,md}` | paired 动作效应表 |
| `selector_dataset_v5_checkpoint.jsonl` | 176 条 action 标签（delta/gate/U） |
| `selector_sft_v5_checkpoint.jsonl` / `selector_preferences_v5_checkpoint.jsonl` | SFT / 偏好数据 |
| `selector_dataset_v5_summary.json` | v5 统计 |
| `PHASE0_OBJECTIVE_MODE_SELECTOR.{json,md}` | P2 离线 mode 表 |
| `README.md` | canonical 目录索引 |

## 3. 执行要点与坑（会话 4 已验证）

- **批量池：** `harness/run_replay_pool.py`（有界并发、每任务 part、v2 汇总、resume、坏记录压缩重试）。
- **线程洞：** `flow/flow_param.tcl` detailed route 默认 `set_thread_count 16`；`EDA_THREADS` 可覆盖。10 并发 × 16 = 160 线程/64 核导致 aes 1800s 超时；`EDA_THREADS=8 × jobs=8` 后稳定（aes 479–1274s，无新超时）。
- **外部负载：** 224 上有其他用户约 16 个满载 CPU 进程，属共享节点；禁止 kill 非本项目进程，动手前 `pgrep -x openroad -a` 确认。
- **超时：** 单任务 timeout 用 7200s；不要用 1800s（aes/ibex 会超时）。
- **控制配对红线：** 动作 delta 只能与同 checkpoint、同 stage 的 control 配对；同 checkpoint 内 control/action 使用相同线程配置。
- **重试：** 重跑池命令即自动跳过已完成、压缩无效记录并重试失败；`retried_ok` 记录在 validation JSON。
- 414 条扩展（全 10 动作）未跑；命令见 §5。

## 4. 下一步任务

### P2（优先）：objective mode selector LLM 评估
- 工具 `harness/selector_objective_mode.py` 已支持 `--no-llm` 离线表；LLM 路径会要求模型输出 `objective_mode + skill_id`，并计算 mode accuracy / conditional regret / gate pass。
- 需先跑 16-token API 自检并实现多 key 回退；参考 `HARNESS.md` §5（`DEEPSEEK_LAB_API_KEY` 优先，注意 rstrip 逗号）。
- 评估口径：mode-conditioned oracle + 条件 regret + gate 通过率；不再宣称唯一 oracle。

### P3：设计族/ODB
- 向 `harness/phase0.py` 的 `DESIGNS` 增加拥塞型/宏密集设计（如 spm 等）；checkpoint 保存 ODB（`write_db`）以减少 replay 状态差。

### P4：signoff
- verifier 接 DRC（KLayout/Magic）、LVS（Netgen）、STA（OpenSTA + SPEF）、hold TNS，形成 L2/L3 门禁。

### P5：seed library
- 按 `../10_完整数学建模体系_EDA布局布线与测试_v1.md` §11：30–60 候选 → F0/F1/F2/F3 多保真筛选 → K=6–10 种子库。

## 5. 服务器运维（224；密码只在 `_harness/secrets/servers.env`）

只读探测与断点续跑：

```bash
cd /Users/duanzeyu/Desktop/文献
bash _harness/scripts/ssh_run.sh 224 'cd /data/dzy/heura_repr/eda && export HEURA_EDA_BASE=/data/dzy/heura_repr/eda && python3 harness/session_status.py | head -40'
```

扩展首轮 222 → 全 10 动作（406 条，已完成项自动跳过）：

```bash
bash _harness/scripts/ssh_run.sh 224 'tmux new-session -d -s hapr_pool "cd /data/dzy/heura_repr/eda && export HEURA_EDA_BASE=/data/dzy/heura_repr/eda && export EDA_THREADS=8 && python3 harness/run_replay_pool.py --plan results/canonical_server/replay_batch_plan_full.jsonl --out-jsonl results/canonical_server/checkpoint_replay_v2.jsonl --parts-dir results/canonical_server/v2_parts --failures results/canonical_server/replay_batch_v2_failures.tsv --jobs 8 --timeout 7200 > logs/session4_pool_full.log 2>&1; echo POOL_EXIT_\$? >> logs/session4_pool_full.log"'
```

（全 10 动作计划需先用 `plan_replay_batch.py` 以全动作目录生成；见会话 3 handoff §3。）

## 6. 路径索引

```text
接替/口径
  HANDOFF_SESSION4_NEXT.md（本文件）
  HANDOFF_SESSION3_NEXT.md（P0 计划）
  HANDOFF_SESSION4_INPROGRESS.md（会话 4 运行记录，已完成）
  docs/METRIC_CONVENTIONS.md / docs/RUNBOOK.md
  results/canonical_server/README.md
工具
  harness/run_replay_pool.py / checkpoint_replay.py / plan_replay_batch.py
  harness/validate_replay_v2.py / summarize_replay_v2.py / build_checkpoint_dataset.py
  harness/make_replay_reports.py / selector_objective_mode.py
报告
  results/PHASE0_REPORT_0011_BATCH_REPLAY_V2.md
  results/PHASE0_REPORT_0012_CHECKPOINT_DATASET_V5.md
方法
  ../09_EDA布局布线_新流程与数学建模_报告v1.md
  ../10_完整数学建模体系_EDA布局布线与测试_v1.md
```
