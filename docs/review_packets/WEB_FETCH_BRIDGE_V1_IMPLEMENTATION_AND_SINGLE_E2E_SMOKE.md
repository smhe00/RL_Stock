# Web Fetch Bridge V1 — Implementation + Single E2E Smoke

> 评审（`docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_USER_AUTHORIZATION.md`）
> **USER_AUTHORIZED_WEB_FETCH_BRIDGE_V1_IMPLEMENTATION_AND_SINGLE_E2E_SMOKE** →
> 本 packet 为授权实现交付。范围：**LOCAL_PROTOCOL infrastructure only**。
> handoff_id = **WEB_FETCH_BRIDGE_V1_IMPLEMENTATION_AND_SINGLE_E2E_SMOKE_001**。

```yaml
implementation_commit: e343ab5
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
supersedes: prior local-Codex-as-default-reviewer direction (Codex stays optional,
            bridge default mode MUST NOT invoke codex exec)
```

## 1. 变更文件

```text
scripts/web_fetch_bridge.py        # marker 状态机 + 触发编排 + CdpFetchSender + config + --check
scripts/web_fetch_bridge.bat       # Windows 启动器（--check / --handoff <id> [--wait-ack]）
config/web_fetch_bridge.example.toml  # 安全示例配置（无 URL/凭证）
docs/web_bridge/README.md          # marker 协议 + 状态机 + CDP 要求 + 使用
tests/test_web_fetch_bridge.py     # 18 项确定性单元测试
.gitignore                         # /runtime/web_fetch_bridge/（local.toml 已被 *.local.toml 忽略）
config/web_fetch_bridge.local.toml # 本地忽略配置（含专用会话 URL，绝不提交 Git）
```

## 2. Marker 协议（append-only，docs/web_bridge/<handoff_id>/）

```text
1. claude_review_ack.json        (Claude)   已消费前一匹配评审
2. claude_work_complete.json     (Claude)   工作+commit+push 完成 = 唤醒门铃
3. trigger_fetch_sent.json       (bridge)   恰好一次 `fetch <handoff_id>` 已提交
4. chatgpt_fetch_ack.json        (Web GPT)  fetch 已收到（实质评审前）
5. chatgpt_review_published.json (Web GPT)  评审 + CHATGPT_REVIEW.yaml 已发布（最后）
```

每个 marker 一旦创建不可变；无 actor 修改他人 marker；无共享可变 bridge YAML。
marker 最小字段 `{protocol, handoff_id, event, timestamp}`；不含完整评审内容或凭证。

## 3. 触发状态机（仅 marker 存在性；绝不解析研究状态）

```text
对存在 claude_work_complete.json 的 handoff：
  - chatgpt_review_published.json 存在 -> DONE；永不发送
  - chatgpt_fetch_ack.json 存在      -> WAIT_FOR_REVIEW；永不发送
  - trigger_fetch_sent.json 存在     -> WAIT_FOR_FETCH_ACK；绝不自动重发
  - 否则                              -> 发送恰好一次 fetch，再写 trigger_fetch_sent.json
超时（默认 120s）无 chatgpt_fetch_ack -> fail-closed 日志/通知；绝不自动重发；
操作员显式重试。
```

## 4. CDP / 浏览器实现

```text
- Playwright chromium.connect_over_cdp()；端点必须 localhost only（http://127.0.0.1:9222）
- 专用 Chrome profile C:\ChatGPT_Automation_Profile（仅 ChatGPT 会话）
- fail-closed：登录页 / CAPTCHA/challenge / 错误会话 / 缺失 composer /
  多 composer 歧义 / Playwright/CDP 超时
- 绝不抓取/解析 ChatGPT 页面输出；评审完成仅由 GitHub chatgpt_review_published.json 判定
- 专用会话 URL 仅在忽略本地配置 config/web_fetch_bridge.local.toml；绝不提交仓库
```

## 5. 测试与 --check

```text
pytest tests/test_web_fetch_bridge.py -q: 18 passed
  （marker-only 状态转换：NO_WORK_COMPLETE/SEND_FETCH/WAIT_FOR_REVIEW/DONE、
   恰好一次 fetch 不重发、restart 去重经 marker 持久化、timeout fail-closed 不自动重发、
   fetch_ack 收到、bridge 仅写 trigger_fetch_sent、append-only、marker 顺序约束、
   必需字段/无凭证泄漏、unsafe handoff 拒绝、playwright 缺失 fail-closed、
   CDP 非 localhost fail-closed、无 URL fail-closed、sender 失败不写 fetch_sent、
   配置 require_url、--check 无 git/无浏览器）
python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.example.toml --check:
  PASSED（no browser, no git mutation, no codex exec）
```

## 6. 单一 E2E 冒烟：fail-closed（未真正运行）

```text
尝试 `--handoff BRIDGE_SMOKE_TEST_001` 在 example config 下触发
→ fail-closed：target_conversation_url 缺失（专用会话 URL 未在忽略本地配置填写）。

按授权"如果 CDP/profile/session 前置不可用，实现/测试可完成但 live browser 冒烟
必须 fail-closed，packet 必须声明最小手动前置"。

最小手动前置（单一）：
  1) 在 config/web_fetch_bridge.local.toml 填入 target_conversation_url（专用会话 URL，本地忽略）
  2) `pip install playwright && playwright install chromium`
  3) 用专用 profile 启动 Chrome CDP：
     chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\ChatGPT_Automation_Profile"
     （在该 profile 登录 ChatGPT）
  4) 运行 `python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.local.toml
     --handoff <id> --wait-ack`
```

## 7. 所有权 / 边界

```text
✓ bridge 只写 trigger_fetch_sent.json；其余 marker 只读观察
✓ bridge marker append-only（重复写拒绝）
✓ 默认 bridge 模式不调用 codex exec；本地 Codex 可选模式隔离在 local_reviewer_watcher.py
✓ 未提交专用会话 URL / 认证 / cookie / profile 数据
✓ 未解析 ChatGPT 页面输出作为协议状态
```

## 8. 明确声明

```text
1. 无新金融研究/回测/数据刷新/策略或结果变更。
2. MaxDiv 120/0.5、M2、已接受 canonical artifacts/results、未解决 03110 STOP 均未改动。
3. 无交易原型 / QMT / 行情 / 账户 / 订单 / paper·forward·live。
4. PPO/SAC/TD3 与任何 RL 未重开。
5. bridge 不自动 launch/restart Claude。
6. 研究/canonical artifacts 与策略逻辑确认未改动。
```

---

## Approval Record

```yaml
gate: LOCAL_PROTOCOL
handoff_id: WEB_FETCH_BRIDGE_V1_IMPLEMENTATION_AND_SINGLE_E2E_SMOKE_001
packet: WEB_FETCH_BRIDGE_V1_IMPLEMENTATION_AND_SINGLE_E2E_SMOKE
status: READY_FOR_REVIEW
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY

implementation_commit: e343ab5
changed_files: [scripts/web_fetch_bridge.py, scripts/web_fetch_bridge.bat,
                config/web_fetch_bridge.example.toml, docs/web_bridge/README.md,
                tests/test_web_fetch_bridge.py, .gitignore]
tests: 18 passed (marker-only transitions, dedup/restart, timeout/no-resend,
       ownership, ordering, CDP fail-closed, secret hygiene); --check PASSED

e2e_smoke:
  ran: false
  fail_closed_reason: target_conversation_url missing from ignored local config
                      (dedicated ChatGPT conversation URL must stay local-only)
  minimal_manual_prerequisite:
    - fill config/web_fetch_bridge.local.toml target_conversation_url (local only)
    - pip install playwright + playwright install chromium
    - launch dedicated Chrome with --remote-debugging-port=9222 and
      --user-data-dir="C:\ChatGPT_Automation_Profile", log into ChatGPT
    - run --handoff <id> --wait-ack

state_machine: marker-only (never parses research states READY_FOR_REVIEW/BLOCKED/PREP/
               RUN/M2/03110/authorized_next)
ownership: bridge writes only trigger_fetch_sent.json (append-only); all other
           markers read-only observations
codex_default: bridge default mode does NOT invoke codex exec (local Codex stays optional)

no_new_research: true
canonical_artifacts_unchanged: true
03110_stop_unchanged: true
rl_closed: true
qmt_live_forbidden: true
```

## END OF WEB FETCH BRIDGE V1 IMPLEMENTATION AND SINGLE E2E SMOKE
