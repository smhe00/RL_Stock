# CORRECTED F0 RL EXECUTION PREP — execution harness 绑定（E1-E4，无训练）

> 评审（`RL_FORMAL_PROTOCOL_PREP_CORRECTIONS_REVIEWER_RESPONSE.md`）**PROTOCOL_APPROVED_EXECUTION_HARNESS_NOT_YET_AUTHORIZED**，
> `authorized_next: CORRECTED_F0_RL_EXECUTION_PREP`（execution-harness prep only，不训练）。本 packet 关闭 E1-E4。
> handoff_id = **CORRECTED_F0_RL_EXECUTION_PREP_001**。

---

# 1. 修正内容（E1-E4）

```text
E1 config→runtime 绑定：新模块 rl_formal.run_fold_rl_config 显式传 configs/rl_formal_protocol.yaml
   冻结超参（PPO/SAC/TD3，非 SB3 默认）；formal run 禁止 env overrides（fail-closed raise）；
   config_sha256 记录于 artifact；构造 spy 证明超参传入。
E2 hard-stop invariants 运行时强制：rl_formal.validate_runtime_invariants——execution_dates==475 mask、
   n_eval_steps==475、cost reconciliation、同一 (algo,seed) 内 fold 互异且覆盖 F1-F4、36 runs；
   任一失败 raise（publication 前 fail-closed）。
E3 P9 命名统一：GO rule / evaluator / tests 用 active_day_annualized_return（无 stitched cagr 字段）。
E4 GO/NO-GO evaluator：rl_formal.evaluate_go_nogo——确定性 per_algorithm（median active_day_annualized_return/
   Sharpe/MaxDD + ≥2/3 seeds + stops）+ project_level（PROMISING/NO_GO）+ Pareto vs MaxDiv；无 Test-based ranking。
```

# 2. 新执行 harness（src/china_etf/evaluation/rl_formal.py）

```text
load_protocol_config()          → config + config_sha256
check_no_forbidden_overrides()  → GATE4_PILOT_* 存在则 fail-closed raise（E1）
run_fold_rl_config(runner, fold, algo_cls, algo_name, seed, cfg)
                                → 显式传冻结超参构造 + learn + E1/E2 语义（E1）
validate_runtime_invariants(results, mask_dates)
                                → 5 invariants fail-closed（E2）
evaluate_go_nogo(per_algo_stitched, cfg)
                                → per_algorithm + project_level + Pareto（E4）
```

# 3. 绑定证明（scripts/gate4_rl_formal_runner.py --dry-run，构造 spy，无训练）

```text
--dry-run: PPO match=True device=cpu | SAC match=True device=cuda | TD3 match=True device=cuda
  （构造 spy 捕获 kwargs == config algorithms 超参；policy_kwargs == {net_arch:[256,256]}）
  config_sha256 = 46c56bc9a204…；无 learn 调用（不训练）
--check:  475 mask OK  config_sha256 = 46c56bc9a204…
```

# 4. 测试（tests/test_rl_formal_protocol.py 27 个）

```text
E1: no-forbidden-overrides fail-closed、config hash 确定性、构造 spy 收到冻结超参
E2: invariants pass + 3 个 fail 分支（execution_dates 错 / n_steps 错 / cost reconciliation 错）
E4: per-algo GO、NO_GO below hurdle、project PROMISING（1 algo GO）、Pareto dominated、no Test ranking
E3: GO rule 用 active_day_annualized_return
```

# 5. 边界与规避

```text
✓ execution harness prep only：dry-run 构造 spy 验证绑定，**无 learn / 无训练**
✓ 不跑 corrected 3-seed（CORRECTED_F0_RL_3SEED 未来独立执行门）
✓ 不 10-seed / Optuna / sweep / F2-F3 / Test-informed / 特征增减 / QMT / SOUTHBOUND
✓ 无 Test-based algorithm ranking
```

# 6. Pytest

```text
collected 227 items  →  227 passed（test_rl_formal_protocol.py 27 个）
```

# 7. Git Commit

`CORRECTED_F0_RL_EXECUTION_PREP` 提交 SHA：**`338693c`**

```text
src/china_etf/evaluation/rl_formal.py          ← E1/E2/E4 harness（config 绑定、invariants、GO/NO-GO evaluator）
scripts/gate4_rl_formal_runner.py              ← --dry-run 构造 spy / --check（无训练）
docs/features/RL_FORMAL_PROTOCOL.md            ← E3 命名 + harness 绑定节
scripts/gate4_rl_formal_protocol_check.py      ← +config_sha256
tests/test_rl_formal_protocol.py               ← +12 测试（E1/E2/E4）
docs/review_packets/CORRECTED_F0_RL_EXECUTION_PREP.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml            ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: CORRECTED_F0_RL_EXECUTION_PREP_001
packet: CORRECTED_F0_RL_EXECUTION_PREP
status: READY_FOR_REVIEW

closed:
  E1_config_to_runtime_binding: true   # explicit frozen kwargs; overrides fail-closed; config_sha256; spy
  E2_hard_stop_invariants_enforced: true  # runtime validator fail-closed; pass+fail tests
  E3_active_day_annualized_return_naming: true  # GO rule/evaluator/tests consistent
  E4_config_driven_go_nogo_evaluator: true  # per-algo + project + Pareto; no Test ranking

binding_proof:
  dry_run_spy: {PPO: true, SAC: true, TD3: true}   # config kwargs reach SB3 constructor
  config_sha256: 46c56bc9a204
  no_learn_called: true
  pytest_227: true

not_done:
  rl_training: false
  corrected_f0_rl_3seed: false         # future execution gate
  ten_seed_execution: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false
  feature_set_change: false
```

## END OF CORRECTED F0 RL EXECUTION PREP
