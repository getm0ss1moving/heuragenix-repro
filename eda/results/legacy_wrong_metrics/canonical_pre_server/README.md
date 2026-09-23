# canonical results（WNS 口径修复后）

本目录是把旧候选/ sweep JSON 按 canonical setup/hold 口径迁移后的副本：

| 文件 | 来源 | 说明 |
|---|---|---|
| `phase0_sweep_0002.json` | `results/legacy_wrong_metrics/phase0_sweep_0002.json` | gcd sweep |
| `aes_candidates_full.json` | `results/legacy_wrong_metrics/aes_candidates_full.json` | aes |
| `jpeg_candidates_full.json` | `results/legacy_wrong_metrics/jpeg_candidates_full.json` | jpeg |
| `ibex_candidates.json` | `results/legacy_wrong_metrics/ibex_candidates.json` | ibex |

迁移规则：
- 旧 `wns_min_ns`（实际 hold）→ `hold_wns_ns`
- 旧 `wns_max_ns`（实际 setup）→ `setup_wns_ns`
- 旧 `tns_ns`（`DRT::tns_max`）→ `setup_tns_ns`
- `hold_tns_ns` 当前缺失（OpenROAD 未输出 `tns_min`）

不要直接修改旧文件；新报告/ selector/stats 只读本目录。口径见 `../../docs/METRIC_CONVENTIONS.md`，重算结论见 `../PHASE0_REPORT_0006_WNS_FIX.md`。
