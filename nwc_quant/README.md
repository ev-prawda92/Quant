# Next Wave Capital — Quant Engine v1.0

A **systematic, backtestable** equity factor engine. This is the real thing you
asked for — not a watchlist, and not "ask an LLM to pick stocks." The decision
is mechanical and reproducible:

```
clean data → factor scores → composite signal → risk-managed portfolio
           → point-in-time backtest → statistical validation → paper trade
```

The difference that matters: the old `nwc_signal_engine` asked Claude "buy or
sell?" — an opinion you can't backtest. Here, every decision is a number
produced by rules, so you can replay it on history and ask the only question
that counts: **did it beat just buying the market, after costs, by more than
luck?**

---

## The 8 components (what you asked to build in)

| # | Component | File | What it does |
|---|-----------|------|--------------|
| 1 | Breadth + clean, point-in-time data | `data.py` | Ranks a broad universe (not 12 names). Providers for Massive.com (ex-Polygon) and Stooq, plus a synthetic generator. Survivorship-bias-free (keeps delisted names). |
| 2 | Backtester | `backtest.py` | No-lookahead event loop over rebalance dates. Benchmarks against equal-weight buy-and-hold. |
| 3 | Factor library | `factors.py` | Momentum, value, quality, low-vol, short-term reversal — each cross-sectionally z-scored. |
| 4 | Signal combination | `signals.py` | Weighted composite of factors, re-standardized. Deliberately simple to resist overfitting. |
| 5 | Risk model + construction | `portfolio.py` | Sector-neutral, inverse-vol weighting, single-name caps, portfolio vol targeting. |
| 6 | Transaction costs | `portfolio.py` | Commission + spread charged on turnover every rebalance. |
| 7 | Validation | `validation.py` | Walk-forward, **deflated Sharpe ratio** (selection-bias haircut), and alpha t-stat vs benchmark. |
| 8 | Paper-trading loop | `paper.py` | Logs signals in advance to build a genuine out-of-sample record. |

---

## Quickstart

```bash
pip install -r requirements.txt

python -m nwc_quant.run          # synthetic demo (factors have a real premium)
python -m nwc_quant.run --null   # control: a market where factors have NO edge
python -m nwc_quant.run --paper  # print today's paper-trade orders (no execution)
```

The demo runs fully offline. It produces `nwc_quant_report.json` and a
`nwc_quant_performance.png` equity-curve chart.

---

## What the demo proves (and what it doesn't)

Because this sandbox can't reach live market data, the demo runs on a
**synthetic universe** — but that's not a cop-out, it's a controlled experiment:

- **With embedded factor premia** (`run`): the engine detects the edge —
  alpha t-stat ~3.5, positive information ratio, verdict *MARGINAL*.
- **Null control** (`run --null`): same code, a market with **no real edge** —
  alpha t-stat ~1.0, negative excess return, verdict *FAIL*.

That contrast is the point: **the machinery captures edge when it exists and
refuses to certify it when it doesn't.** A backtester that "passes" everything
is worthless. This one fails the null.

It also passes a **no-lookahead integrity test**: weights computed on date *d*
are provably identical whether or not future data is present (max difference
0.00). Lookahead bias is the #1 way backtests lie; this one is clean by
construction.

What the demo does **not** prove: that momentum/value/quality have a tradeable
premium *in real markets today*, net of real costs, at retail scale. Nobody can
prove that from a backtest — only a forward paper-traded record can. That's
what `paper.py` is for.

---

## Wiring real data (from your machine)

The sandbox firewalls market-data hosts, but on your own machine:

```python
from nwc_quant.data import MassiveProvider
from nwc_quant.backtest import run_backtest
from nwc_quant.validation import validate
from nwc_quant.config import DEFAULT

md = MassiveProvider(
    tickers=[...],            # your Russell-1000-ish universe
    start="2015-01-01", end="2025-12-31",
    sectors={...},           # ticker -> sector
).load()

res = run_backtest(md, DEFAULT)
report = validate(res.returns, res.benchmark)
```

Your existing Polygon key works against Massive (`MASSIVE_API_KEY` or
`POLYGON_API_KEY`). **One gap to fill:** the value/quality factors need
fundamentals (earnings/price, book/price, ROE, gross profitability). The
Massive adapter ships prices only — plug a fundamentals source (SEC EDGAR is
free) into the `fundamentals` dict and those factors light up. Until then the
engine runs on the price-based factors (momentum, reversal, low-vol) alone.

---

## Honest guardrails

- **This is research tooling, not an advisory.** Nothing it outputs is
  investment advice.
- **No execution path exists, on purpose.** It sizes and logs; it never trades.
  Wiring it to a broker is a much larger step — paper-trade a real OOS record
  first, then talk about small real stakes.
- **The sober base rate:** most retail systematic strategies underperform a
  low-cost index after costs and effort. Build this to *learn how markets
  actually work* and to test ideas honestly — that value is real regardless of
  whether any single config turns out to have an edge.
- **Config lives in `config.py`.** Every knob you turn is another "trial" —
  bump `n_strategy_trials` accordingly so the deflated Sharpe keeps you honest
  about how many things you tried before one looked good.
