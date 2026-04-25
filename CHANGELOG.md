# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `scripts/fred.py` — FRED (St. Louis Fed) macro data wrapper for rates/macro signals
- `scripts/youtube.py` — YouTube Data API v3 wrapper for sentiment signals
- `scripts/chartinspect.py` — ChartInspect Pro API wrapper for chart analysis signals
- `research/RESEARCH-AGENT-DESIGN-V2.md` — revised research agent design with updated schema (§8)
- `research/RESEARCH-DATA-ALTERNATIVES.md`, `research/RESEARCH-DATA-STATUS.md`, `research/RESEARCH-DATAPOINTS.md` — data source research docs
- `requests>=2.31.0` added to `requirements.txt`
- Env var checks for `CHARTINSPECT_API_KEY`, `YOUTUBE_API_KEY`, `FRED_API_KEY` in research routine pre-flight
- `memory/research-reports/2026-04-24-18.json` — first research run output (B-grade, FOMC Apr 28-29 catalyst, HOLD decision)
- `scripts/risk_math.py` — tested BTC-denominated helper for active-cycle unrealized R math
- `memory/state.json` and `scripts/state.py` — machine-readable cycle/halt/cooldown state seed plus validator.

### Changed
- **Strategy pivot (2026-04-24): USD-swing → BTC-accumulation.** Unit of account is now BTC, not USD. Benchmark is pure HODL (0% BTC growth per quarter) instead of risk-adjusted alpha vs buy-and-hold.
- `memory/TRADING-STRATEGY.md` — full rewrite as v2 accumulation playbook. Key rule changes:
  - Steady state: 80–90% BTC by value, 10–20% USD reserve (was: 70–90% deployed when in a position)
  - "Trade" → "cycle" = sell-trigger (`STOP_LIMIT`) + paired re-entry (`LIMIT` buy), both placed in the same workflow run
  - Risk budget in BTC terms (1.0% A / 0.5% B of BTC stack)
  - Position sizing: `fraction_to_sell = risk_pct / (1 − sell_price / worst_case_rebuy_price)`, capped at 30% of stack
  - Sell-trigger never moves up; re-entry never moves up
  - 72h re-entry time cap → market buy with remaining USD if unfilled
  - Minimum 2:1 R:R measured in BTC terms
  - Four setup types reframed from step-in to step-out: `catalyst_driven_breakdown`, `sentiment_extreme_greed_fade`, `funding_flip_divergence`, `onchain_distribution_top`
  - Weekly grading and drawdown halt both in BTC terms
- `memory/PROJECT-CONTEXT.md` — starting baseline changed from $3,000 equity to 0.05342287 BTC stack. New flags: `ACTIVE_CYCLE`, `LAST_LOSING_CYCLE_UTC`, `CONSECUTIVE_LOSING_CYCLES` replace the v1 stop-out flags
- `memory/TRADE-LOG.md` — Day 0 reframed as quarterly BTC baseline (0.05342287 BTC + $15 USD). Flags the out-of-spec USD reserve (0.4% vs. 10–20% target) requiring an admin rebalance before any cycle can fire
- `memory/RESEARCH-LOG.md` — first research entry appended (2026-04-24 18:00 UTC); correction note added retracting the "rule violation" flags that were scored under v1 USD-swing semantics
- `CLAUDE.md` — hard-rules quick-reference and top-line agent instructions rewritten for accumulation semantics (BTC unit of account, cycles, re-entry pairing, 30% cap, 72h time cap)
- `routines/research-and-plan.md` — full rewrite for v2 accumulation semantics. Drops `$3,000` framing, switches to BTC unit-of-account, adds step-out rubric guidance (greed-only sentiment trigger; exchange *inflow* + falling stablecoin supply on the on-chain item; macro aligned with BTC-negative resolution), adds `exchange BTC net inflow/outflow` and stablecoin-supply queries, requires `playbook_setup ∈ {catalyst_driven_breakdown, sentiment_extreme_greed_fade, funding_flip_divergence, onchain_distribution_top}` and `sell_trigger_price` / `rebuy_limit_price` / `worst_case_rebuy_price` / `btc_r_r ≥ 2.0` on every trade idea, refreshes RESEARCH-LOG block fields (BTC stack + USD reserve % instead of equity)
- `routines/execute.md` — full rewrite for paired-order cycles. Adds admin-rebalance branch (STEP 4) for stacks outside the 80–90% BTC band; replaces buy+stop with atomic STOP_LIMIT-sell + LIMIT-buy pair (STEP 7) including rollback on half-placement; persists `ACTIVE_CYCLE` / `LAST_LOSING_CYCLE_UTC` / `CONSECUTIVE_LOSING_CYCLES` flags; new sizing formula uses `risk_pct / (1 − sell_trigger / worst_case_rebuy)` with 30%-of-stack cap; new gate enforces BTC R:R ≥ 2.0 from the same three prices
- `routines/manage.md` — full rewrite for cycle lifecycle (Phases A/B/C/D). Replaces partials/breakeven/trailing ladder with: detect breakdown (sell-trigger fill), enforce 72h re-entry time cap → market-buy with `usd_from_sell`, weekend defense, thesis-break check; on close, computes `btc_delta = btc_rebuy_fill − btc_to_sell`, increments `CONSECUTIVE_LOSING_CYCLES` on negative deltas
- `routines/panic-check.md` — kill-switches re-derived in BTC terms. (A) active-cycle force-close fires when `unrealized_R >= 1.5` measured against `btc_at_risk_1R = btc_to_sell − usd_from_sell / worst_case_rebuy_price`. (B) drawdown halt fires at `current_btc_stack / quarterly_start_btc − 1 ≤ -0.15`, NOT USD equity. (D) USDC de-peg now cancels any pending re-entry limit and rotates remaining USD to BTC at market
- `routines/daily-summary.md` — EOD snapshot reframed in BTC terms: `today_btc_stack`, `btc_delta_24h` (sats and %), `btc_delta_quarter_pct` vs HODL 0%, USD-reserve % steady-state check, cycles opened/closed today, rolling 7d cycle count
- `routines/weekly-review.md` — week stats in BTC: `week_btc_delta`, `alpha_vs_hodl = week_btc_delta_pct` (HODL = 0%), profit factor in sats, Closed Cycles table keyed on sell-trigger / rebuy / `btc_delta`. Grading rubric (A/B/C/D/F) re-keyed to BTC-delta thresholds per TRADING-STRATEGY §6
- `.claude/commands/{execute,manage,research,daily-summary,weekly-review}.md` — local mirrors of the above with the no-commit footer
- `research/RESEARCH-AGENT-DESIGN-V2.md` — §3 setup-type tables rewritten to the four step-out tags. §1 purpose flipped from "buy-and-hold Sharpe alpha" to "grow BTC stack vs HODL = 0%". §6 routine-cadence row for `manage` now describes cycle lifecycle (sell-trigger fill detection, 72h cap, weekend defense) instead of the v1 §2.14 management ladder. §8 documents the trade-idea field renames (`entry`→`sell_trigger_price`, `target`→`rebuy_limit_price`, `stop` removed, new `worst_case_rebuy_price`) and the `playbook_setup` enum. ETF-flow note in §3.3 rewritten against the four step-out triggers
- `.gitignore` — minor update (line ending normalization)

### Fixed
- `scripts/coinbase.py` — added the missing `limit-buy`, `order`, `fills`, and `product` subcommands needed by the v2 paired-order cycle workflow.
- `scripts/coinbase.py` — guarded the all-BTC `close` command behind `--confirm-sell-all`.
- `routines/panic-check.md` — corrected the active-cycle R trigger direction so BTC-loss breaches fire on positive loss R, not favorable downside moves.
- `CLAUDE.md` and research docs — clarified that `RESEARCH-AGENT-DESIGN-V2.md` is the actionable research plan and v1 is stale history.
- Routines and local commands now read `memory/state.json` as the primary machine-readable state and treat `PROJECT-CONTEXT.md` as a legacy mirror.

### Known follow-ups (not yet done)
- Admin rebalance trade — next execute window must sell ~0.005–0.009 BTC at market to open the 10–20% USD reserve before any step-out cycle fires (STEP 4 branch in the new execute routine handles this automatically when the gate passes)

---

## [0.1.1] — 2026-04-23

### Fixed
- `scripts/coinbase.py` — Coinbase JWT auth bug; added missing env-var handling and additional error paths
- `env.template` — added missing keys and restructured comments
- `memory/COINBASE-API-SETUP.md` — added setup guide documenting API key configuration steps

### Changed
- `.claude/settings.json` — additional tool permissions added
- `.gitignore` — added entries for new artifact types

---

## [0.1.0] — 2026-04-22

### Added
- `scripts/coinbase.py` — Coinbase Advanced Trade JWT auth wrapper (portfolio, buy, sell, stop-limit orders)
- `scripts/research.sh` — research stub (v1; exits 3, delegates to WebSearch)
- `scripts/telegram.sh` — Telegram notification wrapper with `ALLOWED_CHAT_IDS` guard
- `routines/execute.md` — cloud routine: signal → entry → hard stop placement
- `routines/manage.md` — cloud routine: open-position management ladder
- `routines/daily-summary.md` — cloud routine: morning P&L + cooldown status digest
- `routines/weekly-review.md` — cloud routine: Sunday performance review
- `routines/research-and-plan.md` — cloud routine: market research and trade-idea scoring
- `routines/panic-check.md` — cloud routine: emergency position/drawdown check
- `.claude/commands/portfolio.md` — local slash command: account + position snapshot
- `.claude/commands/trade.md` — local slash command: manual trade entry with playbook validation
- `.claude/commands/execute.md` — local slash command: execute workflow
- `.claude/commands/manage.md` — local slash command: manage workflow
- `.claude/commands/research.md` — local slash command: research workflow
- `.claude/commands/daily-summary.md` — local slash command: daily summary workflow
- `.claude/commands/weekly-review.md` — local slash command: weekly review workflow
- `memory/TRADING-STRATEGY.md` — full rulebook (risk ladder, management ladder, cooldown rules, drawdown halt)
- `memory/TRADE-LOG.md` — Day 0 baseline entry ($3,000 equity, no open position)
- `memory/RESEARCH-LOG.md` — research log seed
- `memory/WEEKLY-REVIEW.md` — weekly review log seed
- `memory/PROJECT-CONTEXT.md` — starting equity and drawdown-halt flag
- `CLAUDE.md` — agent rulebook and session read-me-first instructions
- `EVALUATION-COINBASE-BTC.md` — strategy evaluation and playbook reference
- `env.template` — required environment variable template
- `pyproject.toml` / `requirements.txt` — Python project config and dependencies
- `.claude/settings.json` — Claude Code tool permissions

[Unreleased]: https://github.com/KielRN/AI-TRADING-ROUTINE/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/KielRN/AI-TRADING-ROUTINE/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/KielRN/AI-TRADING-ROUTINE/releases/tag/v0.1.0
