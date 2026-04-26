# Two-Week Paper Trading Test

This project now has a paper-only validation lane for the BTC accumulation
strategy. The campaign lasts exactly 14 days from initialization and must pass
before automated live cycle opening is enabled.

If started on 2026-04-25, the planned end is 2026-05-09.

## Purpose

- Exercise the v2 sell-trigger plus paired re-entry lifecycle without placing
  live Coinbase orders.
- Catch state drift, bad cycle gates, stale research handling, and rollback
  assumptions before live automation.
- Produce a simple BTC-denominated record of paper cycles and blocked ideas.

## Hard Boundaries

- Do not call live order-producing Coinbase commands for this test:
  `buy`, `sell`, `stop`, `limit-buy`, `cancel`, `cancel-all`, or `close`.
- Read-only Coinbase calls are allowed for prices and balances:
  `quote`, `account`, `position`, `orders`, `order`, and `fills`.
- Paper state lives at `memory/paper-trading/state.json`.
- The paper harness is `python scripts/paper_trade.py`.
- The live bot state at `memory/state.json` must not be modified by paper
  cycles.
- Paper trading is downstream of AI research. It may advance lifecycle from a
  quote, but it must not open a new paper cycle without a fresh
  `memory/research-reports/*.json` produced by `research-and-plan`.

## Agent-First Sequence

The paper campaign validates the full workflow, not just the simulator:

```text
research-and-plan agent -> research report -> paper-trading routine -> paper state
```

The agent owns market interpretation: catalysts, sentiment, macro, structure,
technical levels, and thesis. The code owns safety gates and paper fill
mechanics.

## Start The Campaign

Use the current stack and BTC spot price from read-only calls:

```bash
python scripts/coinbase.py account
python scripts/coinbase.py quote BTC-USD
python scripts/paper_trade.py init \
  --starting-btc <btc_balance> \
  --starting-usd <usd_balance> \
  --btc-price <spot_price>
```

The command writes:

- `status=active`
- `started_at_utc=<now>`
- `ends_at_utc=<now + 14 days>`
- starting BTC-equivalent benchmark

Validate at any time:

```bash
python scripts/paper_trade.py validate
python scripts/paper_trade.py summary
```

## Twice-Daily Paper Execute

Run this at the same cadence as the live execute window, after the
research-and-plan agent produces or refreshes a v2 report.

For local automation, prefer the single auditable runner:

```bash
python scripts/paper_shadow.py \
  --research-report memory/research-reports/YYYY-MM-DD-HH.json
```

If opening a paper cycle is justified by the agent report, pass the same
cycle arguments shown below to `paper_shadow.py`. It will tick from the quote,
validate the research report, and open only if the report gate passes.

1. Validate state:

```bash
python scripts/paper_trade.py validate
```

2. Validate the latest research artifact:

```bash
python scripts/research_gate.py latest --max-age-minutes 45
```

If this fails, still tick the paper lifecycle from price, but do not open a
new paper cycle.

3. Pull read-only quote:

```bash
python scripts/coinbase.py quote BTC-USD
```

4. Advance the paper broker with current bid/ask:

```bash
python scripts/paper_trade.py tick --bid <bid> --ask <ask>
```

5. If the latest v2 research report has an A/B cycle idea that passes the
   checklist, first confirm it is actionable:

```bash
python scripts/research_gate.py latest --max-age-minutes 45 --require-trade-idea
```

Then open the cycle in paper:

```bash
python scripts/paper_trade.py open-cycle \
  --research-report memory/research-reports/YYYY-MM-DD-HH.json \
  --cycle-id paper-YYYYMMDD-HHMM \
  --playbook-setup <setup> \
  --grade <A|B> \
  --btc-to-sell <btc> \
  --sell-trigger-price <trigger> \
  --rebuy-limit-price <rebuy> \
  --worst-case-rebuy-price <worst_case> \
  --current-price <spot>
```

The harness enforces:

- one active paper cycle
- max 30 percent BTC stack sold per cycle
- max two paper cycles per rolling seven days
- `rebuy_limit_price < sell_trigger_price < current_price`
- `worst_case_rebuy_price > sell_trigger_price`
- v2 setup enum and A/B grade only
- the 72h paper time-cap window fits inside the 14-day campaign

## Paper Lifecycle

- Phase A: sell-trigger and re-entry are staged on paper.
- If `bid <= sell_trigger_price`, the paper sell fills at the trigger price
  and the cycle enters Phase B.
- In Phase B, if `bid <= rebuy_limit_price`, the paper re-entry fills at the
  limit price and the cycle closes.
- If 72 hours pass after the paper sell fill while Phase B is still open, the
  harness market-buys on paper at the supplied ask price and closes the cycle
  as a time-cap close.
- At `ends_at_utc`, an untriggered Phase A paper cycle is cancelled with zero
  BTC delta. A Phase B cycle is market-bought on paper at the supplied ask.
- Once no active paper cycle exists and a tick occurs at or after `ends_at_utc`,
  the campaign marks itself complete.

## Daily Review

Each daily summary should include:

- paper campaign day number out of 14
- active paper cycle phase, if any
- paper BTC-equivalent delta versus start
- cycles opened and closed
- blocked ideas and why they failed the paper gate

Use:

```bash
python scripts/paper_trade.py summary
```

## Completion Criteria

The paper test is complete only when all are true:

- `memory/paper-trading/state.json` has `status=complete`.
- At least 14 calendar days elapsed from `started_at_utc`.
- Every paper cycle has an auditable event trail in `events`.
- No live order-producing Coinbase command was used for cycle execution.
- There are no unexplained state mismatches or active-cycle anomalies.
- A final weekly review records paper BTC delta, win/loss/flat count, blocked
  executions, and recommended policy changes before live automation.

Passing this test does not by itself authorize live trading. The remaining
held-balance/product metadata handling, CI gates, and final live-readiness
review in `REMAINING-WORK.md` still need to be complete.
