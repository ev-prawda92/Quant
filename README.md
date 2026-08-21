# NWC Quant

A systematic, backtestable equity factor engine — data → factors → composite signal → risk-managed portfolio → point-in-time backtest → statistical validation → paper trading. Full detail, the 8-component breakdown, and the honest guardrails are in [`nwc_quant/README.md`](nwc_quant/README.md).

## Quickstart

Run from the repo root — `run.py` uses relative imports, so it has to be invoked as a package, not run directly from inside `nwc_quant/`.

```bash
pip install -r nwc_quant/requirements.txt
python -m nwc_quant.run          # synthetic demo — factors have a real, embedded premium
python -m nwc_quant.run --null   # control run — a market with NO edge, should FAIL
python -m nwc_quant.run --paper  # print today's paper-trade orders, no execution
```

Both the demo and the null control are verified working — see [`nwc_quant/README.md`](nwc_quant/README.md) for what each verdict means and why the engine is built to fail bad configurations, not flatter them.

## Live data setup

The demo above runs fully offline on synthetic data — no key needed. To wire in real prices (`nwc_quant.data.MassiveProvider`):

```bash
cp .env.example .env
# then edit .env and set MASSIVE_API_KEY (or POLYGON_API_KEY, if that's what you're holding)
```

`.env` is gitignored and must never be committed. `.env.example` documents what's needed without holding a real value.

## Repo layout

```
nwc_quant/          the engine itself — data, factors, signals, portfolio, backtest, validation, paper trading
deploy/              scheduling config for the paper-trading loop (launchd plist + notes)
paper_book.json      current paper-trading position weights (no account data, safe to version)
paper_signal_log.jsonl   history of logged paper-trade signals
```

## Ownership

Research tooling, not investment advice. See the guardrails section in `nwc_quant/README.md` before treating any output as a signal to trade real capital.
