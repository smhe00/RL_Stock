"""CORRECTED_F0_RL_EXECUTION_PREP — formal runner（dry-run/构造 spy，无训练）。

--dry-run: 用构造 spy 验证 configs/rl_formal_protocol.yaml 超参确实传入 PPO/SAC/TD3 构造器（E1 证明），
           不调用 learn（不训练）。
--check:   验证 475 mask + 两层 benchmark + config_sha256（等价 protocol_check）。

正式训练路径（CORRECTED_F0_RL_3SEED）在本门不执行；runner 仅验证 harness 绑定。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.evaluation.rl_formal import (  # noqa: E402
    FOLD_TEST_LENS,
    _construct_model,
    check_no_forbidden_overrides,
    finalize_publish,
    load_protocol_config,
)
from china_etf.evaluation.benchmark import exact_test_mask  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_research_adj  # noqa: E402
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from gate4_3seed_pilot import build_env  # noqa: E402


def _algo_classes():
    from stable_baselines3 import PPO, SAC, TD3
    return {"PPO": PPO, "SAC": SAC, "TD3": TD3}


def dry_run_constructor_spy(cfg: dict) -> dict:
    """H1：构造 spy——经共享 _construct_model（非手动复制），monkeypatch algo 构造器记录 kwargs，不 learn。"""
    from unittest import mock
    captured: dict[str, dict] = {}
    for name, cls in _algo_classes().items():
        def fake_init(self, policy, env, *, seed=None, policy_kwargs=None, verbose=0,
                      device="cpu", **kwargs):
            captured[self.__class__.__name__] = {
                "seed": seed, "policy_kwargs": policy_kwargs, "device": device, "kwargs": kwargs}

        with mock.patch.object(cls, "__init__", fake_init):
            # 共享 runtime 构造路径（_construct_model）；无 learn
            _construct_model(cls, name, seed=42, cfg=cfg, gym_tr=object())
    # 校验捕获的 kwargs 与 config 一致
    ok = True
    details = {}
    for name in cfg["algorithms"]:
        cap = captured.get(name, {})
        cfg_kwargs = dict(cfg["algorithms"][name])
        got = cap.get("kwargs", {})
        match = got == cfg_kwargs and cap.get("policy_kwargs") == {"net_arch": list(cfg["net_arch"])}
        if not match:
            ok = False
        details[name] = {
            "match": match,
            "captured_kwargs": got,
            "expected_kwargs": cfg_kwargs,
            "device": cap.get("device"),
        }
    return {"ok": ok, "per_algo": details}


def _real_mask_str() -> list[str]:
    """P3：真实 folds + exact_test_mask（475 有序），非 arbitrary bdate。"""
    adj = load_research_adj()
    runner = WalkForwardRunner(
        adj=adj, opens={}, closes={}, slots=list(SLOT_MAP.keys()),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env,
    )
    folds = runner.make_folds(n_folds=4)
    mask = exact_test_mask(folds, calendar=adj.index)
    assert mask["exact_test_date_count"] == 475
    return [str(d.date()) for d in mask["test_dates"]]


def publish_synthetic(loaded: dict) -> dict:
    """F6/P3：synthetic no-training 结果走 finalize_publish（真实 mask，canonical 聚合，不真实 publish）。"""
    cfg = loaded["config"]
    sha = loaded["config_sha256"]
    mask_str = _real_mask_str()  # 真实 475 mask（P3）
    per_algo = {}
    offset = 0
    for a in cfg["algorithms"]:
        per_algo[a] = {}
        for seed in cfg["seeds"]:
            per_algo[a][seed] = {}
            for fold in ("F1", "F2", "F3", "F4"):
                n = FOLD_TEST_LENS[fold]
                seg = mask_str[offset:offset + n]
                offset = (offset + n) % 475
                costs = [0.001] * n
                per_algo[a][seed][fold] = {
                    "config_sha256": sha,
                    "save_load_deterministic_identical": True,
                    "test": {"n_eval_steps": n, "total_cost": sum(costs),
                             "nan_obs_or_reward": 0, "negative_cash_count": 0,
                             "series": {"execution_dates": list(seg), "costs": list(costs),
                                        "net_returns": [0.0] * n, "cash": [1e6] * n,
                                        "actual_weights": [[0.1] * 11] * n,
                                        "raw_weights": [[0.1] * 11] * n,
                                        "post_risk_weights": [[0.1] * 11] * n}}}
    results = {"per_algorithm": per_algo}
    # P1：无 caller stitched —— GO/NO-GO 仅 canonical 聚合
    payload = finalize_publish(results, loaded, mask_str)
    print(f"--publish-synthetic: published=True config_sha256={payload['config_sha256'][:12]} "
          f"project_level={payload['go_nogo']['project_level']} (real mask, canonical aggregation)")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="constructor spy, no training")
    ap.add_argument("--check", action="store_true", help="mask + benchmark + config hash")
    ap.add_argument("--publish-synthetic", action="store_true", help="synthetic publication path (F6)")
    args = ap.parse_args()

    check_no_forbidden_overrides()
    loaded = load_protocol_config()
    cfg = loaded["config"]
    sha = loaded["config_sha256"]

    if args.publish_synthetic:
        payload = publish_synthetic(loaded)
        out = ROOT / "runs" / "gate4_rl_formal_publish_synthetic.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"config_sha256": payload["config_sha256"],
                                   "project_level": payload["go_nogo"]["project_level"],
                                   "published": payload["published"]}, indent=2),
                       encoding="utf-8")
        print(f"  -> {out}  (synthetic, no training)")
        return

    if args.check:
        adj = load_research_adj()
        runner = WalkForwardRunner(
            adj=adj, opens={}, closes={}, slots=list(SLOT_MAP.keys()),
            slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
            build_env=build_env,
        )
        folds = runner.make_folds(n_folds=4)
        mask = exact_test_mask(folds, calendar=adj.index)
        assert mask["exact_test_date_count"] == 475
        print(f"--check: 475 mask OK  config_sha256={sha[:12]}")
        return

    if args.dry_run:
        spy = dry_run_constructor_spy(cfg)
        out = ROOT / "runs" / "gate4_rl_formal_dryrun_spy.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"config_sha256": sha, "spy": spy}, indent=2, ensure_ascii=False,
                                  default=str), encoding="utf-8")
        print(f"--dry-run constructor spy: ok={spy['ok']}")
        for name, d in spy["per_algo"].items():
            print(f"  {name}: match={d['match']} device={d['device']}")
        if not spy["ok"]:
            sys.exit(1)
        print(f"  config_sha256={sha[:12]}")
        print(f"  -> {out}  (no training executed)")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
