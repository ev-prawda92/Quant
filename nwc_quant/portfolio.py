"""
Risk model + portfolio construction (#5) and transaction costs (#6).

This is the layer the old design completely lacked: it turns a ranking into
actual position sizes with risk controls, and it charges realistic costs for
trading. Without it, a "signal" is just an opinion.

Construction pipeline per rebalance:
  1. Select: top quantile of the composite (long-only) or top/bottom (long-short).
  2. Sector-neutralize: demean the signal within each sector so the bet isn't
     secretly "just long Tech".
  3. Weight: proportional to signal strength, then inverse-vol scaled so a
     jumpy name doesn't dominate risk.
  4. Constrain: cap single-name weight; renormalize.
  5. Vol-target: scale gross exposure to hit a target annualized portfolio vol.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import EngineConfig


# ── risk model ────────────────────────────────────────────────────────────
def trailing_vol(prices: pd.DataFrame, asof, lookback: int = 63) -> pd.Series:
    """Annualized per-name volatility from trailing daily returns (point-in-time)."""
    window = prices.loc[:asof].iloc[-(lookback + 1):]
    rets = window.pct_change(fill_method=None)
    return rets.std(ddof=0) * np.sqrt(252)


def portfolio_vol_estimate(weights: pd.Series, prices: pd.DataFrame, asof,
                           lookback: int = 126) -> float:
    """Annualized portfolio vol from the trailing sample covariance."""
    names = list(weights.index)
    window = prices.loc[:asof, names].iloc[-(lookback + 1):]
    rets = window.pct_change(fill_method=None).dropna(how="all")
    if rets.shape[0] < 20 or rets.shape[1] == 0:
        return np.nan
    cov = rets.cov().values * 252
    w = weights.reindex(rets.columns).fillna(0).values
    var = float(w @ cov @ w)
    return np.sqrt(max(var, 0.0))


# ── construction ──────────────────────────────────────────────────────────
def construct_weights(composite: pd.Series, md, asof, cfg: EngineConfig) -> pd.Series:
    """Map a composite signal to target portfolio weights."""
    sig = composite.dropna()
    if sig.empty:
        return pd.Series(dtype=float)

    sectors = md.sectors.reindex(sig.index)

    # 2. sector-neutralize (demean within sector)
    if cfg.sector_neutral:
        sig = sig - sig.groupby(sectors).transform("mean")

    # 1. select
    if cfg.long_only:
        cut = sig.quantile(1 - cfg.top_quantile)
        longs = sig[sig >= cut]
        selected = longs.clip(lower=0)
        if selected.sum() == 0:
            selected = (longs - longs.min() + 1e-9)
        raw_w = selected
        side = 1.0
    else:
        hi = sig.quantile(1 - cfg.top_quantile)
        lo = sig.quantile(cfg.bottom_quantile)
        longs = sig[sig >= hi]
        shorts = sig[sig <= lo]
        raw_w = pd.concat([longs.clip(lower=0), shorts.clip(upper=0)])
        side = None

    # 3. inverse-vol scale
    vol = trailing_vol(md.prices, asof).reindex(raw_w.index)
    inv_vol = (1.0 / vol).replace([np.inf, -np.inf], np.nan)
    inv_vol = inv_vol.fillna(inv_vol.median())
    tilt = raw_w * inv_vol

    # normalize to gross 1.0
    gross = tilt.abs().sum()
    if gross == 0:
        return pd.Series(dtype=float)
    w = tilt / gross

    # 4. single-name cap + renormalize (a couple of passes)
    for _ in range(3):
        w = w.clip(lower=-cfg.max_position_weight, upper=cfg.max_position_weight)
        g = w.abs().sum()
        if g == 0:
            break
        w = w / g

    # 5. vol-target: scale exposure to hit target annualized vol
    pv = portfolio_vol_estimate(w, md.prices, asof)
    if pv and not np.isnan(pv) and pv > 0:
        scale = cfg.target_annual_vol / pv
        scale = float(np.clip(scale, 0.1, 3.0))     # don't lever insanely
        w = w * scale

    return w


# ── cost model (#6) ───────────────────────────────────────────────────────
class CostModel:
    """Charge commission + half-spread on traded notional each rebalance."""
    def __init__(self, cfg: EngineConfig):
        self.per_side = (cfg.commission_bps + cfg.spread_bps) / 1e4

    def cost(self, prev_w: pd.Series, new_w: pd.Series) -> float:
        """Return cost as a fraction of NAV for moving prev_w -> new_w."""
        idx = prev_w.index.union(new_w.index)
        turnover = (new_w.reindex(idx).fillna(0) - prev_w.reindex(idx).fillna(0)).abs().sum()
        return turnover * self.per_side, turnover
