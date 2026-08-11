# Web Fetch Bridge V1 — No-Op Lifecycle Diagnostic + Non-Owning CDP

> 评审（`docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_FAIL_CLOSED_AND_TRUE_E2E_RETRY_001_REVIEWER_RESPONSE.md`）
> **WEB_FETCH_BRIDGE_V1_FAIL_CLOSED_CORE_ACCEPTED_BROWSER_LIFECYCLE_DIAGNOSTIC_REQUIRED** →
> 本 packet 为 **WEB_FETCH_BRIDGE_V1_NOOP_LIFECYCLE_DIAGNOSTIC_AND_NONOWNING_CDP_001**。LOCAL_PROTOCOL infrastructure only。
> handoff_id = **WEB_FETCH_BRIDGE_V1_NOOP_LIFECYCLE_DIAGNOSTIC_AND_NONOWNING_CDP_001_001**。

```yaml
implementation_commit: 31409eb
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
```

## 1. 修正实现（评审 10 项）

```text
1. NoopLifecycleDiagnostic：attach connect_over_cdp >=30s；NO click/type/navigate/create/
   close page/context/browser；before/after DevTools /json target 元数据（URL/title 仅诊断，
   绝不读 ChatGPT 输出）；target 必须存在且不变；->home = STOP 环境/CDP 问题（无导航修复）
2. 诊断要求专用 target URL（忽略本地配置）；诊断不使用 exact-one /c/* 发现
3. sender 重构 NON-OWNING：绝不 page.goto/new_page/page.close/context.close/browser.close；
   配置 target 必须已存在且精确匹配，否则终态 fail-closed（无发现 fallback）
4. daemon 长驻：单条长活 Playwright/CDP 连接归 daemon；仅 daemon 退出时 stop driver
5. 两次 no-op 探针均通过后才尝试 fresh E2E
```

## 2. 测试与 --check

```text
pytest tests/test_web_fetch_bridge.py -q: 36 passed
  （noop 需 URL/非 home、noop target 缺失 fail-closed、sender 绝不 close/goto/new_page、
   非 localhost fail-closed、send-failure 终态、显式重试、时区验证、session/tab probe、远程
   发现/发布/ACK/竞态/dedup/所有权/顺序/append-only）
python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.example.toml --check: PASSED
```

## 3. No-Op 生命周期诊断（两次均 PASS）

```text
probe 1: PASS target=https://chatgpt.com/c/6a78742a-f90c-83ee-9761-3bd204d8ace0 hold_s=30
  （before/after DevTools 元数据一致；无页面变化）
probe 2（refactor 后）: PASS 同上
→ 生命周期中立性证明：dedicated Chrome 会话 + target tab 在纯 no-op 下保持
```

## 4. E2E 冒烟（fresh，第三次授权后）

```text
序列：
  Claude push 修正实现 + packet/status            <- 本 packet（此 commit）
  Claude push fresh claude_work_complete marker LAST（tz-aware UTC）
  bridge daemon 从 origin/main 自动发现
  bridge 通过 CDP 发送恰好一次 fetch <fresh_handoff_id>（NON-OWNING）
  bridge 远程发布 trigger_fetch_sent marker
  Web ChatGPT 收到后先 chatgpt_fetch_ack，再实质评审
  Web ChatGPT 发布评审 + chatgpt_review_published（最后）
  Claude 消费评审并发布 claude_review_ack

结果：<SMOKE_RESULT>
```

## 5. 所有权 / 边界

```text
✓ bridge 只写/发布 trigger_fetch_sent.json；其余 marker 只读观察
✓ NON-OWNING：绝不管理 browser/page lifecycle；仅 stop 自属 Playwright driver
✓ 配置 target 必须已存在且精确匹配，否则终态 fail-closed
✓ send 失败持久终态；绝不自动重试；显式操作员重试唯一
✓ 远程头竞态 STOP-WRITE；绝不 force-push；隔离 bridge worktree
✓ 默认不调用 codex；不解析研究 YAML / ChatGPT 页面输出
✓ 未提交会话 URL / 认证 / cookie / profile 数据
```

## 6. 明确声明

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
handoff_id: WEB_FETCH_BRIDGE_V1_NOOP_LIFECYCLE_DIAGNOSTIC_AND_NONOWNING_CDP_001_001
packet: WEB_FETCH_BRIDGE_V1_NOOP_LIFECYCLE_DIAGNOSTIC_AND_NONOWNING_CDP_001
status: READY_FOR_REVIEW
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY

implementation_commit: 31409eb
tests: 36 passed; --check PASSED

noop_lifecycle:
  probe1_pass: true
  probe2_pass: true                # both after NON-OWNING refactor
  target: https://chatgpt.com/c/6a78742a-f90c-83ee-9761-3bd204d8ace0
  hold_seconds: 30
  target_preserved: true           # unchanged before/after (DevTools metadata)

nonowning_cdp:
  never_goto: true
  never_new_page: true
  never_page_close: true
  never_context_close: true
  never_browser_close: true        # verified by test + code audit
  target_must_exist_exact: true    # missing/mismatch terminal fail-closed
  daemon_long_lived_connection: true  # driver stopped only on daemon exit

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

## END OF WEB FETCH BRIDGE V1 NO-OP LIFECYCLE DIAGNOSTIC AND NON-OWNING CDP
