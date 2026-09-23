# TTS stop 口径与 k10 异常诊断 v1（2026-09-22）

## 0. 一句话结论
231 上 dual kroB200 k=10 的异常 gap 36.24% **不是并行 TTS bug，而是 stop 口径问题**：我们旧实现的 completion 口径在解已完整时跳过随机 rollout，导致 TTS 分数退化为当前值、候选全部并列、选择器锁死在局部最优。released 代码是固定 2N 步；论文正文 §3.3 是 until-completion；附录 D 又写 improvement-stop，三处不一致。

## 1. TTS stop 口径定义
| 口径 | 中间状态 M 步后 | 与论文/代码对应 |
|---|---|---|
| completion（本复现旧默认） | 仅当解未完成才随机补全；解已完整则 0 步 | 接近正文 §3.3 "until completion" 的字面 |
| fixed2n | 无论是否完整，跑满 2N+1 步随机启发式 | released `RandomHyperHeuristic` 的实际行为 |
| improvement | 先补全，再跑直到连续 W 步无改进（W=20） | 附录 D Algorithm 3 的 improvement-stop |

## 2. 单 rollout 耗时/收益基准（225，CPU 单线程，完整解由 NN 构造）
| 实例 | 初始 value | completion | fixed2n | improvement(W=20) |
|---|---|---|---|---|
| kroA100 | 22239 | 0.00s，22239 | 4.65s，21549–21689 | 0.65s，21700–22239 |
| kroB200 | 32162 | 0.00s，32162 | **109.4s**，31247–31583 | **54.7s**，31298–31655 |

- completion 在完整解上 **完全没有 rollout 改进机会**；
- fixed2n/improvement 在完整解上会大量随机选中 `_3opt_e75b` / SA 等 O(n²–n³) 启发式，kroB200 单 rollout 达到分钟级，是 k≥200 时 TTS 在 2h 内不可行的直接原因。

## 3. k10 kroB200 复核
| 运行 | 口径 | value | gap | 轮数 | 状态 |
|---|---|---|---|---|---|
| k=0 dual | 无 TTS | 32492 | 10.38 | 56 | 完整 |
| k=10 dual 原始 | completion(旧) | 40104 | 36.24 | 54 | 完整但锁死局部最优 |
| k=10 dual 重跑 fixed2n | fixed2n | — | — | — | 已终止：推算 30×109s/10 workers≈5.5min/轮 ×80 轮≈7h > 2h |
| k=10 dual 重跑 improvement | improvement | 运行中 | — | — | 推算约 3.6h，仍会触 2h 熔断，作部分对照 |

## 4. 对早期 k10 结果的影响
- 231 已完成的 9 个 k10（dual 全部 + vanilla kroA150）都是 **completion 口径**，不是 paper/released 口径；不能直接当作论文 k=10 复现。
- 之前观察到的 pr152 3.96、kroA150 5.87、kroC100 4.71、bier127 9.03 等提升，只在该口径下成立（解完整后不再探索）。
- 修正后应重新跑或至少重标为 `stop=completion` 基线；最终报告需明确口径。

## 5. 对“论文 2h”的重新认识
- 论文 2h 是熔断上限，不是协议时长；
- released CLI 默认 `-b 0`（即不做 TTS），主表很可能根本没用 k=10；
- 若用 fixed2n k=10，n≥200 单轮 TTS 就分钟级，任何机器都难在 2h 内完成；因此“k=10 不可行”的结论要从“论文不可能”改为“released 口径 + 本机配置下不可行，且主表未必用 k=10”。

## 6. 待办
- [ ] 等 improvement 重跑出结果，作为第三种口径对照；
- [ ] 锁定最终复现口径（建议：主表 k=0 或 paper §3.3 completion；TTS 增益另设固定预算对照）；
- [ ] 231 剩余操作者决定：继续 completion 口径跑完 vanilla/raw，或改 improvement 重跑；
- [ ] B 档 reasoning vs chat 最终结论；
- [ ] 更新 Table3/4 报告 v2。
