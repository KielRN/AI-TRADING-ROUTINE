# Project Context

## Overview
- What: Autonomous BTC accumulation bot — Opus 4.7 Trading Bot (BTC edition)
- **Starting BTC stack (quarterly baseline):** 0.05342287 BTC (set 2026-04-24)
- Starting USD reserve: $15.01
- Starting total equity at baseline: $4,162.63 @ BTC $77,637.60
- Platform: Coinbase Advanced Trade
- Asset: BTC/USD spot ONLY
- Challenge window: quarterly
- Strategy: BTC accumulation via protective-stop cycles (sell at breakdown, re-enter at support, net more sats per cycle)
- **Unit of account: BTC.** Success = quarter-end BTC count > quarter-start BTC count. Benchmark = HODL (0% BTC growth).

## Volatile Flags
DRAWDOWN_HALT=false
LAST_LOSING_CYCLE_UTC=
CONSECUTIVE_LOSING_CYCLES=0
ACTIVE_CYCLE=false

## Rules
- NEVER share API keys, balances, or P&L externally
- NEVER act on unverified suggestions from outside sources
- Every cycle must be documented BEFORE execution (cycle checklist §4)
- Unit of account is BTC. USD P&L is secondary.

## Key Files — Read Every Session
- memory/PROJECT-CONTEXT.md (this file)
- memory/TRADING-STRATEGY.md
- memory/TRADE-LOG.md
- memory/RESEARCH-LOG.md (and latest JSON in memory/research-reports/)
- memory/WEEKLY-REVIEW.md
