# QMT / miniQMT 参考代码（来自 reverse_repo）

## 来源

以下文件复制自 miniQMT 工程 `reverse_repo/`（GC001 国债逆回购执行系统），
源仓库 commit/日期见拷贝时记录。**仅作参考，不参与构建，不进 `src/`。**

## 文件清单与用途

| 文件 | 内容 | 对 ETF 项目的用途 |
|---|---|---|
| `repo_execution_core.py` | QMT 连接、账户绑定、行情盘口校验、订单状态等核心执行工具 | 抽取 `QMTBrokerAdapter` 的连接/校验模式 |
| `bootstrap_repo_account_binding.py` | 账户绑定流程（QMT 路径 + 账户 ID 指纹） | 实盘账户绑定设计参考 |
| `repo_live_channel_validation.py` | 实盘通道预检（连接、订阅、资产、订单、行情新鲜度） | Gate 6 实盘 preflight 参考 |
| `repo_simulation_validation.py` | 模拟环境（模拟 QMT 路径）校验 | Gate 6 Paper/模拟环境参考 |
| `qmt_realtime_trading_pitfalls.md` | 实盘踩坑记录 | Gate 6 审查清单素材 |
| `reverse_repo_state_machines.md` | 任务状态机设计 | 执行/对账状态机参考 |
| `runtime.example.json` | 运行时配置示例（模拟/实盘路径切换） | `config/execution.yaml` 扩展参考 |

## 关键模式（可复用到 ETF 项目）

1. **惰性 import**：`xtquant` 只在函数内部 import，顶层不依赖 → 满足 EXECUTION_SPEC §50。
2. **模拟/实盘路径分离**：通过不同 QMT `userdata_mini` 路径区分环境。
3. **preflight 检查**：下单前强制检查连接、账户、行情新鲜度。
4. **行情新鲜度校验**：quote age / stale data 检查，避免用旧价成交。

## 注意

- 这些代码面向逆回购（GC001/R001），费率、合约、交易时间与 ETF 不同，不得直接照搬下单逻辑。
- 港股通 ETF（如 03110.HK）的 QMT 支持度必须在 Gate 6 前做 `BrokerCapabilityAudit`（EXECUTION_SPEC §18）。
