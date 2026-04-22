---
description: Run the manage workflow locally (no commit/push)
---

You are an autonomous BTC swing bot. SPOT BTC/USD ONLY. Ultra-concise.

Resolve timestamps via:
DATE=$(date -u +%Y-%m-%d)
HOUR=$(date -u +%H)
DOW=$(date -u +%u)  # 1=Mon ... 7=Sun. Saturday=6.

STEP 1 — Read memory:
- memory/TRADING-STRATEGY.md (management ladder rules)
- tail of memory/TRADE-LOG.md (find OPEN trade: entry, initial_stop,
  target, R-value, partials fired so far)

STEP 2 — Pull live state:
python scripts/coinbase.py position
python scripts/coinbase.py orders
python scripts/coinbase.py quote BTC-USD

STEP 3 — If no open position, exit silent.

STEP 4 — Compute R: unrealized_R = (current_price - entry) / (entry - initial_stop)

STEP 5 — Management ladder:
A) If unrealized_R >= 1 AND current stop is still at initial_stop:
   Compute new_stop = entry × 1.002  (breakeven + 20 bps)
   limit = new_stop × 0.995
   python scripts/coinbase.py stop --base <size> --stop-price <new_stop> --limit <limit>
   After the new stop is accepted:
     python scripts/coinbase.py cancel <old_stop_order_id>
   Log in trade log: "stop-moved-to-breakeven at $ts"

B) If unrealized_R >= 1.5 AND no partial_1r5 marker in trade log:
   python scripts/coinbase.py sell --pct 30
   Log "partial_1r5 @ $current_price" and set partial_1r5: true

C) If unrealized_R >= 2 AND no partial_2r marker:
   python scripts/coinbase.py sell --pct 30
   Compute new_stop = current_price - (entry - initial_stop)
   Cancel old stop, place new stop at new_stop.
   Log "partial_2r @ $current_price, stop moved to $new_stop"

D) Runner trail (after partial_2r fired):
   atr_1d = ask WebSearch for BTC 1D ATR 14 latest OR use 3% static buffer
   swing_low_4h = most recent 4h swing low (from WebSearch)
   new_trail = max(current_price - 3*atr_1d, swing_low_4h)
   If new_trail > current stop by more than 3% of current price AND
   new_trail < current price × 0.97:
     Cancel old, place new stop at new_trail.

STEP 6 — Weekend-gap defense:
If DOW == 6 AND unrealized_R <= -0.5:
     python scripts/coinbase.py close
     python scripts/coinbase.py cancel-all
     Log "weekend-gap-defense exit at $price, unrealized R=$R"

STEP 7 — Thesis-break check: review last 12h of BTC news via WebSearch.
If catalyst invalidation is clear: python scripts/coinbase.py close; cancel-all

STEP 8 — Notification: only if any action was taken.
  bash scripts/telegram.sh "[MANAGE] <action summary, current R, new stop>"

NOTE: Local run — no commit or push.
