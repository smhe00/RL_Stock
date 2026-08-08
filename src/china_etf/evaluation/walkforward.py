"""WalkForwardRunner（GATE_4_PILOT_READY WF1/WF2/TB1；Reviewer §16/§20-§25）。

每个 fold 三段：
  TRAIN      → fit 特征 scaler（仅 fold train 决策区间）→ train 模型（train env 数据
               止于 fold.train_end，即 val_start 前一交易日；末决策只执行到 train_end，
               绝不用 val 首日价格）→ freeze
  VALIDATION → train-fit scaler 仅 transform，rollout 记录 val 区间诊断（无 scaler 更新）
  TEST       → 模型/scaler 全冻结，rollout 记录 test 区间诊断

t→t+1 边界（WF2）：train env 数据止于 train_end；val env 止于 val_end（test_start 前一
交易日）；test env 止于 test_end（末行 = terminal mark，非决策）。

4-fold expanding（新 513690 日历，~1015 决策日）：train core [300,478,656,834] +
val 60 + test [118,118,118,121]。

训练预算（TB1）：TRAIN_PASSES × train_decision_steps（不再固定 timesteps/fold）。
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..environment.gym_wrapper import ChinaETFGymEnv
from .rollout import roll_out


@dataclass(frozen=True)
class Fold:
    name: str
    train_start: pd.Timestamp  # 含（= 有效决策起点）
    train_end: pd.Timestamp  # 含（train 末执行日；val_start 前一交易日）
    val_start: pd.Timestamp  # 含
    val_end: pd.Timestamp  # 含（test_start 前一交易日）
    test_start: pd.Timestamp  # 含
    test_end: pd.Timestamp  # 含（terminal mark，非决策）


def make_folds(
    decision_index,
    *,
    n_folds: int = 4,
    min_train_days: int = 300,
    val_days: int = 60,
) -> list[Fold]:
    """expanding-window：每 fold = train core（expanding）→ val（val_days）→ test。

    非末折 test 长度 = step - val_days（step = (n - min_train_days) // n_folds）；
    末折 test 延伸到决策区间末尾。fold 间严格 tiling 无重叠无空隙。
    """
    idx = list(decision_index)
    n = len(idx)
    step = (n - min_train_days) // n_folds
    if step < val_days + 40:
        raise ValueError(
            f"decision region {n} days too small for n_folds={n_folds}, "
            f"min_train={min_train_days}, val={val_days} (step={step})"
        )
    folds: list[Fold] = []
    for k in range(n_folds):
        train_core_days = min_train_days + k * step
        train_end_i = train_core_days - 1
        val_start_i = train_core_days
        val_end_i = train_core_days + val_days - 1
        test_start_i = val_end_i + 1
        test_end_i = (train_core_days + step - 1) if k < n_folds - 1 else (n - 1)
        if test_end_i >= n:
            raise ValueError(
                f"fold F{k + 1} test_end {test_end_i} out of range {n}"
            )
        folds.append(
            Fold(
                name=f"F{k + 1}",
                train_start=idx[0],
                train_end=idx[train_end_i],
                val_start=idx[val_start_i],
                val_end=idx[val_end_i],
                test_start=idx[test_start_i],
                test_end=idx[test_end_i],
            )
        )
    return folds


class WalkForwardRunner:
    def __init__(
        self,
        *,
        adj: pd.DataFrame,
        opens: dict[str, pd.Series],
        closes: dict[str, pd.Series],
        slots: list[str],
        slot_to_instrument: dict[str, str],
        build_env,
        corporate_actions=None,
    ) -> None:
        self.adj = adj
        self.opens = opens
        self.closes = closes
        self.slots = list(slots)
        self.slot_to_instrument = slot_to_instrument
        self.build_env = build_env
        self._ca = corporate_actions
        # 有效起点：全量数据 env 的 warmup（首个全 finite 且 ≥min_history 的观测）
        full = build_env(adj, opens, closes, corporate_actions=self._ca)
        self.decision_start = adj.index[full._warmup_index]

    def make_folds(self, n_folds: int = 4, min_train_days: int = 300, val_days: int = 60) -> list[Fold]:
        decision = self.adj.index[self.adj.index >= self.decision_start]
        return make_folds(
            decision, n_folds=n_folds, min_train_days=min_train_days, val_days=val_days
        )

    def _build_env_upto(self, last: pd.Timestamp):
        return self.build_env(
            self.adj.loc[:last],
            {k: v[v.index <= last] for k, v in self.opens.items()},
            {k: v[v.index <= last] for k, v in self.closes.items()},
            corporate_actions=self._ca,
        )

    def _train_env_for(self, fold: Fold):
        return self._build_env_upto(fold.train_end)

    def fit_scaler(self, train_env, fold: Fold) -> tuple[np.ndarray, np.ndarray]:
        """只 fit 于 fold train 决策区间外生特征（strict isolation，Reviewer §16/§21）。"""
        market = train_env.market_feature_frame()
        region = market.index[
            (market.index >= fold.train_start) & (market.index <= fold.train_end)
        ]
        valid = market.loc[region]
        assert valid.notna().all().all(), f"train scaler region must be finite ({fold.name})"
        return valid.mean().to_numpy(), valid.std().to_numpy().clip(min=1e-8)

    @staticmethod
    def _train_decision_steps(train_env) -> int:
        """train env 每 episode 的决策步数（末行 = terminal mark，非决策）。"""
        return int(len(train_env.calendar) - 1 - train_env._warmup_index)

    def _rollout_segment(self, fold: Fold, kind: str, mean, std, policy) -> dict:
        """段 rollout（GATE_4_EVAL_FIX E1）：在段边界重置记账（现金+零持仓），保留特征历史。

        Validation: 决策于 train_end close → 首执行 val_start open → 首记录 transition val_start
        Test      : 决策于 val_end close  → 首执行 test_start open → 首记录 transition test_start
        """
        if kind == "validation":
            last = fold.val_end
            reset_at = fold.train_end
            start = fold.val_start
        else:
            last = fold.test_end
            reset_at = fold.val_end
            start = fold.test_start
        env = self._build_env_upto(last)
        gym = ChinaETFGymEnv(env)
        gym.set_market_scaler(
            np.asarray(mean, dtype=np.float32), np.asarray(std, dtype=np.float32)
        )
        m = roll_out(env, gym, policy, start, self.slots, reset_at=reset_at)
        m["segment"] = kind
        # E1 manifest 字段：段边界时间线 + 初始组合
        m["segment_predecision_date"] = str(reset_at.date())
        m["segment_first_execution_date"] = str(start.date())
        m["segment_first_metric_date"] = str(start.date())
        m["initial_cash"] = env._initial_cash
        m["initial_positions"] = {}
        return m

    def run_fold_rl(
        self,
        fold: Fold,
        algo_cls,
        *,
        seed: int,
        train_passes: int = 20,
        net=(256, 256),
        device: str = "cpu",
    ) -> dict:
        train_env = self._train_env_for(fold)
        mean, std = self.fit_scaler(train_env, fold)
        gym_tr = ChinaETFGymEnv(train_env)
        gym_tr.set_market_scaler(mean, std)
        train_steps = self._train_decision_steps(train_env)
        total_timesteps = int(train_steps) * train_passes
        model = algo_cls(
            "MlpPolicy",
            gym_tr,
            seed=seed,
            policy_kwargs={"net_arch": list(net)},
            verbose=0,
            device=device,
        )
        model.learn(total_timesteps=total_timesteps)
        save_load_ok = self._save_load_identical(algo_cls, model, gym_tr, device)
        policy = lambda o: model.predict(o, deterministic=True)[0]  # noqa: E731
        val_m = self._rollout_segment(fold, "validation", mean, std, policy)
        test_m = self._rollout_segment(fold, "test", mean, std, policy)
        return {
            "fold": fold.name,
            "kind": "rl",
            "seed": seed,
            "train_decision_steps": train_steps,
            "train_passes": train_passes,
            "total_timesteps": int(total_timesteps),
            "device": str(device),
            "save_load_deterministic_identical": save_load_ok,
            "validation": val_m,
            "test": test_m,
        }

    def run_fold_baseline(self, fold: Fold, policy_factory) -> dict:
        """baseline 权重由 target(t) 决定（PIT，无需模型），走同一 fold-isolation 路径。

        baseline 无模型选型 → 仅记录 test 段诊断；policy 绑定 test env 构造。
        E1：test 段在 val_end 重置记账（现金+零持仓，保留特征历史），首执行 test_start open。
        """
        train_env = self._train_env_for(fold)
        mean, std = self.fit_scaler(train_env, fold)
        env = self._build_env_upto(fold.test_end)
        gym = ChinaETFGymEnv(env)
        gym.set_market_scaler(
            np.asarray(mean, dtype=np.float32), np.asarray(std, dtype=np.float32)
        )
        m = roll_out(env, gym, policy_factory(env), fold.test_start, self.slots,
                     reset_at=fold.val_end)
        m["segment"] = "test"
        m["segment_predecision_date"] = str(fold.val_end.date())
        m["segment_first_execution_date"] = str(fold.test_start.date())
        m["segment_first_metric_date"] = str(fold.test_start.date())
        m["initial_cash"] = env._initial_cash
        m["initial_positions"] = {}
        return {
            "fold": fold.name,
            "kind": "baseline",
            "test": m,
        }

    @staticmethod
    def _save_load_identical(algo_cls, model, gym_tr, device: str) -> bool:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "model.zip")
            model.save(path)
            loaded = algo_cls.load(path, device=device)
        obs0, _ = gym_tr.reset()
        a1 = model.predict(obs0, deterministic=True)[0]
        a2 = loaded.predict(obs0, deterministic=True)[0]
        return bool(np.allclose(a1, a2))
