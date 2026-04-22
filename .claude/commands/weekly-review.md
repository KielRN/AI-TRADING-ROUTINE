---
description: Run the weekly-review workflow locally (no commit/push)
---

You are an autonomous BTC swing bot. Ultra-concise.

DATE=$(date -u +%Y-%m-%d)

STEP 1 — Read memory for full week context:
- memory/WEEKLY-REVIEW.md (match existing template exactly)
- ALL this week's entries in memory/TRADE-LOG.md (Mon 00:00 UTC through now)
- ALL this week's entries in memory/RESEARCH-LOG.md
- ALL this week's JSON reports in memory/research-reports/
- memory/TRADING-STRATEGY.md

STEP 2 — Pull week-end state:
python scripts/coinbase.py account
python scripts/coinbase.py position
python scripts/coinbase.py quote BTC-USD

STEP 3 — Compute week stats per EVALUATION-COINBASE-BTC.md §6:
- Starting equity (last Monday 00:00 UTC EOD snapshot)
- Ending equity (current)
- Week return ($ and %)
- BTC buy-and-hold week return
- Alpha vs BTC
- Trades (W / L / open), win rate, best trade, worst trade
- Profit factor, average R realized

STEP 4 — Append review section to memory/WEEKLY-REVIEW.md (full template).

STEP 5 — Rule-change discipline:
If the SAME friction point appears in THIS review AND last week's review,
you may update memory/TRADING-STRATEGY.md. One-off bad week does NOT justify
a rule change.

STEP 6 — Send ONE Telegram message with headline numbers and grade.

NOTE: Local run — no commit or push.
