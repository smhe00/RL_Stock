# Gate 0 Corrections

## 1. Reviewer decision

`GATE_0_STATUS = APPROVED_WITH_REQUIRED_CORRECTIONS`（2026-08-08）。

## 2. Required Corrections Checklist — 落实记录

- [x] "TD3 不存在" → "TD3 legacy helper 存在（`rl_model.py:175 train_td3()`），但当前未启用为正式 FinRL-X allocator"。
- [x] 增加 `train_td3()` / commented `run_models()` 状态说明（`rl_model.py:265-266` 注释；实际启用 A2C/PPO/DDPG）。
- [x] 删除 "Backtest 与 Live 共享同一 concrete `StrategyResult.weights` schema" 表述。
- [x] 明确 TradeExecutor long-form `gvkey/weight`（`trade_executor.py:245-246`）与 BacktestEngine wide-form `date×ticker`（`backtest_engine.py:132`）的 schema mismatch。
- [x] 增加本项目 `TargetAssetWeights` canonical contract 决策（D-005）。
- [x] 增加 Backtest / Execution Adapter 决策（`to_backtest_frame()` / `FinRLXStrategyAdapter`）。
- [x] 记录三个版本口径：GitHub release `v1.0.0`（2026-03-25, commit `0b5b4235`）、master `e65d6f0`（2026-05-02）、`setup.py version=2.0.2`。
- [x] 补充 dependency gap：`finrl` / `stable-baselines3` / `gymnasium` / `pypfopt` 声明情况（requirements 与 setup extras 均不足以复现 DRL path）。
- [x] 增加 "upstream DRL path（fundamental_portfolio_drl / rl_model）不是正式 BaseStrategy allocator" 说明。
- [x] 增加 `quote failure → FAIL CLOSED` 安全规则（D-006）；上游 `_get_current_price` 失败返回默认 `100.0`（`trade_executor.py:394-404`、`alpaca_manager.py:507/575`）为禁止行为。
- [x] 明确 upstream BacktestEngine 仅 reference / compatibility（D-008），不作为中国 ETF 正式 OOS Source of Truth。
- [x] 更新 `CODEX_AGENT_STATUS.md` 为 Gate 0 approved-with-corrections / corrections complete。

## 3. Changed files

- `docs/review_packets/GATE_0_UPSTREAM_AUDIT.md`（§1/§3/§5/§6/§14 修正）
- `docs/upstream/FINRL_X_UPSTREAM_SNAPSHOT.md`（版本口径、依赖、TD3/DRL 状态）
- `docs/DECISIONS.md`（D-005 ~ D-008）
- `docs/CODEX_AGENT_STATUS.md`
- 新增本文件 `GATE_0_CORRECTIONS.md`

## 4. Commit SHA

`904d388`

## 5. Gate 1 authorization

```text
GATE 1 AUTHORIZED
permission: Data & Universe Audit only
禁止: PortfolioEnv / CostModel / RiskOverlay / 训练 RL / 调参 / QMT 下单 / 改 Frozen Slots
```
