---
description: Run the two-week paper trading workflow
---

You are running the local paper trading workflow. It simulates the v2 BTC
accumulation cycle and MUST NOT place live Coinbase orders.

Research remains upstream. Do not generate trade ideas inside this command:
only act on a fresh `memory/research-reports/*.json` created by
research-and-plan.

Read:
- `PAPER-TRADING-TEST.md`
- `memory/TRADING-STRATEGY.md`
- `memory/paper-trading/state.json`
- Latest `memory/research-reports/*.json`

Allowed Coinbase calls are read-only: `account`, `position`, `quote`, `orders`,
`order`, `fills`.

Forbidden in this command: `buy`, `sell`, `stop`, `limit-buy`, `cancel`,
`cancel-all`, `close`.

Steps:
1. `python scripts/paper_trade.py validate`
2. Validate latest research freshness:
   `python scripts/research_gate.py latest --max-age-minutes 45`
   If this fails, continue only with quote + paper lifecycle tick + summary.
3. If not started, initialize from read-only `account` and `quote BTC-USD`:
   `python scripts/paper_trade.py init --starting-btc <btc> --starting-usd <usd> --btc-price <spot>`
4. Pull read-only quote and run:
   `python scripts/paper_trade.py tick --bid <bid> --ask <ask>`
   Local automation may use:
   `python scripts/paper_shadow.py --research-report memory/research-reports/YYYY-MM-DD-HH.json`
5. If latest v2 research has a fresh A/B idea that passes the execute
   checklist, verify it is actionable:
   `python scripts/research_gate.py latest --max-age-minutes 45 --require-trade-idea`
   Then open it in paper only:
   `python scripts/paper_trade.py open-cycle --research-report memory/research-reports/YYYY-MM-DD-HH.json --cycle-id paper-YYYYMMDD-HHMM --playbook-setup <setup> --grade <A|B> --btc-to-sell <btc> --sell-trigger-price <trigger> --rebuy-limit-price <rebuy> --worst-case-rebuy-price <worst_case> --current-price <spot>`
6. `python scripts/paper_trade.py summary`

Output concise status:
- campaign day N/14
- status
- active paper cycle phase or none
- cycles opened/closed
- BTC-equivalent delta versus start
- blocked idea reason, if any

Local command footer:
- Do not commit or push unless explicitly asked.
