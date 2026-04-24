# Research Pipeline — Data Source Status

**Last updated:** 2026-04-23  
**Legend:** ✅ confirmed live | ⚠️ stale/partial | ❌ missing — no source yet | 🔍 candidate under eval

---

## Rubric #1 — Catalyst

| Datapoint | Status | Source | Notes |
|---|---|---|---|
| US economic calendar (FOMC, CPI, PCE, NFP, etc.) | ❌ | TradingEconomics | Not yet tested |
| BTC-specific events (ETF decisions, CME expiry, token unlocks) | ❌ | TradingEconomics | Not yet tested |

---

## Rubric #2 — Sentiment

| Datapoint | Status | Source | Notes |
|---|---|---|---|
| Funding rate — aggregated | ✅ | ChartInspect `GET /derivatives/futures_funding_rates` → `Funding_Rate_ve` | Hourly; confirmed live 2026-04-23 |
| Funding rate — Binance | ❌ | 🔍 Binance public `GET /fapi/v1/premiumIndex?symbol=BTCUSDT` | No key required; not yet tested |
| Funding rate — OKX | ❌ | 🔍 OKX public `GET /api/v5/public/funding-rate?instId=BTC-USD-SWAP` | No key required; not yet tested |
| Open interest — aggregated | ✅ | ChartInspect `GET /derivatives/futures_open_interest` → `Aggregate_Total` | Daily; $60.8B on 2026-04-23 |
| Open interest — Binance | ✅ | ChartInspect same endpoint → `Binance` | $10.5B on 2026-04-23 |
| Open interest — OKX | ✅ | ChartInspect same endpoint → `OKX` | $3.6B on 2026-04-23 |
| Open interest — Bybit | ✅ | ChartInspect same endpoint → `Bybit` | $4.8B on 2026-04-23 |
| Open interest — CME | ✅ | ChartInspect same endpoint → `CME` | $10.1B on 2026-04-23 |
| Liquidations — 24h long/short USD | ❌ | 🔍 Binance public `GET /fapi/v1/forceOrders?symbol=BTCUSDT` | Binance-only; no key required; not yet tested |
| Long/short ratio — top traders | ❌ | 🔍 Binance public `GET /futures/data/topLongShortPositionRatio?symbol=BTCUSDT&period=1h` | No key required; not yet tested |
| Fear & Greed index (0–100) | ❌ | alternative.me `GET https://api.alternative.me/fng/` | Free, no key; not yet tested |
| YouTube video titles (last 5/channel) | ✅ | YouTube Data API v3 via `scripts/youtube.py titles` | Confirmed live 2026-04-24. YOUTUBE_API_KEY in .env. |
| YouTube upload velocity (48h) | ✅ | YouTube Data API v3 via `scripts/youtube.py velocity` | Same key; confirmed live 2026-04-24. |

---

## Rubric #3 — On-chain / Market Structure

| Datapoint | Status | Source | Notes |
|---|---|---|---|
| BTC exchange net flow — 1d USD | ⚠️ | ChartInspect `GET /exchange-etf/exchange-balances` | **Data frozen at 2026-02-04** (79 days stale). 1d delta must be derived. Support ticket needed. |
| BTC exchange net flow — 7d USD | ⚠️ | ChartInspect same endpoint | Same staleness; 7d delta also derived |
| BTC exchange balance (total BTC on exchanges) | ⚠️ | ChartInspect same endpoint → `allexchanges` | Same staleness |
| Whale wallet movement — 1,000+ BTC, 7d net | ✅ | ChartInspect `GET /onchain/balance-distribution-flows` → `flow_1kto10kbtc` + `flow_above10kbtc` | Daily; current to 2026-04-22. Proxy covers 1k–10k and 10k+ BTC cohorts. |
| Stablecoin total supply — USDT + USDC | ❌ | 🔍 DeFiLlama `GET https://stablecoins.llama.fi/stablecoins` | Free, no key; returns circulating supply per stablecoin; not yet tested |
| Stablecoin supply change — 7d delta | ❌ | 🔍 DeFiLlama same endpoint | 7d change may be derivable from history; not yet tested |
| BTC spot ETF net flow — aggregate USD | ⚠️ | ChartInspect `GET /exchange-etf/etf-balances` | **Data frozen at 2026-02-04.** Returns BTC holdings (not USD flow); delta must be derived. |
| BTC spot ETF net flow — IBIT | ⚠️ | ChartInspect same → `blackrock_ibit` | Same staleness |
| BTC spot ETF net flow — FBTC | ⚠️ | ChartInspect same → `fidelity_fbtc` | Same staleness |
| BTC spot ETF net flow — ARKB | ⚠️ | ChartInspect same → `ark_invest_arkb` | Same staleness |
| BTC spot ETF net flow — BITB | ⚠️ | ChartInspect same → `bitwise_bitb` | Same staleness |
| BTC spot ETF net flow — BRRR | ⚠️ | ChartInspect same → `valkyrie_brrr` | Same staleness |
| BTC spot ETF net flow — EZBC | ⚠️ | ChartInspect same → `franklin_templeton_ezbc` | Same staleness |
| BTC spot ETF net flow — HODL | ⚠️ | ChartInspect same → `vaneck_hodl` | Same staleness |
| BTC spot ETF net flow — BTCO | ⚠️ | ChartInspect same → `invesco_btco` | Same staleness |
| BTC spot ETF net flow — BTCW | ⚠️ | ChartInspect same → `wisdomtree_btcw` | Same staleness |
| BTC spot ETF net flow — GBTC | ⚠️ | ChartInspect same → `grayscale_gbtc` | Same staleness |
| BTC dominance (%) | ⚠️ | ChartInspect `GET /market-indicators/btc-dominance` | **Data frozen at 2025-11-24** (5 months stale). Use CoinGecko instead (see below). |
| Total crypto market cap (USD) | ❌ | 🔍 CoinGecko `GET /api/v3/global` → `total_market_cap.usd` | Free; 30 req/min; not yet tested |
| Stablecoin dominance (%) | ⚠️ | ChartInspect `GET /market-indicators/stablecoin-dominance` | **Data frozen at 2025-11-24.** Use CoinGecko `/global` instead. |
| Mempool size / median fee (sat/vB) | ❌ | 🔍 mempool.space `GET https://mempool.space/api/v1/fees/recommended` | Free, no key; not yet tested |

---

## Rubric #4 — Macro

| Datapoint | Status | Source | Notes |
|---|---|---|---|
| DXY | ❌ | yfinance (`DX=F`) | Not yet tested |
| SPX | ❌ | yfinance (`^GSPC`) | Not yet tested |
| VIX | ❌ | yfinance (`^VIX`) | Not yet tested |
| Gold futures | ❌ | yfinance (`GC=F`) | Not yet tested |
| 10Y Treasury yield | ❌ | FRED API (`DGS10`) | API key in .env; not yet tested |
| 10Y real yield (TIPS) | ❌ | FRED API (`DFII10`) | Not yet tested |
| M2 money supply | ❌ | FRED API (`M2SL`) | Not yet tested |
| 2Y/10Y yield spread | ❌ | FRED API (`T10Y2Y`) | Not yet tested |

---

## Rubric #5 — Technical

| Datapoint | Status | Source | Notes |
|---|---|---|---|
| BTC-USD last trade | ❌ | Coinbase public ticker | Uses existing `scripts/coinbase.py`; not yet wired to research pipeline |
| BTC-USD 24h volume | ❌ | Coinbase public | Same |
| Daily OHLC — trailing 90 days | ❌ | Coinbase / Binance public candles | Not yet tested |
| Weekly OHLC — trailing 52 weeks | ❌ | Coinbase / Binance public candles | Not yet tested |
| Monthly OHLC — trailing 24 months | ❌ | Coinbase / Binance public candles | Not yet tested |
| 1-day ATR | ❌ | Derived from daily OHLC | Computed locally; depends on candle fetch |
| Weekly S/R levels | ❌ | Derived from weekly OHLC | Same |
| Monthly S/R levels | ❌ | Derived from monthly OHLC | Same |

---

## Open Issues

| # | Issue | Action |
|---|---|---|
| 1 | ChartInspect `exchange-balances` + `etf-balances` frozen at 2026-02-04 | **Contact ChartInspect support.** If not fixed, replace with DeFiLlama (stablecoins) and Farside scrape (ETF). |
| 2 | ChartInspect `btc-dominance` + `stablecoin-dominance` frozen at 2025-11-24 | Replace with CoinGecko `/api/v3/global` — free, live, covers both. |
| 3 | No liquidation or long/short data from ChartInspect | Test Binance public futures endpoints (no key needed). |
| 4 | Per-exchange funding rates (Binance, OKX) not in ChartInspect | Test Binance + OKX public endpoints (no key needed). |
| 5 | All Rubric #4 macro sources untested | Test yfinance + FRED in next session. |
| 6 | All Rubric #5 technical candle sources untested | Test Coinbase / Binance public candle endpoints in next session. |
| 7 | TradingEconomics (Rubric #1) untested | Requires API key — check if we have one; test in next session. |
| 8 | YouTube API key missing | YouTube Data API v3 **already enabled**. Create API key in GCP Credentials → add YOUTUBE_API_KEY to .env |
