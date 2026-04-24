# Research Pipeline — Datapoints & Collection Times

**Prepared:** 2026-04-23 (v1.1 single-vendor — derived from RESEARCH-AGENT-DESIGN.md §2.1, §5, §8.1)
**Status:** Reference for building `scripts/research/sources/*.py` collectors.

Pipeline runs **twice daily at 00:00 UTC and 12:00 UTC** (see RESEARCH-AGENT-DESIGN.md §6). Every datapoint below is fetched at both windows unless otherwise noted.

- **Native cadence** = how often the upstream source updates.
- **Fetch** = when our pipeline pulls it.

---

## Rubric #1 — Catalyst (scheduled events)

| Datapoint | Source | Native cadence | Fetch |
|---|---|---|---|
| US economic calendar — FOMC, CPI, PCE, NFP, unemployment, retail sales, GDP, PPI (next 5 days) | TradingEconomics | Daily refresh; events scheduled weeks out | 00:00, 12:00 UTC |
| Known BTC-specific events — ETF decisions, CME contract expiries, token unlocks | TradingEconomics + manual | As announced | 00:00, 12:00 UTC |

---

## Rubric #2 — Sentiment

| Datapoint | Source | Native cadence | Fetch |
|---|---|---|---|
| Funding rate — BTC perp, aggregated | Chartinspect (derivatives) | Every 8h (funding settlement) | 00:00, 12:00 UTC |
| Funding rate — Binance BTC perp | Chartinspect (derivatives) | Every 8h | 00:00, 12:00 UTC |
| Funding rate — OKX BTC perp | Chartinspect (derivatives) | Every 8h | 00:00, 12:00 UTC |
| Open interest — BTC perp USD, aggregated | Chartinspect (derivatives) | 10-min | 00:00, 12:00 UTC |
| Open interest — per venue (Binance, OKX, Bybit, CME) | Chartinspect (derivatives) | 10-min | 00:00, 12:00 UTC |
| Liquidations — 24h long/short USD | Chartinspect (derivatives) | Real-time; 24h aggregate | 00:00, 12:00 UTC |
| Long/short ratio — top traders | Chartinspect (derivatives) | Hourly | 00:00, 12:00 UTC |
| Fear & Greed index (0–100) | alternative.me | Daily at 00:00 UTC | 00:00, 12:00 UTC |
| YouTube video titles (last 5/channel) — Benjamin Cowen, Coin Bureau, InvestAnswers, Crypto Banter, Plan B, Raoul Pal | YouTube Data API v3 (enabled) | Per video upload | 00:00, 12:00 UTC |
| YouTube upload velocity — videos posted in last 48h across channels | YouTube Data API v3 | Per video upload | 00:00, 12:00 UTC |

---

## Rubric #3 — On-chain / market structure

| Datapoint | Source | Native cadence | Fetch |
|---|---|---|---|
| BTC exchange net flow — 1d USD | Chartinspect (on-chain) | 10-min | 00:00, 12:00 UTC |
| BTC exchange net flow — 7d USD | Chartinspect (on-chain) | 10-min | 00:00, 12:00 UTC |
| BTC exchange balance (total held on exchanges) | Chartinspect (on-chain) | 10-min | 00:00, 12:00 UTC |
| Whale wallet movement — 1,000+ BTC addresses, 7d net | Chartinspect (on-chain) | Hourly | 00:00, 12:00 UTC |
| Stablecoin total supply — USDT + USDC | Chartinspect (on-chain) | Hourly | 00:00, 12:00 UTC |
| Stablecoin supply change — 7d delta | Chartinspect (on-chain) | Hourly | 00:00, 12:00 UTC |
| BTC spot ETF daily net flow — aggregate USD | Chartinspect (exchange-etf) | Daily after US close | 00:00 UTC primarily |
| BTC spot ETF daily net flow — per issuer (IBIT, FBTC, ARKB, BITB, BRRR, EZBC, HODL, BTCO, BTCW, GBTC) | Chartinspect (exchange-etf) | Daily after US close | 00:00 UTC primarily |
| BTC dominance (% of total crypto market cap) | CoinGecko | ~1-min | 00:00, 12:00 UTC |
| Total crypto market cap (USD) | CoinGecko | ~1-min | 00:00, 12:00 UTC |
| Stablecoin dominance (%) | CoinGecko | ~1-min | 00:00, 12:00 UTC |
| Mempool size / median fee (sat/vB) — optional | mempool.space | ~1-min | 00:00, 12:00 UTC |

---

## Rubric #4 — Macro

| Datapoint | Source | Native cadence | Fetch |
|---|---|---|---|
| DXY (US Dollar Index) | yfinance (`DX=F` / `^DXY`) | Real-time market hours | 00:00, 12:00 UTC |
| SPX (S&P 500 index) | yfinance (`^GSPC`) | Real-time market hours | 00:00, 12:00 UTC |
| VIX | yfinance (`^VIX`) | Real-time market hours | 00:00, 12:00 UTC |
| Gold futures | yfinance (`GC=F`) | Real-time market hours | 00:00, 12:00 UTC |
| 10Y Treasury yield (nominal) | FRED (`DGS10`) | Daily | 00:00, 12:00 UTC |
| 10Y real yield (TIPS) | FRED (`DFII10`) | Daily | 00:00, 12:00 UTC |
| M2 money supply | FRED (`M2SL`) | Weekly | 00:00, 12:00 UTC |
| 2Y / 10Y yield spread | FRED (`T10Y2Y`) | Daily | 00:00, 12:00 UTC |

---

## Rubric #5 — Technical

| Datapoint | Source | Native cadence | Fetch |
|---|---|---|---|
| BTC-USD spot — last trade | Coinbase public ticker | Real-time | 00:00, 12:00 UTC |
| BTC-USD 24h volume (USD) | Coinbase public | Real-time | 00:00, 12:00 UTC |
| BTC-USD daily OHLC — trailing 90 days | Coinbase / Binance public candles | Daily close | 00:00, 12:00 UTC |
| BTC-USD weekly OHLC — trailing 52 weeks | Coinbase / Binance public candles | Weekly close | 00:00 UTC Sunday |
| BTC-USD monthly OHLC — trailing 24 months | Coinbase / Binance public candles | Monthly close | 00:00 UTC month-start |
| 1-day ATR (for runner trail) | Derived from daily OHLC | Recomputed each fetch | 00:00, 12:00 UTC |
| Weekly S/R levels | Derived from weekly OHLC | Recomputed each fetch | 00:00, 12:00 UTC |
| Monthly S/R levels | Derived from monthly OHLC | Recomputed each fetch | 00:00, 12:00 UTC |

---

## Account state (not research — fetched every routine run)

| Datapoint | Source | Used by |
|---|---|---|
| Account equity (USD) | Coinbase Advanced Trade (`account`) | sizing, drawdown check |
| Open BTC position (size, entry, unrealized P&L) | Coinbase (`position`) | management, panic-check |
| Open orders (stops, limits) | Coinbase (`orders`) | management, panic-check |
| BTC-USD live quote | Coinbase (`quote`) | sizing, management |

---

## Summary — fetch budget per research window

At 00:00 UTC and 12:00 UTC, the pipeline issues roughly:

- **Chartinspect:** ~20 requests (derivatives + on-chain + ETF)
- **CoinGecko:** 1–2 requests
- **yfinance:** 4 requests (DXY, SPX, VIX, gold)
- **FRED:** 4 requests (DGS10, DFII10, M2SL, T10Y2Y)
- **alternative.me:** 1 request (F&G)
- **TradingEconomics:** 1 request (calendar)
- **mempool.space:** 1 request (optional)
- **Coinbase public:** 3–4 requests (ticker + candles)

≈ **35 fetches per window, 70/day total.** Well under every tier's rate limit (Chartinspect Pro is 1,000/hr).
