# Opus 4.7 Trading Bot — Setup Guide (BTC Swing Edition)

*A complete blueprint for building an autonomous, cloud-scheduled swing
trading agent for BTC/USD on Coinbase Advanced Trade, on top of Claude Code.*

Designed to be self-contained: paste this document into your own Claude Code
session and it should have everything needed to replicate the system
end-to-end.

The agent places real BTC spot trades on Coinbase, writes its own twice-daily
research, executes a disciplined swing strategy with hard rules, and notifies
you via Telegram. It is stateless between runs — all memory lives in your Git
repo.

**Prerequisites:**
- GitHub account
- Coinbase account with Advanced Trade API key (CDP JWT auth)
- Telegram account (to create a dedicated bot via @BotFather)
- Claude Code cloud routines access

**Adapted from:** Nate Herk's original Alpaca/stocks setup guide.
**Strategy playbook:** [EVALUATION-COINBASE-BTC.md](EVALUATION-COINBASE-BTC.md)
**Research design:** [RESEARCH-AGENT-DESIGN.md](RESEARCH-AGENT-DESIGN.md)

---

## Table of Contents

1. [What You're Building](#part-1--what-youre-building)
2. [The Trading Strategy](#part-2--the-trading-strategy)
3. [Repository Layout](#part-3--repository-layout)
4. [The Three Wrapper Scripts](#part-4--the-three-wrapper-scripts)
5. [The Six Workflows in Detail](#part-5--the-six-workflows-in-detail)
6. [Memory Model](#part-6--memory-model)
7. [Setting Up Cloud Routines](#part-7--setting-up-cloud-routines)
8. [The Prompt Scaffold](#part-8--the-prompt-scaffold)
9. [First-Run Troubleshooting](#part-9--first-run-troubleshooting)
10. [Replication Checklist](#part-10--replication-checklist)
11. [Notification Philosophy](#part-11--notification-philosophy)
12. [Appendix A — CLAUDE.md Starter](#appendix-a--claudemd-starter)
13. [Appendix B — env.template](#appendix-b--envtemplate)
14. [Appendix C — scripts/coinbase.py](#appendix-c--scriptscoinbasepy)
15. [Appendix D — scripts/research.sh](#appendix-d--scriptsresearchsh)
16. [Appendix E — scripts/telegram.sh](#appendix-e--scriptstelegramsh)
17. [Appendix F — The Six Routine Prompts](#appendix-f--the-six-routine-prompts)
18. [Appendix G — Ad-hoc Slash Commands](#appendix-g--ad-hoc-slash-commands)
19. [Appendix H — Starter Memory Files](#appendix-h--starter-memory-files)

---

## Part 1 — What You're Building

A fully autonomous swing trading agent for BTC/USD that runs on a 24/7
schedule. Six cron jobs fire throughout the day, each one spinning up a
fresh Claude Code cloud container that clones your repo, reads memory, pulls
live account state, decides on action, places real orders if warranted,
writes new memory, commits everything back to Git, and sends you a Telegram
notification.

There is no separate Python bot process. **Claude is the bot.** Every
scheduled run is a fresh LLM invocation reading a well-defined prompt.

### The six daily jobs at a glance

- **research-and-plan** (00:00 UTC and 12:00 UTC): Research catalysts and
  market context, score the 5-point swing rubric, write a research report
  with 0–2 trade ideas.
- **execute** (00:30 UTC and 12:30 UTC): Consume the latest research report,
  re-validate the top idea, run the buy-side gate, place the buy + stop as
  a single atomic sequence.
- **manage** (every 4 hours): Run the management ladder — breakeven shift
  at +1R, partial at +1.5R, partial + trail at +2R, runner trail thereafter.
- **panic-check** (hourly): Pull positions, enforce kill-switch rules
  (drawdown, stop-failure, stablecoin de-peg).
- **daily-summary** (23:30 UTC): 24h P&L snapshot, equity curve commit,
  Telegram recap.
- **weekly-review** (Sunday 00:00 UTC): Compute weekly stats vs BTC
  buy-and-hold, grade performance A–F, update strategy if warranted.

### Why this design

Three properties drove every decision:

- **Stateless runs** — each firing is independent, so failures self-heal on
  the next tick.
- **Git as memory** — every piece of state is a markdown (or JSON) file
  committed to main. Free versioning, diffs, rollback, and a human-readable
  audit trail.
- **Hard rules as gates** — strategy discipline is enforced programmatically
  before every order, not left to interpretation. The rules live in
  [EVALUATION-COINBASE-BTC.md](EVALUATION-COINBASE-BTC.md).

### What's different from the parent stock-swing bot

- **24/7 market** → schedules are UTC, not US market hours; panic-check is
  hourly; a weekend-gap defense routine is built into `manage`.
- **Coinbase JWT auth** → the trading wrapper is Python, not bash (ES256 JWT
  signing doesn't belong in a shell script).
- **Single asset (BTC/USD)** → no "5-6 positions" juggle; the playbook is
  "one position at a time, sized to rubric grade."
- **No PDT rule** → Coinbase has no day-trade count; the discipline
  substitute is the 2-entries-per-rolling-7-days cap.
- **Telegram, not ClickUp** → notifications post via the Telegram Bot API to
  a dedicated bot (not the TxAI inbound assistant).
- **Research agent, not Perplexity** → v1 uses Claude's native WebSearch via
  the `scripts/research.sh` wrapper contract; v2 swaps in the numeric
  pipeline per [RESEARCH-AGENT-DESIGN.md](RESEARCH-AGENT-DESIGN.md).

---

## Part 2 — The Trading Strategy

This is a swing trading strategy for **BTC/USD spot only**. The complete
rulebook lives in [EVALUATION-COINBASE-BTC.md](EVALUATION-COINBASE-BTC.md).
Every workflow reads that file before acting.

### One-paragraph summary

Swing-trade BTC/USD spot on Coinbase Advanced Trade with $3,000 starting
capital. Hold 1–7 days. One open position at a time. Max two entries per
rolling 7-day window. Risk per trade is graded by the research rubric: 1.0%
on A-grade (5/5), 0.5% on B-grade (3–4/5), skip below 3/5. Every entry has a
hard `STOP_LIMIT` GTC order placed on Coinbase in the same run as the buy;
initial stop is 1R below entry at a technical level, not a round percentage.
Targets are ≥ 2:1 R:R. Management ladder: breakeven at +1R, partial 30% at
+1.5R, partial 30% at +2R, runner trails on 3-ATR or 4h swing low
(whichever is higher). Cooldown 48 hours after a stop-out, 7 days after two
consecutive stop-outs. 15% drawdown from the quarterly starting equity
halts new entries until you `/resume` manually.

### The four playbook setups

Every A- or B-grade trade must match one of these (§3 of the playbook):

1. **`catalyst_driven_breakout`** — scheduled macro catalyst + HTF resistance + neutral funding.
2. **`sentiment_extreme_reversion`** — F&G ≤ 20 or ≥ 80 + HTF level + contrarian funding.
3. **`funding_flip_divergence`** — price makes new local high/low, funding flips opposite.
4. **`onchain_accumulation_base`** — 7d net outflow > $100M + stablecoin supply rising + multi-week base.

### The buy-side gate (checked before every order)

- Playbook setup tag matches one of the four
- Rubric grade is A or B
- Current open BTC position count is 0
- Entries placed in the rolling 7 days + this one ≤ 2
- Risk per trade matches the grade-based sizing formula
- Stop price is at a documented technical level (not a round %)
- Stop is ≥ 0.5% below entry (so it's not a "micro-stop" that'll trigger on noise)
- Target ≥ 2R
- Account is not in a cooldown or drawdown-halt state

If any fail, the trade is skipped and the reason is logged in
`memory/TRADE-LOG.md`.

### The sell-side management ladder

Evaluated by the `manage` routine every 4h (§2 rule 14 of the playbook):
- +1R unrealized → cancel initial stop, place stop at breakeven + 0.2% buffer.
- +1.5R unrealized → sell 30% at market, stop stays at breakeven.
- +2R unrealized → sell 30% at market, move stop to +1R below current.
- Runner (last 40%) → trail on max(3×ATR below current, most recent 4h swing low). Never within 3% of current price.

### Coinbase Advanced Trade gotchas

- **JWT auth, not HMAC.** Uses CDP API keys (ES256-signed JWT). The
  `coinbase-advanced-py` SDK handles signing — don't try to roll your own.
- **Product ID is `BTC-USD`** (not `BTCUSD`, not `BTC/USD`, not `BTC-USDT`).
- **`base_size` vs `quote_size`**. `quote_size` is USD; `base_size` is BTC.
  Market buys use `quote_size` (spend $X); market sells use `base_size`
  (sell X BTC).
- **Stop-limit requires four fields:** `base_size`, `limit_price`,
  `stop_price`, `stop_direction` (`STOP_DIRECTION_STOP_DOWN` for a sell
  stop-loss below current price).
- **Fees are taker-only for market orders** (~0.6% at $3K volume tier). Bake
  a 0.6% round-trip into every R calculation.
- **Rate limits:** 30 req/sec public, 30 req/sec private. The wrapper
  handles retries but a too-chatty routine will throttle.
- **Orders can fail silently on insufficient funds** due to post-only/held
  balances. Always read the response `success` field and the order status
  — don't assume "no exception = order placed."
- **Cancelling a stop and placing a new one is NOT atomic.** There's a
  window where the position has no stop. The `manage` routine places the
  new stop *before* cancelling the old one, so at worst the position
  temporarily has two stops (only one can fill; the other auto-cancels or
  is cancelled by the next run).
- **All timestamps are UTC.** Crons should also be UTC. Sanity check:
  `bash -c 'date -u'` in the routine should return UTC.

---

## Part 3 — Repository Layout

Create a new private GitHub repository. Inside, you will have this
structure:

```
trading-bot/
├── CLAUDE.md                  # Agent rulebook (auto-loaded every session)
├── README.md                  # Human-facing quickstart
├── env.template               # Template for local .env file
├── .gitignore                 # Must exclude .env and __pycache__/
├── pyproject.toml             # Python deps (coinbase-advanced-py, httpx)
├── requirements.txt           # Pinned versions for Claude cloud container
├── .claude/
│   └── commands/              # Ad-hoc slash commands for local use
│       ├── portfolio.md
│       ├── trade.md
│       ├── research.md
│       ├── execute.md
│       ├── manage.md
│       ├── daily-summary.md
│       └── weekly-review.md
├── routines/                  # Cloud routine prompts (the prod path)
│   ├── README.md
│   ├── research-and-plan.md
│   ├── execute.md
│   ├── manage.md
│   ├── panic-check.md
│   ├── daily-summary.md
│   └── weekly-review.md
├── scripts/                   # API wrappers (the only way to touch the outside world)
│   ├── coinbase.py            # Trading wrapper (Python — JWT auth)
│   ├── research.sh            # Research wrapper (v1 stub — exits 3 → WebSearch)
│   └── telegram.sh            # Notification wrapper (bash)
└── memory/                    # Agent's persistent state (committed to main)
    ├── TRADING-STRATEGY.md    # Symlink or copy of EVALUATION-COINBASE-BTC.md
    ├── TRADE-LOG.md
    ├── RESEARCH-LOG.md
    ├── research-reports/      # JSON reports from research-and-plan (one per run)
    ├── WEEKLY-REVIEW.md
    └── PROJECT-CONTEXT.md
```

Two parallel execution modes share this codebase:

- **Local mode** — you invoke slash commands like `/portfolio` manually
  inside Claude Code. Credentials come from a local `.env` file. Good for
  testing and ad-hoc runs.
- **Cloud mode** — Claude's cloud routines fire each `routines/*.md` prompt
  on a cron. Credentials come from the routine's environment variables.
  **No `.env` file.** This is the production path.

---

## Part 4 — The Three Wrapper Scripts

All external API calls flow through three scripts in `scripts/`. The agent
never calls `curl` directly (except to Telegram, which is already a `curl`
inside `telegram.sh`). This keeps auth handling in one place, standardizes
error messages, and makes the prompts much shorter.

### scripts/coinbase.py — trading

Wraps the Coinbase Advanced Trade REST API via the `coinbase-advanced-py`
SDK. Reads `COINBASE_API_KEY` and `COINBASE_API_SECRET` from the environment
(or `.env` locally). Uses JWT (ES256) auth under the hood.

Subcommands (mirroring the original `alpaca.sh` shape, adjusted for crypto
spot):

```bash
python scripts/coinbase.py account                 # USD + BTC balances, total equity
python scripts/coinbase.py position                # BTC position (size, cost basis, unrealized P&L)
python scripts/coinbase.py quote BTC-USD           # latest best bid / best ask
python scripts/coinbase.py orders [status]         # default status=OPEN
python scripts/coinbase.py buy --usd 500           # market buy for $500 USD
python scripts/coinbase.py buy --base 0.005        # market buy for 0.005 BTC
python scripts/coinbase.py sell --pct 30           # sell 30% of current BTC position at market
python scripts/coinbase.py sell --base 0.001       # sell 0.001 BTC at market
python scripts/coinbase.py stop \
    --base 0.005 --stop-price 60000 --limit 59900  # place STOP_LIMIT GTC sell
python scripts/coinbase.py cancel ORDER_ID
python scripts/coinbase.py cancel-all
python scripts/coinbase.py close                   # sell entire BTC position at market
```

The three canonical order operations are:

```
# 1. Market buy (spend USD)
python scripts/coinbase.py buy --usd 500

# 2. Protective stop (1R below entry, placed immediately after buy fills)
python scripts/coinbase.py stop --base 0.005 --stop-price 60000 --limit 59900

# 3. Partial sell (management ladder)
python scripts/coinbase.py sell --pct 30
```

Full implementation in [Appendix C](#appendix-c--scriptscoinbasepy).

### scripts/research.sh — research

Wraps the research backend. **v1 is a stub.** It exits with code 3 to signal
"no backend configured — use native WebSearch," matching the parent doc's
fallback contract. This preserves the wrapper shape while deferring the
numeric pipeline to v2 (per
[RESEARCH-AGENT-DESIGN.md §9](RESEARCH-AGENT-DESIGN.md#9-suggested-order-of-work-when-this-becomes-active)).

```bash
bash scripts/research.sh "<query>"
```

When v2 ships, the script's internals will change to invoke the numeric
pipeline; the contract stays the same and none of the routine prompts need
editing.

### scripts/telegram.sh — notifications

Wraps the Telegram Bot API's `sendMessage` endpoint. Posts to a dedicated
chat channel (NOT the existing TxAI assistant bot — this is a separate
bot for trading notifications only).

```bash
bash scripts/telegram.sh "<markdown message>"
```

Graceful fallback: if `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is missing,
the script appends the message to a local fallback file
(`DAILY-SUMMARY.md`) and exits 0. The agent never crashes on missing
notification credentials.

---

## Part 5 — The Six Workflows in Detail

Every workflow follows the same 8-step scaffold (see Part 8). The
differences are what each one reads and writes. All times are UTC.

### 5.1 research-and-plan (00:00 and 12:00 UTC)

1. Read `memory/TRADING-STRATEGY.md`, the tail of `memory/TRADE-LOG.md`, and
   the most recent `memory/research-reports/*.json`.
2. Pull live account state: `account`, `position`, `orders`, `quote BTC-USD`.
3. Run research queries via `bash scripts/research.sh "<q>"`. If the script
   exits 3, fall back to Claude's native WebSearch tool. Queries:
   - "BTC price, 24h volume, funding rate, open interest latest"
   - "Spot BTC ETF net flows last 24h, split by issuer"
   - "Upcoming US economic calendar next 5 days FOMC CPI NFP"
   - "DXY trend last week, 10Y real yield (DFII10) latest"
   - "Crypto Fear & Greed Index latest value"
   - "BTC dominance and total crypto market cap latest"
   - "Any BTC-specific news last 24h regulation SEC ETF exchange"
4. Score the 5-point swing rubric (per
   [RESEARCH-AGENT-DESIGN.md §5](RESEARCH-AGENT-DESIGN.md#5-the-swing-rubric-replaces-the-fx-rubric-in-decidepy)).
5. Write the JSON report to
   `memory/research-reports/YYYY-MM-DD-HH.json` (schema:
   [RESEARCH-AGENT-DESIGN.md §8.1](RESEARCH-AGENT-DESIGN.md#81-machine-readable-memoryresearch-reportsyyyy-mm-dd-hhjson)).
6. Append a dated human-readable summary to `memory/RESEARCH-LOG.md`
   (account snapshot, market context, rubric scores, trade idea(s),
   decision: TRADE or HOLD).
7. Notification: silent unless the drawdown kill-switch trips or a
   stablecoin de-peg is detected.
8. Commit `memory/research-reports/` and `memory/RESEARCH-LOG.md`, push.

### 5.2 execute (00:30 and 12:30 UTC)

1. Read `memory/TRADING-STRATEGY.md` and the **latest** research report from
   `memory/research-reports/`. If the latest report is >45 minutes old,
   abort — research wasn't fresh enough for this execute window.
2. Pull live state: `account`, `position`, `orders`, `quote BTC-USD`.
3. Check cooldown state from the tail of `memory/TRADE-LOG.md`:
   - Any stop-out in the last 48 hours? Skip.
   - Two stop-outs in the last 7 days? Skip.
   - Drawdown halt in effect? Skip.
4. Run the buy-side gate from Part 2. Log every check result — pass or fail.
   If any check fails, skip and exit.
5. If gate passed, compute position size:
   `size_usd = (equity × risk_pct) / ((entry - stop) / entry)`
   Round *down* to the nearest $10.
6. **Atomic buy + stop sequence:**
   - Place the market buy: `python scripts/coinbase.py buy --usd <size_usd>`
   - Wait for fill (poll `orders` until the buy order's status is `FILLED`,
     max 20 seconds).
   - Read the fill price from the filled order.
   - Compute `base_size` from the fill.
   - Place the stop: `python scripts/coinbase.py stop --base <size> --stop-price <1R_below> --limit <1R_below_minus_50bps>`
   - Verify the stop order accepted. If it rejected, **close the position
     immediately** with `close` and log a critical alert.
7. Append the trade to `memory/TRADE-LOG.md` with the full entry checklist
   from [EVALUATION-COINBASE-BTC.md §4](EVALUATION-COINBASE-BTC.md#4-entry-checklist-agent-documents-all-of-these-before-placing).
8. Notification: Telegram message **only if a trade was actually placed or
   an unrecoverable gate/stop-place failure occurred.**
9. Commit `memory/TRADE-LOG.md`, push. Skip commit if no trade fired.

### 5.3 manage (every 4 hours)

1. Read `memory/TRADING-STRATEGY.md` and the tail of `memory/TRADE-LOG.md`
   (identify open position, entry, initial stop, target, R-value).
2. Pull live state: `position`, `orders`, `quote BTC-USD`.
3. If no open position, exit early (silent).
4. Compute unrealized R: `(current_price - entry) / (entry - initial_stop)`.
5. Management ladder (from the playbook):
   - **If ≥ +1R and stop is still at initial:** place new stop at breakeven
     + 0.2% buffer, then cancel the old stop (in that order).
   - **If ≥ +1.5R and no first partial fired yet:** `sell --pct 30`.
   - **If ≥ +2R and no second partial fired yet:** `sell --pct 30` (of
     remaining), move stop to +1R below current price.
   - **Runner (last 40%):** every run, compute new trail level =
     max(current - 3×ATR(1d), most recent 4h swing low). If current stop is
     below the new trail level by more than 3% of current price, cancel
     current stop and place new stop at the trail level.
6. **Weekend-gap defense:** if current UTC weekday is Saturday and the
   unrealized P&L is within 1.5R of the initial stop, close the whole
   position at market. Log "weekend-gap-defense" as the exit reason.
7. Thesis check: if an intraday catalyst invalidation is detected (news
   event counter to the research report), close at market. Document.
8. Notification: Telegram message only if action was taken (stop moved,
   partial filled, runner trail updated, position closed).
9. Commit `memory/TRADE-LOG.md`, push. Skip commit if no-op.

### 5.4 panic-check (hourly)

1. Pull live state: `account`, `position`, `orders`.
2. **Kill-switch checks** (§8 of the playbook):
   - Unrealized P&L ≤ -1.5R on open position → `close` immediately, alert.
   - Total account equity drawdown ≥ 15% from `memory/PROJECT-CONTEXT.md`
     → flag `DRAWDOWN_HALT=true` in project context, alert, no further
     entries until manual `/resume`.
   - Coinbase API returns 5xx on > 3 consecutive calls → abort run, alert,
     exit. The next scheduled run tries again fresh.
   - Stablecoin de-peg (USDC < $0.98) via `quote USDC-USD` → close, flatten
     to BTC-in-wallet, alert.
3. If no open position and no drawdown halt, exit silently without pushing.
4. Notification: Telegram message only if any kill-switch fired.
5. Commit `memory/PROJECT-CONTEXT.md` only if the drawdown-halt flag
   changed; commit `memory/TRADE-LOG.md` if a position was force-closed.

### 5.5 daily-summary (23:30 UTC)

1. Read `memory/TRADE-LOG.md` for today's entries and the prior EOD snapshot
   (needed for 24h P&L math).
2. Pull final daily state: `account`, `position`, `orders`.
3. Compute:
   - 24h P&L ($ and % vs yesterday's EOD equity)
   - Phase-to-date P&L ($ and % vs quarterly starting equity)
   - Trades today (list or "none")
   - Trades in rolling 7 days (running count for §2 rule 5 of the playbook)
4. Append EOD snapshot to `memory/TRADE-LOG.md`:
   ```
   ### YYYY-MM-DD — EOD Snapshot (Day N)
   **Equity:** $X | **USD cash:** $X | **BTC:** N.NNNN ($X) | **24h P&L:** ±$X (±X%) | **Phase P&L:** ±$X (±X%)
   | Position | Size (BTC) | Entry | Current | Unrealized P&L | Stop |
   **Notes:** one-paragraph plain-english summary.
   ```
5. Send one Telegram message, **always** (even on no-trade days). ≤ 15 lines.
6. Commit `memory/TRADE-LOG.md`, push. **Mandatory** — tomorrow's 24h P&L
   depends on this persisting.

### 5.6 weekly-review (Sunday 00:00 UTC)

1. Read the full week of `memory/TRADE-LOG.md` entries, all
   `memory/research-reports/*.json` from the past 7 days, existing
   `memory/WEEKLY-REVIEW.md` template, and `memory/TRADING-STRATEGY.md`.
2. Pull Sunday-open state: `account`, `position`.
3. Compute week stats (per [EVALUATION-COINBASE-BTC.md §6](EVALUATION-COINBASE-BTC.md#6-weekly-grading-friday--end-of-week-review)):
   - Starting equity (Monday 00:00 UTC from last week's EOD snapshot)
   - Ending equity (current)
   - Week return ($ and %)
   - BTC buy-and-hold return: `quote BTC-USD` now vs price at Monday 00:00 UTC
   - Alpha vs BTC
   - Closed trades (W/L), win rate, best trade, worst trade
   - Profit factor, average R realized
4. Append full review section to `memory/WEEKLY-REVIEW.md`.
5. Assign letter grade (A–F) per the playbook's criteria.
6. If a rule has proven itself for 2+ weeks, or failed badly, update
   `memory/TRADING-STRATEGY.md` in the same commit and call out the change
   in the review. Do NOT change rules on a one-off bad week.
7. Send one Telegram message with headline numbers, always.
8. Commit `memory/WEEKLY-REVIEW.md` (and `memory/TRADING-STRATEGY.md` if
   changed), push.

### Ad-hoc: portfolio

Read-only snapshot. Calls `account`, `position`, `orders`, `quote BTC-USD`.
Prints a clean summary. No state changes, no orders, no file writes. The
only commentary allowed: flag if the open position has no stop, or a stop
is below current price (impossible for a long — if seen, Coinbase returned
stale data).

### Ad-hoc: trade

Manual trade helper. Takes `--usd <amount> --stop <price> [--target <price>]`.
Runs the full buy-side gate. Prints the order JSON + validation results,
asks `execute? (y/n)`. On confirm: executes the buy, immediately places the
`STOP_LIMIT` GTC stop, logs to `memory/TRADE-LOG.md`, sends Telegram
message. Refuses any trade that fails a rule check.

---

## Part 6 — Memory Model

Six memory artifacts, all committed to main, are the agent's only state
between runs.

| File / dir | Purpose | Write cadence |
|---|---|---|
| `memory/TRADING-STRATEGY.md` | The rulebook (copy of EVALUATION-COINBASE-BTC.md). Every workflow reads this first. | Only updated on weekly review if a rule proves out / fails |
| `memory/TRADE-LOG.md` | Every trade + daily EOD snapshot | Every trade, every EOD |
| `memory/RESEARCH-LOG.md` | Human-readable research summaries | Every research-and-plan run |
| `memory/research-reports/` | Machine-readable JSON reports | Every research-and-plan run |
| `memory/WEEKLY-REVIEW.md` | Sunday recaps with letter grade | Weekly |
| `memory/PROJECT-CONTEXT.md` | Static background + volatile flags (drawdown halt, cooldown markers) | Rarely, plus panic-check flag writes |

### Why memory-in-git actually works

- Schedules are at least 30 minutes apart (except hourly panic-check).
  Panic-check only writes when a kill-switch fires, so race conditions are
  rare.
- Memory writes are append-only dated sections. Merge conflicts are
  effectively impossible.
- Each run reads from committed main. Nothing held in-memory across
  firings.
- Rollback is `git revert`. Audit is `git log`. Diff is `git diff`. Free
  observability.

### Where memory-in-git would break

- Two routines scheduled seconds apart (don't do that).
- Someone editing memory files manually during a scheduled run (don't do
  that).
- Panic-check writing simultaneously with `manage` or `execute`. Mitigation:
  panic-check's writes are bounded (only on kill-switch trigger) and use
  `git pull --rebase` before push.
- Partial mid-run failure. A Coinbase buy could fill with no trade log
  entry. Mitigation: the next run reads live positions from Coinbase and
  reconciles against the trade log; discrepancies alert.

---

## Part 7 — Setting Up Cloud Routines

This is the most common sticking point for first-time setup. A Claude Code
cloud routine is a scheduled agent run. Each firing is an ephemeral
container: clone, run, destroy.

### What happens on each scheduled run

1. The cron fires in UTC (set on the routine).
2. Claude's cloud spins up a new container.
3. It clones your GitHub repo at main, so it sees the latest memory.
4. It installs Python deps from `requirements.txt` (first run of a fresh
   container).
5. It injects the environment variables you configured on the routine into
   the shell.
6. It starts Claude with the prompt you pasted into the routine.
7. Claude does the work: reads memory, calls wrappers, writes memory.
8. Claude **must run `git commit` and `git push origin main` before
   exiting.** Otherwise everything it did evaporates.
9. The container is destroyed.

**The mental model:** the cloud runner is stateless. Git is the memory. If
it's not in main, it didn't happen.

### One-time prerequisites

Do these once before creating any routine.

#### Prereq 1 — Install the Claude GitHub App

Visit the Claude GitHub App install page, select only your trading bot
repo (least privilege), and grant access. This gives the cloud container
permission to both clone and push to your repo.

#### Prereq 2 — Enable unrestricted branch pushes on the routine's environment

In the routine's environment settings, toggle on **"Allow unrestricted
branch pushes"**. Without this, `git push origin main` silently fails with
a proxy error. **This is the number-one reason first-time setups break.**

#### Prereq 3 — Set environment variables on the routine (NOT in a `.env` file)

In the routine's environment config, add:

```
COINBASE_API_KEY          (required — CDP API key, format "organizations/.../apiKeys/...")
COINBASE_API_SECRET       (required — EC private key PEM, entire string including BEGIN/END lines)
TELEGRAM_BOT_TOKEN        (required — from @BotFather, format "123456789:ABC...")
TELEGRAM_CHAT_ID          (required — numeric chat ID, can be negative for groups)
```

No PERPLEXITY_* vars (v1 doesn't use Perplexity). No research-backend vars
until v2 ships.

#### Prereq 4 — Create the dedicated Telegram bot

1. In Telegram, message `@BotFather`.
2. Send `/newbot`, follow prompts. Pick a name like "BTC Swing Bot" and a
   unique username ending in `bot`.
3. Copy the bot token → `TELEGRAM_BOT_TOKEN`.
4. Message your new bot with any text (e.g., `/start`).
5. In a browser, visit
   `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your numeric
   chat ID in the JSON response. Copy it → `TELEGRAM_CHAT_ID`.
6. **Do NOT reuse the TxAI Assistant bot.** That bot is for inbound user
   commands; this one is for outbound trading notifications only.

#### Prereq 5 — Create the Coinbase CDP API key

1. Sign in to Coinbase → Developer Platform → Create API key.
2. Permissions: **Trade** + **View**. Not Transfer (the bot never moves
   funds off-exchange).
3. Restrict by IP if possible (Claude cloud IPs are documented in the
   routine setup page).
4. Download the key JSON. The `name` field goes to `COINBASE_API_KEY`; the
   `privateKey` field goes to `COINBASE_API_SECRET` (preserve newlines).

### Why the "no .env file" rule matters

The wrapper scripts read `.env` first, falling back to process environment
variables. In local mode you want the `.env`. In the cloud:

- A `.env` with real credentials committed to the repo would leak secrets
  immediately.
- A `.env` created at runtime is either a secret leak (if pushed) or wasted
  work (if not).
- **Every cloud routine prompt contains an explicit "do not create a .env
  file" block to prevent this.**

### Step-by-step: creating your first routine

Walk-through using `research-and-plan` as the example. Repeat for each of
the six.

1. In Claude Code cloud, go to **Routines → New Routine**.
2. Name the routine, for example "BTC bot — research-and-plan".
3. Select your repository (requires the GitHub App from Prereq 1).
4. Select branch: `main`.
5. Add all environment variables from Prereq 3.
6. Toggle on **"Allow unrestricted branch pushes"** (Prereq 2).
7. Set the cron schedule and timezone UTC. For research-and-plan:
   `0 0,12 * * *` (00:00 and 12:00 UTC daily).
8. Paste the prompt from `routines/research-and-plan.md` into the prompt
   field. Copy everything inside the code block. **Paste verbatim — do not
   paraphrase.**
9. Save.
10. Click **"Run now"** once to test. Do not wait for the next scheduled
    firing to discover it's broken.

### The six cron schedules (UTC)

```
research-and-plan:  0 0,12 * * *      (00:00 and 12:00 UTC daily)
execute:            30 0,12 * * *     (00:30 and 12:30 UTC daily)
manage:             0 */4 * * *       (every 4 hours, on the hour)
panic-check:        15 * * * *        (hourly at :15 past)
daily-summary:      30 23 * * *       (23:30 UTC daily)
weekly-review:      0 0 * * 0         (Sunday 00:00 UTC)
```

Cost note: panic-check at 24 runs/day is the expensive one. If cost is a
concern, drop to every 2h (`15 */2 * * *`) — you'll still catch kill-switch
events within 2 hours of occurrence, which is acceptable for a swing
strategy.

---

## Part 8 — The Prompt Scaffold

Every cloud routine prompt follows the same 8-section shape. Reuse this
template verbatim when adding new routines. Three invariants make this
template robust:

- **Environment check first.** Fails fast with a clear message instead of
  cryptic wrapper errors downstream.
- **Persistence warning is loud.** Without the reminder, Claude skips the
  final push in roughly 10% of runs.
- **Rebase on conflict, never force-push.** Guarantees you never overwrite
  another run's memory.

### The template

```
[PERSONA LINE — who the agent is, the mission, the one-line core rule]

You are running the [WORKFLOW NAME] workflow. Resolve current UTC timestamp via:
DATE=$(date -u +%Y-%m-%d)
HOUR=$(date -u +%H)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

IMPORTANT — ENVIRONMENT VARIABLES:
- Every API key is ALREADY exported as a process env var:
  [list all required vars for this workflow]
- There is NO .env file in this repo and you MUST NOT create, write, or source one.
- If a wrapper prints "KEY not set in environment" → STOP, send one Telegram alert
  naming which var is missing, then exit. Do NOT try to create a .env as a workaround.
- Verify env vars BEFORE any wrapper call:
  for v in VAR1 VAR2 ...; do
    [[ -n "${!v:-}" ]] && echo "$v: set" || echo "$v: MISSING"
  done

IMPORTANT — PERSISTENCE:
- This workspace is a fresh clone. File changes VANISH unless you commit and
  push to main. You MUST commit and push at the end.

STEP 1 — Read memory: [which files, what to look for]
STEP 2 — Pull live state: [which wrapper calls]
STEP 3 ... STEP N-2 — Do the work; write memory as you go
STEP N-1 — Notification via Telegram (conditional per workflow)
STEP N — COMMIT AND PUSH (mandatory):
   git add memory/<files touched>
   git commit -m "<tag> $DATE $HOUR"
   git push origin main
   On push failure from divergence:
     git pull --rebase origin main
     then push again. Never force-push.
```

When you build the actual prompt for each of the six routines, fill in the
persona line, the workflow name, the specific list of env vars to check,
and the numbered work steps. See [Appendix F](#appendix-f--the-six-routine-prompts) for the six full prompts.

---

## Part 9 — First-Run Troubleshooting

Every problem you're likely to hit on day one, and the fix.

| Symptom | Cause | Fix |
|---|---|---|
| "Repository not accessible" / clone fails | Claude GitHub App not installed | Install it, grant access to this specific repo |
| `git push` fails with proxy/permission error | "Allow unrestricted branch pushes" toggle is off | Enable it in the routine's environment |
| `COINBASE_API_KEY not set` | Env var missing from routine env | Add it in the routine config, not the repo's `.env` |
| `invalid_grant` or JWT signature errors | Private key formatting (newlines mangled, missing BEGIN/END) | Paste the full PEM including header/footer lines, preserving `\n` |
| Coinbase returns `PRODUCT_NOT_FOUND` | Wrong product ID | Must be `BTC-USD`, not `BTCUSD` or `BTC-USDT` |
| Coinbase returns `INSUFFICIENT_FUND` on a buy that should fit | Previous stop order is holding quote balance | Cancel stale stops first; `cancel-all` before rebuilding |
| Agent creates a `.env` file anyway | Prompt was paraphrased and lost the "DO NOT create .env" block | Re-paste prompt from `routines/*.md` verbatim |
| Yesterday's trades missing from today's run | Previous run didn't commit + push | Check `git log origin/main`. Re-verify the commit step of the prompt |
| Push fails "fetch first" / non-fast-forward | Another run pushed between this one's clone and push | Prompt handles this with `git pull --rebase`. If looping, check for an actual merge conflict |
| Telegram message didn't arrive | One of the two `TELEGRAM_*` vars is missing | Script silently falls back to a local file. Add the missing vars |
| Telegram returns `chat not found` | Chat ID is wrong, OR you never messaged the bot first | Message the bot at least once (`/start`) so it can reach you |
| Research wrapper (v1) exits 3 | Expected — it's a stub | Routine prompt must handle exit 3 by falling back to native WebSearch |
| `execute` skips with "research too old" | `research-and-plan` didn't run or failed | Check the research-and-plan routine logs; the `:30` execute trails the `:00` research by 30 minutes by design |
| `manage` keeps firing `sell --pct 30` repeatedly | Idempotency flag missing from trade log | Every partial should write a `partial_1r5: true` / `partial_2r: true` marker. Check the trade log schema |
| Panic-check force-closes a fine position | Kill-switch threshold too tight | Review `memory/TRADE-LOG.md` for the exit reason. If false positive, loosen the threshold in the playbook and document in weekly review |
| Stop-limit accepted but doesn't fill during a gap | Limit price too far below stop price | Widen the stop→limit gap. Default: limit = stop × 0.995 (50 bps slippage) |

---

## Part 10 — Replication Checklist

Steps to stand up your own instance, in order.

- [ ] Create a new private GitHub repo.
- [ ] Build the directory structure from Part 3.
- [ ] Copy the three wrapper scripts from Appendices C–E.
      `chmod +x scripts/*.sh`.
      `pip install coinbase-advanced-py httpx python-dotenv` (or use `requirements.txt`).
- [ ] Copy the CLAUDE.md starter from Appendix A.
- [ ] Copy env.template from Appendix B. **Do NOT commit a real `.env`.**
- [ ] Add `.env` and `__pycache__/` to `.gitignore`.
- [ ] Copy the seven slash commands (Appendix G) into `.claude/commands/`.
- [ ] Copy the six routine prompts (Appendix F) into `routines/`.
- [ ] Seed the five memory files from Appendix H. Copy
      `EVALUATION-COINBASE-BTC.md` into `memory/TRADING-STRATEGY.md`.
- [ ] Create the dedicated Telegram bot (Prereq 4).
- [ ] Create the Coinbase CDP API key (Prereq 5).
- [ ] **Local smoke test:** copy `env.template` to `.env`, fill in
      credentials, open repo in Claude Code, run `/portfolio`. You should
      see account + position + BTC quote print cleanly.
- [ ] Install the Claude GitHub App on your repo.
- [ ] Create the first cloud routine (`research-and-plan`) per Part 7.
- [ ] Hit "Run now" and watch the logs. Verify research report JSON written,
      research log entry appended, committed, pushed.
- [ ] If that works, create the other five routines with the same pattern.
- [ ] Seed `memory/TRADE-LOG.md` with a Day 0 EOD snapshot so Day 1's
      daily-summary has a baseline.
- [ ] Seed `memory/PROJECT-CONTEXT.md` with starting equity ($3,000) and
      `DRAWDOWN_HALT=false`.
- [ ] Monitor the first week closely. Read every commit the agent makes.

---

## Part 11 — Notification Philosophy

Most bots are chatty. This one is not. The rules:

- **research-and-plan:** silent unless drawdown halt or de-peg alert.
- **execute:** only if a trade was actually placed, or an unrecoverable
  failure fired.
- **manage:** only if action was taken (stop moved, partial filled, runner
  trail adjusted, thesis-break close).
- **panic-check:** only if a kill-switch tripped.
- **daily-summary:** always sends, one message, ≤ 15 lines.
- **weekly-review:** always sends, one message, headline numbers + grade.

The cost of a missed notification is low (you can always `/portfolio` or
check Coinbase directly). The cost of a chatty bot is high (you stop
reading the messages, and then you miss the one that mattered).

---

## Appendix A — CLAUDE.md Starter

This file lives at the root of your repo. Claude Code auto-loads it every
session.

```markdown
# BTC Swing Bot — Agent Instructions

You are an autonomous AI trading bot managing a LIVE $3,000 Coinbase
Advanced Trade account. Your asset is BTC/USD spot ONLY. Your goal is to
generate alpha vs BTC buy-and-hold on a risk-adjusted basis over each
quarterly challenge window. You are disciplined, patient, and ruthless about
rule violations. Communicate ultra-concise: short bullets, no fluff.

## Read-Me-First (every session)

Open these in order before doing anything:

- `memory/TRADING-STRATEGY.md` — Your rulebook. Never violate.
- `memory/TRADE-LOG.md` — Tail for open position, entry, stop, cooldown state.
- `memory/research-reports/` — Latest JSON report for the current execute window.
- `memory/RESEARCH-LOG.md` — Human-readable research summary.
- `memory/PROJECT-CONTEXT.md` — Starting equity + any active DRAWDOWN_HALT flag.
- `memory/WEEKLY-REVIEW.md` — Sunday reviews; template for new entries.

## Daily Workflows

Defined in `.claude/commands/` (local) and `routines/` (cloud). Six
scheduled runs per day plus two ad-hoc helpers.

## Strategy Hard Rules (quick reference)

- SPOT ONLY — no leverage, no options, no perps, no altcoins, no staking.
- ONE open BTC position at a time.
- Max 2 new entries per rolling 7-day window.
- Risk: 1.0% (A-grade), 0.5% (B-grade), skip below 3/5.
- Hard stop as real `STOP_LIMIT` GTC order in the same run as the buy.
- Stop at a technical level, not a round %.
- Never move a stop down.
- Target ≥ 2R.
- Management ladder: BE at +1R, 30% partial at +1.5R, 30% partial + trail at +2R, runner.
- Cooldown 48h after a stop-out, 7d after two consecutive stop-outs.
- 15% drawdown halts new entries until `/resume`.
- Weekend-gap defense: close if ≤1.5R from stop before Saturday UTC.

## API Wrappers

- `python scripts/coinbase.py ...` — trading
- `bash scripts/research.sh "<q>"` — research (v1: exits 3 → use WebSearch)
- `bash scripts/telegram.sh "<msg>"` — notifications

Never call Coinbase or Telegram APIs directly.

## Communication Style

Ultra concise. No preamble. Short bullets. Match existing memory file
formats exactly — don't reinvent tables.
```

---

## Appendix B — env.template

Copy to `.env` locally. The file is gitignored. In cloud routines, set
these as environment variables on the routine itself — do NOT create a
`.env` file in the cloud.

```bash
# Coinbase Advanced Trade (LIVE spot trading)
COINBASE_API_KEY="organizations/.../apiKeys/..."
COINBASE_API_SECRET="-----BEGIN EC PRIVATE KEY-----
MHcCAQEE...
-----END EC PRIVATE KEY-----"

# Telegram (dedicated bot for trading notifications — NOT the TxAI bot)
TELEGRAM_BOT_TOKEN=123456789:ABCdef-your-token-here
TELEGRAM_CHAT_ID=123456789
```

---

## Appendix C — scripts/coinbase.py

```python
#!/usr/bin/env python3
"""Coinbase Advanced Trade wrapper. All trading API calls go through here.

Usage:
    python scripts/coinbase.py <subcommand> [args...]

Subcommands:
    account, position, quote, orders, buy, sell, stop, cancel, cancel-all, close
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # cloud runner may not need it
    load_dotenv = None

from coinbase.rest import RESTClient  # coinbase-advanced-py

PRODUCT = "BTC-USD"
ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

if load_dotenv and ENV_FILE.exists():
    load_dotenv(ENV_FILE)

API_KEY = os.getenv("COINBASE_API_KEY")
API_SECRET = os.getenv("COINBASE_API_SECRET")

if not API_KEY:
    print("COINBASE_API_KEY not set in environment", file=sys.stderr)
    sys.exit(3)
if not API_SECRET:
    print("COINBASE_API_SECRET not set in environment", file=sys.stderr)
    sys.exit(3)

client = RESTClient(api_key=API_KEY, api_secret=API_SECRET)


def _dump(obj) -> None:
    """Dump any SDK response as pretty JSON for the agent to parse."""
    if hasattr(obj, "to_dict"):
        obj = obj.to_dict()
    print(json.dumps(obj, indent=2, default=str))


def _q(n: Decimal, places: int) -> str:
    """Quantize down to `places` decimal places, return string."""
    quant = Decimal(10) ** -places
    return str(n.quantize(quant, rounding=ROUND_DOWN))


def cmd_account(args) -> None:
    accounts = client.get_accounts()
    usd_bal = Decimal("0")
    btc_bal = Decimal("0")
    for a in accounts["accounts"]:
        cur = a["currency"]
        avail = Decimal(a["available_balance"]["value"])
        if cur == "USD":
            usd_bal += avail
        elif cur == "BTC":
            btc_bal += avail
    # Fetch current BTC price for equity math
    bid_ask = client.get_best_bid_ask(product_ids=[PRODUCT])
    price = Decimal(bid_ask["pricebooks"][0]["bids"][0]["price"])
    equity = usd_bal + btc_bal * price
    _dump({
        "usd_balance": str(usd_bal),
        "btc_balance": str(btc_bal),
        "btc_price": str(price),
        "equity_usd": str(equity),
    })


def cmd_position(args) -> None:
    accounts = client.get_accounts()
    btc_bal = Decimal("0")
    for a in accounts["accounts"]:
        if a["currency"] == "BTC":
            btc_bal = Decimal(a["available_balance"]["value"])
            break
    bid_ask = client.get_best_bid_ask(product_ids=[PRODUCT])
    price = Decimal(bid_ask["pricebooks"][0]["bids"][0]["price"])
    _dump({
        "product_id": PRODUCT,
        "size_btc": str(btc_bal),
        "current_price": str(price),
        "notional_usd": str(btc_bal * price),
        "has_position": btc_bal > Decimal("0.00001"),
    })


def cmd_quote(args) -> None:
    product = args.product or PRODUCT
    bid_ask = client.get_best_bid_ask(product_ids=[product])
    pb = bid_ask["pricebooks"][0]
    _dump({
        "product_id": product,
        "bid": pb["bids"][0]["price"] if pb["bids"] else None,
        "ask": pb["asks"][0]["price"] if pb["asks"] else None,
        "time": pb.get("time"),
    })


def cmd_orders(args) -> None:
    status = args.status.upper() if args.status else "OPEN"
    resp = client.list_orders(order_status=[status], product_ids=[PRODUCT])
    _dump(resp)


def cmd_buy(args) -> None:
    coid = str(uuid.uuid4())
    if args.usd:
        usd = Decimal(args.usd).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        resp = client.market_order_buy(
            client_order_id=coid,
            product_id=PRODUCT,
            quote_size=str(usd),
        )
    elif args.base:
        btc = Decimal(args.base)
        resp = client.market_order_buy(
            client_order_id=coid,
            product_id=PRODUCT,
            base_size=_q(btc, 8),
        )
    else:
        print("usage: buy --usd <amt> OR --base <btc>", file=sys.stderr)
        sys.exit(1)
    _dump(resp)


def cmd_sell(args) -> None:
    coid = str(uuid.uuid4())
    if args.pct is not None:
        # Sell a percentage of current BTC balance.
        accounts = client.get_accounts()
        btc_bal = Decimal("0")
        for a in accounts["accounts"]:
            if a["currency"] == "BTC":
                btc_bal = Decimal(a["available_balance"]["value"])
                break
        if btc_bal <= 0:
            print("no BTC balance to sell", file=sys.stderr)
            sys.exit(2)
        size = (btc_bal * Decimal(args.pct) / Decimal(100))
        resp = client.market_order_sell(
            client_order_id=coid,
            product_id=PRODUCT,
            base_size=_q(size, 8),
        )
    elif args.base:
        resp = client.market_order_sell(
            client_order_id=coid,
            product_id=PRODUCT,
            base_size=_q(Decimal(args.base), 8),
        )
    else:
        print("usage: sell --pct <n> OR --base <btc>", file=sys.stderr)
        sys.exit(1)
    _dump(resp)


def cmd_stop(args) -> None:
    coid = str(uuid.uuid4())
    resp = client.stop_limit_order_gtc_sell(
        client_order_id=coid,
        product_id=PRODUCT,
        base_size=_q(Decimal(args.base), 8),
        limit_price=str(Decimal(args.limit)),
        stop_price=str(Decimal(args.stop_price)),
        stop_direction="STOP_DIRECTION_STOP_DOWN",
    )
    _dump(resp)


def cmd_cancel(args) -> None:
    resp = client.cancel_orders(order_ids=[args.order_id])
    _dump(resp)


def cmd_cancel_all(args) -> None:
    open_orders = client.list_orders(order_status=["OPEN"], product_ids=[PRODUCT])
    ids = [o["order_id"] for o in open_orders.get("orders", [])]
    if not ids:
        _dump({"cancelled": 0, "order_ids": []})
        return
    resp = client.cancel_orders(order_ids=ids)
    _dump(resp)


def cmd_close(args) -> None:
    accounts = client.get_accounts()
    btc_bal = Decimal("0")
    for a in accounts["accounts"]:
        if a["currency"] == "BTC":
            btc_bal = Decimal(a["available_balance"]["value"])
            break
    if btc_bal <= Decimal("0.00001"):
        _dump({"closed": False, "reason": "no BTC position"})
        return
    coid = str(uuid.uuid4())
    resp = client.market_order_sell(
        client_order_id=coid,
        product_id=PRODUCT,
        base_size=_q(btc_bal, 8),
    )
    _dump(resp)


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("account")
    sub.add_parser("position")

    sp = sub.add_parser("quote")
    sp.add_argument("product", nargs="?", default=PRODUCT)

    sp = sub.add_parser("orders")
    sp.add_argument("status", nargs="?", default="OPEN")

    sp = sub.add_parser("buy")
    sp.add_argument("--usd")
    sp.add_argument("--base")

    sp = sub.add_parser("sell")
    sp.add_argument("--pct", type=Decimal)
    sp.add_argument("--base")

    sp = sub.add_parser("stop")
    sp.add_argument("--base", required=True)
    sp.add_argument("--stop-price", required=True)
    sp.add_argument("--limit", required=True)

    sp = sub.add_parser("cancel")
    sp.add_argument("order_id")

    sub.add_parser("cancel-all")
    sub.add_parser("close")

    args = p.parse_args()

    handlers = {
        "account": cmd_account,
        "position": cmd_position,
        "quote": cmd_quote,
        "orders": cmd_orders,
        "buy": cmd_buy,
        "sell": cmd_sell,
        "stop": cmd_stop,
        "cancel": cmd_cancel,
        "cancel-all": cmd_cancel_all,
        "close": cmd_close,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
```

`requirements.txt`:
```
coinbase-advanced-py>=1.8.0
httpx>=0.27.0
python-dotenv>=1.0.0
```

---

## Appendix D — scripts/research.sh

```bash
#!/usr/bin/env bash
# Research wrapper. V1 is a stub — exits 3 to signal "no backend configured"
# and let the routine fall back to Claude's native WebSearch tool, matching
# the parent doc's fallback contract.
#
# V2 will replace the internals with the numeric pipeline defined in
# RESEARCH-AGENT-DESIGN.md (§3). The wrapper contract stays the same so no
# routine prompts need editing.
#
# Usage: bash scripts/research.sh "<query>"

set -euo pipefail

query="${1:-}"
if [[ -z "$query" ]]; then
    echo "usage: bash scripts/research.sh \"<query>\"" >&2
    exit 1
fi

# V1: always fall through to WebSearch. Agent is instructed to handle exit 3.
echo "WARNING: research backend not configured. Fall back to WebSearch." >&2
echo "QUERY_FOR_WEBSEARCH: $query"
exit 3
```

---

## Appendix E — scripts/telegram.sh

```bash
#!/usr/bin/env bash
# Notification wrapper. Posts to a dedicated Telegram bot (NOT the TxAI
# inbound assistant). If credentials are unset, appends to a local fallback
# file.
#
# Usage: bash scripts/telegram.sh "<message>"

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
FALLBACK="$ROOT/DAILY-SUMMARY.md"

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

if [[ $# -gt 0 ]]; then
    msg="$*"
else
    msg="$(cat)"
fi

if [[ -z "${msg// /}" ]]; then
    echo "usage: bash scripts/telegram.sh \"<message>\"" >&2
    exit 1
fi

stamp="$(date -u '+%Y-%m-%d %H:%M UTC')"

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
    printf "\n---\n## %s (fallback — Telegram not configured)\n%s\n" "$stamp" "$msg" >> "$FALLBACK"
    echo "[telegram fallback] appended to DAILY-SUMMARY.md"
    echo "$msg"
    exit 0
fi

# Telegram has a 4096-character message cap. Truncate defensively.
if [[ ${#msg} -gt 4000 ]]; then
    msg="${msg:0:3990}…"
fi

curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${msg}" \
    --data-urlencode "parse_mode=Markdown" \
    --data-urlencode "disable_web_page_preview=true"

echo
```

---

## Appendix F — The Six Routine Prompts

Paste each verbatim into its respective Claude Code cloud routine. **Do not
paraphrase.** The env-var check block and the commit-and-push step are
load-bearing.

### F.1 routines/research-and-plan.md — cron: `0 0,12 * * *` (UTC)

```
You are an autonomous BTC swing bot managing a LIVE $3,000 Coinbase
Advanced Trade account. SPOT BTC/USD ONLY — NEVER leverage, NEVER altcoins,
NEVER options. Ultra-concise: short bullets, no fluff.

You are running the research-and-plan workflow. Resolve timestamps via:
DATE=$(date -u +%Y-%m-%d)
HOUR=$(date -u +%H)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

IMPORTANT — ENVIRONMENT VARIABLES:
- Every API key is ALREADY exported: COINBASE_API_KEY, COINBASE_API_SECRET,
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
- There is NO .env file in this repo and you MUST NOT create, write, or source one.
- If a wrapper prints "KEY not set in environment" → STOP, send one Telegram
  alert naming the missing var, and exit.
- Verify env vars BEFORE any wrapper call:
    for v in COINBASE_API_KEY COINBASE_API_SECRET TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
      [[ -n "${!v:-}" ]] && echo "$v: set" || echo "$v: MISSING"
    done

IMPORTANT — PERSISTENCE:
- Fresh clone. File changes VANISH unless committed and pushed. MUST commit
  and push at STEP 8.

STEP 1 — Read memory for context:
- memory/TRADING-STRATEGY.md
- tail of memory/TRADE-LOG.md (open position? cooldown state?)
- tail of memory/RESEARCH-LOG.md
- memory/PROJECT-CONTEXT.md (check DRAWDOWN_HALT flag)

STEP 2 — Pull live state:
python scripts/coinbase.py account
python scripts/coinbase.py position
python scripts/coinbase.py orders
python scripts/coinbase.py quote BTC-USD

STEP 3 — Research via WebSearch. For each query below, run:
    bash scripts/research.sh "<query>"
  If exit code is 3 (expected in v1), use your native WebSearch tool for the
  same query and cite the sources. Queries:
- "BTC price 24h volume funding rate open interest latest"
- "Spot BTC ETF net flows last 24 hours split by issuer"
- "US economic calendar next 5 days FOMC CPI NFP"
- "DXY trend last week, 10Y real yield DFII10 latest"
- "Crypto Fear Greed Index latest"
- "BTC dominance and total crypto market cap latest"
- "BTC-specific news last 24h regulation SEC ETF exchange failure"

STEP 4 — Score the 5-point swing rubric per RESEARCH-AGENT-DESIGN.md §5.
Each item scored boolean:
1. catalyst: clear scheduled catalyst in next 1–5 days?
2. sentiment_extreme_or_divergence: F&G extreme OR price/funding divergence OR OI-vs-price divergence?
3. onchain_or_structure: exchange net flow OR stablecoin supply OR BTC-D regime aligned?
4. macro_aligned: DXY + real yields + SPX regime consistent, no adverse print in 24h?
5. technical_level: entry at weekly/monthly S/R (not daily noise)?
Grade: 5/5 = A; 3–4/5 = B; <3 = skip.
Catalyst=false caps at B regardless.

STEP 5 — Write JSON report to memory/research-reports/$DATE-$HOUR.json
matching the schema in RESEARCH-AGENT-DESIGN.md §8.1. Include 0–2 trade
ideas, each with playbook_setup matching EVALUATION-COINBASE-BTC.md §3.

STEP 6 — Append human-readable summary to memory/RESEARCH-LOG.md:
### $DATE $HOUR:00 UTC — Research
**Equity:** $X | **Position:** [none | size btc @ entry] | **Cooldown:** [none | until XXX]
**Market:** BTC $X | funding X% | F&G X | BTC-D X% | DXY X | 10Y real X%
**Catalyst:** [upcoming events]
**Rubric:** catalyst=X sentiment=X onchain=X macro=X technical=X → Grade X
**Trade idea:** [playbook_setup, entry, stop, target, R:R, thesis] or "HOLD"

STEP 7 — Notification: silent unless DRAWDOWN_HALT=true OR stablecoin de-peg detected.
If alert fires:
    bash scripts/telegram.sh "[ALERT] <one-line reason>"

STEP 8 — COMMIT AND PUSH (mandatory):
    git add memory/research-reports/ memory/RESEARCH-LOG.md memory/PROJECT-CONTEXT.md
    git commit -m "research $DATE $HOUR:00"
    git push origin main
On push failure: git pull --rebase origin main, then push again. Never force-push.
```

### F.2 routines/execute.md — cron: `30 0,12 * * *` (UTC)

```
You are an autonomous BTC swing bot. SPOT BTC/USD ONLY. Ultra-concise.

You are running the execute workflow. Resolve timestamps via:
DATE=$(date -u +%Y-%m-%d)
HOUR=$(date -u +%H)

IMPORTANT — ENVIRONMENT VARIABLES: [same block as research-and-plan]
IMPORTANT — PERSISTENCE: [same block, push at STEP 9]

STEP 1 — Read memory:
- memory/TRADING-STRATEGY.md
- Latest memory/research-reports/*.json (must be dated within last 45 minutes).
  If stale, log "research stale, skipping" and exit without commit.
- tail of memory/TRADE-LOG.md (open position? cooldown? weekly entry count?)
- memory/PROJECT-CONTEXT.md

STEP 2 — Pull live state:
python scripts/coinbase.py account
python scripts/coinbase.py position
python scripts/coinbase.py orders
python scripts/coinbase.py quote BTC-USD

STEP 3 — Check cooldown + halt state:
- Any stop-out in last 48h in TRADE-LOG → skip, log reason, exit
- Two stop-outs in last 7d → skip, exit
- DRAWDOWN_HALT=true in PROJECT-CONTEXT → skip, exit

STEP 4 — Buy-side gate. ALL must pass:
□ Research report has a trade_idea with grade A or B
□ playbook_setup matches one of the four documented setups
□ Current BTC position is 0 (already flat)
□ Entries in rolling 7d + this one ≤ 2
□ Stop is at a technical level (not a round %)
□ Stop is ≥ 0.5% below entry
□ Target ≥ 2R from entry
□ Risk per trade matches grade (1.0% A, 0.5% B)

If any fail → skip, log every check result, exit without commit.

STEP 5 — Compute size:
  risk_pct = 1.0% if A else 0.5%
  risk_usd = equity × risk_pct
  risk_per_btc = entry - stop
  size_btc = risk_usd / risk_per_btc
  size_usd = size_btc × entry, rounded DOWN to nearest $10
Announce size before placing.

STEP 6 — ATOMIC buy + stop:
  python scripts/coinbase.py buy --usd <size_usd>
  Poll orders until buy is FILLED (max 20 sec). Read fill price.
  size_btc = (size_usd / fill_price), rounded DOWN to 8 decimal places
  limit = stop × 0.995  (50 bps slippage buffer below stop)
  python scripts/coinbase.py stop --base <size_btc> --stop-price <stop> --limit <limit>
  Verify stop accepted. If REJECTED:
    python scripts/coinbase.py close
    bash scripts/telegram.sh "[CRITICAL] Stop rejected; position force-closed."
    exit

STEP 7 — Append trade to memory/TRADE-LOG.md using the entry checklist from
EVALUATION-COINBASE-BTC.md §4. Include:
- Rubric grade + scores
- Playbook setup
- Thesis paragraph
- Entry, stop, target, R:R
- Position size (USD and BTC)
- Weekly count including this trade

STEP 8 — Notification (trade placed):
    bash scripts/telegram.sh "[TRADE] BUY BTC @ $fill. Size: X.XXXX BTC ($Y). Stop $Z. Target $T. Setup: <playbook>."

STEP 9 — COMMIT AND PUSH (only if trade fired):
    git add memory/TRADE-LOG.md
    git commit -m "execute $DATE $HOUR:30"
    git push origin main
On push failure: rebase and retry.
```

### F.3 routines/manage.md — cron: `0 */4 * * *` (UTC)

```
You are an autonomous BTC swing bot. SPOT BTC/USD ONLY. Ultra-concise.

You are running the manage workflow. Resolve timestamps via:
DATE=$(date -u +%Y-%m-%d)
HOUR=$(date -u +%H)
DOW=$(date -u +%u)  # 1=Mon ... 7=Sun. Saturday=6.

IMPORTANT — ENVIRONMENT VARIABLES: [same block]
IMPORTANT — PERSISTENCE: [same block, push at STEP 9]

STEP 1 — Read memory:
- memory/TRADING-STRATEGY.md (management ladder rules)
- tail of memory/TRADE-LOG.md (find OPEN trade: entry, initial_stop,
  target, R-value, partials fired so far)

STEP 2 — Pull live state:
python scripts/coinbase.py position
python scripts/coinbase.py orders
python scripts/coinbase.py quote BTC-USD

STEP 3 — If no open position, exit silent (no commit).

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
   Compute new_stop = current_price - (entry - initial_stop)  (trail 1R back)
   Cancel old stop, place new stop at new_stop.
   Log "partial_2r @ $current_price, stop moved to $new_stop"

D) Runner trail (after partial_2r fired):
   atr_1d = ask WebSearch for BTC 1D ATR 14 latest OR compute from historical
            quotes (pull last 14 daily closes — skip if unavailable, use
            3% static buffer)
   swing_low_4h = most recent 4h swing low (from recent quotes or WebSearch)
   new_trail = max(current_price - 3*atr_1d, swing_low_4h)
   If new_trail > current stop by more than 3% of current price AND
   new_trail < current price × 0.97 (not within 3%):
     Cancel old, place new stop at new_trail.
   Log runner trail update.

STEP 6 — Weekend-gap defense:
If DOW == 6 AND current time is <= 4h from 00:00 UTC Saturday AND
   unrealized_R <= -0.5  (within 1.5R of the initial stop, i.e. >=0.5R unfavorable):
     python scripts/coinbase.py close
     python scripts/coinbase.py cancel-all
     Log "weekend-gap-defense exit at $price, unrealized R=$R"

STEP 7 — Thesis-break check: review last 12h of BTC news via WebSearch.
If a catalyst invalidation is clear (Fed walked back, major regulatory
shock against BTC, exchange failure):
  python scripts/coinbase.py close; cancel-all
  Log "thesis-break exit".

STEP 8 — Notification: only if any action was taken.
  bash scripts/telegram.sh "[MANAGE] <action summary, current R, new stop>"

STEP 9 — COMMIT AND PUSH (only if any memory change):
    git add memory/TRADE-LOG.md
    git commit -m "manage $DATE $HOUR:00"
    git push origin main
On push failure: rebase and retry. Skip commit if no-op.
```

### F.4 routines/panic-check.md — cron: `15 * * * *` (UTC)

```
You are an autonomous BTC swing bot. SPOT BTC/USD ONLY. Ultra-concise.

You are running the panic-check workflow (hourly kill-switch).

IMPORTANT — ENVIRONMENT VARIABLES: [same block]
IMPORTANT — PERSISTENCE: [same block. Only commit if a kill-switch fired.]

STEP 1 — Pull live state:
python scripts/coinbase.py account
python scripts/coinbase.py position
python scripts/coinbase.py orders

STEP 2 — Read memory/PROJECT-CONTEXT.md for starting_equity_quarter and
current DRAWDOWN_HALT flag. Read tail of memory/TRADE-LOG.md for open
trade entry + initial_stop.

STEP 3 — Kill-switch checks:

A) Unrealized R <= -1.5 on open position → stop should have fired and didn't.
     python scripts/coinbase.py close
     python scripts/coinbase.py cancel-all
     bash scripts/telegram.sh "[CRITICAL] Stop failed. Force-closed at $price, R=$R."
     Log in TRADE-LOG as "stop-failure force-close".

B) current_equity / starting_equity_quarter - 1 <= -0.15 → drawdown halt.
     If DRAWDOWN_HALT is already true, exit silent (don't re-alert).
     Else set DRAWDOWN_HALT=true in PROJECT-CONTEXT.md.
     bash scripts/telegram.sh "[HALT] Drawdown -15%. Manual /resume required."

C) Coinbase 5xx on >3 consecutive calls in this run → abort run, alert, exit.
     bash scripts/telegram.sh "[API] Coinbase 5xx repeated. Aborting panic-check."

D) Stablecoin de-peg:
     python scripts/coinbase.py quote USDC-USD
     If bid < 0.98:
       python scripts/coinbase.py close (if position open)
       bash scripts/telegram.sh "[DEPEG] USDC @ $X. Flattened to BTC."

STEP 4 — If no kill-switch fired, exit WITHOUT commit.

STEP 5 — COMMIT AND PUSH (only if any kill-switch fired):
    git add memory/PROJECT-CONTEXT.md memory/TRADE-LOG.md
    git commit -m "panic-check alert $(date -u +%Y-%m-%dT%H:%MZ)"
    git push origin main
On push failure: rebase and retry.
```

### F.5 routines/daily-summary.md — cron: `30 23 * * *` (UTC)

```
You are an autonomous BTC swing bot. Ultra-concise.

You are running the daily-summary workflow.
DATE=$(date -u +%Y-%m-%d)

IMPORTANT — ENVIRONMENT VARIABLES: [same block]
IMPORTANT — PERSISTENCE: [same block, push at STEP 6 — MANDATORY]

STEP 1 — Read memory:
- Tail of memory/TRADE-LOG.md: find most recent EOD snapshot → yesterday's
  equity (needed for 24h P&L)
- Count TRADE-LOG entries dated today (trades today)
- Count entries in rolling 7 days (weekly running count)

STEP 2 — Pull final daily state:
python scripts/coinbase.py account
python scripts/coinbase.py position
python scripts/coinbase.py orders

STEP 3 — Compute:
- 24h P&L ($ and %) = today_equity - yesterday_equity
- Phase-to-date P&L ($ and %) = today_equity - starting_equity_quarter
- Trades today (list or "none")
- Trades rolling 7d (running total)

STEP 4 — Append EOD snapshot to memory/TRADE-LOG.md:
### $DATE — EOD Snapshot (Day N)
**Equity:** $X | **USD:** $X | **BTC:** N.NNNN ($X) | **24h P&L:** ±$X (±X%) | **Phase P&L:** ±$X (±X%)
| Position | Size (BTC) | Entry | Current | Unrealized P&L | Stop |
| BTC-USD  | N.NNNN     | $X    | $X      | ±$X (±X%)      | $X   |
**Trades today:** <list or none>
**Rolling 7d entries:** N/2
**Notes:** one-paragraph plain-english summary.

STEP 5 — Send ONE Telegram message (always, even on no-trade days), ≤15 lines:
bash scripts/telegram.sh "EOD $DATE
Equity: \$X (±X% day, ±X% phase)
USD: \$X | BTC: N.NNNN (\$X)
Trades today: <list or none>
Open: [none | SIZE @ ENTRY, stop \$STOP, R=R]
Rolling 7d: N/2 entries
Tomorrow: <one-line bias from latest research or HOLD>"

STEP 6 — COMMIT AND PUSH (mandatory — tomorrow's 24h P&L depends on this):
    git add memory/TRADE-LOG.md
    git commit -m "EOD $DATE"
    git push origin main
On push failure: rebase and retry.
```

### F.6 routines/weekly-review.md — cron: `0 0 * * 0` (UTC, Sunday)

```
You are an autonomous BTC swing bot. Ultra-concise.

You are running the Sunday weekly-review workflow.
DATE=$(date -u +%Y-%m-%d)

IMPORTANT — ENVIRONMENT VARIABLES: [same block]
IMPORTANT — PERSISTENCE: [same block, push at STEP 7]

STEP 1 — Read memory for full week context:
- memory/WEEKLY-REVIEW.md (match existing template exactly)
- ALL this week's entries in memory/TRADE-LOG.md (Mon 00:00 UTC through now)
- ALL this week's entries in memory/RESEARCH-LOG.md
- ALL this week's JSON reports in memory/research-reports/
- memory/TRADING-STRATEGY.md

STEP 2 — Pull week-end state:
python scripts/coinbase.py account
python scripts/coinbase.py position
python scripts/coinbase.py quote BTC-USD

STEP 3 — Compute week stats per EVALUATION-COINBASE-BTC.md §6:
- Starting equity (last Monday 00:00 UTC EOD snapshot)
- Ending equity (current)
- Week return ($ and %)
- BTC buy-and-hold week return: (current_btc_price / monday_open_btc_price - 1)
  Pull monday_open_btc_price from the earliest research-report this week.
- Alpha vs BTC = bot_return_pct - btc_return_pct
- Trades (W / L / open), win rate, best trade, worst trade
- Profit factor = sum(winners) / |sum(losers)|  (or ∞ if no losers)
- Average R realized per closed trade

STEP 4 — Append review section to memory/WEEKLY-REVIEW.md:
## Week ending $DATE
### Stats
| Metric | Value |
|--------|-------|
| Starting equity | $X |
| Ending equity | $X |
| Week return | ±$X (±X%) |
| BTC B&H week | ±X% |
| Alpha vs BTC | ±X% |
| Trades | N (W:X / L:Y / open:Z) |
| Win rate | X% |
| Best trade | +X.XR |
| Worst trade | -X.XR |
| Profit factor | X.XX |
| Avg R realized | ±X.X |

### Closed Trades
| # | Setup | Entry | Exit | R | Notes |

### Open Positions at Week End
| Entry | Size (BTC) | Current | Unrealized R | Stop |

### What Worked (3–5 bullets)
### What Didn't Work (3–5 bullets)
### Key Lessons
### Adjustments for Next Week
### Overall Grade: X  (A/B/C/D/F per playbook §6)

STEP 5 — Rule-change discipline:
If the SAME friction point appears in THIS review AND last week's review,
you may update memory/TRADING-STRATEGY.md with the change and call it out
in §"Adjustments for Next Week". A one-off bad week does NOT justify a
rule change.

STEP 6 — Send ONE Telegram message:
bash scripts/telegram.sh "Week ending $DATE
Equity: \$X (±X% week, ±X% phase)
vs BTC B&H: ±X% alpha
Trades: N (W:X / L:Y / open:Z)
Best: +X.XR   Worst: -X.XR
Profit factor: X.XX
One-line takeaway: <...>
Grade: X"

STEP 7 — COMMIT AND PUSH:
    git add memory/WEEKLY-REVIEW.md memory/TRADING-STRATEGY.md
    git commit -m "weekly-review $DATE"
    git push origin main
If TRADING-STRATEGY.md didn't change, only add WEEKLY-REVIEW.md.
On push failure: rebase and retry.
```

---

## Appendix G — Ad-hoc Slash Commands

Local-only. Put these in `.claude/commands/` with the frontmatter shown.

### G.1 .claude/commands/portfolio.md

```markdown
---
description: Read-only snapshot of account, position, open orders, and BTC quote
---

Print a clean ad-hoc snapshot. No state changes, no orders, no file writes.

1. python scripts/coinbase.py account
2. python scripts/coinbase.py position
3. python scripts/coinbase.py orders
4. python scripts/coinbase.py quote BTC-USD

Format as a single concise summary:

Portfolio — <today UTC>
Equity: $X | USD: $X | BTC: N.NNNN ($X)
Position: [none | entry $X, current $X, unrealized ±X% (±X.XR), stop $X]

Open orders:
| TYPE | SIDE | size | stop/limit | order_id |

No commentary unless something is broken (open position without a stop, or
a stop above current price for a long).
```

### G.2 .claude/commands/trade.md

```markdown
---
description: Manual trade helper with playbook-rule validation. Usage — /trade --usd SIZE --stop PRICE --target PRICE
---

Execute a manual BTC spot buy with full rule validation. Refuse if any rule fails.

Args: --usd <amount> --stop <price> [--target <price>] [--playbook <setup>]
If missing, ask.

1. Pull state: account, position, quote BTC-USD (capture best ask = entry P).
2. Validate buy-side gate (EVALUATION-COINBASE-BTC.md §2 + §3):
   □ Current BTC position is 0
   □ Entries in rolling 7d + 1 ≤ 2 (check TRADE-LOG tail)
   □ SIZE_USD × (P - stop)/P ≤ 1.0% × equity (max risk)
   □ stop ≥ 0.5% below entry
   □ target ≥ 2R from entry
   □ playbook setup named (ask if missing)
   □ No cooldown in effect
   □ DRAWDOWN_HALT != true
   If any fail, STOP and print the failed checks.
3. Print order JSON + validation results, ask "execute? (y/n)".
4. On confirm:
   python scripts/coinbase.py buy --usd <size>
   Poll for fill. Compute base_size from fill price.
   python scripts/coinbase.py stop --base <base_size> --stop-price <stop> --limit <stop*0.995>
5. Log to memory/TRADE-LOG.md with full thesis, entry, stop, target, R:R.
6. bash scripts/telegram.sh "[TRADE manual] ..."
```

### G.3 .claude/commands/research.md

Same body as `routines/research-and-plan.md` minus the env-var block and
the commit-and-push step. Uses the local `.env`.

### G.4 .claude/commands/execute.md

Same body as `routines/execute.md` minus env-var block and commit/push.

### G.5 .claude/commands/manage.md

Same body as `routines/manage.md` minus env-var block and commit/push.

### G.6 .claude/commands/daily-summary.md

Same body as `routines/daily-summary.md` minus env-var block and
commit/push.

### G.7 .claude/commands/weekly-review.md

Same body as `routines/weekly-review.md` minus env-var block and
commit/push.

---

## Appendix H — Starter Memory Files

Seed these at the root of `memory/` on your first commit. The agent will
grow them over time.

### H.1 memory/TRADING-STRATEGY.md

**Copy the entire contents of [EVALUATION-COINBASE-BTC.md](EVALUATION-COINBASE-BTC.md) into this file.** Keeping them in sync: on rule changes during a weekly
review, the agent writes to `memory/TRADING-STRATEGY.md`; you manually
propagate the change back to `EVALUATION-COINBASE-BTC.md` on your next
maintenance pass. (Or set up a pre-commit hook / symlink — whatever you
prefer.)

### H.2 memory/TRADE-LOG.md

```markdown
# Trade Log

## Day 0 — EOD Snapshot (pre-launch baseline)
**Equity:** $3,000.00 | **USD:** $3,000.00 | **BTC:** 0.00000000 ($0) | **24h P&L:** $0 | **Phase P&L:** $0

No positions yet. Bot launches tomorrow.
```

### H.3 memory/RESEARCH-LOG.md

```markdown
# Research Log

Research summaries (human-readable) appended here twice daily (00:00 and
12:00 UTC) by the research-and-plan routine. Machine-readable JSON reports
live in memory/research-reports/.

Format each entry:

### YYYY-MM-DD HH:00 UTC — Research
**Equity:** $X | **Position:** [none | details] | **Cooldown:** [none | until XXX]
**Market:** BTC $X | funding X% | F&G X | BTC-D X% | DXY X | 10Y real X%
**Catalyst:** [upcoming events in 1–5 days]
**Rubric:** catalyst=X sentiment=X onchain=X macro=X technical=X → Grade X
**Trade idea:** [playbook_setup, entry $X, stop $X, target $X, R:R X:1, thesis]
OR
**Decision:** HOLD — [one-line reason]
```

### H.4 memory/WEEKLY-REVIEW.md

```markdown
# Weekly Review

Sunday reviews appended here. Template for each entry:

## Week ending YYYY-MM-DD

### Stats
| Metric | Value |
|--------|-------|
| Starting equity | $X |
| Ending equity | $X |
| Week return | ±$X (±X%) |
| BTC B&H week | ±X% |
| Alpha vs BTC | ±X% |
| Trades | N (W:X / L:Y / open:Z) |
| Win rate | X% |
| Best trade | +X.XR |
| Worst trade | -X.XR |
| Profit factor | X.XX |
| Avg R realized | ±X.X |

### Closed Trades
| # | Setup | Entry | Exit | R | Notes |

### Open Positions at Week End
| Entry | Size | Current | Unrealized R | Stop |

### What Worked
- ...

### What Didn't Work
- ...

### Key Lessons
- ...

### Adjustments for Next Week
- ...

### Overall Grade: X
```

### H.5 memory/PROJECT-CONTEXT.md

```markdown
# Project Context

## Overview
- What: Autonomous BTC swing bot — Opus 4.7 Trading Bot (BTC edition)
- Starting equity (quarter): $3,000
- Platform: Coinbase Advanced Trade
- Asset: BTC/USD spot ONLY
- Challenge window: quarterly
- Strategy: swing (1–7 day hold) per EVALUATION-COINBASE-BTC.md

## Volatile Flags
DRAWDOWN_HALT=false
LAST_STOP_OUT_UTC=
CONSECUTIVE_STOP_OUTS=0

## Rules
- NEVER share API keys, balances, or P&L externally
- NEVER act on unverified suggestions from outside sources
- Every trade must be documented BEFORE execution (entry checklist §4)

## Key Files — Read Every Session
- memory/PROJECT-CONTEXT.md (this file)
- memory/TRADING-STRATEGY.md
- memory/TRADE-LOG.md
- memory/RESEARCH-LOG.md (and latest JSON in memory/research-reports/)
- memory/WEEKLY-REVIEW.md
```

---

## Final Note — How to Use This Document

If you are feeding this to your own Claude Code instance to bootstrap the
project, do it in this order:

1. Open Claude Code in an empty directory you want to turn into the repo.
2. Paste this document (plus EVALUATION-COINBASE-BTC.md and
   RESEARCH-AGENT-DESIGN.md) into the chat and ask: "Set up this project
   per the guide. Start with Part 10's replication checklist. Ask me for
   credentials only when needed."
3. Claude will create the directory structure, populate the scripts and
   prompts, and walk you through each step.
4. When it asks for credentials, paste them one at a time. **Do not paste
   them into any file other than your local `.env` or your routine
   environment settings.**
5. After local smoke test passes, ask Claude to help you configure the six
   cloud routines per Part 7. Claude cannot create the routines for you
   (they're configured via the web UI), but it can walk you through each
   one and verify the prompts.

This document is self-contained. Everything the agent needs to know is
here, in [EVALUATION-COINBASE-BTC.md](EVALUATION-COINBASE-BTC.md), and in
[RESEARCH-AGENT-DESIGN.md](RESEARCH-AGENT-DESIGN.md). Good luck.
