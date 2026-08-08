"""WalkForwardRunner（GATE_4_PRECHECK §G4.2；Reviewer §16 strict fold isolation）。

每个 fold：
  TRAIN  → fit 特征 scaler（仅 fold train 决策区间的外生特征）→ train 模型（train env
           数据止于 fold.train_end，模型绝不见 test 区间数据）→ freeze
  TEST   → 用 train-fit scaler 仅 transform，rollout 记录 test 区间诊断

4-fold expanding：train 起点固定在有效起点（2022-05-18），test 每次前移 ~177 交易日。
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
    train_start: pd.Timestamp  # 含
    train_end: pd.Timestamp  # 含（train 末决策日；test_start 前一交易日）
    test_start: pd.Timestamp  # 含
    test_end: pd.Timestamp  # 含（测试区末尾）


def make_folds(
    decision_index,
    *,
    n_folds: int = 4,
    min_train_days: int = 360,
    test_days: int | None = None,
) -> list[Fold]:
    """expanding-window 划分有效决策日历。

    train 始终从 decision_index[0] 开始并增长；test 为连续前移的固定长度窗口。
    """
    idx = list(decision_index)
    n = len(idx)
    if test_days is None:
        test_days = (n - min_train_days) // n_folds
    if test_days < 20 or min_train_days <= 0:
        raise ValueError(
            f"invalid fold params for decision region {n} days: "
            f"min_train={min_train_days}, test={test_days}"
        )
    folds: list[Fold] = []
    for k in range(n_folds):
        train_end_i = min_train_days - 1 + k * test_days
        test_start_i = train_end_i + 1
        if k == n_folds - 1:
            test_end_i = n - 1  # 最后一折覆盖到决策区间末尾（利用全部剩余 OOS 数据）
        else:
            test_end_i = test_start_i + test_days - 1
        if test_end_i >= n:
            raise ValueError(
                f"decision region {n} days too small for n_folds={n_folds} "
                f"(min_train={min_train_days}, test={test_days})"
            )
        folds.append(
            Fold(
                name=f"F{k + 1}",
                train_start=idx[0],
                train_end=idx[train_end_i],
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
    ) -> None:
        self.adj = adj
        self.opens = opens
        self.closes = closes
        self.slots = list(slots)
        self.slot_to_instrument = slot_to_instrument
        self.build_env = build_env
        # 有效起点：全量数据 env 的 warmup（首个全 finite 且 ≥min_history 的观测）
        full = build_env(adj, opens, closes)
        self.decision_start = adj.index[full._warmup_index]

    def make_folds(self, n_folds: int = 4, min_train_days: int = 360, test_days=None) -> list[Fold]:
        decision = self.adj.index[self.adj.index >= self.decision_start]
        return make_folds(
            decision, n_folds=n_folds, min_train_days=min_train_days, test_days=test_days
        )

    def _train_env_for(self, fold: Fold):
        last = fold.train_end
        return self.build_env(
            self.adj.loc[:last],
            {k: v[v.index <= last] for k, v in self.opens.items()},
            {k: v[v.index <= last] for k, v in self.closes.items()},
        )

    def _test_env_for(self, fold: Fold, mean, std):
        last = fold.test_end
        env = self.build_env(
            self.adj.loc[:last],
            {k: v[v.index <= last] for k, v in self.opens.items()},
            {k: v[v.index <= last] for k, v in self.closes.items()},
        )
        gym = ChinaETFGymEnv(env)
        gym.set_market_scaler(
            np.asarray(mean, dtype=np.float32), np.asarray(std, dtype=np.float32)
        )
        return env, gym

    def fit_scaler(self, train_env, fold: Fold) -> tuple[np.ndarray, np.ndarray]:
        """只 fit 于 fold train 决策区间外生特征（strict isolation，Reviewer §16）。"""
        market = train_env.market_feature_frame()
        region = market.index[
            (market.index >= fold.train_start) & (market.index <= fold.train_end)
        ]
        valid = market.loc[region]
        assert valid.notna().all().all(), f"train scaler region must be finite ({fold.name})"
        return valid.mean().to_numpy(), valid.std().to_numpy().clip(min=1e-8)

    def run_fold_rl(
        self,
        fold: Fold,
        algo_cls,
        *,
        seed: int,
        total_timesteps: int,
        net=(256, 256),
        device: str = "cpu",
    ) -> dict:
        train_env = self._train_env_for(fold)
        mean, std = self.fit_scaler(train_env, fold)
        gym_tr = ChinaETFGymEnv(train_env)
        gym_tr.set_market_scaler(mean, std)
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
        env_te, gym_te = self._test_env_for(fold, mean, std)
        metrics = roll_out(
            env_te,
            gym_te,
            lambda o: model.predict(o, deterministic=True)[0],
            fold.test_start,
            self.slots,
        )
        metrics["fold"] = fold.name
        metrics["kind"] = "rl"
        metrics["seed"] = seed
        metrics["total_timesteps"] = total_timesteps
        metrics["device"] = str(device)
        metrics["save_load_deterministic_identical"] = save_load_ok
        return metrics

    def run_fold_baseline(self, fold: Fold, policy_factory) -> dict:
        """baseline 权重由 target(t) 决定（PIT，无需模型），但走同一 fold-isolation 路径。"""
        train_env = self._train_env_for(fold)
        mean, std = self.fit_scaler(train_env, fold)
        env_te, gym_te = self._test_env_for(fold, mean, std)
        metrics = roll_out(env_te, gym_te, policy_factory(env_te), fold.test_start, self.slots)
        metrics["fold"] = fold.name
        metrics["kind"] = "baseline"
        return metrics

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
