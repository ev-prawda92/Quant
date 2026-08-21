"""
End-to-end runner: provider -> backtest -> metrics -> validation -> report.

Usage:
    python -m nwc_quant.run                 # synthetic demo (with embedded alpha)
    python -m nwc_quant.run --null          # synthetic control (no real edge)
    python -m nwc_quant.run --paper         # print today's paper-trade orders

Wiring a real universe (from your machine, with a key + network):
    from nwc_quant.data import MassiveProvider
    md = MassiveProvider(tickers=[...], start="2015-01-01", end="2025-12-31",
                         sectors={...}).load()
    # then the same run_backtest / validate calls below.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from .config import DEFAULT
from .data import SyntheticProvider
from .backtest import run_backtest
from .metrics import summary
from .validation import validate
from .paper import generate_orders, print_orders


def _fmt(x):
    return f"{x:.4f}" if isinstance(x, float) else str(x)


def make_chart(res, path="nwc_quant_performance.png"):
    """Equity curve (strategy vs benchmark) + drawdown. CVD-safe palette."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  (chart skipped: {e})")
        return None

    STRAT, BENCH, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e6e5e2"
    eq = (1 + res.returns).cumprod()
    beq = (1 + res.benchmark.reindex(res.returns.index).fillna(0)).cumprod()
    dd = eq / eq.cummax() - 1

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 6.5), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    fig.patch.set_facecolor("#fcfcfb")

    ax1.plot(eq.index, eq.values, color=STRAT, lw=2, label="Quant strategy (net)")
    ax1.plot(beq.index, beq.values, color=BENCH, lw=2, label="Equal-weight benchmark")
    ax1.text(eq.index[-1], eq.values[-1], f"  {eq.values[-1]:.2f}x", color=STRAT, va="center", fontsize=9)
    ax1.text(beq.index[-1], beq.values[-1], f"  {beq.values[-1]:.2f}x", color=BENCH, va="center", fontsize=9)
    ax1.set_title("Next Wave Capital — Quant Engine: growth of $1 (net of costs)",
                  color=INK, fontsize=12, loc="left")
    ax1.legend(frameon=False, loc="upper left", fontsize=9)
    ax1.grid(True, color=GRID, lw=0.6)
    ax1.set_facecolor("#fcfcfb")
    for s in ax1.spines.values():
        s.set_color(GRID)

    ax2.fill_between(dd.index, dd.values, 0, color=STRAT, alpha=0.25)
    ax2.plot(dd.index, dd.values, color=STRAT, lw=1)
    ax2.set_ylabel("Drawdown", color=MUTED, fontsize=9)
    ax2.grid(True, color=GRID, lw=0.6)
    ax2.set_facecolor("#fcfcfb")
    for s in ax2.spines.values():
        s.set_color(GRID)

    fig.tight_layout()
    fig.savefig(path, dpi=140, facecolor="#fcfcfb")
    plt.close(fig)
    return path


def run(embed_alpha=True, chart=True):
    cfg = DEFAULT
    label = "WITH embedded factor premia" if embed_alpha else "NULL control (no real edge)"
    print("=" * 68)
    print(f"  NEXT WAVE CAPITAL — QUANT ENGINE  [{label}]")
    print("=" * 68)

    md = SyntheticProvider(n=cfg.universe_size, start=cfg.start, end=cfg.end,
                           embed_alpha=embed_alpha, seed=cfg.seed).load()
    print(f"  Universe: {len(md.tickers)} names, {len(md.prices)} trading days, "
          f"{md.sectors.nunique()} sectors")

    res = run_backtest(md, cfg)
    stats = summary(res.returns, res.benchmark, res.turnover)

    print("\n  PERFORMANCE (net of costs)")
    for k in ["ann_return", "ann_vol", "sharpe", "sortino", "max_drawdown",
              "calmar", "hit_rate", "bench_ann_return", "bench_sharpe",
              "excess_ann_return", "information_ratio", "avg_turnover_per_rebal"]:
        if k in stats:
            print(f"    {k:24} {_fmt(stats[k])}")

    vr = validate(res.returns, res.benchmark,
                  n_trials=cfg.n_strategy_trials, n_splits=cfg.walk_forward_splits)
    print("\n  VALIDATION")
    wf = vr.walk_forward
    print(f"    walk-forward: mean OOS Sharpe {wf['mean_oos_sharpe']:.2f}, "
          f"{wf['positive_folds']}/{wf['n_folds']} folds positive")
    ds = vr.deflated_sharpe
    print(f"    deflated Sharpe ratio: {ds['deflated_sharpe_ratio']:.3f} "
          f"(need >0.95; assumes {ds['n_trials_assumed']} trials)")
    al = vr.alpha
    print(f"    alpha vs benchmark: {al['alpha_annualized']*100:.2f}%/yr, "
          f"t-stat {al['alpha_tstat']:.2f}, beta {al['beta']:.2f}")
    print(f"\n  VERDICT: {vr.verdict()}")

    report = {
        "config": label,
        "performance": stats,
        "validation": {"walk_forward": vr.walk_forward,
                       "deflated_sharpe": vr.deflated_sharpe, "alpha": vr.alpha,
                       "verdict": vr.verdict()},
    }
    with open("nwc_quant_report.json", "w") as f:
        json.dump(report, f, indent=2, default=float)
    print("\n  Report saved: nwc_quant_report.json")

    if chart:
        p = make_chart(res)
        if p:
            print(f"  Chart saved:  {p}")
    return res, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--null", action="store_true", help="run the no-edge control")
    ap.add_argument("--paper", action="store_true", help="print today's paper orders")
    ap.add_argument("--no-chart", action="store_true")
    args = ap.parse_args()

    if args.paper:
        md = SyntheticProvider(n=DEFAULT.universe_size, embed_alpha=True,
                               seed=DEFAULT.seed).load()
        print_orders(generate_orders(md, DEFAULT))
        return
    run(embed_alpha=not args.null, chart=not args.no_chart)


if __name__ == "__main__":
    main()
