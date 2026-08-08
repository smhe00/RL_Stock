"""ActionTransform V2（Reviewer 2026-08-08 BLOCKER-A）：零权重可表达、算法中立。

V2：clip[-1,1] → score=(a+1)/2 ∈ [0,1] → raw = score/sum(score)。
- a=-1 → score=0 → 权重可为 0（消除 softmax 隐含最小权重先验）
- a=0 → 等权（中性动作）
- 无指数放大
- 全 -1（score.sum≈0）→ 等权 fallback（DEGENERATE_ACTION_FALLBACK，无 NaN）
记录 raw_action / raw_policy_weights / fallback 供诊断。
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
        score = (clipped + 1.0) / 2.0
        s = float(score.sum())
        if s <= 1e-8:
            w = np.full(len(self.slots), 1.0 / len(self.slots))
            self.last_fallback = "DEGENERATE_ACTION_FALLBACK"
        else:
            w = score / s
            self.last_fallback = None
        weights = pd.Series(w, index=list(self.slots), dtype=float)
        TargetAssetWeights(decision_time=decision_time, weights=weights)
        taw = TargetAssetWeights(decision_time=decision_time, weights=weights)
        self.last_raw_action = raw.copy()
        self.last_raw_policy_weights = weights.copy()
        self.last_score = score.copy()
        return taw
