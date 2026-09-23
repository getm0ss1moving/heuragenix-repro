# HA-PR EDA Harness Runbook

**规范口径先读：** `docs/METRIC_CONVENTIONS.md`  
**接管状态先读：** `HANDOFF.md`

## 0. 环境

- 本地代码镜像：`/Users/duanzeyu/Desktop/文献/heura_repro/eda`
- 服务器工作目录：`/data/dzy/heura_repr/eda`
- 执行节点：224（本任务工作节点）；234 备份；不要占用 225/231。
- 工具：OpenROAD 2022（`tools/openroad/bin/openroad`）、OpenLane 1（spm 本地流程在 `eda-101/exercises/ex09_openlane`）、sky130hd 测试库。
- Python：服务器 `python3`；本地 Mac `python3`。
- 关键环境变量：
  - `HEURA_EDA_BASE`：默认 `/data/dzy/heura_repr/eda`；本地测试时设为本地 `eda/` 路径。
  - `DEEPSEEK_LAB_API_KEY`：只在需要 dsv4-flash selector 时用；不落盘。

## 1. 同步修复后的代码到服务器

**推荐一键脚本（如已 `export SSHPASS=...` 且本机有 sshpass，会用 `sshpass -e` 免交互；否则 ssh/rsync 会提示密码，不落盘）：**

```bash
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
bash scripts/sync_and_recompute_224.sh
```

脚本会同步 `harness/ docs/ scripts/ HANDOFF.md README.md results/canonical_server/` 与 `PHASE0_REPORT_0006/0007/0008`，在 224 上执行 smoke test → migrate → recompute → cleanup → rebuild canonical，并把重算后的 `results/` 与 `runs/**/{metrics,state_card,verify,meta,flow.log}` 拉回本地。

手动 rsync（沿用下面示例）：

在本地：

```bash
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
rsync -avR harness/ docs/ scripts/ HANDOFF.md README.md results/PHASE0_REPORT_0006_WNS_FIX.md results/PHASE0_REPORT_0007_METRIC_AUDIT_v1.md results/PHASE0_REPORT_0008_SERVER_RECOMPUTE.md \
  <user>@202.121.181.105:/data/dzy/heura_repr/eda/
```

如果 224 不可用，再同步到 234 备份节点；不要碰 225/231。

## 2. 口径审计与旧 run 迁移

```bash
cd /data/dzy/heura_repr/eda
python3 harness/migrate_legacy_metrics.py --audit runs/*/metrics.json
python3 harness/migrate_legacy_metrics.py --runs-dir runs --in-place
python3 harness/migrate_legacy_metrics.py --candidates results/legacy_wrong_metrics/aes_candidates_full.json results/legacy_wrong_metrics/jpeg_candidates_full.json --out-dir results/canonical
```

审计输出中 `setup_wns_ns` 不应有 missing；`hold_tns_ns` 允许缺失（当前 OpenROAD 不总是输出 `tns_min`）。

离线冒烟测试（不需要 OpenROAD/网络；覆盖 canonicalization / setup-hold guard / utility / collect_runs / build_selector_dataset）：

```bash
python3 harness/smoke_test.py
# 期望输出：SMOKE_TEST_PASS
```

## 3. 跑 Phase 0 flow

```bash
cd /data/dzy/heura_repr/eda
BASE=/data/dzy/heura_repr/eda
export HEURA_EDA_BASE="$BASE"

python3 harness/phase0.py run --run-id gcd_baseline_x --design gcd --threads 8
python3 harness/phase0.py run --run-id aes_pad_2 --design aes --pad 2 --threads 8
python3 harness/sweep.py --sweep-id phase0_sweep_x --design gcd --threads 8
python3 harness/phase0.py state --run-id <run_id>
```

参数示例：
- `--density 0.40`：global placement density override。
- `--pad 2`：global placement pad override。
- `--grt-iters 200`：GRT congestion iterations。
- `--layer-adj "met1:0.4,met2:0.4,met3:0.3"`：layer adjustment。

## 4. verifier / 收集 / 统计

```bash
python3 harness/verifier.py \
  --def runs/<id>/results/<design>_sky130hd_route.def \
  --lef flow/sky130hd/sky130_fd_sc_hd_merged.lef \
  --design <design> \
  --ref-def reference/<design>_route.def \
  --netlist flow/<design>_sky130hd.v \
  --out runs/<id>/verify.json

python3 harness/collect_runs.py --design aes --out results/recomputed/aes_candidates_full.json \
  --pair base=aes_baseline_0001 density_040=aes_density_040 pad_2=aes_pad_2

python3 harness/stats.py \
  --sweep results/canonical_server/gcd_candidates.json results/canonical_server/aes_candidates.json \
          results/canonical_server/jpeg_candidates.json results/canonical_server/ibex_candidates.json \
  --out-json results/canonical_server/PHASE0_STATS_4designs_server.json \
  --out-md  results/canonical_server/PHASE0_STATS_4designs_server.md
```

## 5. selector（canonical WNS）

无 API（推荐先跑，确认 gate 行为）：

```bash
python3 harness/selector_v0.py --no-llm \
  --sweep results/canonical_server/gcd_candidates.json results/canonical_server/aes_candidates.json \
          results/canonical_server/jpeg_candidates.json results/canonical_server/ibex_candidates.json \
  --out-json results/canonical_server/PHASE0_SELECTOR_4designs_server.json \
  --out-md  results/canonical_server/PHASE0_SELECTOR_4designs_server.md
```

带 dsv4-flash：

```bash
export DEEPSEEK_LAB_API_KEY=...
python3 harness/selector_v0.py \
  --sweep results/canonical_server/gcd_candidates.json results/canonical_server/aes_candidates.json \
          results/canonical_server/jpeg_candidates.json results/canonical_server/ibex_candidates.json \
  --out-json results/canonical_server/PHASE0_SELECTOR_4designs_server_api.json \
  --out-md  results/canonical_server/PHASE0_SELECTOR_4designs_server_api.md
```

Prompt 中必须显式包含：setup WNS / hold WNS 两条 gate、源键、0.02 ns guardband、baseline 非负则不得转负；WNS 只做 gate，软效用只比 HPWL/TNS/power。

## 6. 蒸馏数据集 v4

```bash
cd /data/dzy/heura_repr/eda
# 先确认 config/dataset_runs.json 指向的 run 已按新 harness 生成，或用迁移后的 run
python3 harness/build_selector_dataset.py \
  --config config/dataset_runs.json \
  --runs-dir runs \
  --out-jsonl results/selector_dataset_v4.jsonl \
  --out-sft results/selector_sft_v4.jsonl \
  --out-summary results/selector_dataset_v4_summary.json \
  --out-preferences results/selector_preferences_v4.jsonl
```

注意：v3 数据集基于错误 WNS 字段，**不要用于训练/评估**；v4 才是 canonical 版本。

## 7. 报告生成

- 通用 sweep 报告：`harness/make_phase0_report.py`。
- 本批 WNS 勘误报告：`results/PHASE0_REPORT_0006_WNS_FIX.md`（本地已生成，服务器重算后升级 v2）。
- 第二批指标审计报告：`results/PHASE0_REPORT_0007_METRIC_AUDIT_v1.md`（power/DRC/instance/HPWL）。
- 所有报告必须声明：
  1. 执行节点、日期、OpenROAD/OpenLane 版本；
  2. timing convention（`setup_hold_v1_2026-09-22`）；
  3. setup/hold 的源键与 gate 结果；
  4. signed WNS/TNS 用 ns 绝对差，不用负基数百分比；
  5. 样本量、CI、失败/兜底情况。


## 9. 第二批口径修复后的服务器重算与清理

```bash
cd /data/dzy/heura_repr/eda
export HEURA_EDA_BASE=/data/dzy/heura_repr/eda
python3 harness/smoke_test.py

# 1) 旧 run 的 timing 字段迁移（先审核）
python3 harness/migrate_legacy_metrics.py --runs-dir runs --in-place

# 2) 从已有 DEF/flow.log 重算 HPWL/线长/via/power，不重跑 flow
python3 harness/recompute_metrics.py --runs-dir runs --in-place \
  --lef flow/sky130hd/sky130_fd_sc_hd_merged.lef

# 3) OpenLane 侧重新 ingest（修正 power/DRC/instance/HPWL 口径）
python3 harness/openlane_ingest.py --run-dir openlane_runs/<run> \
  --lef pdk/sky130A/sky130_fd_sc_hd.lef --out-dir openlane_runs/<run>/ingested_v2

# 4) 缺 DEF 的 run 需要补跑 flow（本次已用 scripts/rerun_missing_224.sh 完成 14 个）
python3 scripts/rerun_missing_224.sh

# 5) 重建 canonical 候选/统计/selector/dataset v4
python3 scripts/rebuild_canonical_224.py

# 6) 清理旧口径产物

python3 harness/cleanup_legacy.py --dry-run
python3 harness/cleanup_legacy.py --apply
```

## 8. 常见坑

- **相对路径**：定时/后台脚本必须用绝对路径，否则会空跑（历史上 eval_scheduler 因此失败过）。
- **LD_LIBRARY_PATH**：OpenROAD 需要 `tools/openroad_syslibs` 与 `tools/tclreadline/lib`；`phase0.py` 已自动加。
- **端口/节点**：EDA 用 224；225/231 不要抢占。
- **旧 metrics**：不要直接读旧 `wns_ns`；一律走 `metrics_schema.canonicalize_record`。
- **OpenLane ingest**：`metrics.csv` 的 `wns/tns` 暂按 setup 处理；需要 hold 时从 OpenROAD raw metrics 提取。
- **缺失字段**：hold 字段缺失时标记 `unchecked`，报告中说明，不能假装通过或假装满足。
