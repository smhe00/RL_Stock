# Feature Ablation Spec — FROZEN（GATE_4_EVAL_FIX）

> 评审（`GATE_4_3_SEED_PILOT_REVIEWER_RESPONSE.md` §Feature-ablation preparation）：
> **spec 冻结 now（在 Test 结果影响特征选择之前）**；ablation **runs NOT yet authorized**。
> 本 spec 只定义候选集，不实现、不运行。授权需评审后续指令。

## 状态

```text
F0 = current baseline (ObsDim 104)
F1 = Risk / Correlation
F2 = Macro / Forward Risk
F3 = F1 + F2 combined
ObsDim 约束: ≤ 120
全部外部特征 strict PIT；China EOD 决策只能用前一个完成的 US session VIX。
禁止加大型 TA bundle（RSI/MACD/KDJ/CCI/ADX/many MAs）——
当前 R5/R20/R60/R120 + vol20/60 + drawdown60/250 已编码充分价格路径信息（评审原话）。
```

## F0 — Current（ObsDim 104）

```text
per-asset × 11（88）: log_return_5/20/60/120, realized_vol_20/60, drawdown_60/250
global × 5        : cross_sectional_dispersion_20, equity_average_corr_60,
                     cn_large_vol_percentile_252, gold_equity_corr_60, bond_equity_corr_60
portfolio weights × 11
```

## F1 — Risk / Correlation（6 特征，ObsDim 110）

```text
corr_pc1_share_60            60 日收益协方差矩阵第一主成分占比（市场共同因子强度）
equity_bond_corr_change_20_60  股票-国债 60 日相关 - 20 日相关（regime 转向）
equity_gold_corr_change_20_60  股票-黄金 60 日相关 - 20 日相关
cn_us_corr_60                沪深300 与美股（代理）60 日相关
equity_vol_ratio_20_60       股票 20 日波动 / 60 日波动（vol regime 位置）
equity_downside_semivol_60   股票 60 日下行半方差
```

实现依赖：全部可由现有 11 槽位研究序列内部计算（无外部数据）；`cn_us_corr_60` 需美股代理
（可复用 US_BROAD 槽位或引入标普500外部序列，须标注来源与 PIT）。

## F2 — Macro / Forward Risk（6 特征，ObsDim 110）

```text
vix_prev_close_percentile_252  VIX 前一日收盘 252 日分位（US 前一完成交易日）
vix_prev_close_change_5        VIX 前一日收盘 5 日变化
usd_cny_return_20              美元/人民币 20 日收益
cgb10y_yield_change_20         中债 10Y 收益率 20 日变化
dr007_zscore_60                银行间质押式回购 DR007 60 日 z-score
a_share_turnover_zscore_20     A 股全市场成交额 20 日 z-score
```

实现依赖：**外部数据源**（VIX / USDCNY / 10Y 国债 / DR007 / 全市场成交额）。strict PIT 要求：
- China EOD 决策（T 日收盘）只能用 **T 日及之前已发布**的数据；
- VIX 等 US 数据只能用 **T-1 前完成的 US 交易日收盘**（T 日 China 收盘时 US 当日尚未收盘）。
- 数据源需固化到本地（同 data/qmt 模式），禁止运行时抓取。

## F3 — Combined（F1 + F2，ObsDim 116）

```text
F1 6 + F2 6 = 12 新特征；ObsDim = 104 + 12 = 116 ≤ 120 ✓
```

## 冻结声明

```text
此 spec 于 GATE_4_EVAL_FIX（2026-08-09）冻结，独立于任何 Test 结果。
ablation 候选集（F1/F2/F3）在 10-seed formal 前不得因 Test 表现增删。
ablation 运行：NOT AUTHORIZED until reviewer directive。
10-seed formal 使用 F0（当前特征集）冻结，不混入 ablation 特征。
```

## 变更记录

- 2026-08-09：spec 冻结（GATE_4_EVAL_FIX，评审 §Feature-ablation preparation）。
