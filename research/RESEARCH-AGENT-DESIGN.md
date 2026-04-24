# Research Agent Design — Swing BTC on Numeric Signals

**Prepared:** 2026-04-22 (revised: 2026-04-23 single-vendor-simplification v1.3)
**Status:** **SUPERSEDED 2026-04-24** by [RESEARCH-AGENT-DESIGN-V2.md](RESEARCH-AGENT-DESIGN-V2.md).
Chartinspect Pro verification (see [RESEARCH-DATA-STATUS.md](RESEARCH-DATA-STATUS.md))
showed the single-vendor thesis broken — ETF/exchange balances and dominance
endpoints frozen. v2 replaces broken slices with free public sources and
collapses the Python orchestrator into CLI wrappers composed by the routine.
Retained here for history; do not build against v1.
**Companion docs:**
- [EVALUATION-COINBASE-BTC.md](EVALUATION-COINBASE-BTC.md) — the swing-BTC playbook (hard rules, setup types, management ladder)
- [Opus 4.7 Trading Bot — Setup Guide.md](Opus%204.7%20Trading%20Bot%20—%20Setup%20Guide.md) — how the bot is built and deployed

This document captures the design for a custom research agent for a swing
Bitcoin strategy on Coinbase. Build after the Coinbase adapter ships and the
trading loop is stable.

**v1 scope decision:** numeric and event-calendar signals plus raw-text sentiment
from YouTube analyst channels. Numeric sources feed the rubric as numbers.
YouTube video titles are passed as raw text directly to the synthesis model
(OpenRouter or HuggingFace) — the synthesis call interprets sentiment and scores
the rubric in a single pass. No separate classification step. Text sources
(news RSS, X/Twitter, Reddit) are deferred with an explicit v2 trigger in §7.1.

---

## 1. Purpose

Swing trade BTC-USD (holding period 1–7 days) using:

- **Scheduled catalysts** — FOMC, CPI, NFP, ETF flow events, known unlocks
- **Positioning & sentiment (numeric)** — funding rates, open interest, F&G index
- **On-chain fundamentals** — exchange flows, whale behavior, stablecoin supply
- **Market structure** — BTC dominance, stablecoin dominance, total market cap
- **Macro context** — DXY, SPX, VIX, gold, 10Y yields, real yields, M2

The research agent's job: twice a day, produce a structured report with a
tactical bias (long / short / flat), a confidence score, and 0–2 specific trade
ideas that conform to the swing playbook.

**What this is NOT:** a day-trading signal generator, a price-prediction model,
a real-time alerting system, or a narrative-awareness layer. Signals are
evaluated on a 12-hour cadence from structured data only.

---

## 2. Signal inputs

### 2.1 v1 stack (must-have)

Every entry is a number or an event record. The LLM never originates a
number — it receives structured context and produces thesis + rubric scores.
This eliminates the "confidently-wrong numeric claim" failure mode and
removes the need for a text-classification pass.

| Source | Rubric slot | Role | Cost |
|---|---|---|---|
| **TradingEconomics** (free tier) or ForexFactory scrape | **#1 catalyst** | Scheduled macro events (FOMC / CPI / NFP / jobs) | Free |
| **Chartinspect Pro** | **#2 sentiment + #3 structure** | Funding rates, OI, liquidations, on-chain flows, stablecoin supply, ETF flows per issuer — one vendor covers derivatives + on-chain + ETF | $24/mo |
| **alternative.me** Fear & Greed | **#2 sentiment** | Contrarian extremes | Free |
| **YouTube Data API v3** (top BTC analyst channels) | **#2 sentiment** | Analyst directional bias — last 5 video titles per channel passed as raw text to synthesis LLM | Free (10K units/day) |
| **mempool.space** / blockchain.com | **#3 structure** (optional) | On-chain activity, fees, unconfirmed txs — not rubric-load-bearing | Free |
| **CoinGecko** | **#3 structure / #5 technical** | BTC dominance, total market cap, stablecoin dominance | Free (~30 req/min) |
| **yfinance** | **#4 macro** | DXY, SPX, VIX, gold | Free |
| **FRED** (St. Louis Fed) | **#4 macro** | 10Y yields, real yields (DFII10), M2 | Free |
| **Coinbase / Binance public** | **#5 technical** | Price, OHLC, ground-truth OI | Free |

Synthesis model is routed via **OpenRouter** (premium tier — Claude Sonnet 4.6,
GPT-5, or Gemini 2.5 Pro; A/B per §10).

### 2.2 Filter rationale — candidate sources

The v1 stack was refined with a 3-must / 1-nice / 2-defer filter. The test:
does the source fill a *distinct* rubric slot, or does it just add correlated
noise to a slot another source already covers?

| Source | Rubric slot | Verdict | Why |
|---|---|---|---|
| Economic calendar (TradingEconomics) | #1 catalyst | **Must** | Rubric #1 literally cannot be scored without a scheduled-event feed. The design had a hole here. |
| CoinGecko (BTC dominance) | #3 structure / #5 technical | **Must** | BTC-D regime is a standalone swing signal not captured by any other source. One endpoint, huge value. |
| FRED | #4 macro | **Must** | Adds real yields (DFII10) and M2, which yfinance tickers don't cover cleanly. Real-yield-vs-BTC is one of the tightest macro correlations at swing timeframe. |
| Reddit | #2 sentiment | **Defer** | Reddit API terms changed in 2026; access complexity outweighs signal value at current stage. Revisit if v2 text-layer trigger fires (§7.1). |
| YouTube (top BTC analyst channels) | #2 sentiment | **Must — v1** | Analyst directional bias 24–48h before the market moves. Last 5 video titles per channel from Benjamin Cowen, Coin Bureau, InvestAnswers, Crypto Banter, Plan B, Raoul Pal. Passed raw to synthesis LLM. |
| X / Twitter (curated pro-tier accounts) | #2 sentiment | **Defer** | Overlaps with YouTube analyst signal on the same rubric slot. High ops cost (API tier, curation, classification) for marginal lift. Revisit via v2 trigger (§7.1). |
| CoinGlass | #2 sentiment / #3 structure | **Reject** | No free tier as of 2026-04. Chartinspect Pro covers the same surface (per-venue funding, OI, liquidations, ETF flows) at $24/mo. No reason to pay twice. |
| News RSS (The Block + CoinDesk headlines) | #1 catalyst (unscheduled) | **Defer** | Only adds value for unscheduled-catalyst detection. Numeric *reactions* (funding flip, OI spike, flow surge) are the v1 proxy; add headlines-only feed if forward-test shows a concrete gap (§7.1). |

Sources already in the v1 stack (Chartinspect, F&G, CoinGecko, yfinance, FRED,
mempool.space, Coinbase/Binance) were not re-contested — they form the data-plane
bones of the pipeline.

---

## 3. Pipeline architecture

```
                    ┌────────────────────────────────────────────┐
                    │ scripts/cli.py research --query "..."      │
                    │ (existing CLI entry — unchanged)           │
                    └────────────────────────┬───────────────────┘
                                             │
                    ┌────────────────────────▼───────────────────┐
                    │ scripts/research.py                        │
                    │ (swap internals; keep signature)           │
                    └────────────────────────┬───────────────────┘
                                             │
                    ┌────────────────────────▼───────────────────┐
                    │ Parallel collectors (async fetch)          │
                    │   price (Coinbase/Binance public)          │
                    │   funding + OI + on-chain + ETF            │
                    │     (Chartinspect Pro — one vendor)        │
                    │   F&G (alternative.me)                     │
                    │   youtube (Data API v3 → raw titles)       │
                    │   structure (CoinGecko — BTC-D, MC)        │
                    │   macro (yfinance, FRED)                   │
                    │   events (TradingEconomics)                │
                    │   mempool (mempool.space, optional)        │
                    └────────────────────────┬───────────────────┘
                                             │
                                             ▼
                    ┌────────────────────────────────────────────┐
                    │ Synthesis (OpenRouter, premium)            │
                    │ Claude Sonnet 4.6 / GPT-5 / Gemini 2.5 Pro │
                    │  - receive structured numeric context      │
                    │  - score the 5-point swing rubric          │
                    │  - output report (see §8)                  │
                    └────────────────────────┬───────────────────┘
                                             │
                                             ▼
                    ┌────────────────────────────────────────────┐
                    │ memory/research-reports/YYYY-MM-DD-HH.json │
                    │ memory/daily-journal/YYYY-MM-DD.md append  │
                    └────────────────────────────────────────────┘
```

**Cost profile:** one synthesis call per run — receives numeric context plus raw
Reddit titles (~500 tokens) and YouTube titles (~200 tokens). Total input grows
to ~6–7K tokens (~$0.06–0.12/call). Two runs/day ≈ $0.12–0.24/day LLM spend.
Add Chartinspect Pro at $24/mo → **$27–31/mo all-in**. Reddit and YouTube API
calls are free within tier limits. No separate classification pass.

---

## 4. Integration point in the existing codebase

The architecture change is small because the existing project already
abstracts research behind a single module.

**Current contract** ([scripts/research.py](scripts/research.py)):

```python
def ask(query: str) -> ResearchResult:
    """Returns structured result with .answer, .citations, .ok, .error."""
```

**Proposed: keep the contract, replace internals.** The routine prompts and
CLI don't change. Swap is localized to one file.

**Extend** the `ResearchResult` dataclass with swing-specific fields:

```python
@dataclass(frozen=True)
class ResearchResult:
    # existing fields
    ok: bool
    answer: str
    citations: list[str]
    error: str | None

    # new fields for swing workflow
    bias: Literal["long", "short", "flat"] | None
    confidence: float | None              # 0-1
    rubric_scores: dict[str, bool] | None # the 5-point swing rubric
    numeric_context: dict[str, float] | None
    catalysts: list[dict] | None          # [{when, event, expected_impact}]
    report_path: Path | None              # full markdown report on disk
```

Older callers that only use `.answer` and `.citations` keep working.

**New files to add:**

```
scripts/research/
  __init__.py           # re-exports ask() for back-compat
  pipeline.py           # orchestrator (parallel fetch + synthesis)
  sources/
    price.py            # Binance / Coinbase public
    chartinspect.py     # funding + OI + liquidations + on-chain + ETF flows
    fear_greed.py       # F&G index (alternative.me)
    reddit.py           # PRAW — r/BitcoinMarkets, r/Bitcoin, r/CryptoCurrency
    youtube.py          # YouTube Data API v3 — top BTC analyst channels
    coingecko.py        # BTC dominance + market structure
    macro.py            # yfinance + FRED
    calendar.py         # economic events (TradingEconomics)
    mempool.py          # mempool.space + blockchain.com (optional)
  synthesize.py         # synthesis (OpenRouter or HuggingFace) — receives numeric context + raw Reddit/YouTube titles
  schema.py             # dataclasses
```

The `research.py` at the top level becomes a 10-line shim that imports from
`research/pipeline.py`. No other file in the project needs to change.

---

## 5. The swing rubric (replaces the FX rubric in decide.py)

Score 1 point per item true at the research window. The LLM fills this in
during synthesis.

1. **Clear catalyst in next 1–5 days** — FOMC, CPI, NFP, known unlock, ETF
   flow anomaly, scheduled macro print. Sourced from the economic calendar.
   *Null catalyst = B-grade ceiling regardless of other points.*
2. **Sentiment extreme OR divergence** — F&G < 25 or > 75, OR price making
   new local high/low while funding flips the opposite way, OR open interest
   rising against price direction.
3. **On-chain / market structure confirmation** — Exchange net outflow
   (accumulation) or inflow (distribution); stablecoin supply shift; whale
   wallet movement; BTC dominance regime aligned (rising BTC-D during chop
   supports long-BTC via rotation from alts; falling BTC-D argues against).
   Any one of these four signals clears the item.
4. **Macro aligned** — DXY trend supports direction; real-yields direction
   supports direction; SPX risk-on/off regime consistent; no imminent adverse
   macro print within 24h.
5. **Technical level** — Entry is at a weekly or monthly S/R, not a daily
   noise level. Swing timeframe demands HTF levels.

**Grade → size:**
- 5/5 → A-grade: 1.0% risk
- 3–4/5 → B-grade: 0.5% risk
- <3 → skip

**Why 3/5 is the B-grade floor (not 4 like FX):** swing setups are rarer
and noisier; demanding 4/5 leaves too many months with zero trades. 3/5 with
mandatory catalyst (#1) preserves discipline.

---

## 6. Routine cadence (swing-specific)

| Routine | Schedule (UTC) | Model | Job |
|---|---|---|---|
| research-and-plan | 00:00 and 12:00 daily | Sonnet for synth | Full pipeline; produce report + journal ideas |
| execute | 00:30 and 12:30 daily | Haiku | Re-validate top idea, run guardrails, place order with SL+TP |
| manage | Every 4h | Haiku | `manage_runners`: breakeven, partial TP, trail |
| panic-check | Hourly | Haiku | Pull positions, alert if unrealized ≤ threshold |
| daily-summary | 23:30 UTC | Haiku | 24h P&L snapshot, commit equity curve |
| weekly-review | Sunday 00:00 UTC | Opus | Grade A–F, propose strategy/playbook edits |

Compare to the intraday FX cadence: ~3× less frequent, matching the holding
period. Panic-check exists because crypto gaps hard on weekends — even a swing
strategy needs a fast heartbeat for risk, just not for decisions.

---

## 7. Hard problems flagged for later

### 7.1 Unscheduled-catalyst blindspot

The numeric-only stack cannot *detect* unscheduled news events (SEC
enforcement, surprise ETF decisions, exchange failures, regulatory shocks).
Mitigation path: the *reactions* — funding flip, OI spike, price gap,
exchange flow surge — are all observable. The synthesis LLM is prompted to
tag "news-driven regime" when these fire together without a scheduled
catalyst on the calendar, and the agent flags "pause new entries until the
next research window confirms."

**v2 trigger for re-adding deferred text sources:** ">3 losses in a quarter
attributable to missed unscheduled catalysts" — logged in weekly-review with
a post-mortem link. When the threshold hits, add in this order:

1. News RSS (The Block + CoinDesk, **headlines only**, no full-text, no classifier)
2. X/Twitter pro-tier voices (curated list, sentiment extraction)

Reddit is on the stage-2 track (§2.2) and doesn't gate on this trigger — it
adds a distinct retail-sentiment dimension, not unscheduled-catalyst detection.

### 7.2 The numeric stack is fully backtestable — use that

Every source in §2.1 has free historical coverage (F&G full history, funding
2018+, ETF flows daily since spot-launch, FRED decades, on-chain free-tier
90d+, CoinGecko full history). Before building the live pipeline, run the
rubric over the last 12 months and verify A-grade setups actually had better
forward returns than B-grade. If not, the rubric needs tuning — not more
signals. This is the single biggest advantage of the numeric-only design
over a text-heavy plan.

---

## 8. Output contract (what the pipeline writes)

Two artifacts per research run:

### 8.1 Machine-readable: `memory/research-reports/YYYY-MM-DD-HH.json`

```json
{
  "ts": "2026-04-22T12:00:00Z",
  "bias": "long",
  "confidence": 0.72,
  "rubric": {
    "catalyst": true,
    "sentiment_extreme_or_divergence": true,
    "onchain_or_structure": true,
    "macro_aligned": false,
    "technical_level": true
  },
  "grade": "B",
  "numeric_context": {
    "price": 67420.5,
    "funding_rate_8h": 0.0009,
    "open_interest_usd": 31200000000,
    "fear_greed": 68,
    "etf_net_flow_1d_usd": 142000000,
    "btc_dominance": 54.2,
    "dxy": 104.8,
    "spx": 5840.2,
    "real_yield_10y": 1.82,
    "m2": 21030000000000
  },
  "catalysts": [
    {"when": "2026-04-24T18:00Z", "event": "FOMC decision", "bias_impact": "asymmetric_upside"}
  ],
  "trade_ideas": [
    {
      "symbol": "BTC-USD",
      "side": "buy",
      "entry": 67200,
      "stop": 63500,
      "target": 74500,
      "rr": 2.0,
      "thesis": "...",
      "playbook_setup": "catalyst_driven_breakout"
    }
  ],
  "sources": {
    "numeric": ["chartinspect", "alternative.me", "coingecko", "yfinance", "fred", "coinbase"],
    "events": ["tradingeconomics"]
  }
}
```

### 8.2 Human-readable: append to `memory/daily-journal/YYYY-MM-DD.md`

Standard journal format, consistent with existing daily journal entries.

---

## 9. Suggested order of work (when this becomes active)

Phase in after the Coinbase adapter is live and the bot has run for 2+ weeks
on the simpler research path.

1. **Collectors** (5–7 days). Build the `sources/*.py` files. Each is a thin
   async client returning a dataclass. Test each in isolation. **First task:
   verify Chartinspect Pro covers per-venue funding (Binance, OKX), per-issuer
   ETF flows (IBIT/FBTC/etc.), and ≥12-month history.** Also wire `reddit.py`
   (PRAW) and `youtube.py` (Data API v3) — both need credentials in `.env`
   before testing (see §2.1). Confirm YouTube API key is enabled in GCP project
   `gen-lang-client-0675309660`. If a specific metric has a gap, surface it in
   the next design pass — do not pre-name a second vendor speculatively.
2. **Historical backtest** (2–3 days). Run rubric logic on 12 months of
   history. Verify A-grade > B-grade > skip in forward returns. If it fails,
   tune the rubric before any live work.
3. **Synthesis layer** (2–3 days). `synthesize.py` with premium OpenRouter
   model. A/B Sonnet vs GPT-5 vs Gemini 2.5 Pro for one week on identical context.
4. **Rubric wiring** (1–2 days). Update `decide.py` to accept `rubric_scores`
   and size accordingly.
5. **Forward-test window** (4–6 weeks). Pipeline runs in shadow mode —
   reports are written, execution still uses old path. Compare signals
   against actual outcomes.
6. **Cut over** — switch the execute routine to consume the new reports.
7. **Stage 2 (Reddit), optional** (3–5 days after v1 is stable). Only add
   if (a) v1 has run cleanly for 2+ weeks and (b) a forward-test gap points
   at retail-sentiment as the missing dimension.

Total: **~2 weeks build + 4–6 weeks shadow** for v1. Stage 2 is purely
additive and gated on v1 performance.

---

## 10. Open decisions (revisit before building)

- [ ] Economic calendar source: TradingEconomics free tier (structured JSON,
      simpler) vs. ForexFactory scrape (richer/ranked events, more fragile)
- [ ] Chartinspect Pro coverage — verify during Phase 1: per-venue funding
      rates? ETF flows per issuer? ≥12-month history? If gaps appear, decide
      then (don't pre-name a fallback vendor in this design).
- [ ] Synthesis model: Claude Sonnet 4.6, GPT-5, or Gemini 2.5 Pro? Run A/B
      for one week on identical context before committing
- [ ] Multi-asset (BTC + ETH + SOL) or BTC-only? Single-asset is simpler;
      adding ETH is cheap because all sources cover it
- [ ] Cooldown rule after a loss — swing losses are bigger (2R on 1% = 2% of
      capital); a day or two sitting out may be wise
- [x] Reddit — deferred. API terms changed 2026; revisit at v2 text-layer trigger.
- [x] YouTube — promoted to v1 must-have. Channels: Benjamin Cowen, Coin Bureau,
      InvestAnswers, Crypto Banter, Plan B, Raoul Pal. Same Haiku → numeric flow.
- [ ] YouTube channel IDs — verify handles map to correct channel IDs during
      Phase 1 implementation (don't hardcode stale IDs in design).
- [ ] v2 text-layer trigger — ">3 losses in a quarter attributable to missed
      unscheduled catalysts" (see §7.1)

---

## 11. Why numeric-first for v1

Reasons the v1 stack is numeric and event-only:

1. **Numeric reliability.** A structured pipeline cannot hallucinate a
   funding rate, an ETF flow size, or a real-yield print. LLM-sourced
   "fundamentals" can, and the failure mode is silent — a confidently wrong
   number reads the same as a correct one.
2. **Backtestability.** Every input in §2.1 has historical coverage
   (Chartinspect serves history via the Pro subscription; other sources free).
   The rubric can be validated against real outcomes before any capital is
   risked. A text-classified pipeline with LLM summaries cannot be
   reconstructed historically — you can't ask an LLM what it would have said
   on 2024-03-15 given the context available that day.
3. **Cost.** Twice-daily runs with one premium synthesis call ≈ $0.10–0.20/day.
   A text-ingestion + classification pipeline at the same cadence is 3–10× that.
4. **Signal coherence.** Numeric signals preserve divergences as first-class
   features the rubric keys on (retail bullish while whales distribute;
   price up while funding flips negative). Text summaries collapse these
   into "mixed sentiment."

Narrative awareness is the one capability forgone in v1. §7.1 documents the
mitigation and the v2 trigger for re-adding deferred text sources.
