# Web Fetch Bridge V1 — ACK/Trigger Race Reconciliation

> 评审（`docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001_REVIEWER_RESPONSE.md`）
> **E2E_BROWSER_FETCH_SUCCEEDED_COMPOSER_FIX_ACCEPTED_ACK_TRIGGER_RACE_CORRECTION_REQUIRED** →
> 授权本 packet **WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001**。LOCAL_PROTOCOL infrastructure only。
> handoff_id = **WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001_001**。

```yaml
implementation_commit: f5fc5f7
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
```

## 1. 背景

```text
首次真实浏览器 fetch 成功（composer 修正被接受）。E2E 暴露 marker 传输固有竞态：
  browser 提交成功 -> Web ChatGPT 立即发 chatgpt_fetch_ack -> bridge 再发
  trigger_fetch_sent；原 publish_bridge_marker 拒绝任何期间 remote-head 变化 ->
  reviewer ACK 合法提交会导致 trigger_fetch_sent 发布失败（即便发送已成功）。
当前 remote handoff 含 claude_work_complete + chatgpt_fetch_ack，但缺 trigger_fetch_sent。
浏览器消息不得重发（ACK 已证明收到）。
```

## 2. 修正实现（marker-only，无浏览器动作）

```text
1. GitTransport.publish_bridge_marker：发布前把隔离 bridge worktree sync 到最新
   origin/main（reset --hard），marker commit 成为 fast-forward；容忍同 handoff
   expected append-only reviewer marker（re-fetch 最新 + 重试限次，绝不 force-push）；
   意外/冲突 remote 变化保持 fail-closed
2. marker-only reconciliation：当 durable local fetch_sent + matching
   chatgpt_fetch_ack 存在且 trigger_fetch_sent 缺失 -> 发布缺失 bridge marker；
   绝不触碰浏览器、绝不发送；daemon scan 自动 + CLI --reconcile-fetch-sent 单次
3. event-field 兼容：marker filename/existence 为权威；event 值兼容 filename-style
   （chatgpt_fetch_ack.json）与语义别名（CHATGPT_FETCH_ACK），不重写已有 marker
```

## 3. 测试与 --check

```text
pytest tests/test_web_fetch_bridge.py -q: 52 passed（新增 7 项）：
  event 语义别名兼容（CHATGPT_FETCH_ACK 接受 / 未知 event 拒绝）
  ACK 存在时 reconcile 发布缺失 trigger（无 browser 调用）
  无 ACK 时 reconcile 等待不发布
  duplicate/append-only：remote 已有 trigger -> ALREADY_PUBLISHED 不覆盖
  无本地 fetch_sent -> 不 reconcile（不触发浏览器）
  真实 git 集成：worktree sync + 并发 reviewer ACK 下 publish 成功（fast-forward）
  真实 git 集成：重复 publish 拒绝（append-only）
python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.example.toml --check: PASSED
```

## 4. Reconciliation 执行（当前 handoff）

```text
handoff: WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001_001
条件:  durable local fetch_sent (dedup.json) ✓
       matching chatgpt_fetch_ack on origin/main (bbd3070) ✓
       trigger_fetch_sent missing on origin/main ✓
动作:  publish 缺失 trigger_fetch_sent（仅 marker，无浏览器）
结果:  <RECONCILE_RESULT>
```

## 5. 所有权 / 边界

```text
✓ reconciliation 只发布缺失 bridge-owned trigger_fetch_sent；绝不触碰浏览器
✓ 不重发当前 handoff；不发送任何新浏览器 fetch
✓ 保留成功的 browser E2E 结果
✓ append-only；远程 head 变化 STOP-WRITE；绝不 force-push
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
handoff_id: WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001_001
packet: WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001
status: RUNNING
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY

authorization:
  decision: E2E_BROWSER_FETCH_SUCCEEDED_COMPOSER_FIX_ACCEPTED_ACK_TRIGGER_RACE_CORRECTION_REQUIRED
  source: docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001_REVIEWER_RESPONSE.md

race_correction:
  worktree_sync_before_publish: true
  same_handoff_reviewer_marker_tolerated: true
  never_force_push: true
  unexpected_remote_change_fail_closed: true

reconciliation:
  marker_only: true          # never touches browser
  no_browser_fetch_sent: true
  publish_only_missing_trigger: true
  requires_durable_local_send_success: true
  requires_matching_ack: true
  duplicate_append_only_safe: true

event_field:
  filename_authoritative: true
  filename_style_accepted: true
  semantic_alias_accepted: true   # e.g. CHATGPT_FETCH_ACK
  no_immutable_marker_rewrite: true

tests: 52 passed; --check PASSED

reconcile_handoff: WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001_001
reconcile_result: <RECONCILE_RESULT>

no_new_research: true
canonical_artifacts_unchanged: true
03110_stop_unchanged: true
rl_closed: true
qmt_live_forbidden: true
codex_default_disabled: true
```

## END OF WEB FETCH BRIDGE V1 ACK TRIGGER RACE RECONCILIATION
