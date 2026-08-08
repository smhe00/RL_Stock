# RL_Stock — FinRL-X 中国 ETF 多资产强化学习配置与实盘系统

独立仓库。主执行规范（Source of Truth）见 [docs/EXECUTION_SPEC.md](docs/EXECUTION_SPEC.md)。

## 项目一句话

基于 FinRL-X（weight-centric）构建 A股/港股通 ETF 多资产动态配置系统，
在严格 Walk-Forward OOS、真实交易成本、多随机种子下对照 TD3 / SAC / PPO，
并最终通过 QMT / miniQMT Paper Trading 与小额实盘验证。

## 冻结核心（详见 EXECUTION_SPEC §87）

- 主框架：FinRL-X（AI4Finance FinRL-Trading）；算法：TD3 / SAC / PPO（Stable-Baselines3）
- 资产：11 个核心 Asset Slot + 5 个政策主题候选（激活 0~2 只）
- RL 输出固定维度权重（Phase 1 = 11，Phase 2 = 12，引入 THEME_SLEEVE），不学 ETF 代码
- 佣金：单边万 0.5（`0.00005`），总成本 = 佣金 + 交易所费 + 税 + 价差 + 滑点 + 冲击 + FX
- 执行语义：T 日收盘决策 → T+1 开盘成交；禁止同日收盘成交；禁止随机切分
- 门禁制：Gate 0 → Gate 7，每个 Gate 产出 Review Packet 后 STOP，等待人工/ChatGPT 复核

## 目录速览

```text
docs/            EXECUTION_SPEC / DECISIONS / CODEX_AGENT_STATUS / Review Packets / RFC
config/          universe / risk / execution / features / fees / algorithms
src/china_etf/   研究核心（不 import xtquant）
references/      （见 docs/references/miniqmt）QMT 模拟/实盘参考代码
```

## 当前状态

见 [docs/CODEX_AGENT_STATUS.md](docs/CODEX_AGENT_STATUS.md)。
首个执行动作：Gate 0 — FinRL-X upstream architecture audit（EXECUTION_SPEC §93）。
