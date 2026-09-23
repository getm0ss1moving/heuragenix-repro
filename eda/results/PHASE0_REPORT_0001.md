# Phase 0 首轮报告：gcd baseline + placement 参数 sweep

- 服务器：202.121.181.105 端口 224（thinklab-105-224），避开训练端口 225
- 工具：OpenROAD 2022 二进制（复制自 /data/lvxianglong/eda/openroad）+ tcl-tclreadline 2.3.8
- 数据：OpenROAD 自带 sky130hd 测试库 + 预综合 gcd 网表
- sweep：phase0_sweep_0001，每条 flow 16 线程，单次约 11–17 s

## Gate（全部通过）

| variant | returncode 0 | DRC 0 | antenna 0 | gate_ok |
|---|---|---|---|---|
| base | yes | yes | yes | True |
| density_025 | yes | yes | yes | True |
| density_035 | yes | yes | yes | True |
| density_040 | yes | yes | yes | True |
| pad_2 | yes | yes | yes | True |
| pad_6 | yes | yes | yes | True |
| grt_50 | yes | yes | yes | True |
| grt_200 | yes | yes | yes | True |

## 指标与基线相对变化（负的 HPWL/WL/TNS 变化为改善；TNS 基数负值）

| variant | HPWL_um | ΔHPWL | WL_um | ΔWL | vias | Δvias | WNS_min | TNS | ΔTNS | power_W | sec |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 7466.38 | +0.0% | 15450.0 | +0.0% | 1886.0 | +0.0% | 0.4841882587472532 | -15.580383646458793 | -0.0% | 0.000967 | 14.18 |
| density_025 | 8195.38 | +9.8% | 16019.0 | +3.7% | 1930.0 | +2.3% | 0.4927729475056563 | -10.63110518597402 | -31.8% | 0.000993 | 12.26 |
| density_035 | 6796.3 | -9.0% | 14916.0 | -3.5% | 1899.0 | +0.7% | 0.48795779908937287 | -14.663922047242433 | -5.9% | 0.000942 | 15.01 |
| density_040 | 6398.2 | -14.3% | 14601.0 | -5.5% | 1918.0 | +1.7% | 0.4940435977932762 | -14.916919677249275 | -4.3% | 0.000966 | 16.87 |
| pad_2 | 6304.42 | -15.6% | 14521.0 | -6.0% | 1877.0 | -0.5% | 0.4988633536352422 | -14.873407815237567 | -4.5% | 0.000963 | 15.65 |
| pad_6 | 7598.88 | +1.8% | 15385.0 | -0.4% | 1902.0 | +0.8% | 0.503403888378618 | -13.44633420445135 | -13.7% | 0.000946 | 11.05 |
| grt_50 | 7466.38 | +0.0% | 15450.0 | +0.0% | 1886.0 | +0.0% | 0.4841882587472532 | -15.580383646458793 | -0.0% | 0.000967 | 13.94 |
| grt_200 | 7466.38 | +0.0% | 15450.0 | +0.0% | 1886.0 | +0.0% | 0.4841882587472532 | -15.580383646458793 | -0.0% | 0.000967 | 14.05 |

## 重复性与结论

- baseline 在 5 条不同 run 中指标完全一致；`density=0.40` 与 `pad=2` 各重复 3 次，指标逐位一致。
- 候选 skill 1：`place.gp.density_weight`（0.40）：HPWL 与 WL 明显下降，TNS 改善，DRC/antenna 仍为 0。
- 候选 skill 2：`place.gp.pad`（2）：HPWL/WL/vias 下降，WNS/TNS 改善，是当前最强单参数 skill。
- 值得注意的 tradeoff：`density=0.25` 的 HPWL/WL 变差，但 TNS 明显改善，适合作为质量-多样性档案中的 route/timing 取向候选。
- null 结果：`route.grt.congestion_iters` 50/200 与 baseline 完全一致，因为 gcd 没有拥塞；需要换 aes/jpeg 等设计再测。
- 当前不声明统计提升：只有单设计 gcd、单次配对；下一步要跑 aes/jpeg、加 state card/selector、做分层 bootstrap。

## 重跑命令

```bash
cd /data/dzy/heura_repr/eda
python3 harness/phase0.py run --run-id gcd_baseline_x --threads 16
python3 harness/sweep.py --sweep-id phase0_sweep_0002 --threads 16
python3 harness/phase0.py state --run-id phase0_sweep_0001_base
```
