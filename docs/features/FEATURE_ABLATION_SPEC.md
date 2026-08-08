# Feature Ablation Spec — FROZEN（GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS）

> 评审（`GATE_4_3_SEED_PILOT_REVIEWER_RESPONSE.md` §Feature-ablation preparation +
> `GATE_4_FEATURE_ABLATION_PREP_REVIEWER_RESPONSE.md` P1-P5）：
> **spec 冻结 now**；ablation **runs NOT yet authorized**。
> 本 spec 是 canonical formula source（评审 P4：spec 与代码不得不一致），实现以 spec 为准。

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
    = sqrt(252 · mean( min(r_CN_LARGE, 0)^2 over 60 obs ))     # F-A1：LPM2 around zero
    （评审 §5：lower partial second moment，非负收益子集标准差；
     同时保留下行幅度与下行频率）
```

### F2 公式（native-calendar-first；评审 P1/P2/P3）

**架构（P1）**：每个源在**原生观测日历**上算窗口特征（rolling/shift 用源观测计数），
再 PIT as-of 对齐到 China 决策日。**禁止**先 ffill 到 China 日历再算窗口（会改变 5/252 session 计数）。

```text
通用流程（每源）:
  native 源 Series（index = 源观测日/available_at）
  → 在 native index 上算窗口特征（rolling/shift 用源观测计数）
  → 得到 native 衍生 Series
  → align_derived_to_china(derived_native, china_index, rule)

vix_prev_close_percentile_252(t):
    native：在 US session 日历上，最近 252 个 US 观测的 percentile
    pct = (rank - 1) / (N - 1)      # N=252；rank=1-based average rank（ties 取平均）
    rule = "strict_prev_session"    # 仅取 available_at < China 决策日 t（前一完成 US session）
    （评审 P2/P3）

vix_prev_close_change_5(t):
    native：vix.pct_change(5)       # 5 个 US session
    rule = "strict_prev_session"

usd_cny_return_20(t):
    native：usd / usd.shift(20) - 1   # 20 个源观测；直接标价（升=人民币贬值→正）
    rule = "asof"（≤ t）

cgb10y_yield_change_20(t):
    native：cgb - cgb.shift(20)       # 20 个源观测 level 差（yield 存小数，Δ 用百分点 0.01 单位）
    rule = "asof"

dr007_zscore_60(t):
    native：(dr - roll60_mean) / (roll60_std + eps)   # 60 个源观测
    rule = "asof"

a_share_turnover_zscore_20(t):
    native：(to - roll20_mean) / (roll20_std + eps)   # 20 个源观测；成交额亿元
    rule = "asof"
```

**Availability-time PIT 契约（P2）**：

```text
首选：每 macro 观测带 available_at 时间戳（timezone-aware）；China 决策有 decision_at；
      as-of 要求 available_at <= decision_at。
date-only 最低要求：US session date < China 决策日历日期（严格早于，非 <=）——
      same-calendar-date US close 对 China close 不可见。
测试覆盖：same-date US close 不可见 / US holiday / China holiday / weekend / DST 日期。
```

### As-of / missing-data / normalization 统一规则（评审 P5 更新）

```text
as-of：全部 F2 特征在 native 日历算好后再对齐；VIX 用 strict_prev_session，其余 asof。
rolling：window = 源原生「最近 w 个可用观测」，不按 China 日数。
missing：无数据或不足 window → NaN；任何模型观测（TRAIN/VALIDATION/TEST）进入模型前
  必须 finite——用 F-A2 train-only imputation（评审 P4）：
    1. impute 均值与 scaler 统计只从 TRAIN 估计（忽略 NaN）；
    2. TRAIN 内零星 NaN：忽略于统计估计、以 TRAIN 均值 impute；
    3. VALIDATION/TEST：只 transform（impute→scale），绝不更新统计；
    4. imputed ≈ normalized 0；
    5. 绝不用 val/test 统计、绝 backward-fill 未来发布值；
    6. train 区某特征无可用观测 → fail-closed（raise），不制造值。
normalization：新特征纳入 FeaturePreprocessor（train-only）。**ddof=1（sample std）**
  与 legacy F0 pandas scaler 一致（评审 P5），保证 ablation 同 F0 transform + 额外特征，
  不改变 F0 基线观测语义。常量特征保护（std≈0 → std=1，mean 中心）保留。
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
- 2026-08-09（GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS）：同步已批准代码契约（评审 P1-P5）：
  F-A1 `downside_semivol` = LPM2 around zero；F-A2 train-only imputation 覆盖所有模型观测；
  F2 **native-calendar-first**（源日历算窗口 → as-of 对齐 China）+ availability-time PIT 契约 +
  VIX 前一完成 US session（strict_prev）；VIX 分位 = **(rank-1)/(N-1)**（ties average rank）；
  FeaturePreprocessor **ddof=1**（F0 legacy parity）。spec = canonical formula source。
