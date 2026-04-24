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

### Changed
- `routines/research-and-plan.md` — STEP 4 and STEP 5 now reference `research/RESEARCH-AGENT-DESIGN-V2.md` instead of `research/RESEARCH-AGENT-DESIGN.md`; STEP 5 schema reference updated to `§8` and playbook reference updated to `memory/TRADING-STRATEGY.md §3`
- `.claude/commands/research.md` — same rubric and schema reference updates as cloud routine
- `.gitignore` — minor update (line ending normalization)

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
