# POST_L2 INSTRUMENT EXECUTION REALISM STOP CLOSEOUT — 决策收尾（文档 only）

> 评审（`POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT_REVIEWER_RESPONSE.md`）
> **STOP_CLOSEOUT_SUBSTANTIVELY_ACCEPTED_DOC_CONSISTENCY_CLEANUP_REQUIRED** →
> 本版为 **DOC_CLEANUP**（文档一致性清理 only，无代码/实验变更）。
> 先期评审（`POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_003_REVIEWER_RESPONSE.md`）
> **EXECUTION_REALISM_RUN_CORRECTION_003_ACCEPTED_STOP_CONFIRMED**（BLOCKED）授权 STOP_CLOSEOUT；
> 本 cleanup 将 closeout 与已接受 CORRECTION_003 记录精确对齐。
> handoff_id = **G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT_DOC_CLEANUP_001**。

---

# 1. 归档：接受的 STOP 结果（评审冻结为有效 STOP）

```text
执行：MaxDiv 120/0.5 project-constrained RiskOverlayV0；L1 真实窗口 1011 决策日
（决策 2022-06-09..2026-08-06，执行 2022-06-10..2026-08-07）；11 真实 ETF（HK_DIVIDEND=03110.HK）
artifacts: artifacts/gate4_instrument_execution_realism_results.json + _raw.json（tracked）
03110 三日期: listing 2013-06-17 / data 2021-01-11 / southbound_eligible_from 2024-05-06
```

```text
commit 绑定（分别、精确）：
  implementation_commit: aabe0ca（CORRECTION_003 7 项忠实性修正，被评审接受）
  result_packet_commit : 7dfabcd（CORRECTION_003 RUN packet + artifact + CLAUDE_STATUS）
  closeout_packet_commit: 8166ffd（本 closeout 评审审阅版本）
  doc_cleanup_commit   : <DOC_CLEANUP_COMMIT>（本 DOC_CLEANUP 文档一致性版本）
```

```text
provenance（canonical，引用已接受 CORRECTION_003 记录）：
  行为回归测试 21 passed；--check PASSED
  provenance manifest：20 个实际消费输入（11 QMT raw 含 513690 + sina_qfq + hkd_cny +
  7 divid_events）SHA256 + 已接受 L1 results/raw artifact SHA256 + commit 绑定
```

| 指标 | 可执行 net（接受） | L1 研究 MaxDiv（无成本参考） |
|---|---:|---:|
| 累计收益 | **+47.21%** | +45.4% |
| Calendar CAGR | **+9.74%** | +9.4% |
| Sharpe | **1.738** | 1.655 |
| MaxDD | **-4.24%** | -4.0% |

| 判据 | 值 | 判定 |
|---|---|---|
| S1 worst 子期恶化 | year_2026 -0.70%（-0.006967，net 4.86% vs research 5.56%） | **PASS** |
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
2. S1 全 7 子期通过：每子期 net CAGR 与研究同边界一致（worst year_2026 -0.70% =
   -0.006967，远优于 -5% 阈值；net 4.86% vs research 5.56%，精确复制自已接受 artifact）。
   2022 研究 CAGR = -0.7%（非全期 0.094154），原 CORRECTION_002 的 S1 FAIL 判据无效。
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

  A. HK_DIVIDEND 槽位改用潜在境内可交易 wrapper（举例：loader 现有 Track A 513690.SH 研究
     序列）——注意：513690.SH 在本窗口的全可交易性/适用性未经验证，须在新 PREP 中单独核实
     （launch 日期、数据覆盖、执行价可得性），不得断言其必然使整个 2022-06..2026-08 窗口
     可交易；另需重冻结 slot->instrument 映射 + 新 PREP。
  B. 将评估窗口起点后移至 03110 Southbound eligible 后（2024-05-06 起）——需重冻结窗口 + 新 PREP。
  C. 引入港股通资格动态/更广资格检查，替代固定 southbound_eligible_from——新研究设计。
  D. 在已可交易 universe 上继续 execution-realism 纵深（如流动性/冲击模型）——新门。
  E. 其他 11 槽位映射变体（不改变 11 槽结构与 MaxDiv 参数）——新 PREP。
```

```text
分支选择状态：A-E 全部保持 UNSELECTED。本 closeout 不选择、不偏好任何分支；
任何分支的实施均需独立 PREP 评审授权（fresh PREP），不得在本 STOP 实验下选择。
```

```text
约束：任何分支不得在见结果后选择性实施；不得改变已冻结的 MaxDiv 参数、11 槽结构、
1011 日窗口、S1-S4 定义、S3 计数语义；不得启动 FORWARD/PAPER/LIVE/QMT_LIVE。
```

# 4. 边界与规避

```text
✓ 文档/决策 only：无代码 / 无新回测 / 无运行 / 无映射·窗口·阈值·资格变更 / 无部署
✓ 未来研究分支仅枚举，不执行 / 不选择（A-E 全部 UNSELECTED；评审：closeout 可枚举但不执行不选择）
✓ PPO/SAC/TD3 保持关闭（除非用户明确重开）；QMT live / FORWARD / PAPER / LIVE 禁止
✓ 本 STOP 为冻结契约预期结果（S3 结构失效），非收益/成本失败
✓ STOP 语义不变：无映射替换 / 无资格日期重释 / 无窗口·分母·S1-S4 阈值变更 / 无重跑
```

# 5. Git Commit

```text
implementation_commit : aabe0ca（CORRECTION_003 实现，被评审接受）
result_packet_commit  : 7dfabcd（CORRECTION_003 RUN packet + artifact + CLAUDE_STATUS）
closeout_packet_commit: 8166ffd（closeout 评审审阅版本）
doc_cleanup_commit    : <DOC_CLEANUP_COMMIT>（本 DOC_CLEANUP 版本）

本 DOC_CLEANUP 改动文件：
docs/review_packets/POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT.md  ← 本 packet（一致性清理）
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
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT_DOC_CLEANUP_001
packet: POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT
status: READY_FOR_REVIEW

doc_cleanup_applied (5, reviewer STOP_CLOSEOUT_DOC_CLEANUP):
  s1_worst_corrected: true           # -0.70% (-0.006967, year_2026)；net 4.86% vs research 5.56%
  provenance_canonical: true         # 21 tests + 20 inputs + L1 artifacts SHA256；无 stale counts
  commits_bound_distinctly: true     # impl aabe0ca / result+packet 7dfabcd / closeout 8166ffd /
                                     # cleanup <DOC_CLEANUP_COMMIT>
  branch_a_softened: true            # 513690.SH 仅作需 fresh PREP 验证的例子；不断言全窗口可交易
  branches_all_unselected: true      # A-E 全部保持 UNSELECTED

accepted:
  stop_confirmed: true               # 评审 ACCEPTED_STOP_CONFIRMED；S3 硬 STOP 冻结
  economic_vs_structural_separated: true  # (a) S1/S2 通过 + 贴近研究 vs (b) 结构资格失效
  southbound_path_exercised: true    # 03110 attempted 217 / fills 217 / notional 735.8k CNY
  s1_pass: true                      # worst -0.70% (-0.006967, year_2026)，7 子期全过
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
