# Web Fetch Bridge V1 — Fail-Closed + True E2E Retry

> 评审（`docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_E2E_TRANSPORT_CORRECTION_001_REVIEWER_RESPONSE.md`）
> **WEB_FETCH_BRIDGE_V1_TRANSPORT_CORE_ACCEPTED_E2E_RETRY_AND_FAIL_CLOSED_FIX_REQUIRED** →
> 本 packet 为 **WEB_FETCH_BRIDGE_V1_FAIL_CLOSED_AND_TRUE_E2E_RETRY_001**。LOCAL_PROTOCOL infrastructure only。
> handoff_id = **WEB_FETCH_BRIDGE_V1_FAIL_CLOSED_AND_TRUE_E2E_RETRY_001_001**。

```yaml
implementation_commit: 90264e3
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
```

## 1. 修正实现（评审 4 项）

```text
1. Send 失败终态：daemon 持久化本地 attempt-failure 记录，绝不自动重试；
   显式操作员 --retry-handoff 恰好清除一次；trigger_fetch_sent 仅在真正提交 fetch 后创建
2. 时区感知时间戳：marker 校验要求 ISO-8601 带 offset（拒绝 naive/无 offset）；
   fresh doorbell 用 tz-aware UTC 时钟生成
3. Playwright 生命周期显式：存储 sync_playwright() driver、断连后 stop、绝不关闭/导航无关
   tab；target_tab_preserved_after_failed_attempt + session_alive_after_disconnect probe
4. 真 E2E 冒烟（fresh handoff，daemon 自动发现）
```

## 2. 测试与 --check

```text
pytest tests/test_web_fetch_bridge.py -q: 33 passed
  （send-failure no-auto-retry、explicit-retry clears once、失败时无 trigger_fetch_sent、
   时区验证 naive/offsetless 拒绝、session/tab probe、远程发现/发布/ACK/竞态/dedup/
   所有权/顺序/append-only）
python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.example.toml --check:
  PASSED
```

## 3. E2E 冒烟（fresh）

```text
序列：
  Claude push 修正实现 + packet/status            <- 本 packet（此 commit）
  Claude push fresh claude_work_complete marker LAST（tz-aware UTC 时间戳）
  bridge daemon 从 origin/main 自动发现
  bridge 通过 CDP 发送恰好一次 fetch <fresh_handoff_id>
  bridge 远程发布 trigger_fetch_sent marker
  Web ChatGPT 收到后先 chatgpt_fetch_ack，再实质评审
  Web ChatGPT 发布评审 + chatgpt_review_published（最后）
  Claude 消费评审并发布 claude_review_ack

结果：<SMOKE_RESULT>
```

## 4. 所有权 / 边界

```text
✓ bridge 只写/发布 trigger_fetch_sent.json；其余 marker 只读观察
✓ send 失败持久终态；绝不自动重试；显式操作员重试唯一
✓ trigger_fetch_sent 仅在真正提交后创建
✓ 远程头竞态 STOP-WRITE；绝不 force-push；隔离 bridge worktree
✓ 默认不调用 codex；不解析研究 YAML / ChatGPT 页面输出
✓ 未提交会话 URL / 认证 / cookie / profile 数据
```

## 5. 明确声明

```text
1. 无新金融研究/回测/数据刷新/策略或结果变更。
2. MaxDiv 120/0.5、M2、已接受 canonical artifacts/results、未解决 03110 STOP 均未改动。
3. 无交易原型 / QMT / 行情 / 账户 / 订单 / paper·forward·live。
4. PPO/SAC/TD3 与任何 RL 未重开。
5. 自动 Claude launch/restart 不作为 bridge 一部分。
6. 研究/canonical artifacts 与策略逻辑确认未改动。
```

---

## Approval Record

```yaml
gate: LOCAL_PROTOCOL
handoff_id: WEB_FETCH_BRIDGE_V1_FAIL_CLOSED_AND_TRUE_E2E_RETRY_001_001
packet: WEB_FETCH_BRIDGE_V1_FAIL_CLOSED_AND_TRUE_E2E_RETRY_001
status: READY_FOR_REVIEW
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY

implementation_commit: 90264e3
tests: 33 passed; --check PASSED

fail_closed:
  send_failure_terminal: true      # daemon never auto-retries a failed browser attempt
  operator_retry_only: true        # --retry-handoff clears terminal failure exactly once
  trigger_fetch_sent_absent_on_failure: true  # marker only after real submission

timestamp:
  timezone_aware_required: true    # naive / offsetless rejected by validation
  fresh_doorbell_tz_utc: true      # fresh claude_work_complete uses tz-aware UTC clock

playwright_lifecycle:
  driver_explicit_stop: true       # sync_playwright().start() stored + .stop() after detach
  unrelated_tabs_untouched: true   # never closes/navigates tabs other than target
  session_alive_probe: true        # session_alive_after_disconnect
  target_tab_preserved_probe: true # target_tab_preserved_after_failed_attempt

e2e_smoke:
  ran: <SMOKE_RAN>
  result: <SMOKE_RESULT>
  minimal_manual_prerequisite: <SMOKE_PREREQ>

no_new_research: true
canonical_artifacts_unchanged: true
03110_stop_unchanged: true
rl_closed: true
qmt_live_forbidden: true
codex_default_disabled: true
```

## END OF WEB FETCH BRIDGE V1 FAIL-CLOSED AND TRUE E2E RETRY
