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
corr_pc1_share_60              相关矩阵 PC1 占比（市场共同因子强度）
equity_bond_corr_change_20_60  corr20 - corr60（CN_LARGE vs CN_DURATION）
equity_gold_corr_change_20_60  corr20 - corr60（CN_LARGE vs GOLD）
cn_us_corr_60                  沪深300 与美股代理 60 日相关
equity_vol_ratio_20_60         股票 20 日波动 / 60 日波动
equity_downside_semivol_60     股票 60 日下行半方差
```

实现依赖：F1 全部可由现有 11 槽位研究序列内部计算（无外部数据）；`cn_us_corr_60` 用 US_BROAD
研究序列（513500.SH）作为美股代理，须标注来源与 PIT。

## F2 — Macro / Forward Risk（6 特征，ObsDim 110）

```text
vix_prev_close_percentile_252  VIX 前一完成 US 交易日收盘 252 日分位
vix_prev_close_change_5        VIX 前一完成 US 交易日收盘 5 日变化
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

## 精确公式 / As-of / Missing-Data 规则（评审 §13 要求冻结）

以下全部特征在实现前必须遵循；`r_i(t)` = 槽位 i 在 t 日对数收益（研究序列），
`Corr_w(A,B)(t)` = 截至 t 的 w 日滚动 Pearson 相关，`λ_j(Corr_w)` = Corr_w 第 j 大特征值（降序）。

### F1 公式

```text
corr_pc1_share_60(t):
    C = Corr_60 矩阵（11 槽位日对数收益，60 日滚动）
    = λ_1(C) / trace(C)            # 相关矩阵 PC1 占比（λ1 / N，N=11）
    （评审 §11：必须用相关矩阵，非协方差矩阵）

equity_bond_corr_change_20_60(t):
    = Corr_20(CN_LARGE, CN_DURATION) - Corr_60(CN_LARGE, CN_DURATION)
    （评审 §12：符号 = corr20 - corr60）

equity_gold_corr_change_20_60(t):
    = Corr_20(CN_LARGE, GOLD) - Corr_60(CN_LARGE, GOLD)
    （评审 §12：符号 = corr20 - corr60）

cn_us_corr_60(t):
    = Corr_60(CN_LARGE, US_BROAD)   # US_BROAD = 513500.SH 研究序列

equity_vol_ratio_20_60(t):
    = ann_vol_20(CN_LARGE)(t) / (ann_vol_60(CN_LARGE)(t) + eps)
    ann_vol_w = std(log ret, w 日) × √252；eps = 1e-8

equity_downside_semivol_60(t):
    downside_ret = min(r_CN_LARGE, 0) over 60 日
    = sqrt( Σ(downside_ret - mean_downside)^2 / (n_down - 1) ) × √252
    若 n_down < 2 → NaN（missing-data 规则）
```

### F2 公式

```text
vix_prev_close_percentile_252(t):
    v = VIX 收盘，取 ≤ T-1 的最近一个已完成的 US 交易日收盘
    = rank_pct(v 在最近 252 个 US 交易日中的分位，pct = (rank-1)/(252-1))

vix_prev_close_change_5(t):
    = (v_t - v_{t-5}) / v_{t-5}     # 5 个 US 交易日变化，pct 形式

usd_cny_return_20(t):
    = usdcny_t / usdcny_{t-20} - 1   # 报价 convention：USD/CNY 直接标价（1 USD = X CNY）
    # 上升 = 人民币贬值；符号方向冻结为「人民币贬值 → 正值」

cgb10y_yield_change_20(t):
    = y_t - y_{t-20}                 # 收益率单位：小数（0.01 = 1pp），Δ20 用 level 差（bp 或 pct）
    # 冻结为：yield 存小数，Δ 用「百分点」（0.01 单位）；上升 = 收益率上行

dr007_zscore_60(t):
    z = (dr007_t - mean(dr007, 60 日)) / std(dr007, 60 日)
    std=0 或 n<10 → NaN

a_share_turnover_zscore_20(t):
    z = (turnover_t - mean(turnover, 20 日)) / std(turnover, 20 日)
    turnover = A 股全市场日成交额（亿元，统一单位）；std=0 或 n<10 → NaN
```

### As-of / missing-data / normalization 统一规则

```text
as-of：所有外部特征在 China EOD 决策日 T 使用 ≤T 已发布值；US 数据用 ≤T-1 完成 US session。
rolling：window 用「截至 t 的最后 w 个可用观测」，无需连续交易日严格对齐。
missing：无数据或不足 window → NaN，参与 obs 时**不得静默 ffill**；缺缺失政策冻结为：
  - train 段缺失行排除出 scaler fit（同现 F0 warmup 语义）；
  - eval 段遇 NaN → 该特征用 train-fit 的均值填充（显式，非静默 ffill 未来值）。
  （评审 §13：无静默前向填充 unavailable publication dates。）
normalization：新特征纳入现有 train-only scaler（与 F0 一致），eval 仅 transform。
```

## 冻结声明

```text
此 spec 于 GATE_4_EVAL_FIX_CORRECTIONS（2026-08-09）冻结，独立于任何 Test 结果。
ablation 候选集（F1/F2/F3）在 10-seed formal 前不得因 Test 表现增删。
ablation 运行：NOT AUTHORIZED until reviewer directive。
10-seed formal 使用 F0（当前特征集）冻结，不混入 ablation 特征。
现有 F0 `equity_average_corr_60` 命名/语义问题（实际为全 11 槽位平均相关，非仅 equity）：
评审 §14 记录为 RFC/ablation note，**不在本轮修改 F0**（避免改变基线观测 contract）。
```

## 变更记录

- 2026-08-09（GATE_4_EVAL_FIX）：初始冻结。
- 2026-08-09（GATE_4_EVAL_FIX_CORRECTIONS）：修正 F1 `corr_pc1_share_60` → **相关矩阵** PC1
  （非协方差）；`corr_change_20_60` 符号 → **corr20 - corr60**；新增全部 12 特征精确公式 +
  as-of / missing-data / normalization 规则表（评审 §11/§12/§13）。
