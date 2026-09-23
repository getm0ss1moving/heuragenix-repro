# HA-PR Phase 0：EDA 布局布线 harness

本目录是 `10_完整数学建模体系_EDA布局布线与测试_v1.md` 的 Phase 0 实现落点。**执行节点：端口 224（thinklab-105-224，本项目工作端口）**。用户澄清：之前“224 是另一个实验，不要占用”的提醒，本意是让其他窗口不要抢占本项目的工作端口，不是禁止本项目使用；曾误读为禁用而临时迁到 234，现以 224 为准，234 仅作备份。OpenLane 1 全流程继续在本地 colima + sky130A 跑。

> **2026-09-22 WNS 口径勘误**：旧 harness 把 `DRT::worst_slack_min`（hold slack）当作 WNS；真正的 setup WNS 是 `DRT::worst_slack_max`。canonical 定义见 `docs/METRIC_CONVENTIONS.md`，实现见 `harness/metrics_schema.py`，本地重算见 `results/PHASE0_REPORT_0006_WNS_FIX.md`。本 README 下面所有旧 “WNS” 数值/结论都已过期，需按 setup/hold 双口径重算；旧报告 0003/0004/0005 已加勘误横幅。
>
> **接管入口：** `HANDOFF.md`（当前状态、关键结论、下一步）；`docs/RUNBOOK.md`（环境与运行命令）。

> **2026-09-22 第二批口径勘误**：OpenLane `power_*_uW` 列实际是 W（旧 ingest 差 1e6）；DRC 旧逻辑把 detailed-route 总数与子计数/Magic/KLayout 混加（已改为分开存储 + canonical 规则）；`instance_count` 改用 `synth_cell_count`（逻辑单元）；DEF HPWL 修正 `( PIN port )`/换行 pin，并拆出 `hpwl_no_ports_um`；新增 `harness/metric_rules.py`、`harness/recompute_metrics.py`、`harness/cleanup_legacy.py`，旧产物已移入 `results/legacy_wrong_metrics/`。

## 当前状态（2026-09-22，canonical 口径）

Phase 0 已完成 **gcd / aes / jpeg / ibex** 四个设计族 + OpenLane spm 接入 + pin-offset HPWL + L0/L1 verifier + selector/stats + timing guard。指标口径已完成两轮审计：

- **WNS/TNS**：canonical setup = `DRT::worst_slack_max`，hold = `DRT::worst_slack_min`；旧报告中的 "WNS" 实为 hold slack，已作废。
- **Power**：OpenLane `power_*_uW` 列实际是 W；修复了 1e6 倍换算错误（spm 1.139e-3 W）。
- **DRC**：不再把 detailed-route 总数与子计数、Magic/KLayout 混加；canonical = max(KLayout, Magic) 或 detailed-route 总数。
- **Instance**：`instance_count` 改用逻辑单元 `synth_cell_count`，`total_cell_count` 单列。
- **HPWL**：DEF pin 中心 + LEF offset + orientation，含顶层端口 `( PIN port )`；另存 `hpwl_no_ports_um` 用于与 OpenLane global HPWL 对照；旧 origin-only 版本仅回归。
- **服务器重算已完成（2026-09-22, 224）**：21 个旧 run 迁移/重算 + 14 个缺 DEF 候选补跑；权威产物在 `results/canonical_server/`，报告 `results/PHASE0_REPORT_0008_SERVER_RECOMPUTE.md`。dsv4-flash API selector 已补跑：3/4 与 oracle 一致；gcd 选 density_035（接近 oracle density_025，utility 近邻分歧）。旧口径与本地 pre-server 产物在 `results/legacy_wrong_metrics/`。
- **新 oracle（服务器 canonical）**：gcd→`density_025`（旧 pad_2 因 HPWL/utility 口径变化被替换）、aes→`pad_2`、jpeg→`layeradj`、ibex→`pad_2`；jpeg 仍是最能体现 timing gate 价值的案例（naive rule regret≈0.79）。
- **接管：** `HANDOFF.md`（状态/下一步）与 `docs/RUNBOOK.md`（运行/重算/清理）；服务器同步重算用 `scripts/sync_and_recompute_224.sh`（已实际跑通）。
- **checkpoint replay 原型：** `harness/checkpoint_replay.py` 已能从 post_global_place/post_cts DEF 续跑（`read_def`，不可先 link_design），支持注入 layer adjustment / congestion 动作；首批 5 条 gcd 标签在 `results/canonical_server/checkpoint_replay_v1.jsonl`，报告 `PHASE0_REPORT_0010_CHECKPOINT_REPLAY_v1.md`。
- **已知不完美：** 旧报告 0003–0005 仅历史；gcd 的 API/oracle 存在 utility 近邻分歧（density_035 vs density_025），需定义目标优先级；样本量小、CI 宽；L2/L3 signoff 尚未接入；hold TNS 仍缺失；replay baseline 与 full-flow 有少量状态差异，动作对比用同 stage replay control。

## 目录

```text
eda/
  tools/openroad/bin/openroad    # OpenROAD 2022 二进制
  tools/openroad_syslibs/        # 跨节点备份补齐的 Qt5/Tcl 等 38 个依赖
  tools/tclreadline/lib/         # libtclreadline
  flow/                          # sky130hd 库 + gcd/aes/jpeg 预综合网表 + flow_param.tcl
  pdk/sky130A/sky130_fd_sc_hd.lef
  harness/
    lef_def.py                   # LEF pin offset + DEF 解析 + HPWL（含 no_ports/origin 三口径）
    metrics_schema.py            # canonical setup/hold WNS/TNS
    metric_rules.py              # power/DRC/instance/HPWL 口径规则
    migrate_legacy_metrics.py    # 旧 timing 字段迁移
    recompute_metrics.py         # 从既有 DEF/flow.log 重算，不重跑 flow
    cleanup_legacy.py            # 旧口径产物移入 results/legacy_wrong_metrics
    phase0.py                    # gcd/aes/jpeg 参数化运行 + metrics/state card + verifier
    verifier.py                  # L0/L1: overlap/row/boundary/net/fixed/netlist hash
    sweep.py                     # 参数 sweep
    openlane_ingest.py           # OpenLane run -> 统一 metrics/state card
    selector_v0.py               # random/rule/oracle/dsv4-flash selector
    stats.py                     # paired delta + bootstrap CI
    collect_runs.py              # run 目录 -> sweep JSON
    make_phase0_report.py        # sweep -> Markdown/JSON
  reference/{gcd,aes}_route.def  # verifier fixed-object 参考
  openlane_runs/                 # OpenLane slim 产物与 ingest 结果
  runs/<run_id>/                 # flow.log / metrics*.json / meta.json / verify.json / results/
  docs/METRIC_CONVENTIONS.md     # 指标口径规范（WNS/power/DRC/HPWL/instance）
  docs/RUNBOOK.md                # 运行、同步、重算、清理命令
  HANDOFF.md                     # 跨会话接替状态
  scripts/sync_and_recompute_224.sh  # 同步 224 + migrate/recompute/cleanup
  results/                       # PHASE0_REPORT_0006_WNS_FIX、*_wnsfix、canonical/
  results/legacy_wrong_metrics/  # 旧口径产物（禁止使用）
  results/canonical_server/             # 服务器 224 重算后的权威结果
```

## 运行（224）

```bash
cd /data/dzy/heura_repr/eda
python3 harness/smoke_test.py   # 离线口径冒烟测试

BASE=/data/dzy/heura_repr/eda
cd "$BASE"
export HEURA_EDA_BASE="$BASE"
python3 harness/phase0.py run --run-id gcd_baseline_x --design gcd --threads 8
python3 harness/phase0.py run --run-id aes_pad_2 --design aes --pad 2 --threads 8
python3 harness/sweep.py --sweep-id phase0_sweep_x --design gcd --threads 8
python3 harness/verifier.py --def runs/<id>/results/<design>_sky130hd_route.def --lef flow/sky130hd/sky130_fd_sc_hd_merged.lef --design <design> --ref-def reference/<design>_route.def --netlist flow/<design>_sky130hd.v --out runs/<id>/verify.json
python3 harness/collect_runs.py --design aes --out results/recomputed/aes_candidates.json --pair base=aes_baseline_0001 density_040=aes_density_040 pad_2=aes_pad_2
python3 harness/stats.py --sweep results/canonical_server/gcd_candidates.json results/canonical_server/aes_candidates.json results/canonical_server/jpeg_candidates.json results/canonical_server/ibex_candidates.json --out-json results/canonical_server/PHASE0_STATS_4designs_server.json --out-md results/canonical_server/PHASE0_STATS_4designs_server.md
python3 harness/selector_v0.py --no-llm --sweep results/canonical_server/gcd_candidates.json results/canonical_server/aes_candidates.json results/canonical_server/jpeg_candidates.json results/canonical_server/ibex_candidates.json --out-json results/canonical_server/PHASE0_SELECTOR_4designs_server.json --out-md results/canonical_server/PHASE0_SELECTOR_4designs_server.md
python3 harness/openlane_ingest.py --run-dir openlane_runs/spm_phase0_0001_src --lef pdk/sky130A/sky130_fd_sc_hd.lef --out-dir openlane_runs/spm_phase0_0001/ingested
```

本地 OpenLane：

```bash
cd /Users/duanzeyu/Desktop/文献/eda-101/exercises/ex09_openlane
bash run_openlane.sh spm phase0_0001
```

## 下一步

0. **最高优先**：把修复后的 harness 同步到 224，依次执行 `migrate_legacy_metrics.py --runs-dir runs --in-place` → `recompute_metrics.py --runs-dir runs --in-place` → 重建 collect/stats/selector → `cleanup_legacy.py --apply`，并升级 `PHASE0_REPORT_0006` 为服务器版（含第二批口径修正）。
1. 重建蒸馏数据集 v4（v3 基于错误 WNS 字段，废弃）；样本目标 200–1000 条。
2. 增加 checkpoint 续跑（post_global_place/post_cts/post_grt）与更多设计族；拥塞型设计优先。
3. 增加 layer adjustment / RRR 批策略 skill，找有拥塞差异的测试。
4. dsv4-flash selector 已四设计验证；下一步本地蒸馏 selector。
5. verifier 增加 fixed/netlist 全量回归、DRC/LVS/STA 报告接入；hold TNS 提取。
