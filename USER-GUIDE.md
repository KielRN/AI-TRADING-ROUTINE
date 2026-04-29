# User Guide

This guide is the human-readable map for the project. It explains what the
bot is, how the pieces fit together, what is currently live, and what to check
each day.

## What This Project Is

This is a BTC accumulation trading bot project.

The goal is not to make the USD account value look bigger every day. The goal
is to grow the amount of BTC held over time. The benchmark is simple:

```text
Did the bot end with more BTC than just holding BTC?
```

The strategy uses Coinbase Advanced Trade and trades spot BTC/USD only.

No leverage. No margin. No options. No futures. No altcoins.

## Current Phase

The project is currently in a two-week paper trading test.

That means:

- The routines are live in Claude Code.
- The bot may read real Coinbase account and price data.
- The bot must not place live buy, sell, stop, cancel, or close orders.
- Paper trades are written to `memory/paper-trading/state.json`.
- The live trading state in `memory/state.json` should not be changed by paper
  trading.

The paper test must finish cleanly before live automated cycle opening is
enabled.

## The Current Live Routines

Two Claude Code routines are active.

### BTC paper - research-and-plan

Purpose:

- Research BTC market conditions.
- Score the setup rubric.
- Decide whether there is a valid trade idea.
- Write a research report for the paper routine to use.

Schedule:

```text
0 7,19 * * *
```

Runs at:

```text
7:00 AM and 7:00 PM local time, every day
```

Prompt file:

```text
routines/research-and-plan.md
```

Main outputs:

```text
memory/research-reports/
memory/RESEARCH-LOG.md
```

### BTC paper - paper-trading

Purpose:

- Initialize the two-week paper campaign if needed.
- Pull current BTC price.
- Advance paper fills.
- Open a paper cycle only if fresh research supports it.
- Update paper trading state.

Schedule:

```text
30 7,12,19 * * *
```

Runs at:

```text
7:30 AM, 12:30 PM, and 7:30 PM local time, every day
```

Prompt file:

```text
routines/paper-trading.md
```

Main output:

```text
memory/paper-trading/state.json
```

Important: the 12:30 PM run is mostly a lifecycle check. It can update paper
fills or time caps, but it should not open a new paper cycle unless there is a
fresh research report within the allowed time window.

## How The Automation Works

Claude Code routines are scheduled agent runs.

Each run does roughly this:

1. Starts a fresh cloud session.
2. Clones the GitHub repo.
3. Loads the selected cloud environment.
4. Runs the prompt from the routine instructions.
5. Reads memory files.
6. Calls wrapper scripts.
7. Updates memory files if needed.
8. Commits and pushes changes back to GitHub.

The repo is the bot's long-term memory. If a routine changes a memory file but
does not commit and push, that change will disappear when the cloud session
ends.

## Strategy In Plain English

The bot normally wants to hold mostly BTC.

The target steady state is:

```text
80% to 90% BTC by value
10% to 20% USD reserve
```

The USD reserve is dry powder. The BTC stack is the main asset.

The bot only tries a "step-out" cycle when research says BTC has a strong
downside setup. A cycle means:

1. Sell some BTC if price breaks down through a technical level.
2. Buy that BTC back lower with a limit order.
3. If the buy-back does not happen within 72 hours, buy back at market.

The reason is simple: temporarily step out during a likely drop, then re-enter
lower and end with more BTC.

Success is measured in sats, not dollars.

## Valid Setup Types

Every trade idea must match one of these setup types:

- `catalyst_driven_breakdown`
- `sentiment_extreme_greed_fade`
- `funding_flip_divergence`
- `onchain_distribution_top`

If the research does not fit one of those, the bot should hold.

## Hard Safety Rules

These rules matter more than any signal:

- Spot BTC/USD only.
- One active cycle at a time.
- Max two new cycles in a rolling seven-day window.
- Max 30% of the BTC stack sold in one cycle.
- Minimum 2:1 reward-to-risk in BTC terms.
- No live orders during the paper test.
- No invented trade ideas inside the paper routine.
- Paper trading can only open from a fresh `research-and-plan` report.
- Never force-push routine memory.
- Do not manually edit state files unless you are intentionally repairing
  state and know why.

## Important Files

Start here:

```text
USER-GUIDE.md
```

The main strategy rulebook:

```text
memory/TRADING-STRATEGY.md
```

Paper trading instructions:

```text
PAPER-TRADING-TEST.md
```

Current paper state:

```text
memory/paper-trading/state.json
```

Live trading state, not used for paper cycle execution:

```text
memory/state.json
```

Human trade log:

```text
memory/TRADE-LOG.md
```

Research log:

```text
memory/RESEARCH-LOG.md
```

Cloud routine prompts:

```text
routines/research-and-plan.md
routines/paper-trading.md
routines/execute.md
routines/manage.md
routines/panic-check.md
routines/daily-summary.md
routines/weekly-review.md
```

Local Claude slash-command mirrors:

```text
.claude/commands/
```

Core scripts:

```text
scripts/coinbase.py
scripts/paper_trade.py
scripts/paper_shadow.py
scripts/research_gate.py
scripts/state.py
scripts/policy.py
scripts/cycle_orders.py
scripts/telegram.sh
```

## Local Setup

For local testing:

1. Install Python 3.11 or newer.
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Copy the template env file locally:

```bash
copy env.template .env
```

4. Fill in `.env` with local credentials.

Do not commit `.env`.

Useful checks:

```bash
python scripts/state.py
python scripts/paper_trade.py validate
python scripts/paper_trade.py summary
```

## Cloud Environment Setup

The Claude Code cloud environment should contain the required variables in
`.env` format:

```text
COINBASE_API_KEY=...
COINBASE_API_SECRET=...
TELEGRAM_BOT_TOKEN=...
ALLOWED_CHAT_IDS=...
CHARTINSPECT_API_KEY=...
YOUTUBE_API_KEY=...
FRED_API_KEY=...
```

Use a private dedicated environment for this project.

The setup script should install dependencies:

```bash
#!/bin/bash
set -e
python3 -m pip install -r requirements.txt
```

## What To Check Each Day

In Claude Code Routines:

- Confirm both routines are active.
- Confirm the latest runs completed.
- Read failed run logs immediately.

In the repo:

- Check `memory/RESEARCH-LOG.md` for the latest market read.
- Check `memory/research-reports/` for new JSON reports.
- Check `memory/paper-trading/state.json` for paper state.
- Run `python scripts/paper_trade.py summary` if you want a quick status.

The most important daily question:

```text
Did the paper system behave safely and update state correctly?
```

## What A Paper Cycle Means

Paper cycle phases:

- Phase A: paper sell-trigger is staged.
- Phase B: paper sell filled, paper re-entry is waiting.
- Closed: paper re-entry filled, time cap closed, or campaign ended.

Paper fills are simulated from price quotes. They do not place Coinbase
orders.

## When The Paper Test Is Complete

The paper test is complete only when:

- `memory/paper-trading/state.json` says `status=complete`.
- At least 14 calendar days elapsed from the paper start time.
- Every paper cycle has an event trail.
- No live order-producing Coinbase command was used for paper execution.
- There are no unexplained state mismatches.
- A final review records what happened and whether live automation should be
  allowed.

Passing the paper test does not automatically mean live trading should begin.
It means the system earned a live-readiness review.

## Future Live Mode

Live mode adds these routines:

```text
execute
manage
panic-check
daily-summary
weekly-review
```

Live mode is different because `execute`, `manage`, and `panic-check` can
place or cancel real Coinbase orders when their safety gates allow it.

Do not enable live order automation until the paper test and live-readiness
review are complete.

## Common Problems

### A routine did not update files

Check whether it committed and pushed. Cloud sessions are temporary, so
uncommitted changes disappear.

### Paper-trading says research is stale

This usually means the paper routine ran too long after the research routine.
It should still tick lifecycle state, but it should not open a new paper
cycle.

### Coinbase key missing

Check the Claude cloud environment variables. The routine should stop instead
of continuing with missing keys.

### A routine failed

Read the run log first. Then check:

```text
memory/paper-trading/state.json
memory/RESEARCH-LOG.md
memory/research-reports/
```

### You want to run something manually

Manual `Run now` uses one of the daily routine starts on the Pro plan. Use it
carefully during the two-week paper test.

## Simple Mental Model

Research decides whether a setup exists.

Paper trading tests whether the system can follow the rules without touching
real orders.

Memory files record what happened.

GitHub keeps the memory alive between routine runs.

The live bot only comes later, after the paper test proves the workflow is
boring, auditable, and safe.
