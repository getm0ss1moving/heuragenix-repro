> **WNS 口径勘误（2026-09-22）**：本报告中的 "WNS" 字段实际为 `DRT::worst_slack_min`（hold slack），不是 setup WNS；setup WNS 应使用 `DRT::worst_slack_max`。请以 `docs/METRIC_CONVENTIONS.md` 和 `results/PHASE0_REPORT_0006_WNS_FIX.md` 为准。本报告的 timing gate / regret / 效用数值需按 canonical 口径重算。

# Phase 0 报告 v4：jpeg + 三设计 selector（LLM vs oracle）

日期：2026-09-22 ｜ 节点：224（本项目工作端口）｜ gcd/aes/jpeg 三个设计、OpenLane spm 接入、pin-offset HPWL

## 0. 结论

- jpeg（96k insts）baseline 305 s 跑通：HPWL 1,875,375 µm、WNS 0.040 ns、TNS −129.90 ns、power 0.159 W、DRC/ant=0。
- jpeg 候选：pad_2 HPWL −12.4%、TNS −38.1%（更好）、WNS −0.178（变差）；density_040 HPWL −11.7%、TNS −50.0%（更好）、WNS −0.041（仍差于 baseline）；layeradj HPWL 不变、TNS/WNS 轻微改善；grt_200 null。
- 三设计配对（gcd+aes+jpeg，n=3）：density_040 HPWL −12.7% CI[−219517,−998.6]、TNS +37.66 CI[0.66,64.87]、WNS 中性；pad_2 HPWL −14.3% CI[−231967,−1190.2]、TNS +41.48 CI[0.71,74.22]、WNS −0.039（略差）。
- selector v0：LLM（dsv4-flash；key 优先本地 `DEEPSEEK_LAB_API_KEY`（解析需 rstrip 逗号），231 B档配置为备用）在三个设计上均与 oracle 一致（gcd/aes 选 pad_2，jpeg 选 density_040），regret=0；rule 固定 pad_2 在 jpeg 上不优，random regret 0.11–0.20。

## 1. jpeg 候选明细

| variant | gate | HPWL_um | ΔHPWL | WL_um | vias | WNS_ns | TNS_ns | ΔTNS | power_W | sec |
|---|---|---|---|---|---|---|---|---|---|---|
| base | True | 1875375 | +0.0% | 2222810 | 315106 | 0.0402 | -129.900 | -0.0% | 0.159 | 305.1 |
| layeradj | True | 1875375 | +0.0% | 2223443 | 312764 | 0.0446 | -128.620 | -1.0% | 0.159 | 308.2 |
| pad_2 | True | 1643408 | -12.4% | 1975417 | 313596 | -0.1783 | -80.389 | -38.1% | 0.152 | 328.1 |
| density_040 | True | 1655858 | -11.7% | 1982833 | 313207 | -0.0415 | -65.027 | -49.9% | 0.152 | 333.1 |

## 2. 三设计配对统计（bootstrap 95% CI，n=3）

| candidate | n | ΔHPWL | ΔHPWL CI | ΔTNS_ns | ΔTNS CI | ΔWNS_ns | Δpower | Δruntime |
|---|---|---|---|---|---|---|---|---|
| density_040 | 3 | -12.7% | [-219517.0, -998.6] | +37.66 | [0.66, 64.87] | -0.000 | -3.5% | +22.4% |
| pad_2 | 3 | -14.3% | [-231967.0, -1190.2] | +41.48 | [0.71, 74.22] | -0.039 | -3.5% | +20.9% |
| layeradj | 1 | +0.0% | [0.0, 0.0] | +1.28 | [1.28, 1.28] | +0.004 | +0.0% | +1.0% |
| grt_200 | 2 | +0.0% | [0.0, 0.0] | +0.00 | [0.00, 0.00] | +0.000 | +0.0% | +8.3% |
| density_040_pad_2 | 1 | -11.1% | [-114247.6, -114247.6] | +90.14 | [90.14, 90.14] | -0.035 | -3.8% | +51.1% |

## 3. selector v0（三设计）

| design | candidates | oracle | rule(固定pad2) | rule regret | dsv4-flash LLM | LLM regret | random mean regret |
|---|---|---|---|---|---|---|---|
| aes | 5 | pad_2 | pad_2 | 0.0 | pad_2 | 0.0 | 0.1245 |
| gcd | 8 | pad_2 | pad_2 | 0.0 | pad_2 | 0.0 | 0.1126 |
| jpeg | 4 | density_040 | pad_2 | 0.0524943958959363 | density_040 | 0.0 | 0.1975 |

## 4. 判断与下一步

- `density_040` 是当前最稳的通用 skill（HPWL/TNS/power 改善，WNS 基本中性）；`pad_2` 在 HPWL/TNS 上更强但对 jpeg 的 WNS 有负作用，LLM selector 能按设计状态避开。
- `layeradj` 在 jpeg 上只带来轻微 timing 改善，且 HPWL 不变；`grt_iters` 在三个设计上均 null。
- 下一步：更多设计族（尤其是拥塞型）验证 selector 泛化；distilled local selector；把 DRC/LVS/STA 报告接入 verifier。

