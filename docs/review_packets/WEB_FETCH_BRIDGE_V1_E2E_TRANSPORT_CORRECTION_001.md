# Web Fetch Bridge V1 — E2E Transport Correction

> 评审（`docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_IMPLEMENTATION_REVIEWER_RESPONSE.md`）
> **WEB_FETCH_BRIDGE_V1_CORE_ACCEPTED_BUT_E2E_TRANSPORT_INCOMPLETE_CORRECTION_REQUIRED** →
> 本 packet 为 **WEB_FETCH_BRIDGE_V1_E2E_TRANSPORT_CORRECTION_001**。范围：LOCAL_PROTOCOL infrastructure only。
> handoff_id = **WEB_FETCH_BRIDGE_V1_E2E_TRANSPORT_CORRECTION_001_001**。

```yaml
implementation_commit: c977265
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
reviewed_authorization: WEB_FETCH_BRIDGE_V1_USER_AUTHORIZATION.md
```

## 1. 修正实现（评审 13 项冻结要求）

```text
1. GitHub marker 传输（GitTransport）：fetch/ls-tree/cat-file/show origin/main；
   触发 publish trigger_fetch_sent.json 至 origin/main（append-only）；远程头竞态 STOP-WRITE；
   绝不 force-push；隔离 bridge worktree（不扰动 dirty Claude worktree）
2. 自动守护（RemoteMarkerWatcher）：仅 origin/main bridge markers 发现 eligible handoff
   （claude_work_complete 存在且无 sent/ack/published）；5-10s 轮询；绝不解析研究 YAML；
   绝不调用 codex
3. Claude doorbell：claude_work_complete.json 在代码/测试/packet/status 全部远程完成后
   最后 push（本次 smoke 执行）
4. send-success/publish-failure：持久本地 dedup 状态；绝不自动重发；fail-closed 供操作员
5. CDP 目标：target_conversation_url（忽略本地配置）OR 恰好一个已打开的 chatgpt.com/c/*
   会话页自动发现（0/>1 fail-closed）；composer 实时验证 fail-closed；
   session_alive_after_disconnect 证明专用 Chrome 断连后仍可用
6. playwright Python 包本地安装（connect_over_cdp；不要求 bundled Chromium）
```

## 2. 测试与 --check

```text
pytest tests/test_web_fetch_bridge.py -q: 27 passed
  （远程 marker 发现独立于研究 YAML、无远程 work_complete 不触发、守护自动发现无需
   --handoff、远程 trigger_fetch_sent 发布、远程 ACK 观察、远程头竞态 STOP-WRITE
   publish-failure 不重发、restart dedup、tab 发现 fallback、session 存活 probe、
   marker 所有权/顺序/append-only、凭证卫生、CDP fail-closed）
python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.example.toml --check:
  PASSED（no browser, no git mutation, no codex exec）
```

## 3. E2E 冒烟（fresh，浏览器生成 fetch）

```text
序列（评审要求顺序）：
  Claude push 修正实现 + packet/status        <- 本 packet（此 commit）
  Claude push fresh claude_work_complete marker LAST（claude-owned doorbell）
  bridge daemon 从 origin/main 发现 marker
  bridge 通过 CDP 发送恰好一次 fetch <fresh_handoff_id>
  bridge 远程发布 trigger_fetch_sent marker
  Web ChatGPT 收到 fetch 后先发布 chatgpt_fetch_ack，再实质评审
  Web ChatGPT 发布评审 + chatgpt_review_published（最后）
  Claude 消费评审并发布 claude_review_ack

结果：<SMOKE_RESULT>（见下方状态；若 CDP 前置不完整则 fail-closed + 最小手动前置）
```

## 4. 所有权 / 边界

```text
✓ bridge 只写/发布 trigger_fetch_sent.json；其余 marker 只读观察
✓ bridge marker append-only；远程头竞态 STOP-WRITE；绝不 force-push
✓ 默认 bridge 模式不调用 codex exec
✓ 未提交专用会话 URL / 认证 / cookie / profile 数据（local.toml 被 *.local.toml 忽略）
✓ 绝不解析 ChatGPT 页面输出作为协议状态
```

## 5. 明确声明

```text
1. 无新金融研究/回测/数据刷新/策略或结果变更。
2. MaxDiv 120/0.5、M2、已接受 canonical artifacts/results、未解决 03110 STOP 均未改动。
3. 无交易原型 / QMT / 行情 / 账户 / 订单 / paper·forward·live。
4. PPO/SAC/TD3 与任何 RL 未重开。
5. 自动 Claude launch/restart 不作为 bridge 的一部分。
6. 研究/canonical artifacts 与策略逻辑确认未改动。
```

---

## Approval Record

```yaml
gate: LOCAL_PROTOCOL
handoff_id: WEB_FETCH_BRIDGE_V1_E2E_TRANSPORT_CORRECTION_001_001
packet: WEB_FETCH_BRIDGE_V1_E2E_TRANSPORT_CORRECTION_001
status: READY_FOR_REVIEW
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY

implementation_commit: c977265
tests: 27 passed; --check PASSED

transport:
  github_marker_transport: true    # fetch/ls-tree/publish origin/main, STOP-WRITE, no force
  autonomous_daemon: true          # marker-only origin/main discovery, 5-10s poll, no codex
  claude_doorbell: true            # claude_work_complete pushed LAST (fresh smoke handoff)
  trigger_fetch_sent_remote_publish: true  # bridge publishes append-only to origin/main
  remote_ack_observation: true     # chatgpt_fetch_ack/review_published from refreshed origin/main
  send_success_publish_failure_fail_closed: true  # durable dedup, NO auto-resend
  dirty_worktree_safe: true        # isolated bridge worktree; never mutates Claude worktree

cdp:
  endpoint: http://127.0.0.1:9222 (localhost only)
  profile: C:\ChatGPT_Automation_Profile
  target: ignored local URL OR exact-one-open chatgpt.com/c/* tab (0/>1 fail-closed)
  composer: live-verify fail-closed (input-only; no assistant-output parsing)
  session_lifetime: session_alive_after_disconnect probe

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

## END OF WEB FETCH BRIDGE V1 E2E TRANSPORT CORRECTION
