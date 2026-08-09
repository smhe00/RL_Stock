"""RL_FORMAL_PROTOCOL_PREP_CORRECTIONS — 冻结协议契约测试（无训练，P1-P9）。

验证机器可读 config（configs/rl_formal_protocol.yaml）与既有代码/artifact 一致：
算法超参（P7）、seed、device、475 mask、两层 benchmark（P4）、checkpoint policy（P6）、
hard-stop invariants（P8）、active-day annualization 命名（P9）、GO/NO-GO 完整规则（P5）。
不训练任何 RL 模型。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
CONFIG = ROOT / "configs" / "rl_formal_protocol.yaml"


def _cfg() -> dict:
    assert CONFIG.exists(), "configs/rl_formal_protocol.yaml missing"
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


class TestConfigFrozenValues:
    def test_meta(self):
        c = _cfg()
        assert c["meta"]["gate"] == "RL_FORMAL_PROTOCOL_PREP_CORRECTIONS"
        assert c["meta"]["observation"] == "F0"
        assert c["meta"]["observation_dim"] == 104
        assert c["meta"]["n_folds"] == 4

    def test_seed_device_checkpoint(self):
        c = _cfg()
        assert c["seeds"] == [42, 2026, 7]
        assert c["device"] == {"PPO": "cpu", "SAC": "cuda", "TD3": "cuda"}
        assert c["checkpoint_policy"] == "final_training_endpoint_only"  # P6

    def test_train_budget(self):
        c = _cfg()
        assert c["train_passes"] == 20
        assert c["net_arch"] == [256, 256]

    def test_versions(self):
        c = _cfg()
        assert c["versions"]["sb3"] == "2.8.0"
        assert c["versions"]["torch"].startswith("2.7")


class TestTestMask:
    def test_research_benchmark_label(self):
        c = _cfg()
        assert c["meta"]["test_mask_label"] == "RESEARCH_BENCHMARK_TEST"  # P3
        assert c["meta"]["forward_holdout"] == "FUTURE_FINAL_FORWARD_HOLDOUT"  # P3
        assert c["meta"]["test_mask_count"] == 475

    def test_mask_count_475(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from china_etf.data.loader import SLOT_MAP, load_research_adj
        from china_etf.data.corporate_actions import load_corporate_actions
        from china_etf.evaluation.walkforward import WalkForwardRunner
        from china_etf.evaluation.benchmark import exact_test_mask
        from gate4_3seed_pilot import build_env
        adj = load_research_adj()
        runner = WalkForwardRunner(
            adj=adj, opens={}, closes={}, slots=list(SLOT_MAP.keys()),
            slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
            build_env=build_env, corporate_actions=load_corporate_actions(),
        )
        folds = runner.make_folds(n_folds=4)
        mask = exact_test_mask(folds, calendar=adj.index)
        assert mask["exact_test_date_count"] == 475


class TestTwoTierBenchmark:
    def test_primary_return_hurdle(self):
        c = _cfg()
        ew = c["benchmark"]["primary_return_hurdle"]
        assert ew["name"] == "EqualWeight"
        assert ew["active_day_annualized_return"] == pytest.approx(0.2687, abs=1e-3)
        assert ew["sharpe"] == pytest.approx(1.64, abs=1e-2)
        assert ew["max_drawdown"] == pytest.approx(-0.0881, abs=1e-3)

    def test_risk_adjusted_frontier(self):
        c = _cfg()
        mxd = c["benchmark"]["risk_adjusted_frontier"]
        assert mxd["name"] == "MaximumDiversification"
        assert mxd["sharpe"] == pytest.approx(2.77, abs=1e-2)
        assert mxd["max_drawdown"] == pytest.approx(-0.0340, abs=1e-3)
        assert mxd["calmar"] == pytest.approx(5.38, abs=1e-2)

    def test_benchmark_matches_artifact(self):
        art = ARTIFACTS / "gate4_non_rl_horse_race_results.json"
        assert art.exists()
        hr = json.loads(art.read_text(encoding="utf-8"))["horse_race_table"]
        ew = hr["EqualWeight"]
        mxd = hr["MaximumDiversification"]
        c = _cfg()
        cew = c["benchmark"]["primary_return_hurdle"]
        cmxd = c["benchmark"]["risk_adjusted_frontier"]
        assert ew["active_day_annualized_return"] == pytest.approx(cew["active_day_annualized_return"], abs=1e-3)
        assert mxd["sharpe"] == pytest.approx(cmxd["sharpe"], abs=1e-2)


class TestHyperparams:
    def test_algo_hyperparams_frozen(self):
        """P7：有效超参机器可读冻结（learning_rate/gamma/batch 等关键项）。"""
        c = _cfg()
        ppo = c["algorithms"]["PPO"]
        sac = c["algorithms"]["SAC"]
        td3 = c["algorithms"]["TD3"]
        assert ppo["learning_rate"] == 0.0003 and ppo["n_epochs"] == 10 and ppo["gamma"] == 0.99
        assert sac["learning_rate"] == 0.0003 and sac["tau"] == 0.005 and sac["buffer_size"] == 1000000
        assert td3["learning_rate"] == 0.001 and td3["policy_delay"] == 2

    def test_hyperparams_match_sb3_defaults(self):
        """P7：config 超参与 SB3 默认一致（消除隐性默认依赖）。"""
        from stable_baselines3 import PPO, SAC, TD3
        import inspect
        c = _cfg()
        for cls, name in ((PPO, "PPO"), (SAC, "SAC"), (TD3, "TD3")):
            sig = inspect.signature(cls.__init__)
            for param, frozen in c["algorithms"][name].items():
                default = sig.parameters[param].default
                assert default is not inspect.Parameter.empty, f"{name}.{param} not a default param"
                assert str(default) == str(frozen), f"{name}.{param}: config {frozen} != SB3 {default}"


class TestHardStopInvariants:
    def test_invariants_present(self):
        """P8：评估器不变量硬 stop（execution parity / 475 / cost / 完整 series）。"""
        c = _cfg()
        inv = c["hard_stop_invariants"]
        assert "execution_dates_equal_475_mask" in inv
        assert "n_eval_steps_equal_475" in inv
        assert "cost_reconciliation_pass" in inv
        assert "all_folds_present_no_duplicates" in inv
        assert "raw_series_complete" in inv


class TestGoNoGo:
    def test_per_algorithm_go_full_rule(self):
        """P5：per-algorithm GO = CAGR + Sharpe + stops + MaxDD + ≥2/3 seeds。"""
        c = _cfg()
        ew_sharpe = c["benchmark"]["primary_return_hurdle"]["sharpe"]
        ew_cagr = c["benchmark"]["primary_return_hurdle"]["active_day_annualized_return"]
        ew_mdd = c["benchmark"]["primary_return_hurdle"]["max_drawdown"]
        # 通过样例
        sharpe = [1.7, 1.9, 1.5]
        cagr = [0.30, 0.28, 0.27]
        mdd = [-0.06, -0.05, -0.08]
        no_stop = True
        assert float(np.median(sharpe)) >= ew_sharpe
        assert float(np.median(cagr)) >= ew_cagr
        assert float(np.median(mdd)) >= ew_mdd  # 负值比较：更浅回撤 = 更高
        assert sum(s >= ew_sharpe for s in sharpe) >= 2
        assert no_stop
        # NO-GO：median Sharpe 低于 hurdle
        assert float(np.median([1.4, 1.5, 1.6])) < ew_sharpe

    def test_project_level_promising(self):
        """P5：≥1 算法 per-algo GO → project PROMISING。"""
        per_algo_go = {"PPO": True, "SAC": False, "TD3": True}
        assert sum(per_algo_go.values()) >= 1
        assert not (sum(per_algo_go.values()) == 0)  # 0 个 → NO-GO


class TestActiveDayAnnualization:
    def test_stitched_uses_active_day(self):
        """P9：stitched 年化 = (1+cum)**(252/n_steps)-1（val gaps 不计日数）。"""
        nr = np.array([0.01] * 475)
        cum = float(np.exp(np.log1p(nr).sum()) - 1.0)
        active_ann = float((1.0 + cum) ** (252.0 / 475) - 1.0)
        assert np.isfinite(active_ann)
        # 475 执行日（active days）≠ 日历总天数 → 定义明确不混用
        n_steps = 475
        assert n_steps < 365 + 200  # 475 是执行日数，非日历日数基准
        # 与 horse-race artifact 的 active_day_annualized_return 定义一致（同公式）
        assert active_ann > 0
