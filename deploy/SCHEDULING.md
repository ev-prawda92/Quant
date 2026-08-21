# Running the monthly paper loop on your Mac

The loop needs live market data, so it runs on **your machine** (where your
Massive key and network live), not in the cloud. Here's the whole setup — about
5 minutes, once.

## 1. Put the code somewhere stable

Unzip `nwc_quant.zip` into a folder you won't move, e.g. `~/nwc/`. You should
end up with `~/nwc/nwc_quant/` (the package) inside it.

```bash
cd ~/nwc
```

## 2. Install dependencies (in a venv, so it's self-contained)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r nwc_quant/requirements.txt
which python3          # <- copy this path, you'll need it for the scheduler
```

## 3. Add your API key

Create a file called `.env` in `~/nwc/`:

```
MASSIVE_API_KEY=your_key_here
# If you're on Massive's FREE tier (~5 requests/min), uncomment the next line
# so the ~80 requests don't get throttled:
# MASSIVE_RATE_SLEEP=13
```

(Your old Polygon key works too — name it `POLYGON_API_KEY` instead.)

## 4. Test it once, by hand

```bash
python -m nwc_quant.run_paper
```

You should see it fetch prices, then print this month's target book and the
orders it *would* place. It writes two files:

- `paper_signal_log.jsonl` — one line per run, your growing track record.
- `paper_book.json` — the current target book (so next month it only shows *changes*).

Nothing is traded. Ever. This is a logbook.

## 5. Schedule it monthly

### Option A — launchd (the native macOS way)

1. Open `deploy/com.nwc.paperloop.plist` and edit the two paths: the venv
   python from step 2, and the `WorkingDirectory` (`/Users/YOU/nwc`).
2. Install it:

```bash
cp deploy/com.nwc.paperloop.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.nwc.paperloop.plist
```

It now fires on the 1st of each month at 9am. To run it right now as a test:

```bash
launchctl start com.nwc.paperloop
cat ~/nwc/paperloop.out.log
```

To stop/remove it later:

```bash
launchctl unload ~/Library/LaunchAgents/com.nwc.paperloop.plist
```

### Option B — cron (simpler, works on Mac or Linux)

```bash
crontab -e
```

Add this line (edit the paths):

```
0 9 1 * * cd /Users/YOU/nwc && /Users/YOU/nwc/.venv/bin/python3 -m nwc_quant.run_paper >> /Users/YOU/nwc/paperloop.out.log 2>&1
```

## 6. What happens next

Each month appends one honest, timestamped snapshot to
`paper_signal_log.jsonl`. After ~6–12 months you'll have a **real
out-of-sample record** — decisions logged *before* the outcome was known. That
is the only thing that can actually tell you the engine has an edge, as opposed
to a backtest that looked good in hindsight.

When you've got a few months logged, the next build is a **grader**: it reads
the log, pulls the realized prices for each period, computes what the paper book
actually returned, and runs it through the same `validation.py` (deflated
Sharpe, alpha t-stat). Ask for it once there's a log to grade.

## Note on the value/quality factors

Until you wire a fundamentals source, the live loop ranks on the three
price-based factors (momentum, reversal, low-vol). To switch on value and
quality, plug SEC EDGAR (free, `data.sec.gov`) into the `fundamentals` dict in
a custom provider — happy to build that adapter when you want it.
