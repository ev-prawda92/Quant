"""
Factor library (#3) — computable signals, not vibes.

Every factor maps the full cross-section on a given date to a standardized
(z-scored) score, so names are comparable and combinable. This is the core
move that turns "Claude thinks NVDA looks good" into a reproducible number.

Implemented factors (all classic, well-documented premia):
  momentum   — 12-1 month total return (skip the most recent month to avoid
               contaminating with short-term reversal).
  reversal   — negative of last-month return (short-term mean reversion).
  low_vol    — negative of trailing volatility (low-risk anomaly).
  value      — earnings- and book-to-price (cheap = high score).
  quality    — ROE and gross profitability (profitable/efficient = high score).

Each factor is computed point-in-time: it only uses data up to `asof`.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from .data import MarketData


# ── cross-sectional standardization ───────────────────────────────────────
def zscore(series: pd.Series, winsor: float = 0.02) -> pd.Series:
    """Winsorize then standardize a cross-section to mean 0 / std 1."""
    s = series.dropna().astype(float)
    if len(s) < 5:
        return pd.Series(dtype=float)
    lo, hi = s.quantile(winsor), s.quantile(1 - winsor)
    s = s.clip(lo, hi)
    std = s.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / std


def _trailing_return(prices: pd.DataFrame, asof, lookback: int, skip: int = 0) -> pd.Series:
    """Total return over [asof-lookback, asof-skip], point-in-time."""
    window = prices.loc[:asof]
    if len(window) < lookback + 1:
        return pd.Series(dtype=float)
    end = window.iloc[-1 - skip]
    start = window.iloc[-1 - lookback]
    return (end / start) - 1.0


# ── individual factors (raw, pre-zscore) ──────────────────────────────────
def momentum_raw(md: MarketData, asof, lookback=252, skip=21) -> pd.Series:
    return _trailing_return(md.prices, asof, lookback=lookback, skip=skip)


def reversal_raw(md: MarketData, asof, lookback=21) -> pd.Series:
    return -_trailing_return(md.prices, asof, lookback=lookback, skip=0)


def low_vol_raw(md: MarketData, asof, lookback=126) -> pd.Series:
    window = md.prices.loc[:asof].iloc[-(lookback + 1):]
    rets = window.pct_change(fill_method=None)
    vol = rets.std(ddof=0)
    return -vol  # lower vol -> higher score


def value_raw(md: MarketData, asof) -> pd.Series:
    parts = []
    for f in ("earnings_to_price", "book_to_price"):
        if f in md.fundamentals:
            col = md.fundamentals[f].loc[:asof]
            if not col.empty:
                parts.append(zscore(col.iloc[-1]))
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).mean(axis=1)


def quality_raw(md: MarketData, asof) -> pd.Series:
    parts = []
    for f in ("roe", "gross_profitability"):
        if f in md.fundamentals:
            col = md.fundamentals[f].loc[:asof]
            if not col.empty:
                parts.append(zscore(col.iloc[-1]))
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).mean(axis=1)


FACTORS = {
    "momentum": momentum_raw,
    "reversal": reversal_raw,
    "low_vol": low_vol_raw,
    "value": value_raw,
    "quality": quality_raw,
}


def compute_factor_scores(md: MarketData, asof, winsor: float = 0.02) -> pd.DataFrame:
    """
    Return a DataFrame (index=ticker, columns=factor) of z-scored factor values
    for the point-in-time universe alive on `asof`.
    """
    alive = md.alive_on(asof)
    out = {}
    for name, fn in FACTORS.items():
        raw = fn(md, asof)
        if raw is None or raw.empty:
            continue
        raw = raw.reindex(alive)
        out[name] = zscore(raw, winsor=winsor)
    if not out:
        return pd.DataFrame()
    return pd.DataFrame(out).reindex(alive)
