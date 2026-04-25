# Research Agent Design v2 — BTC Accumulation on Free/Public Data

**Prepared:** 2026-04-24 (revised 2026-04-24 for accumulation pivot)
**Status:** Design. Supersedes [RESEARCH-AGENT-DESIGN.md](RESEARCH-AGENT-DESIGN.md) v1.
**Companion docs:**
- [TRADING-STRATEGY.md](../memory/TRADING-STRATEGY.md) — the rulebook and 4 step-out setup types this pipeline must serve
- [RESEARCH-DATA-STATUS.md](RESEARCH-DATA-STATUS.md) — per-datapoint live/stale/missing status (drives §3)
- [RESEARCH-DATAPOINTS.md](RESEARCH-DATAPOINTS.md) — collection cadence

> **2026-04-24 revision:** Strategy flipped from USD-swing (step-in) to
> BTC-accumulation (step-out). The **rubric is unchanged** — the five
> questions still select the same underlying market regime. The *direction*
> of the resulting trade ideas changes, and the four `playbook_setup` tags
> are renamed/reframed accordingly. All `"Serves setup"` cells in §3 now
> reference the step-out names from
> [TRADING-STRATEGY.md §3](../memory/TRADING-STRATEGY.md).

---

## 0. Why v2 exists

v1 assumed Chartinspect Pro as a single-vendor source for derivatives +
on-chain + ETF + dominance. [RESEARCH-DATA-STATUS.md](RESEARCH-DATA-STATUS.md)
verification after the subscription went live showed:

- `exchange-balances` and `etf-balances` frozen since 2026-02-04 (79+ days stale)
- `btc-dominance` and `stablecoin-dominance` frozen since 2025-11-24 (5+ months stale)
- No liquidation, long/short ratio, or per-venue funding endpoints

The one-vendor thesis is broken. v1's synthesis-in-Python + monolithic
`scripts/research/` package is also over-engineered for this scale of
stack. v2:

1. Replaces broken Chartinspect slices with free public sources.
2. Collapses the Python orchestrator into the pattern already used by
   [scripts/chartinspect.py](scripts/chartinspect.py) and [scripts/youtube.py](scripts/youtube.py)
   — one CLI wrapper per source, composed by the routine prompt.
3. Removes the separate synthesis model. The LLM in the routine does the
   synthesis, as it already does in v1's stub implementation.

---

## 1. Purpose

Identify high-conviction **step-out** windows in BTC-USD (protective sell
now, paired re-entry at a lower support, hold USD ≤ 72h) using the
5-point rubric in §5. Twice-daily structured report with bias, confidence,
rubric scores, and 0–2 trade ideas. Goal: grow the BTC stack over each
quarterly challenge window versus a pure-HODL benchmark (0% BTC growth).
Not a day-trading signal generator, not a price predictor, not a real-time
alerter.

---

## 2. What changed from v1

| Area | v1 | v2 | Why |
|---|---|---|---|
| Architecture | Python package `scripts/research/` with async orchestrator + `synthesize.py` | Script-per-source CLI wrappers, composed by routine prompt | Matches existing pattern. Simpler at the current stack size. No Python synthesis layer to maintain. |
| Synthesis | Premium OpenRouter call inside `synthesize.py` | LLM in the routine itself scores rubric from collected JSON | Already works this way in v1's stub; removes separate model billing. |
| Chartinspect scope | 7+ endpoints (derivatives + on-chain + ETF + dominance) | 3 endpoints: funding, OI, whale-flows | Rest frozen or missing; keep the paid subscription only for what it serves. |
| ETF flows | Per-issuer via Chartinspect | **Aggregate-only via LLM WebSearch** | Not load-bearing for any of the 4 setup types (see §3.3); WebSearch avoids a fragile HTML scrape. |
| Dominance / market cap | Chartinspect | CoinGecko `/global` | Chartinspect frozen; CoinGecko is free + live. |
| Stablecoin supply | Chartinspect | DeFiLlama `/stablecoins` | Same reason. |
| Per-venue funding | Chartinspect (aggregate only) | Binance + OKX public endpoints | Chartinspect endpoint doesn't expose per-venue. |
| Liquidations, L/S ratio | — | Binance public | Not in Chartinspect; no key required. |
| Macro rates | FRED (design stage, unwired) | FRED with API key already in `.env` | Moved from planned to buildable. |
| Calendar | TradingEconomics in Python | Deferred; LLM WebSearch each routine run | Few events/week, free, no vendor coupling. Revisit only if the LLM misses scheduled events in forward-test. |
| Composer | Python async orchestrator | `scripts/research.sh` rebuilt from stub to parallel fan-out aggregator | Replaces the exit-3 stub. Shell-level concurrency is enough. |

---

## 3. Signal inputs — v2 stack

Every entry below maps to (a) a rubric slot in §5 and (b) at least one of
the 4 step-out playbook setups in [TRADING-STRATEGY.md §3](../memory/TRADING-STRATEGY.md#3-step-out-setup-types).
If it doesn't, it's not in v2.

### 3.1 Live today (wrappers already built)

| Source | Wrapper | Rubric | Serves setup | Notes |
|---|---|---|---|---|
| Chartinspect — aggregate funding | [chartinspect.py](../scripts/chartinspect.py) `funding-rates` | #2 | `funding_flip_divergence`, `sentiment_extreme_greed_fade` | Hourly; confirmed live |
| Chartinspect — open interest | [chartinspect.py](../scripts/chartinspect.py) `open-interest` | #2, #3 | `funding_flip_divergence`, `catalyst_driven_breakdown` | Aggregate + per venue (Binance/OKX/Bybit/CME) |
| Chartinspect — whale flows | [chartinspect.py](../scripts/chartinspect.py) `whale-flows` | #3 | `onchain_distribution_top` | 1k+ BTC cohorts; step-out reads the *inflow* side of this feed |
| YouTube titles | [youtube.py](../scripts/youtube.py) `titles` | #2 | all setups (sentiment texture) | 6 channels, raw titles |
| YouTube velocity | [youtube.py](../scripts/youtube.py) `velocity` | #2 | all setups | 48h upload count — high velocity = regime-change signal |
| Coinbase spot quote | [coinbase.py](../scripts/coinbase.py) `quote BTC-USD` | #5 | all setups | Already used by trading path |

### 3.2 To build (Phase 1 — §9)

| Source | New wrapper | Endpoint | Rubric | Serves setup | Cost |
|---|---|---|---|---|---|
| Fear & Greed Index | `scripts/fng.py` | `alternative.me/fng/` | #2 | `sentiment_extreme_greed_fade` | Free, no key |
| CoinGecko global | `scripts/coingecko.py` | `/api/v3/global` | #3, #5 | all setups (regime) | Free, 30 req/min |
| DeFiLlama stablecoins | `scripts/defillama.py` | `stablecoins.llama.fi/stablecoins` | #3 | `onchain_distribution_top` (watches falling stablecoin supply = dry powder leaving) | Free, no key |
| Binance public | `scripts/binance.py` | `/fapi/v1/premiumIndex`, `/fapi/v1/forceOrders`, `/futures/data/topLongShortPositionRatio` | #2 | `funding_flip_divergence`, `sentiment_extreme_greed_fade` | Free, no key |
| OKX public | `scripts/okx.py` | `/api/v5/public/funding-rate` | #2 | `funding_flip_divergence` | Free, no key |
| FRED | `scripts/fred.py` | `DGS10`, `DFII10`, `M2SL`, `T10Y2Y` | #4 | `catalyst_driven_breakdown` (macro alignment) | Free, API key already in `.env` |
| yfinance | `scripts/yfinance.py` | `DX=F`, `^GSPC`, `^VIX`, `GC=F` | #4 | `catalyst_driven_breakdown` | Free, no key |
| Coinbase candles | `scripts/candles.py` | public `/products/BTC-USD/candles` daily/weekly/monthly + derived ATR + S/R | #5 | all setups (sell-trigger + re-entry levels) | Free, no key |

### 3.3 Handled by routine LLM WebSearch (no wrapper)

| Signal | Query the routine issues | Why not a wrapper |
|---|---|---|
| Economic calendar (next 5 days) | "US economic calendar next 5 days FOMC CPI NFP" | 1–3 events/week; free; no vendor to wire. |
| Spot BTC ETF aggregate net flow (last 24h) | "Spot BTC ETF aggregate net flow last 24 hours USD" | Not load-bearing for any of the 4 setup types (see note below); avoids a fragile HTML scrape. |
| Unscheduled news scan | "BTC-specific news last 24h regulation SEC ETF exchange failure" | Detection-only signal per §7.1 mitigation path. |

**ETF flow note:** review of [TRADING-STRATEGY.md §3](../memory/TRADING-STRATEGY.md#3-step-out-setup-types) shows
no setup's primary trigger is ETF flow — `catalyst_driven_breakdown` keys
on scheduled macro catalyst + consolidation floor + funding, `sentiment_extreme_greed_fade`
on F&G ≥ 80 + funding + weekly resistance, `funding_flip_divergence` on
funding + OI, `onchain_distribution_top` on exchange *inflow* + stablecoin
supply + range-extension. ETF flow is contextual (sustained outflows
strengthen any step-out thesis, sustained inflows weaken it) but never
entry-triggering. WebSearch precision is sufficient.

### 3.4 Deferred (no value for v2 at current equity)

| Source | Why deferred |
|---|---|
| mempool.space fees | Doesn't feed any of the 4 setups load-bearingly. |
| Coin Metrics exchange flows | Chartinspect substitute — only needed if whale-flows proxy proves insufficient. |
| X/Twitter pro-tier | Overlaps YouTube; v2 trigger in §7.1. |
| Reddit PRAW | v2 trigger in §7.1. |
| News RSS (The Block, CoinDesk) | v2 trigger in §7.1. |
| Per-issuer ETF flows | Aggregate is sufficient for the rubric; per-issuer is research nice-to-have. |
| Chartinspect ETF / exchange-balances / dominance endpoints | Frozen data — Phase 1 ticket with vendor; don't rebuild around them. |

---

## 4. Pipeline architecture — the composer pattern

```
┌────────────────────────────────────────────────────────────┐
│  routines/research-and-plan.md  (the LLM-driven routine)   │
└────────────────────────┬───────────────────────────────────┘
                         │ one call, returns merged JSON
                         ▼
┌────────────────────────────────────────────────────────────┐
│  bash scripts/research.sh collect                          │
│    (parallel fan-out — was a stub in v1)                   │
└────────────────────────┬───────────────────────────────────┘
                         │ runs in parallel via `&` + `wait`
      ┌──────────────────┴────────────────────────────────┐
      │                                                   │
      ▼                                                   ▼
 existing wrappers                              new wrappers (Phase 1)
  chartinspect.py funding-rates                  fng.py latest
  chartinspect.py open-interest                  coingecko.py global
  chartinspect.py whale-flows                    defillama.py supply
  youtube.py titles                              binance.py funding|liq|lsr
  youtube.py velocity                            okx.py funding
  coinbase.py quote BTC-USD                      fred.py rates
                                                 yfinance.py quotes
                                                 candles.py daily+weekly+monthly

      └──────────────────┬────────────────────────────────┘
                         │ each wrapper → JSON to stdout
                         ▼
            merged into one JSON payload
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  Routine LLM:                                              │
│   - scores the 5-point rubric from the numeric payload     │
│   - reads YouTube titles as raw text for sentiment         │
│   - WebSearch for: calendar, ETF aggregate flow,           │
│     unscheduled-news scan (see §3.3)                       │
│   - writes memory/research-reports/YYYY-MM-DD-HH.json      │
│   - appends memory/RESEARCH-LOG.md                         │
└────────────────────────────────────────────────────────────┘
```

**Key properties:**

- **One shell command, one JSON.** The routine doesn't call 14 wrappers; it
  calls `research.sh collect` once. Wrappers stay independently testable.
- **Failure isolation.** If `fred.py` fails, its slice is `null` in the
  merged JSON. The routine is instructed to score conservatively
  (lean toward `skip`) when rubric-load-bearing slots are null.
- **No Python orchestrator.** Each wrapper is a standalone CLI following the
  existing pattern: argparse, JSON to stdout, exit codes `0/1/2/3`.
- **Synthesis is prompt-level.** The LLM in the routine receives the merged
  JSON as context and produces rubric scores + trade ideas. No separate
  OpenRouter call. No `synthesize.py`.

---

## 5. The swing rubric — unchanged from v1 §5

Still 5 points:
1. Clear catalyst in next 1–5 days
2. Sentiment extreme OR divergence
3. On-chain / market structure confirmation
4. Macro aligned
5. Technical level (HTF S/R)

Grade → size:
- 5/5 → A-grade: 1.0% risk
- 3–4/5 → B-grade: 0.5% risk
- <3 → skip
- Catalyst=false caps at B regardless

The rubric binds to live data in §3. Each rubric item lists which §3
sources populate it:

| Rubric | Primary sources | Fallback |
|---|---|---|
| #1 catalyst | LLM WebSearch (calendar query in §3.3) | — |
| #2 sentiment | `fng.py`, `chartinspect.py funding-rates`, `binance.py funding+liq+lsr`, `okx.py funding`, `chartinspect.py open-interest`, `youtube.py titles+velocity` | Any single source missing → score from remaining signals |
| #3 structure | `coingecko.py global`, `chartinspect.py whale-flows`, `defillama.py supply`, LLM WebSearch (ETF aggregate flow in §3.3) | Any single source missing → score from remaining signals |
| #4 macro | `fred.py`, `yfinance.py` | Both missing → item scored false conservatively |
| #5 technical | `coinbase.py quote`, `candles.py daily+weekly+monthly` | `candles.py` missing → item scored false (no entry without HTF level) |

---

## 6. Routine cadence — mostly unchanged from v1 §6

| Routine | Schedule (UTC) | Job |
|---|---|---|
| research-and-plan | 00:00 and 12:00 daily | `research.sh collect`, LLM scores rubric, writes report |
| execute | 00:30 and 12:30 daily | Re-validate top idea, place **paired** sell-trigger + re-entry limit (one cycle) |
| manage | Every 4h | Cycle lifecycle: detect sell-trigger fills, enforce 72h re-entry cap, weekend defense per [TRADING-STRATEGY §2 rule 19](../memory/TRADING-STRATEGY.md#2-hard-rules-non-negotiable) |
| panic-check | Hourly | Active-cycle BTC-loss breach (≥1.5R), BTC-stack drawdown halt (≥15%), 5xx abort, stablecoin de-peg |
| daily-summary | 23:30 UTC | 24h BTC-delta snapshot + USD-reserve state |
| weekly-review | Sunday 00:00 UTC | Grade A–F vs HODL (0% BTC growth) |

Only change: the `research-and-plan` prompt is updated to call
`research.sh collect` once instead of the current multi-WebSearch loop, and
to score the rubric from the merged JSON plus the three §3.3 WebSearch
queries (calendar, ETF aggregate flow, unscheduled-news scan).

---

## 7. Hard problems flagged

### 7.1 Unscheduled-catalyst blindspot — carried from v1 §7.1

The numeric stack still can't detect unscheduled news (SEC action, ETF
surprise, exchange failure, regulatory shock). Mitigation unchanged: the
*reactions* (funding flip, OI spike, liquidation spike, price gap) are all
observable — the routine tags "news-driven regime" when these fire without
a scheduled catalyst and pauses new entries until the next window.

**v2 text-layer trigger** — re-add deferred text sources (News RSS first,
then X/Twitter) if weekly-review logs >3 losses/quarter attributable to
missed unscheduled catalysts.

### 7.2 Backtestability — worse than v1, and that's accepted

v1 claimed deterministic rubric scoring in Python, making the pipeline
backtestable against historical data. v2 puts the scorer inside an LLM
prompt, which is not deterministically reproducible over history. **This is
the main trade v2 makes.**

Mitigation path:
- Forward-test is primary validation — 4–6 weeks shadow before cutover.
- Numeric inputs themselves are still historically available. If forward
  tests flag the LLM-scorer as inconsistent, a cheap fallback is a
  deterministic Python rubric scorer operating on the same merged JSON
  (the LLM would then only produce the narrative thesis). That's a
  30-line function — don't build it preemptively.

### 7.3 No HTML scrapers

v2 has zero HTML-parsing wrappers. The one source that would have required
scraping (Farside for aggregate ETF flow) is handled by the routine's
WebSearch call in §3.3. If the LLM cannot find a recent figure, ETF flow
degrades to `null` in `numeric_context` and the rubric's #3 item is scored
from the remaining sources (CoinGecko, Chartinspect whale-flows, DeFiLlama).

---

## 8. Output contract — unchanged from v1 §8

Same two artifacts:

1. `memory/research-reports/YYYY-MM-DD-HH.json` — machine-readable
2. `memory/RESEARCH-LOG.md` — append-only human-readable

JSON schema stays the v1 §8.1 shape (ts, bias, confidence, rubric,
numeric_context, catalysts, trade_ideas, sources).

One schema addition:

```json
"data_health": {
  "fetched_at": "2026-04-24T12:00:00Z",
  "missing_slots": ["fred", "defillama"],  // which wrappers returned null
  "websearch_gaps": ["etf_flow"],          // which §3.3 queries returned no recent figure
  "stale_warnings": []
}
```

The execute routine reads `data_health` and degrades to skip if a
rubric-load-bearing slot is missing (see §5 fallback column).

**`trade_ideas[].playbook_setup` must be one of the four step-out tags in
[TRADING-STRATEGY §3](../memory/TRADING-STRATEGY.md#3-step-out-setup-types):**
`catalyst_driven_breakdown`, `sentiment_extreme_greed_fade`,
`funding_flip_divergence`, `onchain_distribution_top`. Any other tag is a
schema error and the report is rejected by the execute routine.

**`trade_ideas[]` field renames for step-out semantics:**

| v1 field | v2 field | Notes |
|---|---|---|
| `entry` | `sell_trigger_price` | Technical breakdown level where the `STOP_LIMIT` sell fires |
| `stop` | *(removed)* | No hard stop — the protective action *is* the sell-trigger |
| `target` | `rebuy_limit_price` | Technical support where the paired `LIMIT` buy sits |
| — | `worst_case_rebuy_price` | Estimated fill price of the 72h time-capped market buy; feeds the §2 rule 8 sizing formula and the §2 rule 16 R:R check |

The schema otherwise remains the v1 §8.1 shape.

---

## 9. Order of work

**Phase 1 — finish the collector set (~1–2 weeks).** Build wrappers
easiest-first so the composer sees partial functionality early.

1. `scripts/fng.py` — one GET, no key. Half a day.
2. `scripts/coingecko.py` — one GET to `/global`. Half a day.
3. `scripts/defillama.py` — one GET. Half a day.
4. `scripts/fred.py` — 4 series via API key. One day (includes caching — series change daily, not per-fetch).
5. `scripts/yfinance.py` — 4 tickers. Half a day.
6. `scripts/binance.py` — 3 subcommands (funding, liquidations, long/short). One day.
7. `scripts/okx.py` — one subcommand. Half a day.
8. `scripts/candles.py` — Coinbase candles for daily/weekly/monthly, plus ATR and HTF S/R derivation. **Two days** — S/R rule is where judgment lives.

**Phase 2 — composer (~2 days).** Rebuild `scripts/research.sh` from the
exit-3 stub into a parallel aggregator. Use bash `&` + `wait` and merge
stdouts with `jq`. Subcommand: `research.sh collect`. Keep the wrapper
signature so other routines can still invoke with a query string if ever
needed (no-op in v2).

**Phase 3 — routine integration (~2 days).** Update
[routines/research-and-plan.md](../routines/research-and-plan.md) and
[.claude/commands/research.md](../.claude/commands/research.md):
- Replace STEP 3's multi-WebSearch loop with one `bash scripts/research.sh collect` call.
- STEP 3a: the three §3.3 WebSearch queries (calendar, ETF aggregate flow, unscheduled-news scan).
- STEP 4: score the rubric from the merged JSON payload + WebSearch results.
- STEP 5: emit trade ideas using the step-out schema (`sell_trigger_price`, `rebuy_limit_price`, `worst_case_rebuy_price`, `playbook_setup` ∈ the four step-out tags).
- Everything else stays.

**Phase 4 — forward-test (4–6 weeks).** Pipeline runs in shadow mode —
writes reports, but `execute` still uses the current path. Compare:
- Rubric scores against manual review of each window
- Trade ideas against what a human would have taken
- Missing-slot frequency per wrapper (catches flaky sources early)

**Phase 5 — cutover.** `execute` consumes the new JSON. Retire the v1
multi-WebSearch loop. Keep WebSearch only for the three §3.3 queries.

Total: **~2 weeks build + 4–6 weeks shadow** (8 wrappers + composer + routine integration).

---

## 10. Open decisions (revisit before Phase 1 or during)

- [ ] `candles.py` S/R derivation: rule-based (swing highs/lows, N-bar
      fractal) vs. hand the raw OHLC to the LLM and let it pick. **Lean
      rule-based** — "weekly swing low" is well-defined and deterministic.
- [ ] ATR formula: classic Wilder 14-period on daily close, or simpler 14d
      average high-low range? **Lean Wilder** (standard).
- [ ] Aggregator concurrency: bash `&`+`wait` vs a small Python driver.
      **Lean bash** to stay inside the existing pattern.
- [ ] YouTube channel set: 6 channels hardcoded in [youtube.py](scripts/youtube.py).
      Re-eval after 4 weeks of forward-test; drop dead channels, add any
      the LLM cites repeatedly as high-signal in weekly reviews.
- [ ] FRED polling: macro series change daily or weekly — cache in a
      simple file with TTL, or re-fetch every window? **Lean re-fetch** —
      simplicity wins; 4 requests/run is nothing.
- [ ] Chartinspect support ticket: request unfreeze on `exchange-balances`,
      `etf-balances`, `btc-dominance`, `stablecoin-dominance`. If they
      unfreeze before cutover, revisit whether DeFiLlama stays or the
      ETF-flow WebSearch moves to a Chartinspect wrapper. Not load-bearing
      either way.
- [ ] ETF-flow WebSearch precision: after 4 weeks of forward-test, review
      whether the LLM consistently finds aggregate ETF net flow from the
      §3.3 query. If gaps exceed ~20% of windows, revisit with a named
      source (CoinGlass free tier, Blockworks, etc.) — still API or
      read-only JSON, not a scraper.

---

## 11. Why this redesign

1. **Every source is free or already subscribed.** Chartinspect Pro stays
   because 3 endpoints still work. No new vendor costs. LLM synthesis moves
   from a dedicated OpenRouter call back into the routine's existing
   context, eliminating a billing line.

2. **Pay-their-way filter applied ruthlessly.** Every §3 source feeds at
   least one rubric slot AND at least one of the 4 playbook setups. Things
   that didn't clear that bar — per-issuer ETF flows, mempool fees,
   long/short ratio alone, stale Chartinspect endpoints — are cut or
   deferred with explicit triggers.

3. **Matches the existing codebase pattern.** The project already has
   [chartinspect.py](scripts/chartinspect.py), [coinbase.py](scripts/coinbase.py),
   and [youtube.py](scripts/youtube.py) as standalone CLI wrappers.
   v2 adds 8 more in the same style rather than inventing a `scripts/research/`
   package that would need its own abstractions. Zero HTML scrapers — every
   wrapper hits a JSON API.

4. **Ships incrementally.** Each Phase 1 wrapper is independently useful.
   Even before the composer lands, the routine can call individual wrappers
   manually and fold their outputs into WebSearch-based synthesis.

5. **Accepts the backtestability trade** (§7.2) in exchange for not
   building a parallel synthesis layer. If forward-testing shows that trade
   was wrong, the escape hatch (deterministic Python scorer over the same
   JSON payload) is a 30-line function.

---

## 12. Cross-reference

- **Strategy rulebook:** [memory/TRADING-STRATEGY.md](../memory/TRADING-STRATEGY.md)
- **Per-datapoint status:** [RESEARCH-DATA-STATUS.md](RESEARCH-DATA-STATUS.md)
- **Per-datapoint cadence:** [RESEARCH-DATAPOINTS.md](RESEARCH-DATAPOINTS.md)
- **Alternatives parking lot:** [RESEARCH-DATA-ALTERNATIVES.md](RESEARCH-DATA-ALTERNATIVES.md) — CDP, in-house build, hybrid
- **v1 (superseded):** [RESEARCH-AGENT-DESIGN.md](RESEARCH-AGENT-DESIGN.md)
