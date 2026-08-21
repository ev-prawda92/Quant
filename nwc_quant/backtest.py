"""
Point-in-time backtester (#2) — the heart of the engine.

Event loop over rebalance dates. On each date it:
  * sees ONLY data up to that date (no lookahead),
  * builds factor scores -> composite -> target weights,
  * charges transaction costs for the turnover,
  * holds those weights and accrues realized forward daily returns until the
    next rebalance.

Also computes an equal-weight buy-and-hold benchmark on the same point-in-time
universe — the "just buy the market and do nothing" bar every strategy must clear.

Guardrails against the classic backtest lies:
  * Lookahead: weights at date t use prices/fundamentals up to t; returns are
    always t -> t+1 forward.
  * Survivorship: delisted names are held in the panel and simply drop out of
    the alive universe when they stop trading.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import EngineConfig
from .data import MarketData
from .factors import compute_factor_scores
from .signals import combine
from .portfolio import construct_weights, CostModel


@dataclass
class BacktestResult:
    returns: pd.Series                 # daily net strategy returns
    gross_returns: pd.Series           # before costs
    benchmark: pd.Series               # equal-weight universe
    weights: dict = field(default_factory=dict)      # date -> Series
    turnover: pd.Series = None
    costs: pd.Series = None

    @property
    def equity_curve(self) -> pd.Series:
        return (1 + self.returns).cumprod()


def _forward_daily_returns(prices: pd.DataFrame, start, end, names):
    """Daily returns for `names` over (start, end], point-in-time safe."""
    px = prices.loc[start:end, names]
    return px.pct_change(fill_method=None).iloc[1:]


def run_backtest(md: MarketData, cfg: EngineConfig) -> BacktestResult:
    rebal_dates = md.prices.resample(cfg.rebalance_freq).last().index
    rebal_dates = [d for d in rebal_dates if d in md.prices.index or
                   len(md.prices.loc[:d])]
    # align to actual trading days
    all_days = md.prices.index
    rebal_dates = sorted(set(all_days[all_days.searchsorted(rebal_dates, side="right") - 1]))
    # need history before first rebalance for 12m momentum
    rebal_dates = [d for d in rebal_dates if len(md.prices.loc[:d]) > 260]

    coster = CostModel(cfg)
    prev_w = pd.Series(dtype=float)

    strat_gross, strat_net, bench = [], [], []
    weights_hist, turn_hist, cost_hist = {}, {}, {}

    for i, d in enumerate(rebal_dates[:-1]):
        nxt = rebal_dates[i + 1]

        # ---- decide weights using data up to d (no lookahead) ----
        fs = compute_factor_scores(md, d, winsor=cfg.winsorize_pct)
        comp = combine(fs, cfg.factor_weights, winsor=cfg.winsorize_pct)
        w = construct_weights(comp, md, d, cfg)
        if w.empty:
            prev_w = pd.Series(dtype=float)
            continue

        cost, turnover = coster.cost(prev_w, w)
        weights_hist[d] = w
        turn_hist[d] = turnover
        cost_hist[d] = cost

        # ---- realize forward returns d -> nxt ----
        names = list(w.index)
        fwd = _forward_daily_returns(md.prices, d, nxt, names)
        if fwd.empty:
            prev_w = w
            continue

        # hold weights fixed over the period (no intra-period rebalancing)
        daily = fwd.reindex(columns=names).fillna(0.0).mul(w, axis=1).sum(axis=1)

        # charge the cost on the first day of the holding period
        daily_net = daily.copy()
        daily_net.iloc[0] -= cost

        # benchmark: equal weight across the alive universe at d
        alive = md.alive_on(d)
        bfwd = _forward_daily_returns(md.prices, d, nxt, alive)
        bdaily = bfwd.reindex(columns=alive).mean(axis=1)

        strat_gross.append(daily)
        strat_net.append(daily_net)
        bench.append(bdaily)
        prev_w = w

    gross = pd.concat(strat_gross) if strat_gross else pd.Series(dtype=float)
    net = pd.concat(strat_net) if strat_net else pd.Series(dtype=float)
    bmk = pd.concat(bench) if bench else pd.Series(dtype=float)

    # de-dup any overlapping period boundaries
    gross = gross[~gross.index.duplicated(keep="last")]
    net = net[~net.index.duplicated(keep="last")]
    bmk = bmk[~bmk.index.duplicated(keep="last")]

    return BacktestResult(
        returns=net, gross_returns=gross, benchmark=bmk,
        weights=weights_hist,
        turnover=pd.Series(turn_hist), costs=pd.Series(cost_hist),
    )
