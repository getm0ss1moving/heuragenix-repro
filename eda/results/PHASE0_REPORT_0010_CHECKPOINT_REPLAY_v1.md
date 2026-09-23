# PHASE0_REPORT_0010：checkpoint replay v1（原型）

**日期：** 2026-09-22  
**执行：** 服务器 224，`harness/checkpoint_replay.py`  
**产物：** `results/canonical_server/checkpoint_replay_v1.jsonl`（5 条），运行日志 `logs/replay_gcd_*.log`

---

## 1. 机制

1. 从 checkpoint DEF 恢复设计：`read_libraries` → `read_def <checkpoint.def>` → `read_sdc`。
   - 关键点：**不能先 `link_design`**，否则 `read_def` 报 "Chip already exists"。
2. 按 stage 拼接 `flow_param.tcl` 的剩余部分：
   - `post_global_place`：从 `repair_design` 开始，续跑 CTS / timing repair / global route / detailed route / extraction；
   - `post_cts`：从 `# Setup/hold timing repair` 开始，续跑 timing repair / route / extraction。
3. 在 global route 前重新注入 routing setup 与动作：
   - `global_routing_layer_adjustments`（layer adjustment）；
   - `global_route_congestion_iterations`；
   - 可选 `slew_margin/cap_margin`。
4. 运行后解析 `metrics_raw.json` + route DEF，产出 canonical 指标并写入 JSONL。

## 2. 原型结果（gcd, post_global_place / post_cts）

| replay run | stage | action | setup WNS (ns) | hold WNS (ns) | setup TNS (ns) | vias | WL (µm) | DRC | vs replay baseline |
|---|---|---|---|---|---|---|---|---|---|
| replay_gcd_pgp_base | post_global_place | 无 | −0.6416 | +0.4803 | −17.019 | 1920 | 15554 | 0 | control |
| replay_gcd_pgp_grt200 | post_global_place | congestion=200 | −0.6416 | +0.4803 | −17.019 | 1920 | 15554 | 0 | 无变化（gcd 无拥塞） |
| replay_gcd_pgp_layeradj | post_global_place | layeradj | −0.6459 | +0.4869 | −16.244 | 1918 | 15539 | 0 | ΔTNS **+0.776**、ΔWL **−15**、Δsetup −0.004（guard 内） |
| replay_gcd_pcts_base | post_cts | 无 | −0.6407 | +0.4803 | −16.709 | 1915 | 15541 | 0 | control |
| replay_gcd_pcts_layeradj | post_cts | layeradj | −0.6489 | +0.4868 | −15.677 | 1910 | 15479 | 0 | ΔTNS **+1.032**、ΔWL **−62**、Δsetup −0.008（guard 内） |

**结论：**
- replay 机制可用，能生成 `(state, action, Δmetric)` 标签；
- layer adjustment 在 gcd 上是 timing-safe 的轻微线长/TNS 改善；grt 200 对 gcd 无影响（符合“gcd 无拥塞”预期）；
- 动作之间对比必须用 **同 stage 的 replay baseline**：replay 恢复与原始 full flow 有少量状态差异（见 §3）。

## 3. 已知差异与限制

1. **replay baseline 与原始 full flow 不完全相同**：原 `phase0_sweep_0002_base` final setup WNS/ TNS 为 −0.6333 / −15.58，replay baseline 为 −0.6416 / −17.019；差异来自 DEF 重建后的 resizer/CTS 状态与工具内部状态不能 100% 复原。不影响“同 replay baseline 下的动作相对效应”，但不能直接用 replay 数值替代原 full-flow 数值。
2. 目前只覆盖 gcd 一个设计、post-GP/post-CTS 两个 stage、两个动作（grt200/layeradj）。
3. replay 动作目录仍有限；需要扩展到 aes/jpeg/ibex 和更多下游 skill（timing repair、route ordering、antenna 等）。
4. 当前产出是原型标签集，不是最终训练集；需要批量 replay + 质量过滤后才进入 selector 训练。

## 4. 下一步

1. 把 `checkpoint_replay.py` 批量跑在 4 设计 × {post_global_place, post_cts} × 动作目录上，目标 200–1000 条标签。
2. 对每个 (design, stage) 建立 replay baseline；动作效用用 replay-control 配对差。
3. 把 replay 标签接入 `build_selector_dataset` 的 checkpoint 版本（state 来自 `checkpoint_states_v1`，action 来自 replay）。
4. 校准 replay baseline 与 full-flow baseline，必要时增加更多 DEF/ODB 快照或保存 checkpoint ODB。
