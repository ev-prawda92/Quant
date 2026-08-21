"""
Data layer (#1) — breadth, clean panels, and pluggable providers.

Design goals a real quant engine needs and a watchlist ignores:
  * BREADTH: rank a broad cross-section, not 12 names you already own.
  * POINT-IN-TIME: only ever see data available on the decision date.
  * SURVIVORSHIP-BIAS-FREE: keep delisted names in history so backtests
    don't only study winners that happened to survive.

Providers:
  * SyntheticProvider — self-contained; generates a universe with KNOWN
    embedded factor premia (+ optional null mode) so we can prove the
    machinery is correct offline and confirm the validation layer rejects
    noise. This is a *pipeline* test, not evidence of real-world alpha.
  * MassiveProvider — real adapter for Massive.com (ex-Polygon). Needs a key
    and network; drop-in for live/historical prices + news.
  * StooqProvider — free daily price history (no key) as a fallback.

Only the synthetic path runs in this sandbox (external hosts are firewalled);
the real adapters are written to work from your machine.
"""
from __future__ import annotations

import os
import io
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────────────────
# Container
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class MarketData:
    """Point-in-time-safe panel of everything the engine consumes."""
    prices: pd.DataFrame                       # dates x tickers (adjusted close)
    fundamentals: Dict[str, pd.DataFrame]      # field -> (dates x tickers)
    sectors: pd.Series                         # ticker -> sector

    @property
    def tickers(self) -> List[str]:
        return list(self.prices.columns)

    def alive_on(self, date) -> List[str]:
        """Point-in-time universe membership: names with a valid price on `date`.
        Handles delisting — a name that has stopped trading drops out."""
        row = self.prices.loc[:date]
        if row.empty:
            return []
        last = row.iloc[-1]
        return list(last.dropna().index)

    def returns(self) -> pd.DataFrame:
        return self.prices.pct_change(fill_method=None)


# ──────────────────────────────────────────────────────────────────────────
# Providers
# ──────────────────────────────────────────────────────────────────────────
class DataProvider:
    def load(self) -> MarketData:  # pragma: no cover - interface
        raise NotImplementedError


class SyntheticProvider(DataProvider):
    """
    Generates a realistic multi-sector equity universe.

    Return model (daily):
        r_it = drift_i + beta_i * market_t + eps_it
    where drift_i is a small premium tied to each name's latent value and
    quality loadings. When `embed_alpha=False`, all premia are zeroed -> pure
    beta + noise, i.e. a market where the factors have NO edge. That null case
    is the control: the validation layer should refuse to certify it.
    """

    SECTORS = ["Tech", "Financials", "Health", "Energy", "Staples",
               "Discretionary", "Industrials", "Utilities"]

    def __init__(self, n: int = 100, start="2015-01-01", end="2025-12-31",
                 embed_alpha: bool = True, seed: int = 42,
                 delist_frac: float = 0.10):
        self.n = n
        self.start = start
        self.end = end
        self.embed_alpha = embed_alpha
        self.seed = seed
        self.delist_frac = delist_frac

    def load(self) -> MarketData:
        rng = np.random.default_rng(self.seed)
        dates = pd.bdate_range(self.start, self.end)
        T = len(dates)
        n = self.n
        tickers = [f"SYN{i:03d}" for i in range(n)]
        sectors = pd.Series(
            [self.SECTORS[i % len(self.SECTORS)] for i in range(n)],
            index=tickers, name="sector",
        )

        # Latent per-name factor loadings (standardized).
        value_load = rng.normal(0, 1, n)
        quality_load = rng.normal(0, 1, n)
        beta = rng.uniform(0.6, 1.4, n)
        base_vol = rng.uniform(0.012, 0.030, n)      # daily idiosyncratic vol

        # Annual factor premia -> daily drift. Modest and realistic (~3-4%/yr
        # per unit of loading) so it's detectable but not cartoonish.
        ann_value_premium = 0.035 if self.embed_alpha else 0.0
        ann_quality_premium = 0.030 if self.embed_alpha else 0.0
        drift = (value_load * ann_value_premium +
                 quality_load * ann_quality_premium) / 252.0

        # Market factor path.
        mkt = rng.normal(0.06 / 252, 0.011, T)       # ~6%/yr, ~17% vol

        # Idiosyncratic returns with mild momentum (AR(1) in the shocks).
        eps = rng.normal(0, 1, (T, n)) * base_vol
        for t in range(1, T):
            eps[t] += 0.05 * eps[t - 1]              # weak autocorrelation -> momentum

        rets = drift[None, :] + beta[None, :] * mkt[:, None] + eps
        prices = 100 * np.exp(np.cumsum(rets, axis=0))
        prices = pd.DataFrame(prices, index=dates, columns=tickers)

        # Survivorship realism: delist a fraction of names at random dates.
        n_delist = int(self.delist_frac * n)
        if n_delist:
            victims = rng.choice(n, size=n_delist, replace=False)
            for j in victims:
                stop = rng.integers(int(T * 0.3), int(T * 0.95))
                prices.iloc[stop:, j] = np.nan

        # Fundamentals consistent with loadings (slow-moving, noisy).
        def slow_panel(load, scale, floor=None):
            base = load * scale
            noise = rng.normal(0, abs(scale) * 0.15, (T, n))
            # random-walk drift so ratios evolve over time
            walk = np.cumsum(rng.normal(0, abs(scale) * 0.01, (T, n)), axis=0)
            panel = base[None, :] + noise + walk
            df = pd.DataFrame(panel, index=dates, columns=tickers)
            if floor is not None:
                df = df.clip(lower=floor)
            return df.where(~prices.isna())          # delisted -> NaN fundamentals too

        fundamentals = {
            # higher = cheaper (value)
            "earnings_to_price": slow_panel(value_load, 0.02).add(0.05),
            "book_to_price":     slow_panel(value_load, 0.10).add(0.40),
            # higher = better (quality)
            "roe":               slow_panel(quality_load, 0.05).add(0.15),
            "gross_profitability": slow_panel(quality_load, 0.08).add(0.30),
        }

        return MarketData(prices=prices, fundamentals=fundamentals, sectors=sectors)


class MassiveProvider(DataProvider):
    """
    Real prices from Massive.com (ex-Polygon.io). Requires MASSIVE_API_KEY (or a
    legacy POLYGON_API_KEY) and network access. Fundamentals are not covered
    here — wire in a fundamentals vendor (e.g. SEC EDGAR / a data API) to fill
    the same dict shape the engine expects.
    """
    BASE = "https://api.massive.com"

    def __init__(self, tickers: List[str], start: str, end: str,
                 sectors: Optional[Dict[str, str]] = None, pause: float = 0.0):
        self.tickers = tickers
        self.start = start
        self.end = end
        self.sectors = sectors or {}
        # Seconds to sleep between ticker requests. Free tier is ~5 req/min ->
        # set pause≈13. A paid tier can leave this at 0.
        self.pause = pause

    def _bars(self, ticker):
        import requests
        key = os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")
        url = (f"{self.BASE}/v2/aggs/ticker/{ticker}/range/1/day/"
               f"{self.start}/{self.end}")
        for attempt in range(3):
            r = requests.get(url, params={"apiKey": key, "adjusted": "true",
                                          "sort": "asc", "limit": 50000}, timeout=15)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            res = r.json().get("results", []) or []
            idx = pd.to_datetime([b["t"] for b in res], unit="ms")
            return pd.Series([b["c"] for b in res], index=idx, name=ticker)
        return pd.Series(dtype=float, name=ticker)

    def load(self) -> MarketData:
        import time as _time
        cols = []
        for i, t in enumerate(self.tickers):
            cols.append(self._bars(t))
            if self.pause and i < len(self.tickers) - 1:
                _time.sleep(self.pause)
        prices = pd.concat(cols, axis=1).sort_index()
        sectors = pd.Series({t: self.sectors.get(t, "Unknown") for t in self.tickers})
        # Fundamentals left empty; value/quality factors will no-op until wired.
        return MarketData(prices=prices, fundamentals={}, sectors=sectors)


class StooqProvider(DataProvider):
    """Free daily prices from stooq.com (no key). Prices only."""
    def __init__(self, tickers: List[str], start: str, end: str,
                 sectors: Optional[Dict[str, str]] = None):
        self.tickers = tickers
        self.start = start
        self.end = end
        self.sectors = sectors or {}

    def _one(self, ticker):
        import requests
        sym = ticker.lower()
        if "." not in sym:
            sym += ".us"
        url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"]).set_index("Date")
        return df["Close"].rename(ticker)

    def load(self) -> MarketData:
        cols = [self._one(t) for t in self.tickers]
        prices = pd.concat(cols, axis=1).sort_index().loc[self.start:self.end]
        sectors = pd.Series({t: self.sectors.get(t, "Unknown") for t in self.tickers})
        return MarketData(prices=prices, fundamentals={}, sectors=sectors)
