# POST_L2 INSTRUMENT EXECUTION REALISM STOP CLOSEOUT — 决策收尾（文档 only）

> 评审（`POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_003_REVIEWER_RESPONSE.md`）
> **EXECUTION_REALISM_RUN_CORRECTION_003_ACCEPTED_STOP_CONFIRMED**，reviewer_state = **BLOCKED**，
> `authorized_next: POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT`。
> 本 packet 为文档/决策合成 only：冻结有效 STOP，分离 (a) 经济表现发现 与 (b) 结构性资格失效，
> 枚举可能的未来研究分支但不执行/不选择。无新回测/运行授权。
> handoff_id = **G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT_001**。

---

# 1. 归档：接受的 STOP 结果（评审冻结为有效 STOP）

```text
执行：MaxDiv 120/0.5 project-constrained RiskOverlayV0；L1 真实窗口 1011 决策日
（决策 2022-06-09..2026-08-06，执行 2022-06-10..2026-08-07）；11 真实 ETF（HK_DIVIDEND=03110.HK）
implementation_commit: aabe0ca（CORRECTION_003 7 项忠实性修正）
result_commit: 7dfabcd
artifacts: artifacts/gate4_instrument_execution_realism_results.json + _raw.json（tracked）
03110 三日期: listing 2013-06-17 / data 2021-01-11 / southbound_eligible_from 2024-05-06
```

| 指标 | 可执行 net（接受） | L1 研究 MaxDiv（无成本参考） |
|---|---:|---:|
| 累计收益 | **+47.21%** | +45.4% |
| Calendar CAGR | **+9.74%** | +9.4% |
| Sharpe | **1.738** | 1.655 |
| MaxDD | **-4.24%** | -4.0% |

| 判据 | 值 | 判定 |
|---|---|---|
| S1 worst 子期恶化 | year_2026 -0.84%（net 4.72% vs research 5.56%） | **PASS** |
| S2 fee bps | 4.457 ≤ 5 | **PASS** |
| S2 slippage bps | 3.000 ≤ 10 | **PASS** |
| S3 fail-closed | 478/1011 = **47.28%** > 1% | **FAIL** |
| S4 | NOT_APPLICABLE（backtest mode） | N/A |
| **STOP** | — | **TRUE（S3）** |

```text
评审：CORRECTION_003 被接受为冻结实验足够忠实的 execution-realism 结果；
无需第 4 次机械重跑。实验本身不过：S3 为硬 STOP，不授权 forward/paper/live。
```

# 2. 分离：(a) 经济表现发现 vs (b) 结构性资格失效

## (a) 经济表现发现（S1/S2 通过，可执行路径忠实）

```text
1. 可执行 net 贴近已接受 L1 研究 MaxDiv：cum +47.21% vs +45.4%、CAGR 9.74% vs 9.4%、
   Sharpe 1.738 vs 1.655、MaxDD -4.24% vs -4.0%——T+1-open + post-fill NAV + Southbound
   真实成交 + 官方分红全部实现后，可执行性损耗极小。
2. S1 全 7 子期通过：每子期 net CAGR 与研究同边界一致（worst year_2026 -0.84%，远优于
   -5% 阈值）。2022 研究 CAGR = -0.7%（非全期 0.094154），原 CORRECTION_002 的 S1 FAIL 判据无效。
3. S2 通过：fee 4.457bp + slippage 3.000bp 均低于冻结阈值。
4. Southbound 执行分支真实行使：03110 eligible 后 attempted 217 / fills 217 / notional
   735.8k CNY；mean_target_weight 0.048 / max 0.092；lot-feasible 533/550 天。
5. STOP 非由收益弱或模型化交易成本过高导致。
```

## (b) 结构性资格失效（S3 冻结判据，硬 STOP）

```text
1. 冻结实验在 2022-06..2026-08 窗口将 HK_DIVIDEND 映射到 03110.HK，但 Southbound
   eligibility 始于 2024-05-06 → 2022-06-09..2024-05-03 共 461 决策日结构不可交易 → 现金停泊。
2. S3 distinct fail-closed = 结构 461 ∪ 无报价 18（overlap 1）= 478 / 1011 = 47.28%，
   远高于冻结 1% 阈值。结构资格错配为主因，非经济失败。
3. 评审明确：不得在见结果后更改映射 / eligibility 日期 / 分母 / 窗口 / S3 阈值。
4. 本 closeout 冻结该 STOP 为有效决策；任何替代 universe/窗口处理 = 新研究设计，需新 PREP 评审。
```

# 3. 未来研究分支（枚举 only，不执行 / 不选择）

```text
以下均为可能的未来研究分支（文档性枚举），本 closeout 不执行、不选择其中任何一项；
任一分支须作为独立 pre-registered 实验设计、经评审授权后再执行：

  A. HK_DIVIDEND 槽位改用境内可交易 wrapper（如 loader 现有 Track A 513690.SH 研究序列），
     使全窗口可交易——需重冻结 slot->instrument 映射 + 新 PREP。
  B. 将评估窗口起点后移至 03110 Southbound eligible 后（2024-05-06 起）——需重冻结窗口 + 新 PREP。
  C. 引入港股通资格动态/更广资格检查，替代固定 southbound_eligible_from——新研究设计。
  D. 在已可交易 universe 上继续 execution-realism 纵深（如流动性/冲击模型）——新门。
  E. 其他 11 槽位映射变体（不改变 11 槽结构与 MaxDiv 参数）——新 PREP。
```

```text
约束：任何分支不得在见结果后选择性实施；不得改变已冻结的 MaxDiv 参数、11 槽结构、
1011 日窗口、S1-S4 定义、S3 计数语义；不得启动 FORWARD/PAPER/LIVE/QMT_LIVE。
```

# 4. 边界与规避

```text
✓ 文档/决策 only：无代码 / 无新回测 / 无运行 / 无映射·窗口·阈值·资格变更 / 无部署
✓ 未来研究分支仅枚举，不执行 / 不选择（评审：closeout 可枚举但不执行不选择）
✓ PPO/SAC/TD3 保持关闭（除非用户明确重开）；QMT live / FORWARD / PAPER / LIVE 禁止
✓ 本 STOP 为冻结契约预期结果（S3 结构失效），非收益/成本失败
```

# 5. Git Commit

`POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT` 提交 SHA：见 Approval Record。

```text
docs/review_packets/POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml  ← 协议状态
```

# 6. Roadmap 状态

```text
L1 真实工具长区间非 RL 研究（MaxDiv 等）：保持为已接受确定性 benchmark/fallback 路径
L2 proxy 2015-2026 情景研究：已接受（SCENARIO_NOT_STRICT_PIT_OOS）
POST_L2 确定性架构 blend：已接受（静态 blend 不优于纯 MaxDiv core）
POST_L2 可执行 instrument 路径（本实验）：STOP（S3 结构失效）——冻结为有效 STOP
FORWARD / PAPER / LIVE / QMT_LIVE：均不授权
PPO / SAC / TD3：关闭（除非用户明确重开）
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT_001
packet: POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT
status: READY_FOR_REVIEW

accepted:
  stop_confirmed: true               # 评审 ACCEPTED_STOP_CONFIRMED；S3 硬 STOP 冻结
  economic_vs_structural_separated: true  # (a) S1/S2 通过 + 贴近研究 vs (b) 结构资格失效
  southbound_path_exercised: true    # 03110 attempted 217 / fills 217 / notional 735.8k CNY
  s1_pass: true                      # worst -0.84% (year_2026)，7 子期全过
  s2_pass: true                      # fee 4.457bp / slippage 3.000bp
  s3_fail_frozen: true               # 478/1011 = 47.28%（结构 461 U 无报价 18）
  future_branches_enumerated_only: true  # A-E 枚举，不执行不选择
  no_new_backtest: true              # closeout 文档 only

frozen_unchanged:
  maxdiv_120_0.5: true
  11_slot_mapping: true              # HK_DIVIDEND=03110.HK 不变
  1011_day_window: true
  southbound_eligible_from_2024-05-06: true
  s1_s4_definitions: true
  s3_counting_semantics: true

not_authorized:
  forward_paper_live: false
  qmt_live: false
  instrument_substitution: false
  mapping_change: false
  window_change: false
  stop_threshold_change: false
  ppo_sac_td3: false
  rl_retraining_tuning_comparison: false
```

## END OF POST_L2 INSTRUMENT EXECUTION REALISM STOP CLOSEOUT
