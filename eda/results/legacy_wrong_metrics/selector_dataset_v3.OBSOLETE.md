# selector_dataset_v3 已废弃（WNS 口径错误）

`selector_dataset_v3.*`、`selector_sft_v3.*`、`selector_preferences_v3.*` 基于旧 harness 的错误 timing 字段：

- 旧字段 `wns_min_ns` / `wns_ns` 实际是 `DRT::worst_slack_min`（hold slack），被当作 WNS 使用；
- 真正 setup WNS 是 `DRT::worst_slack_max`；
- timing gate / utility / reward gate 因此都是 setup/hold 混用。

**请勿用于训练、评估或论文数字。** 在服务器 224 同步新 harness 后，按 `docs/RUNBOOK.md` §6 重建 `selector_dataset_v4.*`。  
口径说明见 `docs/METRIC_CONVENTIONS.md`，本地重算见 `results/PHASE0_REPORT_0006_WNS_FIX.md`。
