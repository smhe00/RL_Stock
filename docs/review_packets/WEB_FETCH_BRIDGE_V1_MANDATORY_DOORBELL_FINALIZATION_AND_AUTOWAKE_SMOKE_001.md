# Web Fetch Bridge V1 — Mandatory Doorbell Finalization + Autowake Smoke

> 评审（`docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001_REVIEWER_RESPONSE.md`）
> **ACK_TRIGGER_RACE_RECONCILIATION_ACCEPTED_MANDATORY_DOORBELL_FINALIZATION_REQUIRED** →
> 授权本 packet **WEB_FETCH_BRIDGE_V1_MANDATORY_DOORBELL_FINALIZATION_AND_AUTOWAKE_SMOKE_001**。LOCAL_PROTOCOL infrastructure only。
> handoff_id = **WEB_FETCH_BRIDGE_V1_MANDATORY_DOORBELL_FINALIZATION_AND_AUTOWAKE_SMOKE_001_001**。

```yaml
implementation_commit: 0bef3b5
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
```

## 1. 修正实现（对应评审要求）

```text
1. Claude-side 强制 handoff finalization helper: scripts/finalize_handoff.py
   - 显式 handoff id + code commit；只创建 Claude-owned claude_work_complete doorbell
   - tz-aware UTC timestamp；append-only（本地/remote 已存在即 fail closed）
   - remote 状态确认：local HEAD != origin/main（且未给 --expect-head）时 fail closed
   - 不自动 commit/push；doorbell 必须由 Claude 作为 gate 的 FINAL push
2. HANDOFF_PROTOCOL 第 6a 节文档化强制 invariant：
   - packet/status 完整 -> commit/push -> remote confirmation -> doorbell LAST
   - 适用于 READY_FOR_REVIEW / BLOCKED / TEST_FAILED
   - 不为已手动 surfaced+reviewed 的 handoff 补 late doorbell（避免重复 fetch）
3. publish_bridge_marker 并发硬化：
   - 仅 expected same-handoff append-only concurrency 重试（worktree sync + 只加不可变
     bridge marker + fast-forward，无 force-push）
   - 竞态导致 chatgpt_review_published 先于 trigger_fetch_sent -> 顺序违规 fail closed
   - unrelated/conflicting 变化不静默削弱 ownership 保证
```

## 2. 测试与 --check

```text
pytest tests/test_web_fetch_bridge.py tests/test_finalize_handoff.py -q: 58 passed
  （新增：finalize helper 创建/unsafe/bad-sha/append-only/remote-confirmation；
   publish 并发硬化 review-published-raced-ahead fail closed）
python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.example.toml --check: PASSED
```

## 3. 自动唤醒 smoke（fresh handoff）

```text
序列（严格按 finalization invariant）:
  Claude push packet/status（本 packet + CLAUDE_STATUS）        <- 前序 commit
  Claude 用 helper 创建 claude_work_complete.json doorbell LAST <- 本 handoff 的最后动作
  running daemon 从 origin/main 自动发现 doorbell（marker-only，不解析研究 YAML）
  daemon 经 CDP 提交恰好一次 `fetch <fresh_handoff_id>`（NON-OWNING）
    用户无需输入 fetch
  Web ChatGPT 收到后先 chatgpt_fetch_ack，再实质评审
  Web ChatGPT 发布评审 + chatgpt_review_published（最后）
  Claude 消费评审并发布 claude_review_ack

结果：<SMOKE_RESULT>
```

## 3b. 自动唤醒 smoke 结果 — AUTOWAKE OK, AWAITING WEB ACK

```text
序列（严格按 finalization invariant，全部执行）:
  Claude push packet/status (7aa3535)
  Claude 用 helper 创建 claude_work_complete.json doorbell LAST (4b07247, tz-aware UTC 09:18:39)
  running daemon 从 origin/main 自动发现 doorbell（marker-only）   <- 用户未输入 fetch
  daemon 经 CDP 提交恰好一次 fetch <handoff>（NON-OWNING）          <- fetch_sent 17:18:58
  daemon 发布 trigger_fetch_sent to origin/main (3cb5978)          <- 无 publish 竞态失败（硬化生效）
  等待 Web ChatGPT chatgpt_fetch_ack -> chatgpt_review_published    <- 进行中

结论: 自动唤醒链路（Claude doorbell LAST -> daemon marker-only 自动发现 -> 恰好一次
      browser-generated fetch -> trigger_fetch_sent 发布）已完整走通，无需用户输入 fetch。
```


## 4. 明确声明

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
handoff_id: WEB_FETCH_BRIDGE_V1_MANDATORY_DOORBELL_FINALIZATION_AND_AUTOWAKE_SMOKE_001_001
packet: WEB_FETCH_BRIDGE_V1_MANDATORY_DOORBELL_FINALIZATION_AND_AUTOWAKE_SMOKE_001
status: RUNNING
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY

authorization:
  decision: ACK_TRIGGER_RACE_RECONCILIATION_ACCEPTED_MANDATORY_DOORBELL_FINALIZATION_REQUIRED
  source: docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001_REVIEWER_RESPONSE.md

finalization_helper:
  claude_owned_doorbell_only: true
  explicit_handoff_and_commit: true
  tz_aware_utc: true
  append_only_fail_closed: true
  remote_confirmation_required: true
  no_auto_push: true

invariant_documented: true      # HANDOFF_PROTOCOL 6a
applies_to_readylocked_testfailed: true
no_late_doorbell_for_surfaced_handoff: true

publish_hardening:
  expected_same_handoff_concurrency_retried: true
  raced_review_published_before_trigger_fails_closed: true
  no_force_push: true
  ownership_not_weakened: true

tests: 58 passed; --check PASSED

autowake_smoke:
  fresh_handoff: true
  doorbell_pushed_last_via_helper: true
  daemon_auto_discover_from_origin_main: true
  user_does_not_type_fetch: true
  exactly_one_browser_fetch: true
  fetch_sent_published: true      # trigger_fetch_sent on origin/main (3cb5978)
  awaiting_web_ack: true          # chatgpt_fetch_ack / review_published pending

no_new_research: true
canonical_artifacts_unchanged: true
03110_stop_unchanged: true
rl_closed: true
qmt_live_forbidden: true
codex_default_disabled: true
```

## END OF WEB FETCH BRIDGE V1 MANDATORY DOORBELL FINALIZATION AND AUTOWAKE SMOKE
