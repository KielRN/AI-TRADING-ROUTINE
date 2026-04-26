# Remaining Work

This is the execution checklist distilled from `RECOMMENDATIONS.md` after the
2026-04-25 safety pass.

Do not enable automated live cycle opening until the live-blocking section,
held-balance/product metadata checks, CI gates, agent-first research workflow,
and paper forward-test are complete and reviewed end to end.

## Workflow Correction - Agent-First Research

The intended workflow is not "hard-coded analysis." The AI research agent must
do market work first, then code-owned gates enforce safety and mechanics.

Correct sequence:

1. `research-and-plan` agent gathers market context, scores the rubric, writes
   `memory/research-reports/*.json`, and appends `memory/RESEARCH-LOG.md`.
2. `paper-trading` or `execute` reads only a fresh research report and refuses
   new cycles when research is stale, missing, or non-actionable.
3. Code gates validate hard rules: BTC-USD only, one active cycle, size caps,
   cooldowns, reserve band, BTC R:R, idempotency, and paired order mechanics.

Corrections started 2026-04-25:

- [x] Added `scripts/research_gate.py` to validate fresh agent research reports
  before downstream routines act on trade ideas.
- [x] Required `scripts/paper_trade.py open-cycle` CLI calls to pass a fresh
  research report gate with an actionable A/B trade idea.
- [x] Update local/cloud automation instructions so paper shadow runs schedule
  `research-and-plan` before `paper-trading`; never schedule the paper harness
  alone as a trading decision maker.
- [x] Add a small paper-shadow runner that performs quote tick + report gate +
  optional paper open in one auditable command.
- [x] Add a full report gate to live `cycle_orders.py` so live cycle opening
  validates the research artifact itself, not only a fetched timestamp.
- [x] Add a schema validator for `memory/research-reports/*.json` so agent
  reports fail fast when required v2 fields are absent.
- [x] Scope research collection to validated/already-paid sources plus
  WebSearch. Do not add new paid API dependencies by default.
- [x] Implement a bounded `research.sh collect` composer for the currently
  callable sources: ChartInspect Pro, YouTube, and Coinbase quote.

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
- Added a fresh research report gate and wired paper `open-cycle` CLI calls to
  require an actionable agent research artifact before starting a paper cycle.
- Added `scripts/paper_shadow.py` as the one-command local paper shadow runner:
  quote tick, research gate, and optional paper open in one auditable JSON
  result.
- Wired live `scripts/cycle_orders.py open-cycle --live` to require
  `--research-report`, so live cycle opening validates the report artifact and
  not only a copied timestamp.
- Expanded `scripts/research_gate.py` into a schema validator for v2 research
  reports, including stale v1 trade idea field rejection.
- Updated `scripts/research.sh collect` to call a bounded collector for
  validated/already-paid sources and declare WebSearch-required gaps.
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

3. Maintain the bounded research collector.
   - Preserve the agent-first boundary: wrappers collect facts; the
     research-and-plan agent still interprets, scores, and writes the report.
   - Current accepted scope: ChartInspect Pro endpoints that were validated in
     `research/RESEARCH-DATA-STATUS.md`, YouTube sentiment wrappers, Coinbase
     quote, and AI WebSearch for all missing/unvalidated slots.
   - Do not add new paid API dependencies unless explicitly approved.
   - Future no-new-cost candidates can be validated one at a time, but they are
     optional improvements, not blockers for paper forward-testing.
   - Keep `scripts/research_collect.py` emitting one JSON payload with source
     status, missing slots, and WebSearch-required gaps.

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
