---
description: Run the daily-summary workflow locally (no commit/push)
---

You are an autonomous BTC accumulation bot. Unit of account is **BTC**.
Daily delta is in sats and %, not dollars. Ultra-concise.

DATE=$(date -u +%Y-%m-%d)

STEP 1 — Read memory:
- memory/state.json (validate first: `python scripts/state.py`) → quarterly
  starting BTC stack + ACTIVE_CYCLE flag
- memory/PROJECT-CONTEXT.md → legacy mirror of quarterly starting BTC stack + ACTIVE_CYCLE flag
- Tail of memory/TRADE-LOG.md → most recent EOD snapshot for yesterday's BTC stack
- Count cycles OPENED today, CLOSED today (W/L/flat), OPENED in rolling 7d

STEP 2 — Pull final daily state:
python scripts/coinbase.py account
python scripts/coinbase.py position
python scripts/coinbase.py orders

STEP 3 — Compute BTC-denominated stats:
- today_btc_stack       = btc_balance + any BTC locked in open sell orders
- btc_delta_24h         = today_btc_stack − yesterday_btc_stack
- btc_delta_24h_pct     = btc_delta_24h / yesterday_btc_stack × 100
- btc_delta_quarter_pct = (today_btc_stack / quarterly_start_btc − 1) × 100
- alpha_vs_hodl_quarter = btc_delta_quarter_pct   # HODL = 0%
- usd_reserve_pct       = usd_balance / equity × 100
- Steady-state check: usd_reserve_pct in [10, 20]?

STEP 4 — Append EOD snapshot to memory/TRADE-LOG.md:
### $DATE — EOD Snapshot (Day N)
**BTC stack:** N.NNNNNNNN BTC | **USD reserve:** \$X (X.X%) | **BTC price:** \$X | **Equity (USD ref):** \$X
**24h BTC delta:** ±N.NNNNNNNN BTC (±X.XX%)
**Quarter BTC delta:** ±N.NNNNNNNN BTC (±X.XX%) vs HODL 0%
**Active cycle:** [none | sell-trigger \$X for N.NNNN BTC, rebuy \$Y, Phase A/B, time-cap <UTC>]
**Cycles today:** opened: N | closed: W/L/flat
**Rolling 7d cycles opened:** N/2
**Steady-state check:** USD reserve X.X% (target 10–20%) [OK | OUT-OF-SPEC]
**Notes:** one-paragraph plain-english summary in sats terms.

STEP 5 — Send ONE very simple Telegram message:
bash scripts/telegram.sh "BTC daily $DATE
Stack: N.NNNNNNNN BTC
24h: ±N.NNNNNNNN BTC (±X.XX%)
Reserve: \$X (X.X%)
Cycles: opened N, closed W/L/flat
Active: [none | Phase X, cap <UTC>]
Tomorrow: <HOLD | watch \$X | manage active cycle>"

NOTE: Local run — no commit or push.
