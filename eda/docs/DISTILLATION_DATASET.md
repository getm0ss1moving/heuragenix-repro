# HA-PR selector 蒸馏：数据集与训练计划

## 目的
把 dsv4-flash API selector 的“状态→skill 选择”判断，蒸馏到本地 Qwen2.5-7B（LoRA + GRPO），换取：
- 在线选择零 API 成本、毫秒级延迟；
- 可版本冻结、可复现、可在无外网节点运行；
- 支撑大规模 skill 演化/多保真评估的候选排序。

定位：工程放大器，不是项目主贡献；上限仍由 skill 库、演化机制和 verifier 决定。

## 数据导出
```bash
cd /data/dzy/heura_repr/eda
python3 harness/build_selector_dataset.py \
  --config config/dataset_runs.json \
  --runs-dir /data/dzy/heura_repr/eda/runs \
  --out-jsonl results/selector_dataset_v0.jsonl \
  --out-sft results/selector_sft_v0.jsonl \
  --out-summary results/selector_dataset_v0_summary.json
```

### JSONL schema（每条 = 一个设计级决策点）
```json
{
  "design": "jpeg",
  "decision_point": "flow_start",
  "state": {
    "design": "jpeg", "family": "jpeg",
    "base_metrics": {"instance_count": 96000, "hpwl_route_um": 1875375.4, "setup_wns_ns": -1.0944, "hold_wns_ns": 0.0402, "setup_tns_ns": -129.9, "power_w": 0.159, "...": "..."},
    "base_gate_ok": true,
    "stage_metrics": {"def_global_place": {"hpwl_um": 123.4, "utilization_pct_of_die": 0.2, "...": "..."}}
  },
  "candidates": [
    {"skill_id": "density_040", "overrides": {"global_place_density": 0.4},
     "gate_ok": true, "cost_s": 333.1,
     "delta": {"hpwl_route_um": -219517, "setup_tns_ns": 64.87, "setup_wns_ns": 0.32, "hold_wns_ns": -0.22, "...": "..."},
     "utility": -1.18}
  ],
  "oracle_skill": "density_040",
  "utility_spec": "timing_gate_first (setup/hold WNS >= base-0.02ns; baseline nonnegative must stay nonnegative); then U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power"
}
```

### SFT schema
`results/selector_sft_v0.jsonl` 为 chat 格式：system=selector 角色，user=state + 候选卡 + utility 规则，assistant=`{"skill_id": oracle}`。可直接用于 Qwen LoRA SFT 冷启动，再用 GRPO 做偏好优化。

> **v3 数据集已废弃（WNS 字段错误）**：请勿用 `selector_dataset_v3.*` 训练/评估；在服务器按新 harness 重建 `selector_dataset_v4.*`。旧 v3 仅作历史记录。

## 当前样本量
- v3：4 个设计（gcd/aes/jpeg/ibex），16 个候选记录，4 条 SFT，4 条 POR 偏好。
- **WNS 口径勘误（2026-09-22）**：旧规则中的 "WNS" 实际是 hold slack（`DRT::worst_slack_min`）。canonical 口径：setup WNS 用 `DRT::worst_slack_max`，hold WNS 用 `DRT::worst_slack_min`，二者分别过 gate（`>= base - 0.02 ns`；baseline 非负则候选不得转负）；WNS 只做 gate，软效用改为 `U = 0.5*d_HPWL + 0.4*d_abs_TNS + 0.1*d_power`。详见 `docs/METRIC_CONVENTIONS.md`。
- 样本量远不足以训练 Qwen：目标仍是 200–1000 条 state-candidate 记录，覆盖 ≥5 设计族、每设计多 checkpoint、多 skill 候选。

## 扩展方法
1. 跑更多设计/候选（phase0.py run 或 sweep.py），记入 `runs/`；
2. 把 run_id 写进 `config/dataset_runs.json`；
3. 重跑 `build_selector_dataset.py`；
4. 后续增加 `decision_point`：从各 stage checkpoint 继续 flow（需要 checkpoint 续跑 runner），把起点从 `flow_start` 扩展到 `post_global_place / post_cts / post_grt`。

## Qwen GRPO 训练计划（待 GPU 空闲）
- 基座：`/data/dzy/heura_repr/models/Qwen2.5-7B-Instruct-1M`（已下载）。
- 方法：LoRA + TRL GRPO；参考 HeurAgenix `train_dual_full.py`。
- 奖励：
  - CA-POR：按候选 utility（或 LCB）排名分正/负集，正集内线性、负集负奖励、错误区固定惩罚；
  - EDA-CPR：预测状态卡字段（stage/legality/density/拥塞/时序/gate/预算）；
  - gate/cost：预测 gate 风险、成本校准。
- 评估：留出设计族；对比 API selector / rule / random / local；
  - selector regret、top-1 命中率；
  - 最终 PPA、token/时间成本；
  - 低置信度 fallback（回到 API 或 rule）。
- 前置条件：更多数据 + 空闲 GPU（225/231 当前被训练/评测占用；224 GPU 不可用，只能 CPU）。

## 风险
- 4 个设计训练出的 selector 会退化成规则（jpeg→density040，其余→pad2）；必须扩设计族。
- 只用最终 flow 结果做标签，无法区分阶段信用；需要 checkpoint 续跑与反事实 replay。
- API 大模型版本漂移；本地权重需记录 commit/日期，配合固定 eval set 回归。
