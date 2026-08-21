"""
Signal combination (#4) — blend factor z-scores into one composite score.

Kept deliberately simple: a weighted average of standardized factors, then
re-standardized. Fancy weighting schemes (ML, optimization on past returns)
are the single biggest source of overfitting in retail quant, so the default
is transparent and near-equal-weight.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from .factors import zscore


def combine(factor_scores: pd.DataFrame, weights: Dict[str, float],
            winsor: float = 0.02) -> pd.Series:
    """
    factor_scores: DataFrame (ticker x factor) of z-scores.
    weights:       factor -> weight (missing factors ignored, weights renormalized).
    Returns a composite z-scored signal per ticker.
    """
    if factor_scores.empty:
        return pd.Series(dtype=float)

    cols = [c for c in factor_scores.columns if weights.get(c, 0) != 0]
    if not cols:
        return pd.Series(dtype=float)

    w = pd.Series({c: weights[c] for c in cols}, dtype=float)
    w = w / w.abs().sum()

    # Row-wise weighted mean over available factors (skip NaNs per name so a
    # missing fundamental doesn't nuke an otherwise-scored stock).
    sub = factor_scores[cols]
    weighted = sub.mul(w, axis=1)
    composite = weighted.sum(axis=1, min_count=1) / sub.notna().mul(w.abs(), axis=1).sum(axis=1)

    return zscore(composite, winsor=winsor)
