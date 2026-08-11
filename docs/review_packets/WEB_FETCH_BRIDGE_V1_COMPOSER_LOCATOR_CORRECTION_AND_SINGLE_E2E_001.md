# Web Fetch Bridge V1 — Composer Locator Correction + Single E2E

> 评审（`docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_SINGLE_TRUE_E2E_FETCH_001_REVIEWER_RESPONSE.md`）
> **E2E_FAIL_CLOSED_ACCEPTED_COMPOSER_LOCATOR_CORRECTION_AUTHORIZED** →
> 授权本 packet **WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001**。LOCAL_PROTOCOL infrastructure only。
> handoff_id = **WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001_001**。

```yaml
implementation_commit: e7c0d1c
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
```

## 1. 修正实现（对应评审 10 项）

```text
1. 只读 DOM 元数据探针（仅候选 composer/input 元素：tag/id/role/contenteditable/
   data-lexical-editor/aria-label/visibility/bounding box/form scope；绝不读 ChatGPT 输出）
   -> 确认真实 composer 为可见 <div id="prompt-textarea" contenteditable="true" role="textbox">
   （555x42），隐藏 fallback <textarea class="wcDTda_fallbackTextarea"> (display:none, 0x0) 为其误选根因
2. 替换 textarea-only 为语义可见性感知 editable-composer 查找：
   优先可见 #prompt-textarea[contenteditable=true] -> 可见 [contenteditable=true][data-lexical-editor=true]
   -> 唯一 composer-scoped 可见 [contenteditable=true]
3. 要求恰好一个可见可编辑候选；0 或 >1 -> fail-closed（歧义）
4. 显式排除隐藏 fallback textarea（wcDTda_fallbackTextarea / display:none / 零尺寸 /
   disabled / 非可编辑）；不单靠 opaque CSS class
5. fill() 注入精确文本 `fetch <fresh_handoff_id>` 到选中可见 contenteditable（无需 click）
6. Enter 后正向确认提交：composer 清空/reset 且 URL 保持配置对话（不读 assistant 输出）；
   无法确认 -> fail closed，不发布 trigger_fetch_sent
7. 保持 NON-OWNING：不 goto/new_page/page/context/browser close、不修复、不触无关 tab
8. 保持终态 fail-closed 与无自动重发
```

## 2. 测试与 --check

```text
pytest tests/test_web_fetch_bridge.py -q: 45 passed（新增 9 项针对性测试）：
  hidden fallback 排除、仅 fallback fail-closed、无候选 fail-closed、
  唯一可见 contenteditable 选择、lexical 优先、歧义 fail-closed、
  selector 映射、submission-confirmed 纯检查、未确认提交 withhold trigger_fetch_sent
python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.example.toml --check: PASSED
```

## 3. E2E（fresh handoff，修正后恰好一次）

```text
序列：
  Claude push 修正实现 + packet/status（本 packet）
  Claude push fresh claude_work_complete.json doorbell LAST（tz-aware UTC）
  bridge daemon 从 origin/main 自动发现
  bridge 通过 CDP 提交恰好一次 `fetch <fresh_handoff_id>`（NON-OWNING，可见 contenteditable）
  Enter 后确认 composer 清空 + URL 不变 -> 才发布 trigger_fetch_sent
  Web ChatGPT 收到后先 chatgpt_fetch_ack，再实质评审
  Web ChatGPT 发布评审 + chatgpt_review_published（最后）
  Claude 消费评审并发布 claude_review_ack

结果：<SMOKE_RESULT>
```

## 3b. E2E 执行结果 — SUBMIT OK, PUBLISH FAILED (NEW INFRASTRUCTURE BLOCKER)

```text
状态: 授权执行一次。composer 修正 PROVEN：真实 browser-generated fetch 已于
  16:21:38 提交（event=fetch_sent；submission 正向确认：composer 清空 + URL 不变）。
  但 trigger_fetch_sent 发布到 origin/main 失败（git push 被拒，non-fast-forward）。
序列:
  doorbell WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001_001
    pushed LAST (tz-aware UTC, commit 8a44fc6)
  daemon 自动发现 -> fetch_send_start 16:21:36
  恰好一次 CDP 提交 -> fetch_sent 16:21:38（真实提交成功；修正生效）
  发布 trigger_fetch_sent -> PUBLISH_FAILED_FAIL_CLOSED 16:21:43
失败原因: git command failed: push origin（non-fast-forward）
  bridge worktree = detached HEAD 从旧历史 6026d08 fork，从不刷新；
  origin/main 8a44fc6 不是 worktree HEAD 9c535f4 (parent cfc80e9) 的祖先
  -> GitTransport._ensure_worktree 只在首次创建时 add，从不同步到 origin/main
  （此前所有 send 均 SEND_FAILED，从未走到 publish，故该缺陷首次暴露）
后果:
  dedup.json 正确将 handoff 标记为 fetch_sent -> daemon 不重发（无重复提交）✓
  trigger_fetch_sent 不在 origin/main -> Web ChatGPT 无法自动 ACK 本 handoff
  daemon 已由 operator 停止；不手动发布 bridge-owned marker；不改代码；不重试
恢复点: reviewer 授权 (a) 刷新/同步 bridge worktree 到 origin/main 后再发布，
  及/或 (b) 对已提交的 trigger_fetch_sent 授权手动 marker 发布
```

## 4. 所有权 / 边界

## 4. 所有权 / 边界

```text
✓ bridge 只写/发布 trigger_fetch_sent.json；其余 marker 只读观察
✓ NON-OWNING：绝不管理 browser/page lifecycle；仅 stop 自属 Playwright driver
✓ 提交未正向确认 -> fail closed 且不发布 trigger_fetch_sent
✓ 恰好一次 fetch；任何失败不自动重发；显式操作员重试唯一
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
handoff_id: WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001_001
packet: WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001
status: RUNNING
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY

authorization:
  decision: E2E_FAIL_CLOSED_ACCEPTED_COMPOSER_LOCATOR_CORRECTION_AUTHORIZED
  source: docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_SINGLE_TRUE_E2E_FETCH_001_REVIEWER_RESPONSE.md

locator_correction:
  read_only_dom_probe: true
  semantic_visibility_aware: true
  prefer_prompt_textarea: true
  exclude_hidden_fallback: true
  exactly_one_visible_editable_required: true
  ambiguity_fails_closed: true
  no_opaque_class_alone: true

submission_confirmation:
  fill_no_click: true
  confirm_composer_cleared_after_enter: true
  url_unchanged_required: true
  no_assistant_output_read: true
  unconfirmed_withholds_trigger_fetch_sent: true

tests: 45 passed; --check PASSED

fresh_handoff: true            # new unique handoff; no reuse of prior SEND_FAILED ids
doorbell_pushed_last: true
daemon_discovers_from_origin_main: true
exactly_one_browser_fetch: true   # real browser submission SUCCEEDED 16:21:38
nonowning_no_navigation_close_repair: true
no_browser_close: true
fail_closed_no_auto_resend: true

e2e_smoke:
  submit: SUCCEEDED   # composer correction proven; fetch_sent logged 16:21:38
  publish: FAILED     # trigger_fetch_sent push non-fast-forward (stale detached worktree)
  trigger_fetch_sent_on_origin_main: false
  dedup_fetch_sent_marked: true   # daemon will not resend
  new_blocker: GITTRANSPORT_WORKTREE_NEVER_SYNCED
  await_review: not reached (no trigger_fetch_sent marker for Web ChatGPT to ACK)

no_new_research: true
canonical_artifacts_unchanged: true
03110_stop_unchanged: true
rl_closed: true
qmt_live_forbidden: true
codex_default_disabled: true
```

## END OF WEB FETCH BRIDGE V1 COMPOSER LOCATOR CORRECTION AND SINGLE E2E
