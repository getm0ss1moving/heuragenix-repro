# PHASE0_REPORT_0009：checkpoint 状态卡数据集 v1

**日期：** 2026-09-22  
**执行：** 服务器 224，`harness/checkpoint_states.py`  
**产物：** `results/canonical_server/checkpoint_states_v1.jsonl` + `.summary.json`（本地已回拉）

---

## 1. 目的

Phase 0 的候选结果目前都来自 `flow_start`（整条 flow 从头跑某个 override）。为了向 Phase 1 的“多决策点选择”推进，本步骤从已有 run 的 DEF 快照中抽取三个阶段的**无标签状态卡**：

```text
flow_start
  └─ post_global_place
        └─ post_cts
              └─ post_route
```

每条状态卡包含：design、run_id、variant/overrides、stage、DEF 路径、HPWL（含/不含端口/origin）、components/nets、pin hits/misses、setup/hold WNS、setup TNS、post_route 的 power/DRC/antenna。

## 2. 规模

| design | post_global_place | post_cts | post_route |
|---|---|---|---|
| gcd | 11 | 11 | 11 |
| aes | 5 | 5 | 5 |
| jpeg | 4 | 4 | 4 |
| ibex | 3 | 3 | 3 |
| **合计** | **23** | **23** | **23** |

总计 69 条状态卡；所有记录带 `timing_convention=setup_hold_v1` 与 `metric_convention_version=metrics_v2`。

## 3. 预处理示例（aes_baseline）

| stage | hpwl_um | hpwl_no_ports_um | setup_wns_ns | hold_wns_ns | setup_tns_ns |
|---|---|---|---|---|---|
| post_global_place | 1,099,711.105 | 851,902.811 | −1.2415 | +0.0022 | −209.47 |
| post_cts | 1,201,644.961 | 951,806.437 | −1.2415 | +0.0022 | −209.47 |
| post_route | 1,227,554.093 | 待核对 | −1.8613 | −0.1463 | −289.19 |

说明：pre-route 阶段使用 `RSZ::worst_slack_max/min`，post_route 使用 `DRT::...`；两套源键在记录中由 `stage` 区分。

## 4. 当前限制

1. **无动作标签**：这些只是状态卡，不是 `(state, skill, Q)` 监督数据；不能直接训练 selector。
2. **时序阶段口径**：post_global_place/post_cts 用的是 RSZ（resizer/工具有限）估计，不等于 signoff STA；不能当最终 PPA。
3. **power/DRC 只在 post_route 填**；pre-route 留 None。
4. 要得到标签，需要 **checkpoint replay**：从同一阶段 DEF 恢复 flow，应用不同 skill，跑完剩余阶段并记录最终效用。

## 5. 下一步

1. 在 224 上实现 `post_global_place` 和 `post_cts` 的 checkpoint replay（OpenROAD 从 DEF 继续跑后续阶段），生成 `(state, action, delta)` 数据。
2. 将 `checkpoint_states_v1` 扩展为 design/stage 均衡的 200–1000 条。
3. 把中段时序估计替换/补充为 signoff STA（L3），避免用 pre-route RSZ 估计做最终标签。
4. 与 Phase 1 的 seed library 对接：每个 checkpoint 状态簇至少有一个可重放 skill。
