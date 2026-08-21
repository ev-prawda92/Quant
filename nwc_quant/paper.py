"""
Paper-trading loop (#8) — build a REAL out-of-sample track record.

A backtest is in-sample by construction. The only way to know the edge is real
is to log the engine's decisions in advance and grade them later. This loop:
  * loads the latest data via any provider,
  * computes today's target weights with the exact same code the backtest uses,
  * diffs against the last saved book to produce orders (NOT executed),
  * appends a timestamped snapshot to a JSONL log.

Run it on a schedule (e.g. monthly). After ~6-12 months you have a genuine
out-of-sample record to validate against instead of a backfill.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd

from .config import EngineConfig
from .data import MarketData
from .factors import compute_factor_scores
from .signals import combine
from .portfolio import construct_weights

def _log_path() -> str:
    return os.getenv("NWC_PAPER_LOG", "paper_signal_log.jsonl")


def _book_path() -> str:
    return os.getenv("NWC_PAPER_BOOK", "paper_book.json")


def _load_book() -> pd.Series:
    path = _book_path()
    if os.path.exists(path):
        with open(path) as f:
            return pd.Series(json.load(f), dtype=float)
    return pd.Series(dtype=float)


def _save_book(w: pd.Series):
    with open(_book_path(), "w") as f:
        json.dump({k: float(v) for k, v in w.items()}, f, indent=2)


def generate_orders(md: MarketData, cfg: EngineConfig, asof=None) -> dict:
    """Compute target weights as of `asof` (default: last available date) and
    diff against the saved book. Returns a dict; also logs it."""
    asof = asof or md.prices.dropna(how="all").index[-1]

    fs = compute_factor_scores(md, asof, winsor=cfg.winsorize_pct)
    comp = combine(fs, cfg.factor_weights, winsor=cfg.winsorize_pct)
    target = construct_weights(comp, md, asof, cfg)

    book = _load_book()
    idx = book.index.union(target.index)
    delta = target.reindex(idx).fillna(0) - book.reindex(idx).fillna(0)
    orders = delta[delta.abs() > 1e-4].round(4)

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asof": str(pd.Timestamp(asof).date()),
        "n_positions": int((target.abs() > 1e-4).sum()),
        "target_weights": {k: round(float(v), 4) for k, v in target.items() if abs(v) > 1e-4},
        "orders": {k: float(v) for k, v in orders.items()},
        "gross_exposure": float(target.abs().sum()),
    }

    with open(_log_path(), "a") as f:
        f.write(json.dumps(snapshot) + "\n")
    _save_book(target)

    return snapshot


def print_orders(snapshot: dict):
    print(f"\n  PAPER SIGNAL — as of {snapshot['asof']}")
    print(f"  {snapshot['n_positions']} target positions | "
          f"gross exposure {snapshot['gross_exposure']:.2f}")
    if not snapshot["orders"]:
        print("  No changes since last book.")
        return
    print("  Orders (Δ weight, + = buy / - = trim):")
    for tkr, dw in sorted(snapshot["orders"].items(), key=lambda kv: -abs(kv[1]))[:20]:
        print(f"    {tkr:8} {dw:+.4f}")
    print("  ⚠️  Paper only — no trades placed. Logged for OOS tracking.")
