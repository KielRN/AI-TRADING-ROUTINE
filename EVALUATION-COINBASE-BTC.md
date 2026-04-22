# BTC/USD Swing Playbook — Coinbase Advanced Trade

**Prepared:** 2026-04-22 (v1)
**Status:** Strategy playbook. This is the rulebook the bot reads every session.
**Companion docs:**
- [Opus 4.7 Trading Bot — Setup Guide.md](Opus%204.7%20Trading%20Bot%20—%20Setup%20Guide.md) — how the bot is built and deployed
- [RESEARCH-AGENT-DESIGN.md](RESEARCH-AGENT-DESIGN.md) — the 5-point rubric that grades each setup

This document defines the trading rules for a swing BTC/USD bot running on
Coinbase Advanced Trade. The rules are non-negotiable. Every workflow in the
setup guide reads this file first and must validate against it before placing
an order.

---

## 1. Mission

Grow a **$3,000** BTC spot account on Coinbase Advanced Trade over a rolling
quarterly challenge window by trading a disciplined swing strategy (holding
period 1–7 days). Beat spot-BTC buy-and-hold on a risk-adjusted basis
(Sharpe > BTC's Sharpe over the same window), not just on raw return.

**What this bot is:** a swing trader of BTC/USD spot.
**What this bot is not:** a day trader, a high-frequency strategy, a leveraged
strategy, a multi-asset strategy, or a narrative-chaser.

---

## 2. Hard rules (non-negotiable)

These are the rules. They were chosen deliberately for a 24/7 market with
real weekend-gap risk, higher volatility than equities, and no PDT-equivalent
constraint. They replace the stock-swing rules in Nate Herk's original
Alpaca setup.

### Instrument & leverage
1. **Spot BTC/USD only.** No futures, no perpetuals, no leverage, no margin,
   no options, no altcoins, no staking. Ever.
2. **Coinbase Advanced Trade** is the only venue. No cross-venue arbitrage,
   no moving capital off-exchange mid-trade.

### Position structure
3. **One open BTC position at a time.** A single-asset strategy does not need
   position-count caps — it needs a "max one" rule to prevent the bot from
   averaging down or doubling up on the same thesis.
4. **70–90% of capital deployed when in a position.** The remaining 10–30% is
   a liquidity buffer for fees, slippage, and the next entry. When flat, all
   cash is idle — no "earn" products, no auto-staking.
5. **Max 2 new entries per 7-day rolling window.** Crypto chops — forcing a
   third entry in a week has historically been the single biggest source of
   realized losses across similar strategies.

### Risk per trade
6. **Risk is a function of rubric grade**, set by the research agent
   ([RESEARCH-AGENT-DESIGN.md §5](RESEARCH-AGENT-DESIGN.md#5-the-swing-rubric-replaces-the-fx-rubric-in-decidepy)):
   - **A-grade (5/5):** 1.0% of account equity at risk
   - **B-grade (3–4/5):** 0.5% of account equity at risk
   - **< 3/5:** skip. No trade.
7. At $3,000 starting equity this means **$30 at risk on an A-grade setup,
   $15 at risk on a B-grade setup.** Position size is derived from risk, not
   fixed at a dollar amount.
8. **Position size formula:**
   `size_usd = (equity × risk_pct) / ((entry - stop) / entry)`
   Round *down* to the nearest $10 USD to stay under the risk ceiling.

### Stops
9. **Every entry has a hard stop placed as a real `STOP_LIMIT` sell order on
   Coinbase, GTC.** Never a mental stop. Never a market-if-touched. The stop
   goes in the same run as the buy — if the stop order fails to place, the
   buy is reversed within the same workflow.
10. **Initial stop is 1R below entry,** where 1R is sized so the whole trade
    risks the §6 dollar amount. The stop is placed at a *technical* level
    (weekly swing low, prior consolidation floor, HTF S/R) — not a round
    percentage. If no technical stop is within the risk budget, the trade is
    skipped.
11. **Stops never move down.** A stop only moves toward or past breakeven.
    Never widen a stop mid-trade.
12. **Weekend gap defense:** before 00:00 UTC Saturday, if the position is
    within 1.5R of the stop and the next research window shows a deteriorating
    setup, the bot closes at market. Weekends are a risk multiplier — don't
    hold a losing trade over one.

### Targets & management
13. **Minimum 2:1 reward-to-risk** required for every entry. A 1R stop demands
    a 2R target documented before the buy.
14. **Management ladder** (run every 4h by the `manage` routine):
    - At **+1R unrealized:** cancel the initial stop, place a new stop at
      breakeven + fees buffer (~0.2% above entry for a long). Trade is now
      risk-free.
    - At **+1.5R unrealized:** sell 30% of the position at market ("partial
      take-profit"), keep the remainder with stop at breakeven.
    - At **+2R unrealized (the documented target):** sell another 30% at
      market. Move stop to +1R below current price. The last 40% is the
      "runner" — let it trail.
    - **Runner trail:** 3-ATR (1-day ATR) or the most recent 4h swing low,
      whichever is higher. Never within 3% of current price.
15. **Thesis-break exit:** if the catalyst that justified rubric #1 is
    invalidated intraday (Fed speaker walks back a decision, ETF flows flip,
    on-chain flows reverse hard), close the whole position at market
    regardless of P&L state. Document the break in the trade log.

### Cooldown
16. **After a full-stop loss (stopped out at initial 1R stop):** no new
    entries for **48 hours.** The research rubric has to re-score a fresh
    setup in a new window. This is the discipline equivalent of "sector
    cooldown" in the stock playbook — except crypto has no sectors, so the
    cooldown applies to the whole asset.
17. **After two consecutive stop-outs:** no new entries for **7 days.** The
    weekly-review routine triggers a strategy post-mortem. If the rubric is
    producing A-grades that lose, the rubric is the problem, not the rules.

---

## 3. Setup types (the swing playbook)

Every rubric A- or B-grade trade must match one of these four documented
setups. The research agent tags each trade idea with a `playbook_setup` field
(see [RESEARCH-AGENT-DESIGN.md §8.1](RESEARCH-AGENT-DESIGN.md#81-machine-readable-memoryresearch-reportsyyyy-mm-dd-hhjson)).
If a trade idea doesn't match one of these, it's skipped regardless of grade.

### 3.1 `catalyst_driven_breakout`
**When:** scheduled macro catalyst in the next 1–3 days (FOMC, CPI, NFP, major
ETF decision), price is consolidating at or below a weekly resistance level,
funding rate neutral-to-negative (crowd is short or unconvinced), BTC
dominance stable or rising.

**Entry:** buy stop above the consolidation high, or market buy on a confirmed
breakout with volume.

**Stop:** below the consolidation floor (not a round %).
**Target:** next weekly resistance or 2R, whichever is further.

### 3.2 `sentiment_extreme_reversion`
**When:** F&G ≤ 20 (extreme fear) or ≥ 80 (extreme greed), price at a weekly
S/R level, funding aligned with the contrarian direction (funding deeply
negative when F&G is extreme-fear → short squeeze setup; funding deeply
positive when F&G is extreme-greed → long squeeze setup).

**Entry:** market buy (for extreme-fear reversal) or skip if long-only is
wrong-sided.
**Stop:** below the most recent weekly swing low.
**Target:** mean of the 30-day price range, or 2R minimum.

**Note:** this playbook is long-only. Extreme-greed setups surface as "no
trade, wait for reversion, consider a hedged entry later" — the bot does
not short.

### 3.3 `funding_flip_divergence`
**When:** price is making a new local high but funding rates flip from
positive to negative across 2+ exchanges (Binance, OKX per CoinGlass), or
vice versa at a local low. Open interest expanding in the opposite direction
of price.

This is the "smart money is leaning against the crowd" setup.

**Entry:** market buy when price pulls back to the level where the divergence
started.
**Stop:** 1R below the pullback low, at a technical level.
**Target:** retest of the recent high + 2R minimum.

### 3.4 `onchain_accumulation_base`
**When:** exchange net outflow > $100M over 7 days (accumulation), stablecoin
supply rising (dry powder), price in a sideways base at a monthly S/R level,
no adverse macro catalyst in the next 72 hours.

**Entry:** market buy at the base's midpoint or a pullback to its floor.
**Stop:** below the base (not the daily low; the multi-week structure).
**Target:** prior range high or 2R, whichever is further.

This is the slowest setup — holding can be the full 7 days. Discipline: don't
exit early because of chop. The thesis is multi-day accumulation, and the
stop does the risk work.

---

## 4. Entry checklist (agent documents all of these before placing)

Every entry requires the agent to fill this in and append to
`memory/TRADE-LOG.md` **before** the buy order fires. No documentation, no trade.

```
Date (UTC):
Playbook setup: [catalyst_driven_breakout | sentiment_extreme_reversion
                 | funding_flip_divergence | onchain_accumulation_base]
Rubric grade: [A | B]
Rubric scores: catalyst=X sentiment=X onchain=X macro=X technical=X
Specific catalyst / thesis: (one paragraph)
Entry price:
Stop price: (must be at a documented technical level)
Target price: (must be ≥ 2R)
Risk per trade ($): (must match §6)
Position size (USD):
Position size (BTC):
Risk/reward ratio:
Weekly trade count (including this one):  /2
```

---

## 5. Exit rules (beyond the management ladder)

### Normal exits
- Stop hit → trade is done. Log realized P&L.
- Target hit (2R) → partial + runner per §2 rule 14.
- Runner trail hit → trade is done.

### Discretionary / thesis-break exits
- **Catalyst invalidated:** close at market, log "thesis broken".
- **Major regulatory shock / exchange failure:** close at market, flatten,
  wait for the next research window before re-engaging.
- **Weekly-review grades the setup D or F retroactively:** close any still-open
  position from that trade on Monday's first research window.

### Forced exits
- **Weekend gap defense:** §2 rule 12.
- **Panic-check breach:** the hourly `panic-check` routine closes the position
  if unrealized P&L ≤ -1.5R (i.e., the stop failed or was skipped; halt and
  investigate before the next entry).

---

## 6. Weekly grading (Friday / end-of-week review)

Every Sunday 00:00 UTC the `weekly-review` routine grades the week.

### Stats computed
- Starting equity (Monday 00:00 UTC), ending equity (Sunday 00:00 UTC)
- Week return ($ and %)
- BTC buy-and-hold return (Sunday 00:00 UTC / Monday 00:00 UTC −1)
- Alpha vs BTC (bot % − BTC %)
- Closed trades: W / L / open counts
- Win rate on closed trades
- Best trade, worst trade
- Profit factor: sum(winners) / |sum(losers)|
- Average R realized per trade (closed)

### Letter grade
- **A:** alpha > +2% for the week, profit factor > 1.5, no rule violations
- **B:** alpha > 0, no rule violations
- **C:** alpha in (-2%, 0], no rule violations
- **D:** any rule violation, or alpha ≤ -2%
- **F:** stop-loss failure, cooldown violation, leverage/altcoin/option attempted, or two+ rule violations

### Rule-change discipline
- A rule change requires two consecutive weekly reviews where the same
  specific friction point is documented. One-off bad weeks don't justify
  rule changes — that's exactly how discipline erodes.
- Rule changes are committed to `memory/TRADING-STRATEGY.md` (this playbook)
  in the same commit as the weekly review, with a diff the human can review.

---

## 7. Integration with the research agent

The research agent ([RESEARCH-AGENT-DESIGN.md](RESEARCH-AGENT-DESIGN.md))
writes two artifacts twice a day: a JSON report and a journal entry. The
execute workflow consumes the JSON:

```
rubric.grade  →  §2 rule 6 (sizing)
rubric.catalyst  →  §3 playbook match (catalyst_driven_breakout requires true)
trade_ideas[0].playbook_setup  →  §3 (must be one of the four types)
trade_ideas[0].entry/stop/target  →  §4 (feeds the entry checklist)
```

**Order of authority on conflict:** this playbook > research agent output.
If the research agent outputs an A-grade long with a stop that violates §2
rule 9–10 (e.g., stop is a percentage not a technical level, or stop moves
down), the bot skips and logs the conflict for the weekly review.

---

## 8. Panic conditions & kill switch

The `panic-check` routine (hourly) enforces these.

1. **Unrealized P&L ≤ -1.5R on the open position:** close at market. The
   initial stop should have fired; if it didn't, the stop order failed.
   Investigate before any new entry.
2. **Account equity drawdown ≥ 15% from the quarterly starting equity:** halt
   all new entries. The bot sends a Telegram alert and waits for a manual
   `/resume` command before any further trades.
3. **Coinbase Advanced Trade returns 5xx on >3 consecutive calls across a
   routine run:** halt that run, send an alert, exit. The next scheduled run
   will retry from a fresh state.
4. **Stablecoin de-peg event (USDC ≤ $0.98 or USDT ≤ $0.97):** close any
   position, flatten to BTC-in-wallet (not USD), send an alert. Do not
   re-engage until USDC/USDT re-peg.

---

## 9. Defaults — locked in v1

These are the parameter choices for v1. Re-evaluate only at a weekly review.

| Parameter | v1 value | Re-evaluation trigger |
|---|---|---|
| Starting capital | $3,000 | Quarterly challenge reset |
| Risk per trade | 0.5% B / 1.0% A | 4+ weeks of stable performance → consider 0.75% B / 1.5% A |
| Max open positions | 1 | Never — strategy is single-asset |
| Max new entries / week | 2 | 4+ weeks at < 2 trades/week average → consider raising to 3 |
| Deployed capital | 70–90% when in a trade | Fixed |
| Initial stop | 1R at a technical level | Fixed |
| Target | ≥ 2R | Fixed |
| Management ladder | BE at +1R, partial at +1.5R, partial at +2R, runner | Fixed |
| Cooldown after 1 stop-out | 48 hours | Fixed |
| Cooldown after 2 stop-outs | 7 days + post-mortem | Fixed |
| Drawdown kill switch | 15% from quarterly start | Fixed |
| Asset | BTC/USD spot | Stage-2 eval: BTC + ETH (not before v2) |
| Leverage | None | Never |

---

## 10. Open decisions (revisit after 4 weeks live)

- [ ] Does the 2-entries-per-week cap leave too much cash idle in trending
      quarters? If weekly review consistently shows "high-grade setups skipped
      due to cap," raise to 3.
- [ ] Does the 48h post-stop cooldown cost more than it saves? Measure: sum
      of "missed A-grade setups during cooldown" vs "bot sanity preserved."
- [ ] Should partials fire at +1.5R or +2R? Currently both fire. If runner
      P&L consistently underperforms full-position exit, collapse the ladder.
- [ ] Weekend gap defense (§2 rule 12) — is it actually firing helpfully, or
      is it just cutting winners? Tag each invocation in the trade log.
- [ ] Stablecoin de-peg defense (§8 rule 4) — BTC-in-wallet is safer than
      USD-in-Coinbase during a de-peg, but is Coinbase custody itself a
      worry? At $3K, probably no. Reconsider at $30K+.

---

## 11. Why this playbook

Every rule here has a specific reason. If you want to change one, match it
against the reason first.

| Rule | Why |
|---|---|
| Spot-only, no leverage | 100% of leveraged crypto bot "blowup" stories trace to a single bad leveraged trade. Spot drawdowns are recoverable; liquidation isn't. |
| One position at a time | Eliminates correlation confusion — every open trade is the same asset, so "multiple positions" is actually "one bigger position," which the risk math doesn't capture. |
| Max 2 entries / 7d | Overtrading is the #1 P&L killer in swing strategies. Crypto chop makes this worse, not better. |
| Risk by grade, not fixed | Makes the rubric load-bearing. A stronger signal earns more size; a weaker signal earns less. |
| Hard stop as GTC order | Mental stops don't work when the market is 24/7 and the bot sleeps between routine runs. |
| Stop at technical level | A 7% stop is arbitrary; a stop below the last weekly swing low has a reason. Reasons survive; arbitrary numbers get front-run. |
| Stops never move down | Moving a stop down is "hoping," which is not a strategy. |
| Weekend gap defense | The 4.7 doc's parent bot traded stocks; weekends were free. For BTC, Saturday is the expensive day. |
| 2:1 R:R minimum | With a 50% win rate, 2:1 is profitable. Below that, you're paying fees to break even. |
| Management ladder | Full position to 2R leaves money on the table in strong moves and blows it up in fakeouts. The ladder banks some, runs some. |
| Cooldown after stop-out | Revenge trading is the #2 P&L killer after overtrading. The cooldown is automated so it doesn't require discipline — the bot just can't trade. |
| Drawdown kill switch | If the strategy is broken, you want the bot to stop before it drains the whole account. 15% is 4–5 max-risk losses in a row — past that, something's wrong at the strategy level, not the trade level. |

---

## 12. Cross-reference

- **How trades are executed:** [Opus 4.7 Trading Bot — Setup Guide.md](Opus%204.7%20Trading%20Bot%20—%20Setup%20Guide.md) Part 5 (workflows)
- **How setups are graded:** [RESEARCH-AGENT-DESIGN.md](RESEARCH-AGENT-DESIGN.md) §5 (rubric)
- **Which APIs the bot calls:** [Opus 4.7 Trading Bot — Setup Guide.md](Opus%204.7%20Trading%20Bot%20—%20Setup%20Guide.md) Part 4 (wrapper scripts)
- **Memory files the bot reads:** `memory/TRADING-STRATEGY.md` (this file, canonicalized), `memory/TRADE-LOG.md`, `memory/RESEARCH-LOG.md`, `memory/WEEKLY-REVIEW.md`
