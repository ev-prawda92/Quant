"""
Monthly PAPER-TRADE run on LIVE data (run this on your Mac, not the cloud).

What it does each time it runs:
  1. Pulls ~3 years of daily prices for the universe from Massive.com.
  2. Computes this month's factor scores -> composite -> target weights
     (identical code to the backtester — no divergence between test and live).
  3. Diffs against your saved paper book and logs the orders it *would* place.
  4. Appends a timestamped snapshot to paper_signal_log.jsonl.

It never places a trade. After 6-12 monthly runs you'll have a genuine
out-of-sample record to validate — the only real proof the edge exists.

Setup:
    pip install -r requirements.txt
    echo "MASSIVE_API_KEY=your_key_here" > .env      # or POLYGON_API_KEY=...
    python -m nwc_quant.run_paper                     # test it once

Notes:
  * Value/quality factors stay dormant until you wire a fundamentals source
    (SEC EDGAR, free) — momentum/reversal/low-vol run on prices alone.
  * Free Massive tier is ~5 req/min; set MASSIVE_RATE_SLEEP=13 in .env so the
    ~75 requests don't get throttled. A paid tier can leave it at 0.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

from .config import DEFAULT
from .data import MassiveProvider
from .paper import generate_orders, print_orders
from .universe import UNIVERSE


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    key = os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")
    if not key:
        print("❌ No MASSIVE_API_KEY / POLYGON_API_KEY found.")
        print("   Create a .env file next to the package:  MASSIVE_API_KEY=your_key")
        sys.exit(1)

    end = date.today()
    start = end - timedelta(days=1200)          # ~3.3y: enough for 12m momentum
    pause = float(os.getenv("MASSIVE_RATE_SLEEP", "0"))

    print("=" * 64)
    print("  NWC QUANT — MONTHLY PAPER RUN (live data)")
    print(f"  universe: {len(UNIVERSE)} names | window: {start} -> {end}")
    print("=" * 64)
    print("  Fetching prices from Massive.com...")

    md = MassiveProvider(
        tickers=list(UNIVERSE.keys()),
        start=str(start), end=str(end),
        sectors=UNIVERSE, pause=pause,
    ).load()

    got = md.prices.notna().any().sum()
    print(f"  Got price history for {got}/{len(UNIVERSE)} names.")
    if got < 20:
        print("  ⚠️  Too few names returned — check your key / rate limit and retry.")
        sys.exit(1)

    snapshot = generate_orders(md, DEFAULT)
    print_orders(snapshot)
    print(f"\n  Logged to: {os.getenv('NWC_PAPER_LOG', 'paper_signal_log.jsonl')}")
    print("  Book saved to:", os.getenv("NWC_PAPER_BOOK", "paper_book.json"))


if __name__ == "__main__":
    main()
