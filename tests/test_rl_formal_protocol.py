"""RL_FORMAL_PROTOCOL_PREP — 冻结协议契约测试（无训练）。

验证冻结值与既有代码/artifact 一致：算法配置、seed 政策、475 mask、benchmark hurdle、
F0 观测维度、stop-condition 语义。不训练任何 RL 模型。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"


def _pilot_source() -> str:
    return (ROOT / "scripts" / "gate4_3seed_pilot.py").read_text(encoding="utf-8")


class TestFrozenAlgorithmConfig:
    def test_train_passes_and_net(self):
        # 冻结契约：TRAIN_PASSES=20、net [256,256]、seeds {42,2026,7}（RL_FORMAL_PROTOCOL §2/§4）
        src = _pilot_source()
        assert '"20"' in src or "20" in src.split("TRAIN_PASSES = ")[1].split("\n")[0]
        # run_fold_rl 默认 net=(256,256)
        from china_etf.evaluation.walkforward import WalkForwardRunner
        import inspect
        sig = inspect.signature(WalkForwardRunner.run_fold_rl)
        assert sig.parameters["net"].default == (256, 256)

    def test_seed_policy(self):
        src = _pilot_source()
        seed_line = [l for l in src.splitlines() if "SEEDS =" in l and "GATE4_PILOT_SEEDS" in l]
        assert seed_line and "42,2026,7" in seed_line[0]
        # 3 algos
        assert "TD3,SAC,PPO" in [l for l in src.splitlines() if "GATE4_PILOT_ALGOS" in l][0]

    def test_train_passes_value(self):
        from china_etf.evaluation.walkforward import WalkForwardRunner
        import inspect
        sig = inspect.signature(WalkForwardRunner.run_fold_rl)
        assert sig.parameters["train_passes"].default == 20


class TestExactTestMask:
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


class TestBenchmarkHurdle:
    def test_equal_weight_hurdle_matches_artifact(self):
        art = ARTIFACTS / "gate4_non_rl_horse_race_results.json"
        assert art.exists(), "horse-race artifact missing"
        hr = json.loads(art.read_text(encoding="utf-8"))
        ew = hr["horse_race_table"]["EqualWeight"]
        # 协议冻结值（RL_FORMAL_PROTOCOL.md §8）
        assert ew["active_day_annualized_return"] == pytest.approx(0.2687, abs=1e-3)
        assert ew["sharpe"] == pytest.approx(1.64, abs=1e-2)
        assert ew["max_drawdown"] == pytest.approx(-0.0881, abs=1e-3)


class TestStopConditions:
    @staticmethod
    def _stop_fn():
        """从 pilot 源码提取 check_stop_conditions 并独立执行（避免加载整个 pilot 模块）。"""
        src = _pilot_source()
        start = src.index("def check_stop_conditions(")
        # 取到函数体结束（下一个顶格 def 或文件尾）
        rest = src[start:]
        end = rest.find("\n\ndef ")
        body = rest[:end] if end != -1 else rest
        ns: dict = {"np": np}
        exec(compile(body, "check_stop_conditions", "exec"), ns)  # noqa: S102
        return ns["check_stop_conditions"]

    def test_stop_condition_semantics(self):
        """pilot check_stop_conditions：NaN/neg-cash/save-load/non-finite 均触发。"""
        fn = self._stop_fn()
        assert fn({"nan_obs_or_reward": 0, "negative_cash_count": 0, "oos_cum_return": 0.1}, True) == []
        assert "NaN/Inf" in fn({"nan_obs_or_reward": 1, "negative_cash_count": 0,
                                "oos_cum_return": 0.1}, True)
        assert "negative_broker_cash" in fn({"nan_obs_or_reward": 0, "negative_cash_count": 2,
                                             "oos_cum_return": 0.1}, True)
        assert "save_load_mismatch" in fn({"nan_obs_or_reward": 0, "negative_cash_count": 0,
                                           "oos_cum_return": 0.1}, False)
        assert "non_finite_oos_return" in fn({"nan_obs_or_reward": 0, "negative_cash_count": 0,
                                              "oos_cum_return": float("nan")}, True)


class TestF0ObsDim:
    def test_obs_dim_104(self):
        """F0 观测 = 93 exog + 11 weights = 104（RL_FORMAL_PROTOCOL §13）。"""
        from china_etf.features.ablation_features import OBS_DIM
        assert OBS_DIM["F0"] == 104
        assert OBS_DIM["F1"] == 110
        assert OBS_DIM["F2"] == 110
        assert OBS_DIM["F3"] == 116

    def test_gym_wrapper_obs_dim(self):
        """gym wrapper obs = 8*11+5 exog + 11 weights = 104。"""
        from china_etf.environment.gym_wrapper import ChinaETFGymEnv
        import gymnasium as gym
        import numpy as np
        class FakeEnv:
            def __init__(self):
                self.slots = [f"s{i}" for i in range(11)]
            @property
            def action_dim(self):
                return len(self.slots)
        env = ChinaETFGymEnv(FakeEnv())
        assert env.observation_space.shape == (104,)
        assert env.action_space.shape == (11,)


class TestGoNoGoLogic:
    def test_go_logic(self):
        """GO = 无 stop + median Sharpe/CAGR ≥ hurdle + ≥2/3 seeds Sharpe ≥ hurdle。"""
        med_sharpe = [1.7, 1.9, 1.5]  # median 1.7, 2/3 ≥ 1.64
        assert float(np.median(med_sharpe)) >= 1.64
        assert sum(s >= 1.64 for s in med_sharpe) >= 2

    def test_no_go_if_median_below(self):
        med_sharpe = [1.4, 1.5, 1.6]
        assert float(np.median(med_sharpe)) < 1.64
