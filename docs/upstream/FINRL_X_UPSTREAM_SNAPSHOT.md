# FinRL-X Upstream Snapshot

> 按 EXECUTION_SPEC §3 记录。观察日期：2026-08-08（Agent 实际拉取）。

## 版本记录

```yaml
finrl_x:
  repository: AI4Finance-Foundation/FinRL-Trading
  name: FinRL-X
  github_latest_release: v1.0.0            # "FinRL-X: Initial Public Release" (2026-03-25, 已核实)
  github_release_commit: 0b5b4235640e74cd6e59f374bb13b3779e898e57
  github_release_commit_date: 2026-03-25 10:13:15 +0800
  head_ahead_of_release_commits: 1         # HEAD 仅领先 v1.0.0 一个提交
  latest_check_2026_08_08: master unchanged (e65d6f0, 2026-05-02); tags=[v1.0.0]
  branch: master
  head_commit: e65d6f0483ead7d2ef4a5fc940cdf960392a25c1
  head_date: 2026-05-02 23:12:36 +0800
  head_subject: Update ml_bucket_selection.py
  package_metadata_version: 2.0.2          # setup.py:27（与 release tag 不同口径）
  clone_mode: shallow (depth=1)
  paper: "FinRL-X: An AI-Native Modular Infrastructure for Quantitative Trading"
  arxiv: "2603.21330"
  python: "3.11+ (README badge)"
  observed_date: 2026-08-08
```

> 版本口径说明：`github_latest_release`（v1.0.0, 2026-03-25）、`audited_commit`（master, 2026-05-02）、
> `package_metadata_version`（setup.py 2.0.2）三者不同；项目 reproducibility 以 `audited_commit` 为准。

## 依赖情况（requirements.txt 事实）

- 锁定方式：未锁定精确版本（`numpy>=...`、`pandas>=...` 等区间）。
- **关键缺口**：DRL 相关依赖（`finrl`、`stable-baselines3`、`gymnasium`、`gym`）不在 requirements.txt 中。
- `setup.py` extras 声明了 `gymnasium>=0.29.0` 与 `stable-baselines3>=2.1.0`（`setup.py:80-81/91-92`），
  但**未声明 `finrl` 与 `pypfopt`**。
- 因此 **requirements 与 setup extras 均不足以完整复现现有 `fundamental_portfolio_drl.py` / `rl_model.py` 路径**。
- DRL 代码（`src/strategies/fundamental_portfolio_drl.py`、`rl_model.py`）实际 import 经典 `finrl` 包
  （`finrl.agents.stablebaselines3.models.DRLAgent`、`finrl.meta.env_portfolio_allocation.env_portfolio.StockPortfolioEnv`），
  因此干净安装后按 README 无法直接跑通 DRL 路径；且代码内含 monkey-patch（`_safe_DRL_prediction` 修复 vec env 提前结束）。

## TD3 / DRL path 状态（Gate 0 修正后事实）

- `rl_model.py:175` 存在 `train_td3()` legacy helper（`get_model("td3")` → 经典 FinRL DRLAgent → SB3 TD3）。
- `run_models()` 中 `#td3_model = train_td3(agent)` / `#sac_model = train_sac(agent)` 被注释（`:265-266`）；
  实际启用 A2C / PPO / DDPG。
- `fundamental_portfolio_drl.py` / `rl_model.py` 属于较老/独立的 DRL workflow，
  **未实现 `BaseStrategy.generate_weights()` contract**，不能假设 README 的 "DRL Allocator" 等于
  contract-compliant 实现。本项目统一 allocator layer 由此而来。

## 架构事实（审计证据）

| 层 | 上游实现 | 位置 |
|---|---|---|
| Strategy contract | `BaseStrategy.generate_weights(data: Dict[str, pd.DataFrame], target_date=None) -> StrategyResult` | `src/strategies/base_strategy.py:26` |
| 输出对象 | `StrategyResult{strategy_name, weights: pd.DataFrame, metadata}` | `src/strategies/base_strategy.py:8` |
| Stock Selection (S) | ML 股票选择（Random Forest、bucket selection） | `src/strategies/ml_strategy.py`、`ml_bucket_selection.py`、`ML_STOCK_SELECTION.md` |
| Portfolio Allocation (A) | 经典 FinRL DRLAgent + StockPortfolioEnv（PPO/SAC/DDPG/A2C）；pypfopt Equal/MinVar/MV | `fundamental_portfolio_drl.py`、`rl_model.py`、`ml_strategy.py` |
| Timing (T) | KAMA timing（README Use Case 1 提及） | README |
| Risk (R) | 组合级 RiskOverlay 缺失；仅 adaptive_rotation 个股止损 + TradeExecutor 风控检查 | `adaptive_rotation/risk_manager.py`、`trade_executor.py` |
| Backtest | `bt` 库；flat transaction_cost=0.001；benchmark SPY/QQQ；可选 AlmgrenChriss cost model | `src/backtest/backtest_engine.py:46` |
| Broker | `AlpacaManager`（alpaca-py 封装，多账户/订单/再平衡） | `src/trading/alpaca_manager.py:75` |
| Walk-Forward | 存在于 adaptive_rotation（point-in-time 切片） | `src/strategies/adaptive_rotation/walk_forward.py` |
| Execution | `ExecutionManager`（再平衡频率/最小权重阈值/目标权重） | `src/strategies/execution_engine.py` |
| Data | FMP > WRDS > Yahoo；SQLite `finrl_trading.db` | `src/data/data_fetcher.py`、`data_store.py` |
| Tests | 仓库根无 tests/ 目录 | — |

### 安全反面教材（禁止复制）

- `trade_executor.py:394-404` `_get_current_price()` 在行情失败时返回默认 `100.0`；
  `alpaca_manager.py:507/575` 同样存在 `price = 100.0` fallback。
- 本项目规则（D-006）：`quote missing / stale → NO ORDER（FAIL CLOSED）`，禁止发明默认价格。

## 结论

上游是 **US 市场权重合同平台**：weight-centric 合同（`StrategyResult.weights`）与概念分层（S/A/T/R）
可复用；但数据源、回测语义、执行券商、DRL 依赖均不适合直接用于中国 ETF，需在 `src/china_etf/` 自建。
