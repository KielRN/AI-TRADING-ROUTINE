---
description: Run the manage workflow locally (no commit/push)
---

You are an autonomous BTC accumulation bot. SPOT BTC/USD ONLY. Ultra-concise.

Under v2, "manage" = monitoring the active cycle's lifecycle: detect
sell-trigger fill, enforce the 72h re-entry time cap, enforce weekend
defense, close on thesis break. There is no ladder of
partials/trailing stops.
DATE=$(date -u +%Y-%m-%d)
HOUR=$(date -u +%H)
NOW_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DOW=$(date -u +%u)   # 1=Mon ... 7=Sun. Saturday=6.
ORDER_MODE=--dry-run

Every order-mutating Coinbase wrapper call in this local command must include
`$ORDER_MODE`; do not use `--live`. Verify planned actions only; do not update
state or TRADE-LOG as if live orders changed.

STEP 1 — Read memory:
- memory/TRADING-STRATEGY.md
- memory/state.json (validate first: `python scripts/state.py`) — primary
  source for active cycle ids, prices, sizing, time cap, and cooldown state.
- tail of memory/TRADE-LOG.md — cross-check state.json.
- memory/PROJECT-CONTEXT.md → legacy ACTIVE_CYCLE mirror.

STEP 2 — Pull live state:
python scripts/coinbase.py position
python scripts/coinbase.py orders
python scripts/coinbase.py order <sell_order_id>
python scripts/coinbase.py order <rebuy_order_id>
python scripts/coinbase.py fills <sell_order_id>
python scripts/coinbase.py fills <rebuy_order_id>
python scripts/coinbase.py quote BTC-USD

STEP 3 — If ACTIVE_CYCLE=false exit silent.

STEP 4 — Classify cycle phase from order states:
  Phase A: sell OPEN,    rebuy OPEN    → waiting for breakdown
  Phase B: sell FILLED,  rebuy OPEN    → in USD, waiting for re-entry
  Phase C: sell FILLED,  rebuy FILLED  → cycle COMPLETE → STEP 7
  Phase D: any CANCELLED externally → anomaly, alert, exit without auto-reopen

STEP 5 — Phase-specific actions:

  Phase A:
    - Thesis-break check (WebSearch last 12h): if clear invalidation
      (Fed walks back, BTC-positive shock, flows reverse): cancel both
      orders, log "cycle aborted — thesis break (pre-trigger)",
      ACTIVE_CYCLE=false, zero BTC delta.
    - Weekend defense (§2 rule 19): if DOW==6 AND ≤4h to 00:00 UTC Saturday
      AND research bias shifted bullish: cancel both, log, ACTIVE_CYCLE=false.
    - Else: no action.

  Phase B:
    - hours_since_sell = (now − sell_fill_time) in hours.
    - If hours_since_sell ≥ 72 AND rebuy OPEN (§2 rule 15):
        cancel rebuy_order_id
        usd_from_sell = btc_to_sell × sell_fill_price
        python scripts/coinbase.py buy $ORDER_MODE --usd <usd_from_sell>
        → STEP 6 (cycle close, time-cap).
    - Weekend defense (§2 rule 19): if DOW==6 AND ≤4h to Saturday 00:00 UTC
      AND (research deteriorating OR price > sell_fill_price): cancel rebuy,
      market-buy with usd_from_sell, → STEP 6 (weekend_defense=true).
    - Thesis break: same action as 72h cap.
    - Else: no action.

  Phase D: alert, log, exit without commit.

STEP 6 — Cycle close math (72h cap or forced close):
  btc_rebuy_fill = usd_from_sell / market_buy_fill_price
  btc_delta      = btc_rebuy_fill − btc_to_sell
  If btc_delta < 0:
    LAST_LOSING_CYCLE_UTC=$NOW_UTC
    CONSECUTIVE_LOSING_CYCLES += 1
  Else:
    CONSECUTIVE_LOSING_CYCLES = 0
  ACTIVE_CYCLE=false.

STEP 7 — Phase C (clean close):
  btc_rebuy_fill = rebuy_order.filled_size
  btc_delta      = btc_rebuy_fill − btc_to_sell
  Update loss counters as in STEP 6.
  Append "Cycle closed (re-entry filled)" block to TRADE-LOG with
  btc_delta in sats and %.

STEP 8 — Notification: only if state changed.
  bash scripts/telegram.sh "[CYCLE] <close type>: btc_delta ±N.NNNN (±X.X%)."

NOTE: Local run — no commit or push.
