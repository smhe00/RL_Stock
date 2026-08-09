# RL_Stock — 中国 ETF 多资产配置研究报告

> **Research closeout · 2026-08-09**  
> 本仓库最初用于研究基于 FinRL-X / Stable-Baselines3 的中国 ETF 多资产强化学习配置系统。经过数据、环境、执行语义、Walk-Forward、强非 RL 基准、特征诊断和正式 3-seed RL 评估后，当前 **F0 + PPO/SAC/TD3 分支正式结论为 `NO_GO`**。  
> 项目最重要的产出并不是一个“胜出的 RL 模型”，而是一套可复用、可审计、fail-closed 的多资产量化研究环境，以及一个明确的实证结论：**在本研究设置和已冻结协议下，复杂 RL 没有证明相对强确定性基准具有足够的增量经济价值。**

主执行规范（历史 Source of Truth）：[docs/EXECUTION_SPEC.md](docs/EXECUTION_SPEC.md)  
最终决策记录：[docs/DECISIONS.md](docs/DECISIONS.md)  
最终 reviewer 状态：[docs/reviewer_state/CHATGPT_REVIEW.yaml](docs/reviewer_state/CHATGPT_REVIEW.yaml)

---

## 1. Executive Summary

这个项目回答的不是“能否训练出一个历史收益为正的 RL agent”，而是更严格的问题：

> **在中国可交易 ETF 多资产配置中，PPO / SAC / TD3 在严格 Walk-Forward、真实可执行时序、交易成本、公司行为、风险约束和多随机种子条件下，能否稳定优于简单而强的确定性资产配置方法？**

最终答案是：**当前没有足够证据支持。**

研究得到三个不同意义上的“冠军”：

| 目标 | 当前最好方法 | 核心结果 | 解读 |
|---|---|---|---|
| 最高收益 | `Momentum_12_1` | active-day 年化约 **30.0%** | 收益最高，但 MaxDD **-17.0%**，风险明显更大 |
| 最简单强收益基线 | `EqualWeight` | 年化 **26.9%** / Sharpe **1.64** / MaxDD **-8.8%** | 极难被复杂方法稳定击败，是正式 RL 的主要 hurdle |
| 最佳风险调整表现 | `MaximumDiversification` | Sharpe **2.77** / Sortino **4.33** / MaxDD **-3.4%** / Calmar **5.38** | 当前最强 risk-adjusted frontier，也是本项目总体最有价值的 deterministic 结果 |
| 最接近通过的 RL | `PPO` | 年化 **27.4%** / Sharpe **1.62** / MaxDD **-9.1%** | 收益有竞争力，但未通过预注册的风险与 seed 稳定性门槛 |

因此，如果必须给出一个“当前最好策略”：

- **追求绝对收益**：Momentum_12_1；
- **追求简单、稳健、低研究自由度**：EqualWeight；
- **追求风险调整收益和回撤控制**：**MaximumDiversification（本项目推荐的研究冠军 / 下一阶段风险核心）**。

这不是实盘盈利承诺。当前 475 日 benchmark 已被多轮研究观察，正式名称应视为 `RESEARCH_BENCHMARK_TEST`，而不是 pristine final holdout。任何更强的盈利结论都需要新的、从未看过的 forward period。

---

## 2. 背景：为什么做这个项目

原始目标是建立一套中国投资者可实际执行的 ETF 多资产动态配置系统，并研究 RL 是否能在资产配置层创造增量价值。

研究问题不是：

> “预测哪只 ETF 明天涨。”

而是：

> “给定市场状态、当前组合、交易成本和风险约束，下一期应该如何分配多个风险资产的目标权重？”

抽象流程：

```text
Market Data
    ↓
Point-in-Time Features
    ↓
Portfolio Policy
    ├─ Deterministic allocators
    └─ PPO / SAC / TD3
    ↓
Raw Asset Weights
    ↓
Risk Overlay
    ↓
Tradability / Premium Controls
    ↓
Instrument Weights
    ↓
Order Generator
    ↓
Broker Adapter
```

原规划最终希望衔接 QMT / miniQMT Paper Trading 和小资金实盘。但本阶段在 Gate 4 已得到正式 RL `NO_GO`，因此**没有推进 live execution**。仓库中的 QMT / miniQMT 内容应视为后续执行层参考，而不是已经验证的生产交易系统。

---

## 3. 投资范围与 F0 状态空间

### 3.1 11 个核心 Asset Slots

当前核心资产池由中国境内证券账户可交易 ETF 风险槽位构成：

| Slot | 代表 ETF | 经济含义 |
|---|---|---|
| CN_LARGE | 510300 | 沪深300 / A股大盘 |
| CN_SMALL | 512100 | A股小盘 |
| CN_DIVIDEND | 512890 | A股红利 |
| CHINEXT | 159915 | 创业板 |
| STAR | 588000 | 科创板 |
| HK_TECH | 513180 | 港股科技 |
| HK_DIVIDEND | 03110.HK | 港股红利 |
| US_BROAD | 513500 | 美国宽基 QDII |
| GOLD | 518880 | 黄金 |
| CN_DURATION | 511260 | 中国利率债久期 |
| CASH_LIKE | 511360 | 现金类 / 短久期 |

完整配置见 [config/universe.yaml](config/universe.yaml)。

另保留半导体、AI、机器人、生物科技、航空航天等 Theme candidates，但**未进入最终正式 F0 RL 结论**。

### 3.2 F0 observation / action

正式 F0：

```text
ActionDim = 11
ObsDim    = 104
```

Observation：

- 每资产 8 个特征 × 11：
  - `log_return_5/20/60/120`
  - `realized_vol_20/60`
  - `drawdown_60/250`
- 当前资产权重：11
- 全局状态：5
  - cross-sectional dispersion
  - equity average correlation
  - CN large volatility percentile
  - gold-equity correlation
  - bond-equity correlation

约束：long-only、无杠杆、组合权重和为 1。RL 学的是**经济风险槽位权重**，不是 ETF 代码。

---

## 4. 本项目实际实现了什么

这套仓库已经远超过一个“调用 SB3 训练模型”的 demo。核心功能包括：

### 4.1 数据与 Point-in-Time 语义

- raw execution price 与 research total-return series 分离；
- 公司行为 / 分红 / 份额折算处理；
- Point-in-Time adjustment tests；
- 禁止未来数据前向泄漏；
- train-only feature preprocessing / scaling；
- ETF universe 与资产槽位映射。

关键代码：

```text
src/china_etf/data/
src/china_etf/features/
src/china_etf/fx.py
```

### 4.2 金融会计与执行环境

- `PortfolioAccounting`：现金、持仓、费用、公司行为、组合价值；
- `MockBroker` / Broker abstraction；
- Mainland / Southbound cost model；
- `OrderGenerator`；
- `TradabilityMask`；
- `PremiumGuard` fail-closed；
- RiskOverlay；
- Gym wrapper 与 11-dim portfolio environment。

关键代码：

```text
src/china_etf/accounting.py
src/china_etf/cost/
src/china_etf/environment/
src/china_etf/execution/
src/china_etf/risk/
```

### 4.3 严格时间语义

正式语义是：

```text
T 日可用信息 / 收盘决策
        ↓
T+1 开盘执行
```

项目专门测试并禁止：

- T 收盘看到价格后假设仍以 T 收盘成交；
- random train/test split；
- Test/OOS 数据参与 scaler fit；
- validation gap 暴露被错误带入 Test；
- fold 之间会计状态偷偷 carry；
- ex-date 当天开盘新买入却错误获得当日分红。

### 4.4 Walk-Forward 与评估基础设施

实现了：

- 4-fold Walk-Forward；
- fold-local reset；
- exact Test date mask；
- raw per-step series 保存；
- stitched OOS aggregation；
- cost reconciliation；
- benchmark date/count parity；
- seed dispersion；
- deterministic baselines / optimizers；
- RL formal protocol + config hash；
- hard-stop invariants；
- raw results → canonical metrics → GO/NO-GO 的唯一发布路径。

关键代码：

```text
src/china_etf/evaluation/walkforward.py
src/china_etf/evaluation/rollout.py
src/china_etf/evaluation/benchmark.py
src/china_etf/evaluation/baselines.py
src/china_etf/evaluation/optimizers.py
src/china_etf/evaluation/rl_formal.py
```

### 4.5 研究治理 / Agent gate

Claude Code 负责实现与实验，ChatGPT reviewer 负责 gate review，GitHub 作为共享状态机：

```text
Developer / Runner
      ↓ Review Packet
GitHub
      ↓
Independent Reviewer
      ↓ decision / authorized_next
```

协议见 [docs/HANDOFF_PROTOCOL.md](docs/HANDOFF_PROTOCOL.md)。

这一机制看似“慢”，但它阻止了多次高风险问题进入正式实验，例如：benchmark 时间口径错误、统计 resampling 不成立、config 未真正绑定 runtime、publication metrics 与 raw results 断开、schema false-green 等。

---

## 5. 研究数据窗口与“沪深300持有”基准

正式可比较 Test mask：

```text
label                = RESEARCH_BENCHMARK_TEST
exact execution days = 475
first Test date      = 2023-11-24
last Test date       = 2026-08-07
excluded Val dates   = 240
```

### 5.1 为什么不能直接拿一条普通 510300 曲线来比较

策略的正式 OOS 是多个 Test fold 拼接而成，中间存在 Validation gap。因此“连续从第一天持有到最后一天”的 510300 曲线与策略并不处于同一个资本暴露时钟。

本项目专门实现了：

`510300_EXECUTABLE_NET_STITCHED_BUY_HOLD`

语义：

1. 每个 fold 独立从现金开始；
2. `test_start` 开盘买入 510300；
3. 计入当前成本模型；
4. Test 段内持有；
5. 不跨 Validation gap；
6. 公司行为按同一会计顺序处理；
7. F1→F4 拼接，严格 475 个执行日。

结果：

```text
510300 executable stitched cumulative net return = +50.06%
returns count = 475
exact date parity = True
```

将这一累计收益按与项目其它 stitched 指标相同的 252 active-day 口径换算：

```text
active-day annualized return ≈ +24.03%
```

注意：正式 benchmark artifact 重点冻结了 executable cumulative return / date parity；没有保存与 horse-race 同样完整的 Sharpe、MaxDD 等风险统计。因此下文与 510300 的“全面对比”在收益维度可以严格同口径，而风险调整比较主要依赖 EqualWeight / MaxDiv 等完整策略 artifact。

### 5.2 研究复权沪深300（CN_LARGE）完整风险指标（补充口径）

作为**补充参照**，用研究复权序列（`CN_LARGE` 槽位，即 510300 复权价）在**同一 475 执行日窗口**上
直接计算（`log(adj[t]/adj[t-1])` 逐日对数收益，无交易成本、无 fold 拼接——与可执行 stitched 口径不同，
仅供与策略的风险调整维度做研究级对比）：

```text
沪深300 研究复权（475 执行日）：
  active-day 年化  +21.5%
  夏普            1.06
  最大回撤        -14.6%
  Sortino / Calmar 1.50 / 1.48
```

分 fold test 段：

```text
F1 (118d): +4.3% / 0.36 / -9.9%    F2 (118d): +35.7% / 1.19 / -14.6%
F3 (118d): +55.2% / 3.26 / -4.0%   F4 (121d): -0.1% / 0.10 / -10.2%
```

全决策区间（2022-06-06 → 末，1015 决策日，含研究期前段熊市）：

```text
active-day 年化 +4.3% | 夏普 0.33 | 最大回撤 -28.1%
```

**口径说明**：这里 `+21.5% / 1.06 / -14.6%`（475 日研究复权）与 §5.1 的 `+24.03%`（可执行 stitched）
存在差异，原因包括研究复权收益不含成本、非 fold-local 拼接、以及收益定义（log 复权日收益 vs 可执行净收益）。
因此这张补充表**不能**与 §9 的 `Δ vs 510300`（基于可执行 24.03%）直接混用；它主要用于与策略的
Sharpe / MaxDD 做研究级参照——结论仍是：EqualWeight（1.64 / -8.8%）与 MaxDiv（2.77 / -3.4%）在风险
调整上显著优于裸持有沪深300（1.06 / -14.6%）。

---

## 6. 评估过的非 RL 方法

最终 horse race 在 corrected execution path、相同 475 个 Test 执行日和相同 project constraints 下比较了：

- Equal Weight
- Inverse-Vol Risk Parity
- Trend Risk Parity
- Minimum Variance
- Shrinkage Minimum Variance
- ERC Project-Projected
- HRP Project-Projected
- Maximum Diversification
- Minimum CVaR 95%
- 12-1 Momentum

最终结果：

| 方法 | Active-day Ann. | Sharpe | Sortino | MaxDD | Calmar | Cost / Traded |
|---|---:|---:|---:|---:|---:|---:|
| **Momentum_12_1** | **30.0%** | 1.63 | 2.09 | **-17.0%** | 1.76 | 3.5 bp |
| **EqualWeight** | **26.9%** | 1.64 | 2.60 | -8.8% | 3.05 | 3.5 bp |
| ShrinkageMV | 26.1% | 1.60 | 2.37 | -8.6% | 3.02 | 3.5 bp |
| MinimumVariance | 22.8% | 1.75 | 2.75 | -6.0% | 3.81 | 3.5 bp |
| HRP_ProjectProjected | 22.7% | 1.76 | 2.76 | -5.9% | 3.83 | 3.5 bp |
| ERC_ProjectProjected | 22.5% | 1.87 | 2.87 | -5.6% | 4.05 | 3.5 bp |
| TrendRiskParity | 21.6% | 1.85 | 2.93 | -5.4% | 4.01 | 3.5 bp |
| RiskParity_IVOL | 21.6% | 1.82 | 2.90 | -5.4% | 4.00 | 3.5 bp |
| **MaximumDiversification** | 18.3% | **2.77** | **4.33** | **-3.4%** | **5.38** | 3.5 bp |
| MinimumCVaR_95 | 16.8% | 2.30 | 3.00 | -4.3% | 3.87 | 3.5 bp |

完整 artifact：

- [artifacts/gate4_non_rl_horse_race_results.json](artifacts/gate4_non_rl_horse_race_results.json)
- [artifacts/gate4_non_rl_horse_race_raw.json](artifacts/gate4_non_rl_horse_race_raw.json)

### 6.1 这里最重要的结论

**第一，EqualWeight 比想象中强。**  
它在这个多资产 universe 中取得 26.9% active-day 年化、Sharpe 1.64、MaxDD -8.8%，超过多数更复杂优化器的收益。这提醒我们：协方差 / 期望收益估计误差完全可能侵蚀理论上的优化优势。

**第二，MaxDiv 是非常清晰的风险调整前沿。**  
它只取得 18.3% 年化，但将 MaxDD 压低到 -3.4%，同时 Sharpe 2.77、Calmar 5.38，说明“少赚一些、但大幅降低风险”在本样本中非常有效。

**第三，Momentum 的高收益不是免费午餐。**  
30% 年化是全场最高，但 -17% 最大回撤也是明显代价。

---

## 7. 正式 RL 实验

### 7.1 冻结协议

最终 RL 不是从大量超参数搜索中挑最佳结果，而是在看到正式结果前冻结：

```text
Observation  = F0, dim 104
Algorithms   = PPO / SAC / TD3
Seeds        = 42 / 2026 / 7
Folds        = F1 / F2 / F3 / F4
Total runs   = 3 × 3 × 4 = 36
Train passes = 20
Net          = [256, 256]
Checkpoint   = final training endpoint only
Test         = exact 475-day RESEARCH_BENCHMARK_TEST
```

机器可读协议：[configs/rl_formal_protocol.yaml](configs/rl_formal_protocol.yaml)  
协议说明：[docs/features/RL_FORMAL_PROTOCOL.md](docs/features/RL_FORMAL_PROTOCOL.md)

正式结果：

| RL | Median Active-day Ann. | Median Sharpe | Median MaxDD | Median Calmar | Seeds Sharpe≥1.64 | Decision |
|---|---:|---:|---:|---:|---:|---|
| **PPO** | **27.36%** | **1.617** | **-9.10%** | 3.01 | 1/3 | **NO_GO** |
| SAC | 24.90% | 1.527 | -8.68% | 2.83 | 0/3 | **NO_GO** |
| TD3 | 18.98% | 1.210 | -12.33% | 1.57 | 0/3 | **NO_GO** |

36/36 runs 完成，`stop_violations = 0`。也就是说，**NO_GO 是策略表现结论，不是程序崩溃、NaN 或执行器失败。**

完整 artifact：

- [artifacts/gate4_rl_formal_results.json](artifacts/gate4_rl_formal_results.json)
- [artifacts/gate4_rl_formal_raw.json](artifacts/gate4_rl_formal_raw.json)

---

## 8. 为什么 RL 没有通过检验

正式 RL hurdle 在运行前冻结为 EqualWeight：

```text
每个算法要 GO，必须同时满足：
1. 无 stop / invariant violation
2. median(seed active-day annualized return) >= 26.87%
3. median(seed Sharpe) >= 1.64
4. median(seed MaxDD) >= -8.81%
5. 至少 2/3 seeds 的 Sharpe >= 1.64
```

项目级只有至少一个算法 GO，才能成为 `PROMISING` 并考虑下一阶段 robustness。

### PPO

PPO 是最接近成功的 RL：

```text
median return = 27.36%   > EqualWeight 26.87%
median Sharpe = 1.617    < 1.64
median MaxDD  = -9.10%   < -8.81%
Sharpe pass   = 1 / 3    < required 2 / 3
```

三个 seed：

| PPO Seed | Ann. | Sharpe | MaxDD | Calmar |
|---:|---:|---:|---:|---:|
| 42 | 27.66% | 1.692 | -8.59% | 3.22 |
| 2026 | 27.36% | 1.617 | -9.10% | 3.01 |
| 7 | 24.45% | 1.568 | -9.10% | 2.69 |

如果只看 seed=42，PPO 很容易被描述成“成功”；多 seed 让这个结论变得明显更谨慎。

### SAC

SAC 的 seed 稳定性反而不错，但整体收益 / Sharpe 都低于 EqualWeight hurdle，因此 NO_GO。

### TD3

TD3 在收益、Sharpe、MaxDD 和 seed consistency 上均明显不够，NO_GO 最清晰。

### MaxDiv 的进一步约束

即使只看 PPO 的绝对收益，三种 RL 的 Sharpe / MaxDD / Calmar 都被 MaximumDiversification 风险前沿 Pareto 主导。

因此本项目没有接受下面这种后验解释：

> “PPO 看起来还不错，不如再挑 PPO 单独调一调。”

因为这正是 Test-informed model selection。正式结果已经看过之后，再因为 PPO 最接近门槛而调参，会显著提高过拟合风险。

最终 closeout：[docs/review_packets/GATE_4_RL_NO_GO_CLOSEOUT.md](docs/review_packets/GATE_4_RL_NO_GO_CLOSEOUT.md)

---

## 9. 所有策略相对“只持有沪深300”的收益对比

正式沪深300可执行参考使用 510300 fold-local stitched buy-and-hold：

```text
累计净收益 +50.06%
active-day 年化约 +24.03%
```

以下 `Δ vs 510300` 仅表示 active-day 年化收益差，不代表风险调整后的超额收益：

| 方法 | Active-day Ann. | Δ vs 510300 | Sharpe | MaxDD | 备注 |
|---|---:|---:|---:|---:|---|
| 510300 executable stitched | **24.03%** | — | — | — | 同 475-day executable mask；风险统计未在最终 benchmark artifact 完整保留 |
| Momentum_12_1 | **30.0%** | **+6.0pp** | 1.63 | -17.0% | 收益冠军，回撤显著更大 |
| PPO | **27.36%** | **+3.3pp** | 1.62 | -9.1% | RL best，但 formal NO_GO |
| EqualWeight | **26.9%** | **+2.8pp** | 1.64 | -8.8% | 简单强基线 |
| ShrinkageMV | 26.1% | +2.1pp | 1.60 | -8.6% | 收益略高于 510300 |
| SAC | 24.9% | +0.9pp | 1.53 | -8.7% | 未形成足够增量 |
| MinimumVariance | 22.8% | -1.2pp | 1.75 | -6.0% | 牺牲收益换低风险 |
| HRP_ProjectProjected | 22.7% | -1.3pp | 1.76 | -5.9% | 低风险 |
| ERC_ProjectProjected | 22.5% | -1.5pp | 1.87 | -5.6% | 风险调整改善 |
| TrendRiskParity | 21.6% | -2.4pp | 1.85 | -5.4% | 风险调整改善 |
| RiskParity_IVOL | 21.6% | -2.4pp | 1.82 | -5.4% | 风险调整改善 |
| TD3 | 19.0% | -5.0pp | 1.21 | -12.3% | 明显不具竞争力 |
| MaximumDiversification | 18.3% | -5.7pp | **2.77** | **-3.4%** | 风险调整冠军 |
| MinimumCVaR_95 | 16.8% | -7.2pp | 2.30 | -4.3% | 强防御型 |

> 注：上表 `Δ vs 510300` 基于**可执行** 510300（24.03%）。若用**研究复权**沪深300（见 §5.2，
> 475 日 active-ann 21.5%），各策略的 Δ 会整体上移约 2.5pp（如 EqualWeight 26.9% vs 21.5% ≈ +5.4pp、
> PPO 27.36% vs 21.5% ≈ +5.9pp），但**风险调整维度不变**。

### 研究复权沪深300 风险参照（补充口径）

与 §5.2 一致，用研究复权 `CN_LARGE` 在 475 执行日上的完整风险指标，与策略直接做研究级对比
（注意口径：研究复权、无成本、非可执行 stitched，仅作风险调整参照）：

| 方法 | Active-day Ann. | Sharpe | MaxDD | Calmar |
|---|---:|---:|---:|---:|
| **沪深300（研究复权）** | **21.5%** | **1.06** | **-14.6%** | 1.48 |
| EqualWeight | 26.9% | 1.64 | -8.8% | 3.05 |
| MaximumDiversification | 18.3% | **2.77** | **-3.4%** | **5.38** |
| PPO（RL best） | 27.4% | 1.62 | -9.1% | 3.01 |
| SAC | 24.9% | 1.53 | -8.7% | 2.83 |
| TD3 | 19.0% | 1.21 | -12.3% | 1.57 |

研究级结论：EqualWeight / MaxDiv 在夏普与回撤上**显著优于**裸持有沪深300（夏普 1.64/2.77 vs 1.06；
回撤 -8.8%/-3.4% vs -14.6%）——多资产分散（含债券/黄金）相对单一股指的价值在风险调整维度清晰可见。

### 如何正确读这张表

- 如果唯一目标是收益，Momentum / PPO / EW 看起来最好；
- 如果目标是“用更小回撤取得合理收益”，MaxDiv / MinCVaR / ERC 更突出；
- PPO 超过 510300 的收益**不等于** PPO 通过了研究检验，因为正式问题是“RL 是否稳定优于强可实现替代方案”，不是“RL 是否跑赢某一个指数”；
- EqualWeight 已经用极低模型复杂度取得比 510300 更高的年化表现，因此复杂 RL 必须证明明显增量才值得承担模型风险、训练成本和解释难度。

---

## 10. 特征研究做了什么

除了 F0，本项目冻结过 F1/F2 feature research plan。

### F1：Risk / Correlation features

6 个候选：

```text
corr_pc1_share_60
equity_bond_corr_change_20_60
equity_gold_corr_change_20_60
cn_us_corr_60
equity_vol_ratio_20_60
equity_downside_semivol_60
```

经过 transition quarantine 和多轮统计 review，最终只保留一个谨慎的**描述性**结论：

> 在隔离 Test-transition 的 development data 上，没有看到六个 F1 特征中存在“大且稳定”的 next-day market absolute return 单调关系；此前 Test 中观察到的 vol-ratio 关系也没有同号复现。

这**不证明 F1 没有预测价值**，也不授权因为结果不好就删掉 F1。恰恰相反，这一阶段最大的价值是演示了：统计方法如果不能可靠处理时间依赖、quarantine gaps 和 resampling，就应该降低结论强度，而不是强行给出“显著/不显著”。

相关 artifact：

[artifacts/gate4_feature_importance_diagnostic_closeout.json](artifacts/gate4_feature_importance_diagnostic_closeout.json)

### F2：Macro / Forward Risk features

曾规划 VIX、USD/CNY、CGB10Y、DR007、A股换手等严格 PIT / native-calendar 特征，但没有在本项目正式 RL closeout 前推进真实宏观数据实验。

未来如重启，需要作为**新 pre-registered hypothesis**，并使用新的 forward period，不能继续利用当前已被反复观察的 475-day benchmark 做选择。

---

## 11. 当前这套环境还能怎么用

虽然 end-to-end F0 RL 分支关闭，但研究基础设施本身仍然非常有价值。

### 11.1 Deterministic portfolio research engine

可以继续研究：

- Maximum Diversification；
- Equal Weight；
- Risk Parity / Trend Risk Parity；
- MinVar / Shrinkage covariance；
- ERC / HRP；
- CVaR；
- Momentum / trend sleeves；
- 不同风险预算和 portfolio constraints。

### 11.2 Regime / Risk Overlay sandbox

相比让 RL 直接输出 11 维权重，更值得研究：

```text
market regime
    ↓
risk budget / target volatility / drawdown control
    ↓
deterministic portfolio core
```

例如让宏观 / 波动 / 相关性状态控制：

- MaxDiv 与 EW 的风险预算；
- equity gross exposure；
- cash-like allocation；
- momentum sleeve 大小；
- volatility target。

### 11.3 Hybrid RL testbed

如果未来重新研究 RL，更建议把 RL 限制为 meta-controller：

```text
RL output = risk multiplier / blend coefficient / regime action
```

而不是让 RL 从头学习全部 11 维资产权重。

这样可以：

- 减少 action space；
- 强化经济先验；
- 降低 sample complexity；
- 保留 deterministic core 的稳定性；
- 更容易解释 RL 是否真的创造增量。

但这必须是**新协议 + 新 forward data**，不是在当前 Test 上继续试。

### 11.4 Execution / accounting validation environment

环境仍适合测试：

- 新成本模型；
- 公司行为；
- T→T+1 execution；
- tradeability；
- premium guard；
- order generation；
- QMT adapter 前的 shadow execution semantics。

### 11.5 Quant research governance template

Gate / review / immutable artifact / config hash / fail-closed publication 这套流程本身可以迁移到其他量化项目。

---

## 12. 最重要的经验教训

### 12.1 先建立强 baseline，再谈 AI Alpha

如果没有 EqualWeight 和 MaxDiv，PPO 27% 年化很容易被误判为成功。

真正的问题应该是：

> **复杂模型是否比最简单、最稳健、最便宜的替代方案创造足够大的增量？**

### 12.2 Evaluation semantics 可能比模型本身更重要

本项目多轮修正证明以下细节足以改变结论：

- fold reset 在哪里；
- Test 首日收益是否计入；
- benchmark 是否跨 validation gap carry；
- 公司行为先 apply 还是先成交；
- cost 是否真正 reconciliation；
- execution date 是否与 strategy exact parity；
- stitched metrics 是否由 raw results 唯一推导。

### 12.3 单 seed 非常危险

PPO seed=42 单独看已经很像“成功”：年化 27.66%、Sharpe 1.69、MaxDD -8.59%。

但 3-seed 中只有 1 个 seed 的 Sharpe 过 hurdle。

因此“最佳 seed”不是证据。

### 12.4 预注册门槛能阻止结果出来后的自我说服

如果没有预先冻结 GO/NO-GO，很容易在看到 PPO 最接近后改口：

> “收益都超过 EW 了，Sharpe 差一点没关系。”

这就是典型的 post-hoc rule changing。

### 12.5 Test 被反复看过后，就不再是 final holdout

当前 475 日窗口已经用于：

- RL pilot；
- benchmark/evaluator debugging；
- non-RL horse race；
- feature diagnostics；
- formal RL reporting。

因此它现在只能称为：

`RESEARCH_BENCHMARK_TEST`

下一阶段必须真正预留：

`FUTURE_FINAL_FORWARD_HOLDOUT`

### 12.6 “tests 全绿”不代表研究链真的正确

项目曾遇到一个很典型的 false-green：aggregation 输出 schema 与 GO/NO-GO evaluator 不匹配，但 synthetic 测试本来就预期 NO_GO，因此测试仍全部通过。

最终通过增加：

- positive raw → GO / PROMISING；
- 同一 positive case + stop flip → NO_GO；

才验证了完整正负路径。

**研究测试必须有能成功的 positive control。**

### 12.7 Fail-closed 比“尽量跑完”更适合量化研究

关键证据缺失时，应该停止发布，而不是默认零错误：

- missing `n_eval_steps`；
- missing raw series；
- config hash mismatch；
- algo/class mismatch；
- seed 不完整；
- stop evidence 缺失；
- publication metric 与 raw result 不一致。

### 12.8 优化复杂度并不天然带来收益

很多理论更复杂的 portfolio optimizer 没有在收益上超过 EqualWeight。估计误差、约束和样本有限性会抵消理论最优。

### 12.9 负结果也是研究资产

接受 RL `NO_GO` 节省的，可能是未来大量 Optuna、feature expansion 和 seed mining 的时间。

这个项目不是“RL 失败所以没有成果”；相反，它建立了一个足够严格的系统，能够可信地说：

> **目前这条 RL 路线不值得继续加码。**

---

## 13. 当前已知限制

这套环境不能直接被描述为生产级盈利系统：

- 没有完成 QMT / miniQMT live execution 验证；
- 没有经过新的 untouched final forward holdout；
- Southbound / FX 主循环尚未达到完整生产验证状态；
- spread / slippage / impact 仍然是模型假设，未来真实成交可能不同；
- 当前 Test 已被重复观察，不能继续承担最终确认性检验；
- deterministic horse-race 的优秀历史结果也需要 forward reproduction；
- 本项目没有证明任何策略未来必然盈利。

---

## 14. 下一阶段最有价值的方向

### Priority 1 — Deterministic Portfolio Engine v2

建议从当前证据最强的结构出发，而不是重新从复杂 RL 出发：

```text
MaximumDiversification core
        +
volatility / drawdown risk budget
        +
regime-aware exposure
        +
optional EW / Momentum sleeve
```

其中：

- **MaxDiv**：作为低回撤、risk-adjusted core；
- **EqualWeight**：作为收益和简单性 hurdle；
- **Momentum**：作为潜在 return sleeve，而不是整个组合的唯一核心。

### Priority 2 — 先预留新的 forward period

在写 v2 策略代码前先冻结：

- observation / signals；
- rebalance frequency；
- constraints；
- cost model；
- selection rules；
- GO/NO-GO；
- forward holdout 起点。

当前 475 日数据只作为 research benchmark，不再负责 v2 的最终确认。

### Priority 3 — 更好的 PIT Regime Data

比再增加大量 TA indicators 更值得投入：

- VIX；
- USD/CNY；
- 中国国债 10Y；
- DR007；
- A股成交额 / 换手；
- breadth / cross-asset correlation；
- realized / downside volatility；
- liquidity regime。

重点是**识别风险状态**，而不是强行预测下一天涨跌。

### Priority 4 — 如重启 RL，只做 Hybrid / Meta-control

候选研究假设：

```text
alpha_t ∈ [0,1]
final portfolio = alpha_t × risky deterministic portfolio
                + (1-alpha_t) × cash / defensive portfolio
```

或让 agent 在有限的几个已知组合模板之间调风险预算。

只有在 deterministic v2 和新数据协议冻结后，才值得单独开一个新的 RL hypothesis。

### Priority 5 — Shadow / Paper → Small Capital

更合理的实盘路线：

```text
pre-register v2
      ↓
new forward holdout
      ↓
shadow / paper trading
      ↓
execution reconciliation
      ↓
small-capital live
      ↓
scale only after evidence
```

不要让“回测很好”直接跳到真实资金。

---

## 15. 建议的下一阶段路线图

```text
             ┌────────────────────────────┐
             │  v1 Research Closeout      │
             │  F0 RL = NO_GO             │
             └─────────────┬──────────────┘
                           │
                           ▼
             ┌────────────────────────────┐
             │ Pre-register v2            │
             │ Reserve new forward period │
             └─────────────┬──────────────┘
                           │
                           ▼
             ┌────────────────────────────┐
             │ Deterministic Engine v2    │
             │ MaxDiv + Regime/RiskBudget │
             └──────────┬─────────┬───────┘
                        │         │
                        │         └──────────────┐
                        ▼                        ▼
              Shadow / Paper          Optional Hybrid RL
                        │              Meta-controller only
                        └──────────────┬─────────┘
                                       ▼
                             New Forward Holdout
                                       │
                                       ▼
                              Small Capital Live
```

---

## 16. 如何继承本项目

新研究者不要从“重新跑 PPO”开始。推荐阅读顺序：

1. [README.md](README.md) — 当前研究结论与路线；
2. [docs/EXECUTION_SPEC.md](docs/EXECUTION_SPEC.md) — 原始工程约束与时间语义；
3. [docs/DECISIONS.md](docs/DECISIONS.md) — 关键决策历史；
4. [docs/HANDOFF_PROTOCOL.md](docs/HANDOFF_PROTOCOL.md) — gate / reviewer 工作流；
5. [docs/features/RL_FORMAL_PROTOCOL.md](docs/features/RL_FORMAL_PROTOCOL.md) — 正式 RL 冻结协议；
6. [configs/rl_formal_protocol.yaml](configs/rl_formal_protocol.yaml) — machine-readable formal config；
7. [docs/features/FEATURE_ABLATION_SPEC.md](docs/features/FEATURE_ABLATION_SPEC.md) — feature research 规范；
8. [docs/review_packets/GATE_4_NON_RL_HORSE_RACE_FINALIZATION.md](docs/review_packets/GATE_4_NON_RL_HORSE_RACE_FINALIZATION.md) — 非 RL 最终比较；
9. [docs/review_packets/CORRECTED_F0_RL_3SEED.md](docs/review_packets/CORRECTED_F0_RL_3SEED.md) — 正式 RL 结果包；
10. [docs/review_packets/GATE_4_RL_NO_GO_CLOSEOUT.md](docs/review_packets/GATE_4_RL_NO_GO_CLOSEOUT.md) — 分支最终关闭结论。

### 关键 immutable / tracked artifacts

```text
artifacts/gate4_non_rl_horse_race_results.json
artifacts/gate4_non_rl_horse_race_raw.json
artifacts/gate4_rl_formal_results.json
artifacts/gate4_rl_formal_raw.json
artifacts/gate4_feature_importance_diagnostic_closeout.json
```

不要为了让新研究看起来更好而覆盖这些 artifact。

---

## 17. 目录速览

```text
config/                 资产、费用、风险、执行、基础算法配置
configs/                正式机器可读研究协议
src/china_etf/
  accounting.py         组合会计
  contracts.py          canonical domain objects
  cost/                 Mainland / Southbound cost
  data/                 PIT / CA / loader
  environment/          portfolio env + Gym wrapper
  evaluation/           walk-forward / baseline / optimizer / RL formal
  execution/            broker abstraction / order / premium / tradability
  features/             F0/F1 features + preprocessing
  risk/                 RiskOverlay
artifacts/               tracked research results / raw evidence
docs/
  EXECUTION_SPEC.md      原始执行规范
  DECISIONS.md           决策日志
  HANDOFF_PROTOCOL.md    Claude ↔ Reviewer gate protocol
  features/              feature / formal RL specifications
  review_packets/        developer experiment packets
  reviewer_responses/    reviewer decisions
  references/miniqmt/    QMT / miniQMT execution reference material
scripts/                 Gate 1–4 research / validation scripts
tests/                   accounting / PIT / timing / execution / RL formal tests
```

在最终 formal harness closeout 阶段，测试套件达到 **246 passed**；non-RL horse-race finalization 对应阶段为 **162 passed**。数字不是质量本身，但说明大量时间被投入到 timing、accounting、benchmark、raw evidence 与 fail-closed contracts，而不是只优化收益曲线。

---

## 18. 项目最终状态

截至 2026-08-09：

```text
Gate 4 F0 PPO/SAC/TD3 RL branch = CLOSED
formal project_level             = NO_GO
10-seed robustness               = NOT AUTHORIZED
Optuna / hyperparameter sweep    = NOT AUTHORIZED
Test-informed feature/model tune = FORBIDDEN
QMT live                          = NOT VALIDATED / NOT AUTHORIZED
```

未来任何新方向都应作为独立、pre-registered 的研究假设，并使用新的 forward period 或独立授权的数据 regime。

---

## 19. 一句话结论

> **本项目最有价值的结果不是训练出了一个更复杂的 agent，而是建立了一套足够严格的研究机器，证明在当前中国 ETF 多资产配置任务中，F0 + PPO/SAC/TD3 没有稳定超过强确定性方法；当前最值得继承的路线是以 MaximumDiversification 为风险核心、EqualWeight 为强基准、Momentum 为可控收益增强，并在新的 forward 数据上验证 regime-aware deterministic / hybrid portfolio system。**

---

## Disclaimer

本仓库是研究项目，不构成投资建议或收益保证。所有历史回测、Walk-Forward 和研究 benchmark 都可能受到样本选择、成本模型、市场结构变化和模型风险影响。任何真实资金使用前都需要新的 forward validation、paper/shadow execution 和独立风控审查。
