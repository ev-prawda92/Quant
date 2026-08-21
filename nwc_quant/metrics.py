"""Performance & risk analytics."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _ann_return(r: pd.Series) -> float:
    if r.empty:
        return np.nan
    return (1 + r).prod() ** (TRADING_DAYS / len(r)) - 1


def _ann_vol(r: pd.Series) -> float:
    return r.std(ddof=0) * np.sqrt(TRADING_DAYS)


def sharpe(r: pd.Series, rf: float = 0.0) -> float:
    v = _ann_vol(r)
    return np.nan if v == 0 else (_ann_return(r) - rf) / v


def sortino(r: pd.Series, rf: float = 0.0) -> float:
    downside = r[r < 0].std(ddof=0) * np.sqrt(TRADING_DAYS)
    return np.nan if not downside else (_ann_return(r) - rf) / downside


def max_drawdown(r: pd.Series) -> float:
    curve = (1 + r).cumprod()
    peak = curve.cummax()
    return float((curve / peak - 1).min())


def hit_rate(r: pd.Series) -> float:
    nz = r[r != 0]
    return float((nz > 0).mean()) if len(nz) else np.nan


def information_ratio(r: pd.Series, bench: pd.Series) -> float:
    active = (r - bench).dropna()
    v = _ann_vol(active)
    return np.nan if v == 0 else _ann_return(active) / v


def summary(r: pd.Series, bench: pd.Series | None = None,
            turnover: pd.Series | None = None) -> dict:
    r = r.dropna()
    out = {
        "ann_return": _ann_return(r),
        "ann_vol": _ann_vol(r),
        "sharpe": sharpe(r),
        "sortino": sortino(r),
        "max_drawdown": max_drawdown(r),
        "calmar": (_ann_return(r) / abs(max_drawdown(r))) if max_drawdown(r) != 0 else np.nan,
        "hit_rate": hit_rate(r),
        "n_days": int(len(r)),
    }
    if bench is not None:
        b = bench.reindex(r.index).dropna()
        rr = r.reindex(b.index)
        out["bench_ann_return"] = _ann_return(b)
        out["bench_sharpe"] = sharpe(b)
        out["excess_ann_return"] = _ann_return(rr) - _ann_return(b)
        out["information_ratio"] = information_ratio(rr, b)
    if turnover is not None and len(turnover):
        # avg one-way turnover per rebalance, annualized to a rough figure
        out["avg_turnover_per_rebal"] = float(turnover.mean())
    return out
