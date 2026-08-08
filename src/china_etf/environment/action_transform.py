"""ActionTransform（Reviewer BLOCKER-1 / §5）：算法中立、显式、可审计。

V1：clip[-1,1] → stable softmax → raw policy weights。
记录 raw_action 与 raw_policy_weights 供诊断。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..contracts import TargetAssetWeights


@dataclass
class ActionTransform:
    slots: list[str]

    def transform(self, action: np.ndarray, decision_time: pd.Timestamp) -> TargetAssetWeights:
        raw = np.asarray(action, dtype=float).ravel()
        if raw.size != len(self.slots):
            raise ValueError(f"action dim {raw.size} != slots {len(self.slots)}")
        clipped = np.clip(raw, -1.0, 1.0)
        z = clipped - clipped.max()
        exp = np.exp(z)
        w = exp / exp.sum()
        weights = pd.Series(w, index=list(self.slots), dtype=float)
        taw = TargetAssetWeights(decision_time=decision_time, weights=weights)
        self.last_raw_action = raw.copy()
        self.last_raw_policy_weights = weights.copy()
        return taw
