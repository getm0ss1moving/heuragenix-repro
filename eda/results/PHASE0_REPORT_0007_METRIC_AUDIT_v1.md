# PHASE0_REPORT_0007：第二批指标口径审计与本地重算 v1

**日期：** 2026-09-22  
**范围：** 除 WNS 外的其他 EDA 指标（power / DRC / instance / HPWL / wirelength / vias）  
**结论：** 修好四类口径问题并把规则集中到 `harness/metric_rules.py`；本地 OpenLane spm run 已重算出正确值。服务器 224 需执行 `scripts/sync_and_recompute_224.sh` 做同样重算与清理。

---

## 1. 发现与修正

### 1.1 Power 单位错误（factor 1e6）

- OpenLane 1 `metrics.csv` 列名 `power_*_uW`，但数值实际是 **W**。
- 本地证据：`eda-101/exercises/ex09_openlane/parse_reports.py` 注释明确；spm 三列相加 `0.00082 + 0.000319 + 1.88e-7 = 1.139188e-3 W`，与 OpenSTA power report 一致。
- 旧 `openlane_ingest.py` 按 µW 处理并 `round(...,9)`，得到 `1e-9 W`，低估 10^6 倍。
- 修正：`metric_rules.openlane_power_w(raw)` 直接求和为 W；`phase0.parse_log_power` 统一使用 `metric_rules.parse_power_log_line`。

### 1.2 DRC 重复计数

- `tritonRoute_violations` 已是 detailed router 总违例数；`Short/MetSpc/OffGrid/MinHole/Other` 是它的子计数，Magic/KLayout 是另一套 signoff DRC。
- 旧逻辑把所有列相加，会重复计算 detailed-route 违例。
- 修正规则：
  - `drc_detailed_route` = `tritonRoute_violations`，缺失时用子计数之和；
  - `drc_violations` = `max(KLayout, Magic)`（有 signoff DRC 时），否则等于 detailed-route 总数；
  - Magic/KLayout/子项分别保存。

### 1.3 Instance count 口径

- `TotalCells` 含 filler/decap/welltap；旧 ingest 把它当设计规模。
- 修正：规范 `instance_count = synth_cell_count`（逻辑单元），另存 `total_cell_count = TotalCells`。
- spm 实测：logic 301，total 1108。

### 1.4 HPWL 解析与三口径

- 旧 DEF 解析漏掉两类 pin：
  - 顶层端口连接 `( PIN portName )`；
  - 换行/无 `+` 的 continuation 行（真实 DEF 存在这种写法）。
- 修正后新增：
  - `hpwl_um`：DEF pin 中心 + LEF pin offset + orientation，**含顶层端口**（规范）；
  - `hpwl_no_ports_um`：同上但忽略顶层端口，用于与 OpenLane global-placement `HPWL` 指标对照；
  - `hpwl_origin_um`：仅组件 origin，旧结果回归用，不作主指标。
- spm placement 本地数值：`hpwl_um=5372.552`、`hpwl_no_ports_um=4939.075`、`hpwl_origin_um=5740.820`；OpenLane `HPWL` 指标 `4514.213`（global placement log，单位 DB/1000）。
- `openlane_ingest` 的 `HPWL` 明确标为 `hpwl_metric_csv_um`，与 DEF pin-offset HPWL 分开，不再混用。

### 1.5 其他

- `wirelength_um` 来源 = detailed router log `Total wire length (um)`；`vias` = `Total number of vias`，均已标注 source。
- `phase0.py` 中无 pin offset 的旧 `def_metrics` 已删除，避免后续误用。
- `clock_skew_ns` 仍取 `DRT::clock_skew`（ns）；后续若工具版本变化再审计。

## 2. 本地重算证据（spm）

| 指标 | 旧 ingest | 修正后 |
|---|---|---|
| power_w | 1e-9 | **0.001139188** |
| drc_violations | 0（恰好无 DRC，未暴露重复计数） | 0 |
| instance_count | 1108 | **301（逻辑单元）** |
| total_cell_count | 未记录 | 1108 |
| hpwl_placement_um | 4661.723（旧解析漏 pin） | **5372.552（含端口）** |
| hpwl_no_ports_um | 未记录 | **4939.075** |
| OpenLane HPWL 指标 | 4514.213 | 4514.213（单列，仅对照） |

## 3. 代码/文档变更

- `harness/metric_rules.py`：power / DRC / instance / HPWL 规则集中实现。
- `harness/lef_def.py`：支持 `( PIN port )`、continuation、三口径 HPWL。
- `harness/openlane_ingest.py`、`phase0.py`：接入规则；删除旧 HPWL 函数。
- `harness/recompute_metrics.py`：从已有 DEF/flow.log 重算，不重跑 flow。
- `harness/cleanup_legacy.py`：旧口径产物移入 `results/legacy_wrong_metrics/`。
- `harness/smoke_test.py`：增加 power/DRC/instance/HPWL 与端口 pin 测试。
- `docs/METRIC_CONVENTIONS.md` §8–9；`docs/RUNBOOK.md` §9；`README.md` / `HANDOFF.md` 同步。

## 4. 服务器下一步

```bash
cd /Users/duanzeyu/Desktop/文献/heura_repro/eda
bash scripts/sync_and_recompute_224.sh    # 需要 ssh/rsync 凭据
```

或在 224 上手动执行：

```bash
cd /data/dzy/heura_repr/eda
export HEURA_EDA_BASE=/data/dzy/heura_repr/eda
python3 harness/smoke_test.py
python3 harness/migrate_legacy_metrics.py --runs-dir runs --in-place
python3 harness/recompute_metrics.py --runs-dir runs --in-place \
  --lef flow/sky130hd/sky130_fd_sc_hd_merged.lef
python3 harness/cleanup_legacy.py --apply
```

重算后需重建 `collect_runs` / `stats` / selector / dataset v4，并写 `PHASE0_REPORT_0008`（服务器实跑版）。
