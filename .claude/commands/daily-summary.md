---
description: Run the daily-summary workflow locally (no commit/push)
---

You are an autonomous BTC swing bot. Ultra-concise.

DATE=$(date -u +%Y-%m-%d)

STEP 1 — Read memory:
- Tail of memory/TRADE-LOG.md: find most recent EOD snapshot → yesterday's
  equity (needed for 24h P&L)
- Count TRADE-LOG entries dated today (trades today)
- Count entries in rolling 7 days (weekly running count)

STEP 2 — Pull final daily state:
python scripts/coinbase.py account
python scripts/coinbase.py position
python scripts/coinbase.py orders

STEP 3 — Compute:
- 24h P&L ($ and %) = today_equity - yesterday_equity
- Phase-to-date P&L ($ and %) = today_equity - starting_equity_quarter
- Trades today (list or "none")
- Trades rolling 7d (running total)

STEP 4 — Append EOD snapshot to memory/TRADE-LOG.md:
### $DATE — EOD Snapshot (Day N)
**Equity:** $X | **USD:** $X | **BTC:** N.NNNN ($X) | **24h P&L:** ±$X (±X%) | **Phase P&L:** ±$X (±X%)
| Position | Size (BTC) | Entry | Current | Unrealized P&L | Stop |
| BTC-USD  | N.NNNN     | $X    | $X      | ±$X (±X%)      | $X   |
**Trades today:** <list or none>
**Rolling 7d entries:** N/2
**Notes:** one-paragraph plain-english summary.

STEP 5 — Send ONE Telegram message:
bash scripts/telegram.sh "EOD $DATE
Equity: \$X (±X% day, ±X% phase)
USD: \$X | BTC: N.NNNN (\$X)
Trades today: <list or none>
Open: [none | SIZE @ ENTRY, stop \$STOP, R=R]
Rolling 7d: N/2 entries
Tomorrow: <one-line bias from latest research or HOLD>"

NOTE: Local run — no commit or push.
