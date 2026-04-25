# Remaining Work

This is the execution checklist distilled from `RECOMMENDATIONS.md` after the
2026-04-25 safety pass.

Do not enable automated live cycle opening until the live-blocking section,
held-balance/product metadata checks, CI gates, and paper forward-test are
complete and reviewed end to end.

## Completed Safety Pass

- Fixed the panic-check R sign and added tested BTC-denominated R math.
- Added Coinbase `limit-buy`, `order`, `fills`, and `product` primitives.
- Added first order/fill normalization helpers and Coinbase wrapper tests.
- Added `memory/state.json`, `scripts/state.py`, and state validation tests.
- Disabled the stale v1 manual trade helper.
- Marked v2 research docs as authoritative and the large setup guide as partly
  historical.
- Guarded `coinbase.py close` behind `--confirm-sell-all`.
- Aligned direct Python dependencies across `requirements.txt` and
  `pyproject.toml`.
- Added a two-week paper trading harness and paper-state lane for forward
  testing without live order placement.
- Added a tested live cycle-opening policy layer and wired execute workflows
  to call it before paired sell-trigger plus re-entry order placement.
- Added a tested `scripts/cycle_orders.py open-cycle` transaction helper for
  dry-run paired cycle planning, explicit-live placement, and rollback when
  the re-entry order fails.
- Added tested atomic state transition helpers in `scripts/state.py`, including
  cycle open, sell fill, clean close, forced close, cooldown updates, drawdown
  halt updates, validation, and atomic state-file replacement.
- Wired `scripts/cycle_orders.py open-cycle --live` to persist successful live
  cycle opens into `memory/state.json` through the validator.
- Added per-run idempotency keys, a local routine lock for live cycle-opening
  writes, and live-order reload/recovery after uncertain Coinbase write
  failures.
- Normalized Coinbase order write/read responses across the wrapper and added
  tests for accepted, rejected, terminal-status, exception-recovery, and
  rollback cases.

## Live-Blocking Work

1. [x] Add a tested policy layer. Completed 2026-04-25 continuation.
   - `scripts/policy.py validate-cycle` validates BTC-USD spot only, one
     active cycle, max 30 percent BTC stack per cycle, max two cycles per
     rolling seven days, cooldown, drawdown halt, data freshness, BTC R:R,
     re-entry below sell-trigger, current-price relation, and USD reserve
     band.
   - `tests/test_policy.py` covers pass, rejection, cap, cooldown, stale
     research, reserve, price, and R:R cases.
   - `scripts/cycle_orders.py`, `routines/execute.md`, and
     `.claude/commands/execute.md` call the policy gate before the paired live
     cycle order path can start.
   - Direct order-wrapper bypass prevention is now covered by the dry-run/live
     wrapper flags below.

2. [x] Add dry-run by default. Completed 2026-04-25 continuation.
   - Added `--dry-run` / `--live` flags to Coinbase write paths; direct
     wrapper calls now dry-run unless `--live` is explicit.
   - Required an explicit live flag for real Coinbase order placement and
     cancellation.
   - `scripts/cycle_orders.py open-cycle --dry-run` plans the full paired
     sell-trigger plus re-entry transaction.
   - `--simulate-rebuy-failure` exercises the dry-run rollback path.
   - In `--live`, the helper cancels the sell-trigger if the re-entry order
     fails, and emits one stable JSON status: `planned`, `opened`,
     `rolled_back`, or `blocked`.

3. [x] Make state writes code-owned and atomic. Completed 2026-04-25
   continuation.
   - `scripts/state.py` now owns validated state transitions for cycle open,
     sell fill, clean close, forced close, cooldown updates, and drawdown halt
     updates.
   - Active-cycle state now carries `phase`, `sell_filled_at_utc`,
     `sell_fill_price`, `rebuy_fill_price`, and related fill/close fields.
   - `write_state_atomic()` validates before replacing `memory/state.json`.
   - `scripts/cycle_orders.py open-cycle --live` writes successful live opens
     into `memory/state.json`; dry-runs and rollbacks do not mark
     `ACTIVE_CYCLE=true`.
   - `tests/test_state.py` and `tests/test_cycle_orders.py` cover the state
     transition and live-open persistence paths.

4. [x] Add idempotency and routine locks. Completed 2026-04-25 continuation.
   - Stable `client_order_id` values are generated from `cycle_id` plus order
     role.
   - `scripts/cycle_orders.py open-cycle` accepts `--run-id` and emits an
     idempotency key; default is `open-cycle:<cycle_id>`.
   - Live cycle-opening writes are wrapped in a local atomic lock file at
     `memory/.locks/cycle-orders.lock` unless explicitly disabled for tests.
   - After uncertain Coinbase write exceptions, the helper reloads live open
     orders by stable client order IDs and recovers matching sell/rebuy orders
     before deciding whether rollback is required.

5. [x] Normalize all order responses. Completed 2026-04-25 continuation.
   - `buy`, `sell`, `stop`, `limit-buy`, `close`, `order`, and `orders` now
     emit the same stable local order schema when an order response is present.
   - Rejected Coinbase create-order responses map into `reject_reason` and
     `reject_message`.
   - Tests cover accepted live write normalization, rejected create-order
     normalization, partial/filled/cancelled statuses, API exception recovery,
     and rollback behavior.

## High Priority

1. Account for held balances, fees, and product metadata.
   - Report available, hold/locked, and total balances separately.
   - Include BTC locked in open sell orders when computing stack size and
     drawdown.
   - Enforce Coinbase BTC-USD min size, quote increment, base increment, and
     price increment before placing orders.
   - Include estimated fees and stop-limit slippage in BTC R:R, sizing, and
     admin rebalance math.

2. Reconcile v1/v2 documentation.
   - Split the large setup guide into current `README.md`, `OPERATIONS.md`,
     and `ARCHITECTURE.md`, or keep it explicitly archived.
   - Finish moving routines and commands to one canonical env contract.
   - Add a docs consistency checklist for old terms such as `entry`, `stop`,
     `target`, `USD-swing`, `open position`, and old Coinbase org-path key
     examples.

3. Build the research collector.
   - Implement `research.sh collect`, or explicitly label the current system as
     WebSearch-only shadow mode.
   - Prioritize `fng.py`, `coingecko.py`, `defillama.py`, `candles.py`, and
     `binance.py`.
   - Make `candles.py` a blocker for technical-level trade ideas.
   - Emit one JSON payload with source timestamps, missing slots, stale
     warnings, and raw source snippets.

4. Add CI and linting.
   - Run the current unit tests on every push.
   - Add Ruff formatting/linting for Python.
   - Add shell checks for `scripts/*.sh`.
   - Add secret scanning such as gitleaks or git-secrets.
   - Add a lockfile for the live bot environment.

## Medium Priority

1. Improve notification and audit behavior.
   - Move Telegram fallback notifications from root `DAILY-SUMMARY.md` to
     `memory/NOTIFICATIONS.md` or an ignored log.
   - Use Telegram plain text mode or escape Markdown.
   - Include event IDs in alerts: `cycle_id`, `order_id`, and routine name.
   - Alert on blocked execution, rollback, stale data, and state validation
     failures.

2. Strengthen local/cloud boundaries.
   - Decide whether cloud routines should refuse `.env` loading via
     `BOT_ENV=cloud`.
   - Log credential source only as `process_env` or `local_env_file`, never
     values.

3. Forward-test before live automation.
   - Run the two-week paper campaign in `PAPER-TRADING-TEST.md`.
   - Review false positives, blocked execution events, state drift, and
     rollback behavior before enabling live cycle opening.
