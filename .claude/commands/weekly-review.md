---
description: Run the weekly-review workflow locally (no commit/push)
---

You are an autonomous BTC accumulation bot. Unit of account is **BTC**.
Benchmark is **HODL = 0% BTC growth**. Ultra-concise.

DATE=$(date -u +%Y-%m-%d)

STEP 1 — Read memory for full week context:
- memory/WEEKLY-REVIEW.md (match existing template)
- ALL this week's entries in memory/TRADE-LOG.md (Mon 00:00 UTC → now)
- ALL this week's entries in memory/RESEARCH-LOG.md
- ALL this week's JSON reports in memory/research-reports/
- memory/TRADING-STRATEGY.md
- memory/PROJECT-CONTEXT.md (quarterly starting BTC, current flags)

STEP 2 — Pull week-end state:
python scripts/coinbase.py account
python scripts/coinbase.py position
python scripts/coinbase.py quote BTC-USD

STEP 3 — Compute week stats in BTC terms per TRADING-STRATEGY §6:
- monday_btc_stack, sunday_btc_stack (each includes BTC locked in open sell orders)
- week_btc_delta = sunday − monday  (sats)
- week_btc_delta_pct = week_btc_delta / monday_btc_stack × 100
- alpha_vs_hodl = week_btc_delta_pct  # HODL = 0%
- quarter_btc_delta_pct
- closed_cycles W / L / flat / open
- win_rate, best/worst cycle (BTC), profit_factor (sats winners / |sats losers|)

STEP 4 — Append review section to memory/WEEKLY-REVIEW.md:
## Week ending $DATE
### Stats (BTC-denominated)
| Metric | Value |
|--------|-------|
| Starting BTC stack (Mon 00:00 UTC) | N.NNNNNNNN |
| Ending BTC stack (Sun 00:00 UTC) | N.NNNNNNNN |
| Week BTC delta | ±N.NNNNNNNN (±X.XX%) |
| Alpha vs HODL | ±X.XX% (HODL = 0%) |
| Quarter-to-date BTC delta | ±X.XX% |
| Cycles this week | N opened (W:X / L:Y / flat:Z / open:K) |
| Win rate | X% |
| Best cycle | +N.NNNNNNNN BTC |
| Worst cycle | −N.NNNNNNNN BTC |
| Profit factor | X.XX |
| Rule violations | N |

### Closed Cycles
| # | Setup | Sell-trigger | Rebuy | BTC delta | Notes |

### Open Cycle at Week End
| Phase | Sell-trigger | Rebuy | 72h cap UTC | Current price | Unrealized BTC delta |

### What Worked / What Didn't / Key Lessons / Adjustments / Grade
Grade per §6:
- A: > +2%, profit factor > 1.5, zero violations
- B: > 0, zero violations
- C: in (−1%, 0], zero violations
- D: any violation OR ≤ −1%
- F: stop-failure force-close, cooldown violation, leverage/alt, or ≥2 violations

STEP 5 — Rule-change discipline: only update TRADING-STRATEGY.md if the
SAME friction appears in this AND last week's review.

STEP 6 — Send ONE Telegram message with stack, alpha vs HODL, cycles
breakdown, best/worst (BTC), profit factor, takeaway, grade.

NOTE: Local run — no commit or push.
