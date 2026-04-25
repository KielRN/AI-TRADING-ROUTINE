# Project Recommendations

This review covers engineering, operational, and automation risk in the BTC
accumulation bot repository. It is not a market call or financial advice.

## Executive Summary

The project has a solid rulebook-first foundation: the strategy is explicit,
trade lifecycle rules are documented, sensitive local files are ignored by git,
and the wrapper-per-service pattern is simple enough to operate. The main risk
is that live trading workflows currently depend on prompt instructions for
critical safety behavior that the code does not yet enforce.

Do not allow the automated cycle-opening path to run live until the hard policy
gates, dry-run/live controls, idempotency, and state-writing paths are
implemented and tested end to end. The missing Coinbase primitives,
panic-check sign issue, first machine-readable state model, and first unit
tests were addressed in the 2026-04-25 safety pass.

Implementation note, 2026-04-25: the first safety pass added the missing
Coinbase order primitives, fixed the panic-check R direction, seeded
`memory/state.json` with validation, disabled the stale v1 manual trade helper,
clarified that research v2 is authoritative, guarded the all-stack `close`
command behind explicit confirmation, aligned direct Python dependencies, and
added unit tests for the new risk/state/Coinbase helper paths. The larger
policy-layer, dry-run, idempotency, and end-to-end routine integration work
remains.

## Critical Recommendations

### 1. Finish the Coinbase execution wrapper before live cycles

Status: substantially implemented on 2026-04-25 for the primitives required by
the v2 routine docs. Keep the remaining normalization, rollback, and
integration items below on the short list before live cycle-opening automation.

Current workflow docs require:

- `python scripts/coinbase.py limit-buy --usd <amt> --price <limit>`
- specific order lookup by ID
- reliable fill price and filled size extraction
- lifecycle classification for OPEN, FILLED, CANCELLED, and partial states

`scripts/coinbase.py` now exposes the required `limit-buy`, `order`, `fills`,
and `product` subcommands. It also has order/fill normalization helpers and
unit coverage for the limit-buy conversion path, nested limit-order
normalization, fill average calculation, and `close` confirmation guard. The
paired sell-trigger plus re-entry order still needs end-to-end dry-run and
live-sandbox-style validation before production cycle opening.

Recommended next work:

- Normalize every order-producing command, including `buy`, `sell`, `stop`,
  and `close`, to the same stable local schema:
  `order_id`, `client_order_id`, `product_id`, `side`, `type`, `status`,
  `base_size`, `quote_size`, `limit_price`, `stop_price`, `filled_size`,
  `average_fill_price`, `created_time`.
- Expand tests that mock Coinbase responses for accepted, rejected, partial
  fill, filled, cancelled, and API failure cases.
- Dry-run the full paired sell-trigger plus re-entry placement, including the
  rollback path when the second order fails.
- Keep production cycle opening blocked until the policy layer and dry-run/live
  controls in recommendation 3 exist.

### 2. Fix the panic-check R-sign bug

Status: fixed on 2026-04-25 in `routines/panic-check.md` and covered by
`scripts/risk_math.py` unit tests.

The old `routines/panic-check.md` active-cycle force-close fired when:

```text
unrealized_R <= -1.5
```

But the documented formula makes losses positive:

```text
unrealized_btc_loss = btc_to_sell - btc_at_market_now
unrealized_R = unrealized_btc_loss / btc_at_risk_1R
```

If BTC price rises after the sell, `btc_at_market_now` is lower than
`btc_to_sell`, so `unrealized_btc_loss` is positive. The trigger should be
`unrealized_R >= 1.5`. The old condition would have triggered on a favorable
move instead of the dangerous move.

Completion notes:

- `routines/panic-check.md` now uses `unrealized_R >= 1.5`.
- The routine includes a numeric example showing rising BTC as bad and falling
  BTC as favorable after the sell fill.
- `scripts/risk_math.py` contains the tested helper, and
  `tests/test_risk_math.py` covers favorable and unfavorable moves.

### 3. Move hard risk gates from prompts into code

Status: not implemented, except that `coinbase.py close` now requires
`--confirm-sell-all`.

The prompts contain strong trading rules, but the executable wrappers can still
place broad market buys, market sells, and stop sells without checking the
playbook. They also do not default to dry-run.

Recommended next work:

- Add a `scripts/policy.py` or `scripts/trade_guard.py` module that validates:
  product is BTC-USD, spot only, max 30 percent of BTC stack per cycle, one
  active cycle, max two cycles per rolling seven days, cooldown, drawdown halt,
  data freshness, BTC R:R, re-entry below sell-trigger, and USD reserve band.
- Make `execute`, manual trade helpers, and order wrappers call that policy
  before any live order.
- Add `--dry-run` to all order paths and make local commands default to dry-run
  unless an explicit live flag is present.
- Keep the `close` confirmation guard covered by tests.

### 4. Replace prompt-parsed state with machine-readable state

Status: started on 2026-04-25 with `memory/state.json`, `scripts/state.py`, and
routine docs that read state first. Remaining work is to make order-writing
code update this file atomically instead of relying on prompt edits.

Current workflows now read `memory/state.json` as the primary source for
`ACTIVE_CYCLE`, cooldown, drawdown halt, and active-cycle order IDs. The brittle
part that remains is that routine prompts still ask the agent to hand-edit JSON
and markdown after live order activity.

Recommended next work:

- Add code-level state transition helpers that update `memory/state.json`
  atomically, instead of relying on prompt edits.
- Extend the active-cycle schema for fill-phase fields such as
  `sell_filled_at_utc`, sell fill price, rebuy fill price, and current phase.
- Keep `memory/TRADE-LOG.md` as the human journal, but make order-writing code
  read/write `state.json` through the validator.
- Add an idempotency key per scheduled run so retries do not double-place
  orders after a partial failure.

## High Priority Recommendations

### 5. Reconcile v1/v2 documentation drift

Several docs and local commands still reference the older USD-swing model:

- `Opus 4.7 Trading Bot - Setup Guide.md` includes older buy/stop lifecycle
  sections and old Coinbase key format examples, but it is now marked with a
  2026-04-25 status note saying those sections are historical unless explicitly
  ported to v2.
- `.claude/commands/trade.md` has been disabled until a v2-safe manual helper
  exists.
- The root setup guide is large enough that stale snippets are easy to copy by
  accident.

Recommended next work:

- Split the large setup guide into current `README.md`, `OPERATIONS.md`, and
  `ARCHITECTURE.md` docs, or keep it clearly archived.
- Finish moving every command and routine to one canonical env contract:
  `COINBASE_API_KEY`, `COINBASE_API_SECRET`, `TELEGRAM_BOT_TOKEN`,
  `ALLOWED_CHAT_IDS`, plus research source keys.
- Add a docs consistency checklist that searches for old terms:
  `entry`, `stop`, `target`, `USD-swing`, `open position`, and old Coinbase
  org-path key examples.

### 6. Build the research collector or downgrade expectations

`research/RESEARCH-AGENT-DESIGN-V2.md` describes a Phase 1 collector set and a
`research.sh collect` composer. The actual `scripts/research.sh` is still a
stub that exits 3 and relies on WebSearch fallback. The latest report also
contains many missing data slots.

Recommended next work:

- Either implement `research.sh collect` or clearly label the current system as
  WebSearch-only shadow mode.
- Prioritize `fng.py`, `coingecko.py`, `defillama.py`, `candles.py`, and
  `binance.py` because they feed load-bearing rubric slots.
- Make `candles.py` a blocker for any technical-level trade idea. Without HTF
  S/R data, the technical rule is not enforceable.
- Have `research.sh collect` emit a single JSON payload with source timestamps,
  missing slots, stale warnings, and raw source snippets.

### 7. Account for held/locked balances, fees, and product metadata

`cmd_account` and `cmd_position` currently use available balances. Open orders
can lock BTC or USD, so available balance can understate the true stack. The
strategy also needs fee-aware BTC R:R and Coinbase product increments.

Recommended next work:

- Report available, hold/locked, and total balances separately.
- Include BTC locked in open sell orders when computing stack size and drawdown.
- Fetch product metadata for BTC-USD and enforce min size, quote increment,
  base increment, and price increment before placing orders.
- Add estimated fees and stop-limit slippage to BTC R:R, position sizing, and
  admin rebalance math.

### 8. Add tests, linting, and CI before more live automation

Status: started. The repo now has `tests/test_risk_math.py`,
`tests/test_state.py`, and `tests/test_coinbase_wrapper.py`. There is still no
lockfile or CI configuration in the repo.

Recommended next work:

- Add or expand unit tests for sizing math, BTC R:R math, state transitions,
  policy gates, and wrapper response normalization.
- Add mock integration tests for Coinbase order placement and rollback.
- Add shell checks for `scripts/*.sh`.
- Add Ruff formatting/linting for Python.
- Add a GitHub Actions workflow that runs the existing unit tests and lint on
  every push.

## Medium Priority Recommendations

### 9. Normalize packaging and dependencies

Status: partially implemented. `requirements.txt` and `pyproject.toml` now
match on the direct runtime dependencies, including `requests`, `PyJWT`, and
`cryptography`. The remaining issue is that there are still two dependency
lists and no lockfile for the live bot environment.

Recommended next work:

- Pick one dependency source of truth or add a process that keeps
  `requirements.txt` and `pyproject.toml` synchronized.
- Add a lockfile with pinned versions for the live bot environment.
- Add a documented setup command for local dev and cloud routine environments.

### 10. Strengthen secret hygiene and local/cloud boundaries

The current `.gitignore` covers `.env`, `*cdp_api_key.json`, and Google key
folders. `git ls-files` did not show `.env` or key JSON files tracked. That is
good. The remaining risk is accidental future leakage or confusion between
local `.env` and cloud env vars.

Recommended next work:

- Add a secret scanner such as gitleaks or git-secrets to CI.
- Keep real credentials out of docs and examples; use `env.template` only.
- Make wrappers log where credentials came from only as `process_env` or
  `local_env_file`, never values.
- Decide whether cloud routines should tolerate wrapper-level `.env` loading or
  whether the wrappers should support `BOT_ENV=cloud` to refuse `.env`.

### 11. Add routine concurrency controls

The scheduled routines commit and push state. Overlap between research,
execute, manage, panic-check, manual commands, or retries could create state
drift or duplicate order attempts.

Recommended next work:

- Add a lock file or remote lock around order-writing routines.
- Use stable `client_order_id` values derived from `cycle_id` and order role so
  retries can detect already-created orders.
- Require routines to reload live order state after any network failure before
  deciding whether to retry.
- Never force-push routine state.

### 12. Improve notification and audit behavior

Telegram fallback writes to `DAILY-SUMMARY.md` in the repo root, which can
create an unexpected artifact. Markdown parse mode can also reject or mangle
messages containing special characters.

Recommended next work:

- Move fallback notifications to `memory/NOTIFICATIONS.md` or an ignored log.
- Use Telegram plain text mode or escape Markdown.
- Include event IDs in alerts: `cycle_id`, `order_id`, and routine name.
- Send alerts on blocked execution, rollback, stale data, and state/schema
  validation failures.

## Suggested Implementation Order

Completed in the 2026-04-25 safety pass:

1. Fixed `panic-check` sign and added tests for the math.
2. Added Coinbase `limit-buy`, `order`, `fills`, and `product` primitives plus
   first response normalization tests.
3. Added machine-readable `memory/state.json`, `scripts/state.py`, and routine
   docs that validate/read state first.

Remaining recommended order:

1. Complete response normalization and mock tests for failed, partial, filled,
   cancelled, and rollback cases.
2. Move rule gates into a tested Python policy layer with dry-run by default.
3. Add atomic state transition helpers, idempotency keys, and routine locks.
4. Account for held/locked balances, fees, and Coinbase product increments.
5. Reconcile v1/v2 docs into current operations docs.
6. Build the research collector and candle/SR pipeline.
7. Add CI, linting, secret scanning, and lockfile.
8. Forward-test in dry-run/shadow mode for at least several weeks before
   enabling cycle-opening automation.

## Positive Notes

- The strategy constraints are unusually explicit for an automation project.
- The wrapper-per-service design is easy to inspect and debug.
- Git ignore rules already cover the obvious local secret files.
- The changelog honestly calls out the 2026-04-25 safety pass and known
  follow-ups.
- The BTC-denominated measurement discipline is clear and consistently reflected
  in the newer v2 memory/routine files.
