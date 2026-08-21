"""
Next Wave Capital — Quant Engine
================================

A systematic, backtestable equity factor engine. Unlike the v0.x "signal
engine" (which asked an LLM to make the call), the decision here is mechanical:
computable factors -> cross-sectional ranking -> risk-managed portfolio ->
point-in-time backtest -> statistical validation. That is what makes it a
quant engine rather than a watchlist.

Component map (matches the 8-item design):
  #1 breadth + clean data ....... data.py       (providers, point-in-time universe)
  #2 backtester ................. backtest.py    (no-lookahead event loop)
  #3 factor library ............. factors.py     (momentum/value/quality/lowvol/reversal)
  #4 signal combination ......... signals.py     (composite z-score)
  #5 risk + construction ........ portfolio.py   (vol targeting, sector neutral, caps)
  #6 cost + turnover ............ portfolio.py   (CostModel)
  #7 validation ................. validation.py  (walk-forward, deflated Sharpe, alpha t-stat)
  #8 paper-trading loop ......... paper.py       (logs signals for real OOS track record)
"""

__version__ = "1.0.0"
