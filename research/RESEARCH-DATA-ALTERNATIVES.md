# Research Data — Alternatives to Chartinspect (brief, for future review)

**Prepared:** 2026-04-23
**Status:** Parking-lot eval. Not scheduled. Revisit if Chartinspect Pro proves
insufficient after Phase 1 verification (see RESEARCH-AGENT-DESIGN.md §9).

Two parallel questions the user raised:

1. Can Coinbase Developer Platform (CDP) replace Chartinspect?
2. Can we build our own data pipeline from raw sources?

---

## 1. Coinbase Developer Platform (CDP)

CDP surfaces observed in the portal: **Metrics, SQL API, Webhooks, Node, AgentKit**,
plus Consumer/Business/Institutional API groups.

### Fit against our rubric

| Rubric slot | What we need | Does CDP cover it? |
|---|---|---|
| #1 catalyst | FOMC/CPI/NFP calendar | **No** — macro events aren't in CDP scope |
| #2 sentiment | Funding, OI, liquidations | **Partial at best** — CDP Institutional has Coinbase Derivatives, but that's one venue only. Binance/OKX funding is the primary rubric signal and not in CDP |
| #3 on-chain | BTC exchange flows, whale wallets, stablecoin supply | **Likely no** — CDP Data (SQL API, Webhooks, Node) is **Base-chain focused** ("mainnet RPC endpoint for Base", "smart contract events on Base"). Bitcoin UTXO chain isn't the native target |
| #3 ETF flows | Per-issuer spot BTC ETF flows | **No** — competitor-ETF flow data (IBIT, FBTC) is not Coinbase's to publish |
| #4 macro | DXY, yields, M2 | **No** — not in scope |
| #5 technical | BTC price, OHLC | **Yes** — Coinbase Advanced Trade public API already covers this (we use it) |

### Verdict (preliminary)

CDP is built for **Base-chain / smart-contract development**, not for Bitcoin
market research. It would not replace Chartinspect. The one piece already in
use is the Advanced Trade public API for spot price/OHLC.

### AgentKit

"Toolkit enabling AI agents to interact onchain." **Execution-oriented**, not
research. It could replace parts of our trading wrappers (`scripts/coinbase.py`)
if we moved to a CDP-native agent runtime, but that's orthogonal to the research
question and would trade a working adapter for an unknown one.

---

## 2. Building our own pipeline from raw sources

Technically feasible. Here's what it costs:

### What "our own" means — raw public sources

| Data | Raw source | Engineering cost |
|---|---|---|
| Funding rates (per venue) | Binance/OKX/Bybit public `/fapi/v1/premiumIndex` etc. | Low — just wrappers per venue |
| Open interest (per venue) | Same public endpoints | Low |
| Liquidations | Binance/Bybit WebSocket `forceOrder` stream | **Medium — requires persistent connection, aggregation, deduping** |
| On-chain flows (BTC) | Run Bitcoin Core node + ElectRS index + tag exchange addresses ourselves | **High — node sync (~500GB), address-tagging dataset, ongoing curation** |
| Stablecoin supply | Tether / Circle transparency pages + ERC-20 token contracts via Etherscan API | Medium — two issuers, schema changes |
| ETF flows | Scrape Farside Investors daily + issuer IR pages | Low — Farside is already usable; add issuer scrapes as backup |
| Whale wallets | Tag "whale" (>1000 BTC) addresses ourselves | **High — labeling is the hard part, not the query** |

### What it buys us

- **No vendor lock-in** / no $24/mo subscription
- **Lower latency** for liquidation streams (WebSocket vs 10-min Chartinspect polls)
- **Custom metrics** not in any vendor catalog
- **Full historical depth** for backtesting (we control retention)

### What it costs

- **Ops burden grows to match a junior data-engineering job.** Exchanges change
  endpoints. Address labels drift. Node resync after an outage is a half-day.
- **Correctness risk.** Chartinspect has engineers whose full-time job is getting
  "BTC exchange net flow" right. We'd be rediscovering edge cases the first time
  Binance moves wallets.
- **Backtest inconsistency.** Our historical liquidation stream starts the day
  we turn it on. Chartinspect has already-indexed history.
- **At $3K equity, this is inverted ROI.** Saving $24/mo (0.8% of capital) by
  spending 40+ engineering hours is uneconomic. It only starts making sense at
  $50K+ equity where the monthly fee is a rounding error AND the custom metrics
  deliver measurable alpha.

### Viable hybrid (if Chartinspect underperforms)

Not "build everything" but "slot specific gaps":

- **Funding + OI from Binance/OKX public** — fully replaces Chartinspect derivatives
  for ~1 day of wrapper work. Worth doing if Chartinspect's per-venue funding is
  missing.
- **ETF flows from Farside scrape** — already the design's documented fallback.
- **On-chain from Coin Metrics Community** — free tier has BTC exchange flow
  (3x/day refresh, 24h delay). Lower fidelity than Chartinspect but free.

The hybrid path is already baked into RESEARCH-AGENT-DESIGN.md §9 Phase 1 as
the fallback for Chartinspect verification gaps.

---

## Recommendation (carry to future review)

1. **Ship v1 on Chartinspect Pro.** $24/mo is cheap insurance against data-ops
   debt at current equity. Revisit if Phase 1 verification shows gaps bigger
   than the documented fallbacks can cover.
2. **CDP is not a research substitute.** Re-eval only if we add a Base-chain
   strategy (not on the roadmap).
3. **Build-our-own makes sense at $50K+ equity**, or if a specific rubric signal
   proves load-bearing and only buildable in-house. Track which signals actually
   drive the grade → size decision in the first 4 weeks of live data; that list
   is the true shopping list for any future in-house work.
4. **AgentKit is a separate question** (execution layer, not research). Eval
   alongside any future move off `scripts/coinbase.py` — not before.

---

## Trigger for re-evaluation

Revisit this doc if **any** of the following fires:

- Chartinspect Pro verification (§9 Phase 1) finds ≥2 rubric-load-bearing gaps
- Equity crosses $50K (the economics of in-house flip)
- Weekly review logs >3 consecutive weeks of "data-source issue" as a grading
  factor
- Strategy expands beyond BTC spot to Base-chain assets (then CDP becomes relevant)
