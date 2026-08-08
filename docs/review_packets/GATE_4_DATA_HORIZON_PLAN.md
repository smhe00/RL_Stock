# Gate 4 Data Horizon Plan（Reviewer §29-§31）

## 问题

11 Core 真实 ETF 的共同有效观测起点为 **2022-05-18**（CASH_LIKE 2020-09 上市 + HK_TECH 2021-05 上市 + 252 日 warm-up），
至 2026-08-07 仅约 **4.2 年**。对 10~20 seeds / walk-forward / 多 regime 而言样本极短，
不足以单独支撑"长期 RL Alpha"结论。

## 三个候选轨

### Track A — Real Instrument OOS（严格可执行）

```text
数据：11 只真实 ETF 共同有效历史（2022-05-18 → 2026-08-07，~1040 交易日）
性质：最接近真实 ETF 可执行性；样本短、regime 少、fold 少
结论口径：REAL-INSTRUMENT OOS / limited-history
```

### Track B — Point-in-Time Proxy Method Research（需先关 C2）

```text
数据：经 launch-date / backfill 审计、当时真实可获得的指数代理（每条 proxy 记录
      index_base_date / index_launch_date / data_series_start / is_backfilled_before_launch）
性质：延长 Method Research 历史；禁止 pre-launch backfilled 冒充 PIT
前置：C2（proxy PIT audit）必须完成
```

### Track C — Scenario Proxy Research

```text
数据：允许更长的 retrospective/backfilled proxy
性质：SCENARIO，非 strict PIT OOS；用于机制/方法研究
结论口径：明确标注 not strict PIT OOS
```

## 推荐：双轨结论

```text
Method / Scenario Long-History Study（Track B/C，研究"算法能否学会配置"）
  +
Real-ETF Short-History OOS Study（Track A，研究"具体 ETF 是否可执行"）
```

与 `Asset Slot != Instrument` 架构一致：算法长期有效性（Slot 层面）与 ETF 可执行性（Instrument 层面）分开论证。

## Gate 4 执行建议（待 Reviewer 批准）

1. 先完成 C2 proxy 审计（Track B 启用）与 F1 历史费率规则；
2. 主实验 = Track A 真实 ETF 短历史 OOS（10 seeds、walk-forward、1x/2x/3x 成本）；
3. 辅证 = Track C 长历史 Scenario（不进入严格 OOS 结论）。
