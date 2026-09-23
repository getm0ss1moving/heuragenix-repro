# legacy_wrong_metrics

这些文件产生于 2026-09-22 指标口径审计之前，包含错误的口径：
- WNS 字段把 `DRT::worst_slack_min`（hold）当成 WNS；
- OpenLane power 单位曾按 µW 误换算；
- DRC 曾把 detailed-route 总数与子计数、Magic/KLayout 混加；
- HPWL 解析曾漏 `( PIN port )`/换行 pin。

**禁止用于报告、训练、selector 或论文。** 新口径与重算产物见 `../canonical/`、`../PHASE0_REPORT_0006_WNS_FIX.md`、`docs/METRIC_CONVENTIONS.md`。
