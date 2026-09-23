# HA-PR EDA 指标口径规范（v1，2026-09-22）

## 0. 为什么要单独写这一页

旧 harness 把 OpenROAD/OpenSTA 的 `DRT::worst_slack_min` 直接命名为 `wns_ns`，但该字段是 **min-delay（hold）分析的 slack**，不是 setup WNS。真正的 setup worst slack 是 `DRT::worst_slack_max`。这导致：

- 旧报告里的 "WNS" 实际是 hold slack，而 "TNS" 用的是 setup TNS，出现 setup/hold 混用；
- selector/prompt/oracle 的 timing gate 实际在守 hold，而不是守 setup WNS；
- `jpeg baseline WNS=0.040, TNS=-129.9` 这种看起来矛盾的数字，就是 setup TNS 配 hold WNS。

本文件是 harness 的**唯一口径来源**；代码实现见 `harness/metrics_schema.py`。

## 1. 规范定义（v1）

| 规范字段 | 含义 | OpenROAD/OpenSTA 源键 | 符号约定 | 单位 |
|---|---|---|---|---|
| `setup_wns_ns` | setup（max-delay）分析的最差 slack | `DRT::worst_slack_max`，回退 `RSZ::worst_slack_max` | 越大越好；`>=0` 表示 setup 满足，`<0` 表示 setup 违例 | ns |
| `hold_wns_ns` | hold（min-delay）分析的最差 slack | `DRT::worst_slack_min`，回退 `RSZ::worst_slack_min` | 越大越好；`>=0` 表示 hold 满足，`<0` 表示 hold 违例 | ns |
| `setup_tns_ns` | setup 分析的 total negative slack | `DRT::tns_max`，回退 `RSZ::tns_max` | 通常 `<=0`；越接近 0 越好 | ns |
| `hold_tns_ns` | hold 分析的 total negative slack（若工具输出） | `DRT::tns_min`，回退 `RSZ::tns_min` | 通常 `<=0`；越接近 0 越好 | ns |

> 关键记忆点：`worst_slack_max` 的 "max" 指 **max-delay/setup** 分析，不是"最大 slack"；它的值通常是负的。`worst_slack_min` 的 "min" 指 **min-delay/hold** 分析。

## 2. 计时门禁（timing guardband）

对 setup 和 hold **分别**应用（若该分析的字段缺失，则记录 `unchecked`，不能假装通过）：

$$
\text{cand}_{analysis} \ge \text{base}_{analysis} - g,\qquad g=0.02\,\text{ns}
$$

并且：

$$
\text{base}_{analysis} \ge 0 \;\Rightarrow\; \text{cand}_{analysis} \ge 0
$$

即：
1. 不允许相对 baseline 退化超过 0.02 ns；
2. 如果 baseline 该分析本来是满足的（非负），候选不允许把它变成违例。

**与旧规则的区别：** 旧规则只用 hold slack（`worst_slack_min`）做单次门禁；新规则 setup/hold 分别门禁。这样既保留原来的 timing 安全性，又不会再漏守 setup。

## 3. 软目标（gate 通过之后）

WNS 只做硬门禁，不再进入软效用。设定：

$$
U = 0.5\cdot d_{\mathrm{HPWL}} + 0.4\cdot d_{|\mathrm{TNS}|} + 0.1\cdot d_{\mathrm{power}}
$$

其中各项为相对 baseline 的归一化改进。TNS 用 `setup_tns_ns` 的绝对值；WNS/TNS 的绝对变化在报告中单列（ns），不要把 signed WNS/TNS 的百分比变化当主要证据（负基数下百分比会误导）。

## 4. 旧字段到新字段的迁移

| 旧字段 | 旧含义 | 新字段 |
|---|---|---|
| `wns_min_ns` | 实际是 hold WNS（旧 `collect_runs.py` 命名错误） | `hold_wns_ns` |
| `wns_max_ns` | 实际是 setup WNS | `setup_wns_ns` |
| `wns_ns` / `wns_ps`（旧 phase0.py） | 实际是 hold WNS | `hold_wns_ns` |
| `wns_ns`（openlane_ingest，source=openlane1） | OpenLane metrics.csv 的 `wns`，按 setup 处理 | `setup_wns_ns` |
| `tns_ns` / `tns_ps` | setup TNS（旧 phase0.py 用 `DRT::tns_max`） | `setup_tns_ns` |

迁移工具：

```bash
cd /data/dzy/heura_repr/eda
python3 harness/migrate_legacy_metrics.py --runs-dir runs --in-place
python3 harness/migrate_legacy_metrics.py --candidates results/aes_candidates_full.json --out-dir results/canonical
python3 harness/migrate_legacy_metrics.py --audit results/canonical/aes_candidates_full.json
```

## 5. 四设计 baseline 的真实 setup/hold 值（本地已存数据）

| design | setup_wns_ns | hold_wns_ns | setup_tns_ns | 旧报告称 "WNS" |
|---|---|---|---|---|
| gcd | -0.6333 | +0.4842 | -15.58 | +0.484（实际 hold） |
| aes | -1.8613 | -0.1463 | -289.19 | -0.146（实际 hold） |
| jpeg | -1.0944 | +0.0402 | -129.90 | +0.040（实际 hold） |
| ibex | -5.2052 | -0.1259 | -299.05 | -0.126（实际 hold） |

可以看到 gcd/jpeg baseline 的 setup 本来就有违例，旧报告却因为拿 hold slack 当 WNS 而显示为"正 slack"；这会误导 selector 和结论。

## 6. 报告时必须写的五件事

1. 使用的是哪个 analysis（setup 还是 hold）；
2. 源键（`worst_slack_max` 或 `worst_slack_min`）；
3. 单位和符号约定；
4. timing gate 的 guardband 与基线是否非负；
5. signed WNS/TNS 不使用百分比作为主要证据。

## 7. 验证

每次修改工具版本或 PDK 后，用已知 golden 设计重跑并确认：

- `DRT::worst_slack_max` 与 `RSZ::worst_slack_max` 的 setup 值一致（容差内）；
- `DRT::worst_slack_min` 与 `RSZ::worst_slack_min` 的 hold 值一致（容差内）；
- `tns_max` 与 setup 违例数/报告一致；
- `harness/metrics_schema.py --audit` 无 `missing setup_wns_ns`。

## 8. 其他指标口径（v1）

| 规范字段 | 来源/定义 | 方向 | 备注 |
|---|---|---|---|
| `hpwl_route_um` | route DEF 的 pin 中心（含 `( PIN port )` 顶层端口）按 LEF + orientation 变换后计算 | 越小越好 | 规范 pin-offset HPWL；`hpwl_no_ports_um` 为去掉顶层端口、更接近 OpenROAD global placement 口径的对照 |
| `hpwl_no_ports_um` | 同上但忽略 `( PIN port )` 连接 | 越小越好 | 与 OpenLane `HPWL` 指标对照用；不要与 `hpwl_route_um` 混用 |
| `hpwl_origin_um` | 组件 origin（无 pin offset）bbox | 越小越好 | 仅旧结果回归对照，不再作为主指标 |
| `wirelength_um` | `drt::wire length::total` / `detailed_wirelength_um` | 越小越好 | 与 HPWL 不同，是详细布线总长 |
| `vias` | `drt::vias::total` | 通常越小越好 | 与 WL/DRC 有 tradeoff |
| `drc_violations` | 规范 DRC：signoff 可用时 = max(`klayout_violations`, `Magic_violations`)，否则 = detailed-route 总数 `tritonRoute_violations`（或子项之和） | 0 是 signoff 目标 | **不得**把 tritonRoute 总数与它的子项 Short/MetSpc/... 再加 Magic/KLayout 混加；详见 §9 |
| `drc_detailed_route` | detailed router 总违例数 | 0 | 与 signoff DRC 分开记录 |
| `drc_klayout` / `drc_magic` | KLayout/Magic signoff DRC 计数（-1/缺失记为 None） | 0 | canonical 取两者最大 |
| `lvs_errors` | OpenLane metrics.csv `lvs_total_errors` | 0 是 signoff 目标 | L1 gate 要求 0 |
| `total_power_w` | typical internal + switching + leakage；OpenSTA power report / 列值单位均为 W | 越小越好 | OpenLane 1 列名 `power_*_uW` 是历史误标，数值实际是 W；旧 ingest 除以 1e6 会差 6 个数量级（已修） |
| `logic_cell_count` / `total_cell_count` | `synth_cell_count`（逻辑单元）/ `TotalCells`（含 filler/decap/welltap） | 越大代表设计规模越大 | 规范 `instance_count` 取逻辑单元数；物理单元数单列 |
| `duration_s` | 实际 flow runtime | 预算项 | 不作为 PPA 目标 |
| `clock_skew_ns` | `DRT::clock_skew`（或 `RSZ::clock_skew`） | 越小越好 | CTS 阶段核心指标 |

另外：
- `gate_ok` = returncode 0 且 DRC 0 且 antenna 0（有 `l1_verdict` 时还要其为 true）；
- `l1_verdict` = overlap/row/boundary/net/fixed/netlist-hash 检查全通过；
- 报告中的百分比只对非时序、正基数指标使用；signed WNS/TNS 用 ns 绝对差。

## 9. 第二批口径勘误（2026-09-22）

本次审计又发现并修复了四类问题，均已落到 `harness/metric_rules.py`：

1. **Power 单位**：OpenLane 1 `metrics.csv` 列名 `power_*_uW`，但数值实际是 **W**（本地 OpenLane `eda-101/parse_reports.py` 注释也确认；spm 三列相加 = 1.139e-3 W，与 flow log 一致）。旧 `openlane_ingest.py` 按 µW 又除以 1e6，低估 10^6 倍。现在直接求和为 W。
2. **DRC 重复计数**：`tritonRoute_violations` 已是 detailed router 总数；`Short/MetSpc/OffGrid/MinHole/Other` 是它的子计数，Magic/KLayout 是另外的 signoff DRC。旧逻辑全部相加会重复计算。规范：
   - `drc_detailed_route` = tritonRoute 总数（缺失时子项之和）；
   - `drc_violations` = max(KLayout, Magic)（有 signoff DRC 时），否则 detailed route 总数；
   - 子项、Magic、KLayout 分列保存。
3. **实例数口径**：`TotalCells` 含 filler/decap/welltap；规范 `instance_count = synth_cell_count`（逻辑单元），另存 `total_cell_count`。Phase 0 OpenROAD run 的 `instance_count` 来源是 `IFP::instance_count`，也按逻辑单元理解。
4. **HPWL 三口径**：
   - `hpwl_um`：DEF pin 中心 + LEF pin offset + orientation，含顶层端口 `( PIN port )`（规范）；
   - `hpwl_no_ports_um`：同上但忽略顶层端口，用于与 OpenLane global-placement `HPWL` 指标对照；
   - `hpwl_origin_um`：仅组件 origin，用于旧结果回归，不再作主指标。
   OpenLane `metrics.csv` 的 `HPWL` 来自 global placement log，单位是 DEF DB（通常 1000 DB/µm），已 /1000 为 `hpwl_metric_csv_um` 并单列来源。
   另外修正了 DEF 解析器：支持换行/无 `+` 的 continuation 行、`( PIN portName )` 顶层端口，避免漏 pin。

**清理：** `phase0.py` 中无 pin offset 的旧 `def_metrics` 已删除；旧派生 JSON/数据集在 `results/legacy_wrong_metrics/`（由 `harness/cleanup_legacy.py` 迁移），只读 `results/canonical/` 与新报告。

服务器重算命令见 `docs/RUNBOOK.md` §2/§9：`python3 harness/recompute_metrics.py --runs-dir runs --in-place --lef ...`。
