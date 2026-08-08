"""FeaturePreprocessor（GATE_4_FEATURE_ABLATION_PREP F-A2）——train-only imputation + 标准化。

评审 §6（F-A2）冻结契约：
1. 每个特征的 impute 均值与 scaler 统计只从 TRAIN 估计（忽略 NaN）。
2. 估计 TRAIN 统计时忽略 NaN。
3. 任何 TRAIN/VALIDATION/TEST 观测进入模型前：NaN → 该特征 TRAIN 均值。
4. 再按 TRAIN mean/std 标准化（imputed ≈ normalized 0）。
5. 绝不用 Validation/Test 统计做 impute 或 scale。
6. 绝不 backward-fill / 用未来发布值。
7. train 区某特征无可用观测 → fail-closed（raise），不制造值。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class FeaturePreprocessor:
    def __init__(self) -> None:
        self._fit = False
        self._impute_mean: np.ndarray | None = None
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None
        self._columns: list[str] = []

    @property
    def is_fitted(self) -> bool:
        return self._fit

    def fit_train(self, df: pd.DataFrame) -> "FeaturePreprocessor":
        """只从 train 区域估计 impute_mean/mean/std（忽略 NaN）。"""
        self._columns = list(df.columns)
        arr = df.to_numpy(dtype=float)
        n_cols = arr.shape[1]
        impute = np.zeros(n_cols)
        mean = np.zeros(n_cols)
        std = np.zeros(n_cols)
        for j in range(n_cols):
            col = arr[:, j]
            valid = col[np.isfinite(col)]
            if len(valid) == 0:
                raise ValueError(
                    f"feature '{self._columns[j]}' has no usable observations in train region "
                    f"(F-A2 fail-closed; do not fabricate)"
                )
            impute[j] = float(valid.mean())
            mean[j] = float(valid.mean())
            std[j] = float(valid.std())
            if std[j] <= 1e-12:
                std[j] = 1.0  # 常量特征 → 标准化后为 0（mean 中心）
        self._impute_mean = impute
        self._mean = mean
        self._std = np.maximum(std, 1e-8)
        self._fit = True
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """impute NaN→train mean → (x - train mean)/train std；返回全 finite ndarray。"""
        if not self._fit:
            raise RuntimeError("FeaturePreprocessor.transform before fit_train")
        if list(df.columns) != self._columns:
            raise ValueError("transform columns mismatch with fit_train columns")
        arr = df.to_numpy(dtype=float).astype(float)
        nan_mask = ~np.isfinite(arr)
        if nan_mask.any():
            # impute NaN → train feature mean（F-A2；不 ffill 未来值）
            arr[nan_mask] = np.take(self._impute_mean, np.where(nan_mask)[1])
        out = (arr - self._mean) / self._std
        if not np.isfinite(out).all():
            raise RuntimeError("preprocessor output contains non-finite (F-A2 contract violated)")
        return out
