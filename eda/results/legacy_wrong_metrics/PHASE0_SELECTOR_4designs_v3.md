> **WNS 口径勘误（2026-09-22）**：本报告中的 "WNS" 字段实际为 `DRT::worst_slack_min`（hold slack），不是 setup WNS；setup WNS 应使用 `DRT::worst_slack_max`。请以 `docs/METRIC_CONVENTIONS.md` 和 `results/PHASE0_REPORT_0006_WNS_FIX.md` 为准。本报告的 timing gate / regret / 效用数值需按 canonical 口径重算。

# Phase 0 selector v0

| design | candidates | oracle | rule | rule regret | dsv4-flash | llm regret | random mean regret |
|---|---|---|---|---|---|---|---|
| aes | base,density_040,pad_2,grt_200,density_040_pad_2 | pad_2 | pad_2 | 0.0 | pad_2 | 0.0 | 0.14668172319472383 |
| gcd | base,density_025,density_035,density_040,pad_2,pad_6,grt_50,grt_200 | pad_2 | pad_2 | 0.0 | pad_2 | 0.0 | 0.045297287424932484 |
| ibex | base,density_040,pad_2 | pad_2 | pad_2 | 0.0 | pad_2 | 0.0 | 0.09831253897621639 |
| jpeg | base,layeradj,pad_2,density_040 | layeradj | pad_2 | 0.7264042399461953 | layeradj | 0.0 | 0.22330521902285577 |
