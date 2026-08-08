# GATE 3 Corrections

> Reviewer: `GATE_3_STATUS = REVISIONS_REQUIRED_BEFORE_GATE_4`（2026-08-08）。
> 修正 BLOCKER-1..5 + 延续项登记 + Gate 4 数据跨度方案。

## 1. Action-space correction

- `action_space: Box(-10,10)^11 → Box(-1,1)^11`（SB3 官方建议的归一化对称连续动作域）。
- 原因（Reviewer §2/§3）：softmax 对 logit 差极敏感——`Δ=4 → w_max≈0.845` 恰等于旧 TD3 的 0.846；
  旧集中是 action 尺度伪影而非策略偏好。

## 2. ActionTransform（显式、算法中立）

```python
class ActionTransform:
    def transform(self, action, decision_time) -> TargetAssetWeights:
        a = clip(action, -1, 1)
        z = a - a.max(); w = exp(z)/sum(exp(z))
        # 记录 last_raw_action / last_raw_policy_weights 供诊断
```

三算法共用同一 transform（禁止各自 softmax temperature）。
极端界校验：`一个 +1、十个 −1 → w_max = e²/(e²+10) ≈ 0.425`（非 ~1.0）。

## 3. RiskOverlayV0 接入 transition（BLOCKER-2）

```text
RL action → ActionTransform → raw_policy_weights
        → RiskOverlayV0 → post_risk_target_weights
        → OrderGenerator/Lot/Tradability → actual_portfolio_weights
```

Core-only 约束：`single_core_max=0.25`、`china_growth_max=0.50`（CHINEXT+STAR 组）、long_only、Σw=1。
语义：cap 作用于 rebalance target（V1）；actual 因市场波动超限由下次再平衡纠正。

## 4. bounded-simplex tests

实现 water-filling（非 naive clip+renormalize）；不可行 → `InfeasibleConstraints`（不静默放松）。
测试：`test_single_core_cap / test_china_growth_group_cap / test_projection_sum_to_one /
test_projection_caps_after_renormalization / test_projection_idempotent /
test_infeasible_constraints_raise` + **10,000 随机 action property test**（max≤0.25+ε、
ChinaGrowth≤0.50+ε、sum=1）全过。

## 5. Raw / Post-Risk / Actual 三层权重诊断

env.step 的 info 输出 `weights = {raw_policy, post_risk, actual}`；本 packet 主表按三层分别报告。

## 6. Observation normalization

方案 A：自定义 train-only scaler（mean/std per feature）。train 期收集 500 步观测 → fit →
冻结 → train/eval 同一 scaler；随模型保存/加载。禁止全样本 fit（`ScalerFitRange ⊆ TrainRange`）。

## 7. Train-only scaler proof

```text
scaler fit 数据：train 环境（≤2025-10-23）EW 500 步观测
eval 仅 transform（不更新统计）
```

## 8. Chronological Train / Sanity-Eval split

```text
Train = 2011-12-09 → 2025-10-23（数据止于 eval 起点；最后 200 交易日保留）
Eval  = 2025-10-23 → 2026-08-07（held-out，199 步诊断）
no shuffle；eval 不进 scaler fit；eval 不进训练
```

## 9. SB3 check_env + termination semantics

- `stable_baselines3.common.env_checker.check_env(gym_env, warn=True)` **通过**（无异常）。
- 语义：数据到达日历末尾 = **truncated=True, terminated=False**（无 policy 终止态）；
  truncated 后 step 行为已定义（持续返回 truncated=True）；reset 返回合法 obs（在 observation_space 内）。
- 测试：`test_sb3_check_env / test_episode_end_semantics / test_reset_returns_valid_obs /
  test_step_after_terminal_is_defined`。

## 10. Re-run TD3/SAC/PPO sanity（held-out，199 步）

| 指标 | EW | TD3 | SAC | PPO |
|---|---:|---:|---:|---:|
| raw_policy max_mean | 0.0909 | 0.1523 | 0.1772 | 0.1005 |
| post_risk max_mean | 0.0909 | 0.1523 | 0.1772 | 0.1005 |
| actual max_mean | 0.0916 | 0.1519 | 0.1724 | 0.0989 |
| raw/post/actual HHI | 0.091 | 0.131 | 0.107 | 0.091 |
| **>25% 单资产步数占比（三层）** | 0.0% | 0.0% | 0.0% | 0.0% |
| actual ChinaGrowth mean | 0.180 | 0.165 | 0.125 | 0.181 |
| cash residual mean | 1.94% | 1.72% | 1.84% | 1.92% |
| reward mean / std | 1.9e-4 / 9.1e-3 | 1.6e-4 / 1.1e-2 | 1.7e-4 / 7.8e-3 | 1.5e-4 / 9.1e-3 |
| NaN | 0 | 0 | 0 | 0 |
| save/load 一致 | — | true | true | true |
| device / train_sec | — | cuda/260 | cuda/377 | cpu/157 |

**关键观察**：旧 TD3 max 0.846 / SAC 0.926 的集中现象在归一化动作域 + RiskOverlay 下消失
（现 max≈0.15/0.18，全部 ≤0.25）——确认为 action 参数化伪影；三层权重一致说明
Risk/Execution 未引入额外集中。无性能结论。

## 11. Equal Weight same-environment baseline

EW 与三算法走同一环境路径（同成本/同 T+1 开盘/同整手/同 RiskOverlay），held-out 199 步，
仅作 sanity 参照。

## 12. Exact pytest output

```text
collected 58 items
============================= 58 passed in 15.48s ==============================
```

## 13. Carry-forward register

```text
C1 03110 same-day rule          : OPEN（Gate 6 前）
C2 proxy PIT audit              : OPEN（Gate 3/4 只用真实 ETF 序列；Track B 启用前必须关闭）
C3 adjustment PIT               : PARTIALLY_RESOLVED（算法+14 真实事件验证；Gate 4 前对 13.8bp
                                   最坏事件做独立来源交叉验证——基金公告/独立调整收益源）
F1 历史费率规则 PIT             : OPEN（Gate 4 前）
F2 港股通券商佣金               : OPEN（Gate 4/6 前）
H1 03110 total-return 验证      : NEW（Gate 4 正式结论前：sina qfq 与 Global X/HKEX 官方
                                   派息数据 2~3 个派息日交叉验证）
```

## 14. Gate 4 data-horizon proposal summary

见 `GATE_4_DATA_HORIZON_PLAN.md`：推荐双轨结论
（Track A 真实 ETF 短历史 OOS + Track B/C 长历史 Method/Scenario），
不把 2022~2026 短样本单独当作长期 RL Alpha 证据。

## 15. Git commit

`e88f462`

---

## END OF GATE 3 CORRECTIONS
