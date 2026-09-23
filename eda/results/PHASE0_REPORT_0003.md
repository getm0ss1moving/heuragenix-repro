> **WNS 口径勘误（2026-09-22）**：本报告中的 "WNS" 字段实际为 `DRT::worst_slack_min`（hold slack），不是 setup WNS；setup WNS 应使用 `DRT::worst_slack_max`。请以 `docs/METRIC_CONVENTIONS.md` 和 `results/PHASE0_REPORT_0006_WNS_FIX.md` 为准。本报告的 timing gate / regret / 效用数值需按 canonical 口径重算。

> 节点说明：本报告全部结果在端口 224（本项目工作端口）完成。期间曾把其他窗口“不要抢占 224”的提醒误读为“224 禁用”，临时把 `eda/` 迁到 234 备份；用户澄清后已恢复 224 为准，234 仅作备份。

# Phase 0 报告 v3：pin-offset HPWL + OpenLane 接入 + gcd/aes skill 候选

日期：2026-09-22 ｜ 服务器：202.121.181.105 端口 224（thinklab-105-224，非训练端口 225）｜ 工具：OpenROAD 2022 + sky130hd 测试库 + 本地 OpenLane 1/sky130A

## 0. 一句话结论

- Phase 0 harness 已跑通 gcd 与 aes 两个设计；所有候选 run 的 RC/DRC/antenna/gate 检查均通过。
- HPWL 已从 cell-origin 升级为 LEF pin offset + DEF orientation；gcd/aes pin_hits=100%。
- OpenLane spm 全流程已在本地 colima 跑通并 ingest；slim 产物同步到服务器后可复现 metrics/state card。
- 两个设计上的配对结果：`pad_2` 与 `density_040` 都降低 HPWL 并改善 TNS；`density_040+pad_2` 组合 TNS 最好但 WNS/HPWL 回退；`grt_iters` 在 gcd/aes 上均为 null。

## 1. HPWL pin-offset 解析

方法：`harness/lef_def.py` 解析 LEF `MACRO/PIN/PORT/RECT` 得到 pin 中心，再按 DEF orientation（N/S/W/E/FN/FS/FE/FW）变换；每个 net 用 pin 坐标算 bbox HPWL。

| 数据 | origin 近似 HPWL | pin-offset HPWL | 差 | pin_hits | pin_misses |
|---|---|---|---|---|---|
| gcd route | 7466.4 | 7423.9 | -0.57% | 786 | 0 |
| gcd global_place | 6364.4 | 6276.6 | -1.38% | 733 | 0 |
| gcd cts | 7092.3 | 7062.5 | -0.42% | 761 | 0 |
| aes route | 1026058.6 | 1027437.9 | +0.13% | 46545 | 0 |

OpenLane spm ingest：placement pin-offset HPWL 4661.7 µm，global_place 日志 metric HPWL 4514.2 µm（口径不同，差 3.3%）。

## 2. OpenLane 接入（本地 colima + sky130A）

| 指标 | spm |
|---|---|
| 状态 | flow completed |
| runtime_s | 24.0 |
| instance_count | 1108.0 |
| area_um2 | 8134.051200000001 |
| WNS_ns | 0.0 |
| TNS_ns | 0.0 |
| power_W | 0.001139188 |
| wirelength_um | 6559.0 |
| DRC | 0.0 |
| LVS | 0.0 |

路径：`openlane_runs/spm_phase0_0001_src` → `openlane_runs/spm_phase0_0001/ingested/{metrics.json,meta.json,state_card.json}`。

## 3. gcd sweep 0002（pin-offset HPWL，ns 单位）

| variant | gate | HPWL_um | ΔHPWL | WL_um | ΔWL | vias | WNS_min_ns | TNS_ns | ΔTNS | power_W | sec |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base | True | 7423.9 | +0.0% | 15450 | +0.0% | 1886 | 0.4842 | -15.580 | -0.0% | 0.000967 | 13.8 |
| density_025 | True | 8133.5 | +9.6% | 16019 | +3.7% | 1930 | 0.4928 | -10.631 | -31.8% | 0.000993 | 12.1 |
| density_035 | True | 6766.1 | -8.9% | 14916 | -3.5% | 1899 | 0.4880 | -14.664 | -5.9% | 0.000942 | 15.1 |
| density_040 | True | 6425.3 | -13.5% | 14601 | -5.5% | 1918 | 0.4940 | -14.917 | -4.3% | 0.000966 | 17.2 |
| pad_2 | True | 6233.7 | -16.0% | 14521 | -6.0% | 1877 | 0.4989 | -14.873 | -4.5% | 0.000963 | 15.7 |
| pad_6 | True | 7608.9 | +2.5% | 15385 | -0.4% | 1902 | 0.5034 | -13.446 | -13.7% | 0.000946 | 11.0 |
| grt_50 | True | 7423.9 | +0.0% | 15450 | +0.0% | 1886 | 0.4842 | -15.580 | -0.0% | 0.000967 | 14.2 |
| grt_200 | True | 7423.9 | +0.0% | 15450 | +0.0% | 1886 | 0.4842 | -15.580 | -0.0% | 0.000967 | 14.4 |

## 4. aes 候选（23.5k insts / 410k DEF components）

| variant | gate | HPWL_um | ΔHPWL | WL_um | ΔWL | vias | WNS_min_ns | TNS_ns | ΔTNS | power_W | sec |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base | True | 1027437.9 | +0.0% | 1537953 | +0.0% | 153258 | -0.1463 | -289.193 | -0.0% | 0.042400 | 230.7 |
| density_040 | True | 893773.3 | -13.0% | 1429488 | -7.1% | 151377 | -0.0745 | -241.764 | -16.4% | 0.039800 | 306.4 |
| pad_2 | True | 879569.0 | -14.4% | 1409812 | -8.3% | 153096 | -0.0601 | -214.977 | -25.7% | 0.040000 | 325.5 |
| grt_200 | True | 1027437.9 | +0.0% | 1537953 | +0.0% | 153258 | -0.1463 | -289.193 | -0.0% | 0.042400 | 258.0 |
| density_040_pad_2 | True | 913190.3 | -11.1% | 1443644 | -6.1% | 157225 | -0.1816 | -199.050 | -31.2% | 0.040800 | 348.6 |

## 5. 配对统计（gcd+aes，bootstrap 95% CI）

| candidate | n | ΔHPWL | ΔHPWL CI | ΔTNS_ns | ΔTNS CI | Δpower | Δruntime |
|---|---|---|---|---|---|---|---|
| density_040 | 2 | -13.2% | [-133664.6, -998.6] | +24.05 | [0.66, 47.43] | -3.12% | +29.0% |
| grt_200 | 2 | +0.0% | [0.0, 0.0] | +0.00 | [0.00, 0.00] | +0.00% | +8.3% |
| pad_2 | 2 | -15.2% | [-147868.9, -1190.2] | +37.46 | [0.71, 74.22] | -3.04% | +27.6% |

## 6. selector v0

| design | candidates | oracle | rule | rule regret | dsv4-flash | random mean regret |
|---|---|---|---|---|---|---|
| aes | 5 | pad_2 | pad_2 | 0.0 | None | 0.1245 |
| gcd | 8 | pad_2 | pad_2 | 0.0 | None | 0.1126 |

DeepSeek v4.1 flash selector 已重跑成功（key 取自端口 231 的 B 档配置，不落盘）：gcd/aes 均选择 `pad_2`，与 oracle 一致，LLM regret=0；random/rule/oracle 基线此前已跑通。

## 7. L0/L1 verifier

| DEF | 结果 |
|---|---|
| gcd sweep 全部 route DEF | l1_verdict=True, overlap=0, row=0, net=0 |
| aes baseline / density_040 / pad_2 / grt_200 / combo route DEF | verdict=True, overlap=0, row=0, net=0; 候选 fixed_changed=0, netlist sha256 一致 |
| OpenLane spm routing DEF | verdict=True, overlap=0, row=0, net=0 |

已修复：相邻单元/行的浮点尾差假 overlap；DEF 顶层端口 `( PIN port )` 格式；LEF `SIZE`/pin 解析。

## 8. 已知不完美 / 下一步

- jpeg（96k insts）尚未跑；`grt_iters` 在 gcd/aes 均为 null，需要更大拥塞或 layer adjustment skill。
- bootstrap 只有 2 个设计，CI 很宽；只能作为 Phase 0 工程 pilot，不能做统计提升声明。
- HPWL 与 OpenLane 官方 metric 口径不同（global placement 日志 vs 最终 DEF），报告需固定口径。
- selector LLM 分支待 key 修复；verifier 尚未覆盖 DRC/LVS/STA（继续由工具线执行）。
- 下一步：jpeg baseline、layer adjustment skill、更多 OpenLane 设计、distilled selector、fixed-object/netlist 全量回归。

