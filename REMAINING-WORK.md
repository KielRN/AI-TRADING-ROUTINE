# Remaining Work

This is the execution checklist distilled from `RECOMMENDATIONS.md` after the
2026-04-25 safety pass.

Do not enable automated live cycle opening until the live-blocking section is
complete and tested end to end.

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

## Live-Blocking Work

1. Add a tested policy layer.
   - Validate BTC-USD spot only.
   - Enforce one active cycle.
   - Enforce max 30 percent BTC stack per cycle.
   - Enforce max two cycles per rolling seven days.
   - Enforce cooldown, drawdown halt, data freshness, BTC R:R, re-entry below
     sell-trigger, and USD reserve band.
   - Call the policy layer before every live order path.

2. Add dry-run by default.
   - Add `--dry-run` to all order-producing paths.
   - Require an explicit live flag for real Coinbase orders.
   - Dry-run the full paired sell-trigger plus re-entry placement.
   - Dry-run rollback when the second order fails.

3. Make state writes code-owned and atomic.
   - Add state transition helpers for cycle open, sell fill, clean close,
     forced close, cooldown updates, and drawdown halt.
   - Extend state with fill-phase fields such as `sell_filled_at_utc`,
     `sell_fill_price`, `rebuy_fill_price`, and `phase`.
   - Keep `memory/TRADE-LOG.md` as the human journal, but make order-writing
     code update `memory/state.json` through the validator.

4. Add idempotency and routine locks.
   - Generate stable `client_order_id` values from `cycle_id` plus order role.
   - Add an idempotency key per scheduled run.
   - Add a lock file or remote lock around order-writing routines.
   - Reload live order state after network failures before retrying.

5. Normalize all order responses.
   - Make `buy`, `sell`, `stop`, `limit-buy`, `close`, `order`, and `orders`
     emit the same stable local order schema.
   - Cover accepted, rejected, partial fill, filled, cancelled, API failure,
     and rollback cases in tests.

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
   - Run in dry-run or shadow mode for several weeks.
   - Review false positives, blocked execution events, state drift, and
     rollback behavior before enabling live cycle opening.
