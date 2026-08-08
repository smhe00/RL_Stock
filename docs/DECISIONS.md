# DECISIONS

本文档记录冻结决策与已批准变更。冻结项以 `EXECUTION_SPEC.md` 为准；此处只记录增量决策。

## 2026-08-08

### D-001 RL_Stock 作为独立仓库

- 本目录独立于 miniQMT 主工程，后续单独上传 gitee。
- 主规范复制自 ChatGPT 整理的 `FINRL_X_CHINA_ETF_EXECUTION_SPEC_V1.0.md`（原始文件保留在仓库根，作为交付物来源）。

### D-002 QMT 参考代码来源

- `docs/references/miniqmt/` 下文件复制自 miniQMT 工程 `reverse_repo/`（GC001 国债逆回购执行系统）。
- 用途：Phase 5/6 实现 `QMTBrokerAdapter` 时的连接/预检/账户绑定/行情新鲜度模式参考。
- 约束：研究核心（`src/china_etf/`）不得 import `xtquant`（EXECUTION_SPEC §50）；参考代码不做集成，仅作参考。

### D-003 初始配置草稿

- `config/` 下 YAML 依据 EXECUTION_SPEC §59/§88/§89 冻结值建立；费用类参数标记为 `pending verification`，
  Gate 1（数据审计）与 Gate 6（QMT Paper）前必须核实，不得把草案当事实。

### D-004 Gate 0 上游快照

- 固定 FinRL-X upstream snapshot：AI4Finance-Foundation/FinRL-Trading，HEAD `e65d6f0`（2026-05-02）。
- 审计结论：复用 weight contract 与 S/A/T/R 分层概念；中国 ETF 核心模块在 `src/china_etf/` 自建；
  不深度依赖 upstream 运行时（其 requirements.txt 未声明 DRL 依赖）。
- 详细证据见 `docs/review_packets/GATE_0_UPSTREAM_AUDIT.md`（待 Reviewer 批准）。
