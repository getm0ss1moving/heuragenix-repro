# PHASE0_REPORT_0006：WNS 口径勘误与 canonical 重算

**日期：** 2026-09-22  
**范围：** gcd / aes / jpeg / ibex 四设计旧派生数据（本地 `results/*candidates*.json`，已迁移到 `results/canonical/`）  
**结论：** 旧 harness 把 `DRT::worst_slack_min`（hold slack）当作 WNS；已建立 canonical setup/hold 口径并用本地已有数据重算。四个设计的 oracle 与旧报告一致，但 timing gate 的理由、软效用和 regret 数值需要以本报告为准。

> **服务器权威版本：** 2026-09-22 已在 224 完成 canonical 重算与缺 DEF 候选补跑；权威结果见 `results/PHASE0_REPORT_0008_SERVER_RECOMPUTE.md` 与 `results/canonical_server/`。本文件（0006）是本地 pre-server 版；它引用的 `*_wnsfix*` 已归档到 `results/legacy_wrong_metrics/`，仅供口径修正过程说明。

---

## 1. 问题定义

旧字段映射（`harness/phase0.py`、`collect_runs.py`、`selector_v0.py`）：

| 旧字段 | 实际来源 | 真实含义 |
|---|---|---|
| `wns_ns` / `wns_min_ns` / `wns_ps` | `DRT::worst_slack_min` | **hold**（min-delay）worst slack |
| `wns_max_ns` | `DRT::worst_slack_max` | **setup**（max-delay）worst slack |
| `tns_ns` / `tns_ps` | `DRT::tns_max` | setup TNS |

旧代码把 hold slack 命名为 `wns_ns` 并用于 timing gate，导致：
1. setup WNS 从未被显式守护；
2. 报告出现 "jpeg baseline WNS=0.040、TNS=-129.9" 的 setup/hold 混用；
3. 旧 soft utility 中含有的 WNS 项实际上是 hold slack 项，使 regret 可被 hold 改善掩盖。

## 2. Canonical 口径（v1，2026-09-22）

- `setup_wns_ns` = `DRT::worst_slack_max`（越大越好，负值=setup 违例）
- `hold_wns_ns` = `DRT::worst_slack_min`（越大越好，负值=hold 违例）
- `setup_tns_ns` = `DRT::tns_max`
- `hold_tns_ns` = `DRT::tns_min`（当前数据缺失）
- Gate：setup/hold 分别满足 `cand >= base - 0.02 ns`；且若 base ≥ 0，cand 不得转负。
- Soft utility（gate 之后）：`U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power`；WNS 只做 gate。

详见 `docs/METRIC_CONVENTIONS.md` 与实现 `harness/metrics_schema.py`。

## 3. 四设计 baseline 真实 timing（旧数据重算）

| design | setup_wns_ns | hold_wns_ns | setup_tns_ns | 旧报告 "WNS" |
|---|---|---|---|---|
| gcd | -0.6333 | +0.4842 | -15.58 | +0.484（实际 hold） |
| aes | -1.8613 | -0.1463 | -289.19 | -0.146（实际 hold） |
| jpeg | -1.0944 | +0.0402 | -129.90 | +0.040（实际 hold） |
| ibex | -5.2052 | -0.1259 | -299.05 | -0.126（实际 hold） |

**关键修正：** gcd 与 jpeg baseline 的 setup 本来就是负 slack（违例），旧报告却因为取 hold slack 而显示为正；这并不意味着 setup 被 gate 正确守护。

## 4. canonical 重算的 oracle 与 selector

用 `--no-llm`（random/rule/oracle）在 `results/canonical/` 上重算：

| design | oracle | rule（naive） | rule regret（gate-aware） | random mean regret |
|---|---|---|---|---|
| gcd | pad_2 | pad_2 | 0.0 | 0.177 |
| aes | pad_2 | pad_2 | 0.0 | 0.280 |
| ibex | pad_2 | pad_2 | 0.0 | 0.378 |
| jpeg | layeradj | pad_2 | **0.785** | 0.383 |

- Oracle 与旧报告相同：gcd/aes/ibex→pad_2，jpeg→layeradj。
- jpeg 旧报告的 rule regret=0.7264 来自错误 WNS 软项；canonical 下 naive rule（pad_2）在 gate-aware regret 下为约 **0.785**，更准确地反映 "未守 timing gate 的代价"。
- jpeg 的 pad_2/density_040 并非 setup 变差被拒，而是 **hold 从非负转负** 被新 gate 拒绝；layeradj 是唯一 setup/hold 双 safe。
- gcd/aes/ibex 的结论不变，但 gate 理由现在显式区分 setup 与 hold。

## 5. 产物

- `results/canonical/{phase0_sweep_0002,aes_candidates_full,jpeg_candidates_full,ibex_candidates}.json`
- `results/PHASE0_STATS_4designs_wnsfix.json` / `.md`
- `results/PHASE0_SELECTOR_4designs_wnsfix.json` / `.md`
- `docs/METRIC_CONVENTIONS.md`
- `harness/metrics_schema.py`
- `harness/migrate_legacy_metrics.py`

## 6. 尚未完成/必须在服务器 224 重跑

1. 旧 run 的 `metrics.json` 通过 `migrate_legacy_metrics.py --runs-dir runs --in-place` 迁移到 canonical；
2. 用新 `collect_runs.py` / `stats.py` / `selector_v0.py`（可带 API）在服务器重算四设计；
3. 重建 `selector_dataset_v4`（v3 基于错误字段，废弃）；
4. 写 `PHASE0_REPORT_0007`（服务器实跑版）并把旧报告 0003/0004/0005 标为历史。

## 7. 旧报告引用规则

- `PHASE0_REPORT_0003/0004/0005`：仅作历史记录；其中所有 "WNS" 数值按 hold slack 解读，不能用于 gate、训练标签或论文数字。
- 本报告 `PHASE0_REPORT_0006`：本地重算版本；服务器重跑后以 `0007` 为最终版本。
