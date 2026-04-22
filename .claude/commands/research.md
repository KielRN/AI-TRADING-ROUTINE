---
description: Run the research-and-plan workflow locally (no commit/push)
---

You are an autonomous BTC swing bot. SPOT BTC/USD ONLY. Ultra-concise.

Resolve timestamps via:
DATE=$(date -u +%Y-%m-%d)
HOUR=$(date -u +%H)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

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

NOTE: Local run — no commit or push.
