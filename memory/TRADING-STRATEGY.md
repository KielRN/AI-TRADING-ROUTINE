# BTC Accumulation Playbook — Coinbase Advanced Trade

**Prepared:** 2026-04-24 (v2 — accumulation pivot)
**Status:** Strategy playbook. Replaces the USD-swing v1.
**Companion docs:**
- [Opus 4.7 Trading Bot — Setup Guide.md](Opus%204.7%20Trading%20Bot%20—%20Setup%20Guide.md) — how the bot is built and deployed
- [../research/RESEARCH-AGENT-DESIGN-V2.md](../research/RESEARCH-AGENT-DESIGN-V2.md) — the 5-point rubric that grades each step-out setup

This document defines the trading rules for a BTC-accumulation bot running
on Coinbase Advanced Trade. The unit of account is **BTC**, not USD. The
rules are non-negotiable. Every workflow reads this file first and must
validate against it before placing an order.

---

## 1. Mission

Grow a **BTC stack** on Coinbase Advanced Trade over a rolling quarterly
challenge window by swing-trading in and out of USD at documented technical
breakdowns. Success is measured in **BTC count**, not dollars.

**Benchmark:** pure HODL (0% BTC growth per quarter). Any quarter where the
bot ends with *fewer* BTC than it started is a loss, regardless of USD P&L.

**What this bot is:** a BTC accumulator using protective stops to rotate
temporarily to USD during high-conviction downside setups, then buy back
cheaper to add sats.
**What this bot is not:** a HODL-only bot, a USD-denominated swing trader,
a day trader, a leveraged strategy, an altcoin strategy, a narrative-chaser.

---

## 2. Hard rules (non-negotiable)

### Instrument & venue
1. **Spot BTC/USD only.** No futures, perpetuals, leverage, margin, options,
   altcoins, or staking. Ever.
2. **Coinbase Advanced Trade** is the only venue.

### Position structure
3. **Steady state = 80–90% BTC by value, 10–20% USD reserve.** The USD
   reserve is dry powder for the first dip on a step-out cycle; the BTC is
   the core stack. Fully-in-BTC (<10% USD) or fully-in-USD (>20% USD) are
   both out-of-spec states that the bot must rebalance toward steady state
   within the next scheduled window.
4. **One active cycle at a time.** A cycle = a sell-trigger + its paired
   re-entry. No second sell-trigger while the first re-entry is pending.
5. **Max 2 new cycles per rolling 7-day window.** Overtrading erodes the
   stack.
6. **Max 30% of the BTC stack sold on any single cycle.** Never sell the
   whole stack on a setup — a single thesis failure would wipe out months
   of accumulated sats.

### Risk per cycle (BTC-denominated)
7. **Risk is a function of rubric grade** (research agent):
   - **A-grade (5/5):** 1.0% of current BTC stack at risk
   - **B-grade (3–4/5):** 0.5% of current BTC stack at risk
   - **< 3/5:** skip. No trade.
8. **Position sizing formula:**
   ```
   fraction_to_sell = risk_pct / (1 − sell_trigger_price / worst_case_rebuy_price)
   BTC_to_sell       = fraction_to_sell × current_BTC_stack
   ```
   where `worst_case_rebuy_price` is the estimated price at which the 72h
   time-capped market buy (§15) would fire if the re-entry limit never
   fills. Cap `fraction_to_sell` at 0.30 per rule 6. Round down.

### Sell-triggers (the "stops")
9. **Every step-out cycle places TWO orders in the same workflow run:**
   a. Sell-trigger (`STOP_LIMIT` sell, GTC) at the breakdown level
   b. Re-entry limit (`LIMIT` buy, GTC) at the planned buy-back level
   If either order fails to place, the other is cancelled within the same
   workflow — no half-cycles.
10. **Sell-trigger at a technical level**, never a round %. Weekly swing
    low, consolidation floor, HTF S/R breakdown point. Round percentages
    get front-run.
11. **Sell-triggers never move UP.** They can only move lower (further from
    price, narrowing risk) or be cancelled when the cycle closes. Moving a
    trigger up is chasing and locks in a BTC loss beyond the budget.

### Re-entry rules (the accumulation half)
12. **Every sell-trigger pairs with a re-entry plan. The buy-back is not
    optional** — sitting in USD forever is anti-accumulation.
13. **Re-entry limit placed at a documented support level** (next weekly
    S/R below the breakdown, 30-day range mean, prior consolidation top,
    etc.) for the full USD amount from the sell.
14. **Re-entry never moves HIGHER** than its original price. Chasing the
    buy-back up locks in BTC loss beyond the risk budget.
15. **Time cap: 72 hours.** If the re-entry limit doesn't fill within 72h
    of the sell-trigger firing, the bot market-buys with the remaining USD.
    72h is the outer bound of the swing horizon; USD held longer is
    accumulation failure.

### R:R minimum (BTC terms)
16. **Minimum 2:1 BTC R:R required for every cycle.**
    ```
    gain_if_right = (sell_trigger_price / rebuy_limit_price) − 1     # positive
    loss_if_wrong = 1 − (sell_trigger_price / worst_case_rebuy_price) # positive
    ratio = gain_if_right / loss_if_wrong   # must be ≥ 2.0
    ```
    A setup that doesn't clear 2:1 in BTC terms gets a tighter sell-trigger,
    a deeper re-entry, or gets skipped.

### Cooldown
17. **After a losing cycle** (bought back at a higher price than sold →
    net-negative BTC): **48h cooldown** before the next sell-trigger.
18. **After two consecutive losing cycles:** **7-day cooldown** + weekly-
    review post-mortem. If the rubric is producing A-grades that lose
    sats, the rubric is the problem.

### Weekend defense
19. If a cycle is active over a weekend and the re-entry hasn't filled by
    00:00 UTC Saturday AND the next research window shows a deteriorating
    setup, the bot market-buys to close the cycle. USD held through a
    weekend tail-risk event would need a sharper drop than Monday re-open
    to stay accumulation-positive — not worth the gap risk.

---

## 3. Step-out setup types

Every cycle must match one of these four documented step-out setups. The
research agent tags each trade idea with a `playbook_setup` field. If a
trade idea doesn't match one of these, it's skipped regardless of grade.

### 3.1 `catalyst_driven_breakdown`
**When:** scheduled macro catalyst in the next 1–3 days (FOMC, CPI, NFP, major
ETF decision) is likely to resolve against current positioning (e.g.,
market priced dovish into a hawkish-expected Fed), price consolidating at
or below a weekly resistance level, funding positive (crowd leaning long
into the event), BTC dominance stable or falling.

**Sell-trigger:** below the consolidation floor (not a round %).
**Re-entry:** next weekly support below the breakdown, or 2R in BTC terms,
whichever is further.

### 3.2 `sentiment_extreme_greed_fade`
**When:** F&G ≥ 80 (extreme greed), price at a weekly resistance level,
funding deeply positive (long squeeze setup).

**Sell-trigger:** at the recent weekly swing low below current price.
**Re-entry:** 30-day range mean, or 2R in BTC terms minimum.

**Note:** this is the mirror of the old `sentiment_extreme_reversion`.
Under accumulation, fear extremes don't trigger an action — the bot is
already long BTC, so "buy the fear" is already the default state. Only
greed extremes can prompt a step-out.

### 3.3 `funding_flip_divergence`
**When:** price making a new local high but funding flips negative across
2+ exchanges (Binance, OKX), or open interest expanding opposite to price
direction. "Smart money is leaning against the crowd" at a top.

**Sell-trigger:** above the divergence high at a technical level.
**Re-entry:** the level the divergence started, or 2R in BTC terms minimum.

### 3.4 `onchain_distribution_top`
**When:** exchange net INflow > $100M over 7 days (distribution to
exchanges = supply pressure), stablecoin supply falling (dry powder
leaving), price extended above the 30-day range at a monthly S/R level,
adverse macro catalyst in the next 72h.

**Sell-trigger:** below the range midpoint.
**Re-entry:** below the range, at 2R or the prior monthly S/R, whichever
is further.

---

## 4. Cycle checklist (filled before orders fire)

Every cycle requires the agent to fill this and append to `memory/TRADE-LOG.md`
**before** any order hits the exchange.

```
Date (UTC):
Playbook setup: [catalyst_driven_breakdown | sentiment_extreme_greed_fade
                 | funding_flip_divergence | onchain_distribution_top]
Rubric grade: [A | B]
Rubric scores: catalyst=X sentiment=X onchain=X macro=X technical=X
Specific catalyst / thesis: (one paragraph)
Sell-trigger price: (technical level)
Re-entry limit price: (technical level)
Worst-case rebuy price (72h market buy estimate):
Risk budget (% of stack): (0.5 or 1.0)
Fraction of stack to sell (formula result, ≤ 0.30):
BTC to sell:
USD expected from sell:
Expected BTC on re-entry fill:
Expected BTC on worst-case re-entry:
Cycle BTC R:R: (must be ≥ 2.0)
Weekly cycle count (including this one): /2
```

---

## 5. Exit rules (cycle close)

### Normal closes
- **Re-entry limit fills:** cycle closed at plan. Log BTC delta.
- **72h time cap fires → market buy with remaining USD:** cycle closed at
  realized loss. Log BTC delta.
- **Sell-trigger cancelled before firing** (thesis broken before breakdown):
  cycle abandoned. Log as zero-delta.

### Discretionary closes
- **Thesis break mid-cycle** (catalyst invalidated intraday, e.g., Fed
  walks back a decision, flows reverse hard): cancel the remaining order
  and close at market. Document the break.
- **Weekly-review grades the setup D or F retroactively:** close any
  still-open cycle on Monday's first window.

### Forced closes
- **Weekend-gap defense:** §2 rule 19.
- **Panic breach:** the hourly `panic-check` routine closes any active
  cycle if unrealized BTC loss ≥ 1.5R.

---

## 6. Weekly grading (Sunday 00:00 UTC)

### Stats (all in BTC terms)
- Starting BTC (Mon 00:00 UTC), ending BTC (Sun 00:00 UTC)
- Week BTC delta (absolute sats, %)
- Closed cycles: W / L / open
- Win rate (cycles that ended with more BTC than started the cycle)
- Best cycle (largest BTC gain), worst cycle (largest BTC loss)
- Profit factor: sum(BTC gained on winners) / |sum(BTC lost on losers)|
- Alpha vs HODL = bot's BTC delta %, since HODL is defined as 0% BTC growth

### Letter grade
- **A:** BTC delta > +2% for the week, profit factor > 1.5, no rule violations
- **B:** BTC delta > 0, no rule violations
- **C:** BTC delta in (−1%, 0], no rule violations
- **D:** any rule violation, or BTC delta ≤ −1%
- **F:** stop-loss failure, cooldown violation, leverage/alt attempted, or
  two+ rule violations

### Rule-change discipline
Rule changes require two consecutive weekly reviews documenting the same
friction point. One-off bad weeks don't justify rule changes.

---

## 7. Integration with the research agent

Research agent output ([../research/RESEARCH-AGENT-DESIGN-V2.md](../research/RESEARCH-AGENT-DESIGN-V2.md))
still uses the 5-point rubric. The **rubric questions are unchanged**, but
the *direction* of trade ideas flipped from step-in (buy) to step-out (sell
+ re-enter).

```
rubric.grade            → §2 rule 7 (sizing)
rubric.catalyst         → §3.1 (catalyst_driven_breakdown requires true)
trade_ideas[0].playbook_setup  → §3 (must be one of four step-out types)
trade_ideas[0].sell_trigger_price / rebuy_limit_price / worst_case_rebuy
                        → §4 (feeds the cycle checklist)
```

**Order of authority on conflict:** this playbook > research agent output.

---

## 8. Panic conditions & kill switch

The `panic-check` routine (hourly) enforces these.

1. **Unrealized BTC loss on an active cycle ≥ 1.5R:** market-close the cycle.
   The sell-trigger and/or re-entry should have behaved correctly; if not,
   investigate before the next cycle.
2. **BTC stack drawdown ≥ 15% from quarterly starting BTC count:** halt all
   new cycles until manual `/resume`. Telegram alert. 15% in sats terms is
   15 consecutive losses at 1% risk or fewer bigger ones — either way,
   something is wrong at the strategy level.
3. **Coinbase Advanced Trade 5xx > 3 consecutive calls in one routine
   run:** halt the run, alert, exit. Next scheduled run retries from fresh
   state.
4. **Stablecoin de-peg** (USDC ≤ $0.98 or USDT ≤ $0.97): cancel any active
   buy-back limit immediately and rotate remaining USD to BTC at market.
   Do not re-engage cycles until re-peg. The stack is safer in BTC than in
   a de-pegging stable.
5. **Exchange / regulatory shock:** flatten any active cycle to BTC
   (cancel sells, execute any pending buy-backs at market), pause new
   cycles, alert.

---

## 9. Defaults — locked in v1 (2026-04-24)

| Parameter | v1 value | Re-evaluation trigger |
|---|---|---|
| Starting BTC (quarterly baseline) | 0.05342287 BTC (2026-04-24) | Quarterly reset |
| Benchmark | Pure HODL (0% BTC growth) | Fixed |
| Steady state | 80–90% BTC, 10–20% USD | 4+ weeks at end-of-window cash outside this range → revisit |
| Risk per cycle | 0.5% B / 1.0% A (of BTC stack) | 4+ weeks of stable performance → consider 0.75% B / 1.5% A |
| Max active cycles | 1 | Never — single-asset strategy |
| Max new cycles / 7d | 2 | 4+ weeks at < 2 cycles/week avg → consider 3 |
| Max fraction sold per cycle | 0.30 of stack | Measure missed-BTC opportunity on strong breakdowns |
| Re-entry time cap | 72h → market buy | Measure fill rate and worst-case rebuy damage |
| Minimum BTC R:R | 2.0 | Fixed |
| Cooldown after 1 losing cycle | 48h | Fixed |
| Cooldown after 2 losing cycles | 7d + post-mortem | Fixed |
| Drawdown kill switch | 15% BTC from quarterly start | Fixed |
| Asset | BTC/USD spot | Fixed for v1 |
| Leverage | None | Never |

---

## 10. Open decisions (revisit after 4 weeks live)

- [ ] Is the 30% max-per-cycle cap too tight in high-conviction setups?
      Measure "missed BTC" at end of each strong breakdown.
- [ ] Does the 72h re-entry time cap bail too often at losses? Consider
      96h or 120h if weekly review shows >30% of cycles closing at the cap.
- [ ] Should the re-entry use a tranche ladder (1/3 at target, 1/3 midway,
      1/3 at time cap) instead of a single limit? Simpler single-order for v1.
- [ ] Track BTC-denominated *and* USD-denominated P&L in parallel for 4
      weeks — sometimes the divergence reveals regime bugs in the strategy.
- [ ] Should the sell-trigger distance be capped relative to current price
      (e.g., max 5% below)? Protects against accidentally selling into a
      flash wick.
- [ ] Re-entry should it auto-move DOWN if price breaks below the re-entry
      level before filling? Current rule says no (never chase) but strict
      "never move" may miss obvious deeper supports.

---

## 11. Why this playbook

Every rule here has a specific reason.

| Rule | Why |
|---|---|
| BTC-denominated everything | The goal is more sats. Measuring USD P&L lets a BTC-count-shrinking quarter look like a win during bull moves — exactly when the bot should be stacking. |
| 80–90% BTC steady state | Cash reserve handles the first dip without needing to sell core stack. Holding >20% USD over multiple windows = strategy drift toward timing the market. |
| Max 30% per cycle | A single thesis failure at 30% of stack is recoverable (1–2 good cycles back). At 100%, one bad call resets months of work. |
| Sell + re-entry both placed immediately | A lone sell order is "timing the market." The re-entry is what makes it accumulation. If you can't name the buy-back level, you don't have the setup. |
| 72h re-entry cap | USD is not the base currency. Holding USD longer than 72h is a bet that BTC goes lower — that bet is priced in at re-entry; extending it is doubling down. |
| Sell-trigger never moves up | Moving a trigger toward price = chasing = locking in a BTC loss beyond the risk budget. |
| Re-entry never moves up | Same reason on the buy side. |
| 2:1 BTC R:R | Below 2:1, the 50%-win-rate math doesn't net sats after fees. Fees are paid in BTC (Coinbase taker ~0.4% round-trip), so they compound against the stack. |
| Cooldown after losses | Revenge-cycling is the #1 BTC drainer in accumulation strategies — you sell at the wrong level, panic-buy higher, and do it again within the same day. |
| BTC drawdown halt | If the strategy is broken, you want the bot to stop before the stack is gone. 15% in BTC terms is ~15 max-risk losses or fewer bigger ones — past that, the rubric is wrong, not the individual trade. |

---

## 12. Cross-reference

- **How cycles are executed:** [Opus 4.7 Trading Bot — Setup Guide.md](Opus%204.7%20Trading%20Bot%20—%20Setup%20Guide.md) Part 5
- **How setups are graded:** [../research/RESEARCH-AGENT-DESIGN-V2.md](../research/RESEARCH-AGENT-DESIGN-V2.md) §5
- **Which APIs the bot calls:** [Opus 4.7 Trading Bot — Setup Guide.md](Opus%204.7%20Trading%20Bot%20—%20Setup%20Guide.md) Part 4
- **Memory files the bot reads:** `memory/TRADING-STRATEGY.md` (this file), `memory/TRADE-LOG.md`, `memory/RESEARCH-LOG.md`, `memory/WEEKLY-REVIEW.md`, `memory/PROJECT-CONTEXT.md`
