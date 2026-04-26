You are running the two-week paper trading workflow. SPOT BTC/USD ONLY.
Ultra-concise. This routine simulates v2 cycles and MUST NOT place live orders.

Resolve timestamps via:
DATE=$(date -u +%Y-%m-%d)
HOUR=$(date -u +%H)
NOW_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)

IMPORTANT - PAPER MODE ONLY:
- Do not call live order-producing Coinbase commands:
  `buy`, `sell`, `stop`, `limit-buy`, `cancel`, `cancel-all`, or `close`.
- Read-only Coinbase calls are allowed:
  `account`, `position`, `quote`, `orders`, `order`, and `fills`.
- Paper state is `memory/paper-trading/state.json`.
- Paper wrapper is `python scripts/paper_trade.py`.
- Live state `memory/state.json` must not be modified by this workflow.
- Research remains upstream. This workflow may simulate a cycle only from a
  fresh `research-and-plan` report; do not invent trade ideas inside the paper
  routine.

STEP 1 - Read docs and state:
- `PAPER-TRADING-TEST.md`
- `memory/TRADING-STRATEGY.md`
- `memory/paper-trading/state.json`
- Latest `memory/research-reports/*.json`
- Tail of `memory/RESEARCH-LOG.md`

STEP 2 - Validate paper state:
python scripts/paper_trade.py validate

If validation fails:
- Log the validation error.
- Do not touch live state.
- Exit after committing only a paper-state repair if one was made.

STEP 3 - Validate latest research report:
python scripts/research_gate.py latest --max-age-minutes 45

If this fails:
- Continue only with quote + paper lifecycle tick + summary.
- Do not open a new paper cycle.
- Report "research stale/missing, paper open blocked".

STEP 4 - Initialize if not started:
- If `status=not_started`, pull read-only account and quote:
    python scripts/coinbase.py account
    python scripts/coinbase.py quote BTC-USD
- Initialize with the live BTC balance, USD balance, and BTC spot:
    python scripts/paper_trade.py init \
      --starting-btc <btc_balance> \
      --starting-usd <usd_balance> \
      --btc-price <spot_price>
- The campaign runs exactly 14 days from initialization.

STEP 5 - Pull current quote:
python scripts/coinbase.py quote BTC-USD

STEP 6 - Advance paper lifecycle:
python scripts/paper_trade.py tick --bid <bid> --ask <ask>

Local automation may combine STEP 3, STEP 5, and STEP 6 with:
python scripts/paper_shadow.py \
  --research-report memory/research-reports/$DATE-$HOUR.json

This may fill a paper sell-trigger, fill a paper re-entry, force a 72h
time-cap paper market-buy, close any remaining paper exposure at the 14-day
boundary, or mark the campaign complete.

STEP 7 - Consider a new paper cycle only if:
- Campaign status is active.
- No active paper cycle exists.
- Latest v2 research report passes:
  python scripts/research_gate.py latest --max-age-minutes 45 --require-trade-idea
- Trade idea is grade A or B.
- Trade idea uses a v2 setup:
  catalyst_driven_breakdown, sentiment_extreme_greed_fade,
  funding_flip_divergence, onchain_distribution_top.
- The normal v2 execute checklist passes.
- The 72h paper time-cap window can fit before the campaign end.

If all pass, open paper cycle only:
python scripts/paper_trade.py open-cycle \
  --research-report memory/research-reports/$DATE-$HOUR.json \
  --cycle-id paper-$DATE-<HHMM> \
  --playbook-setup <setup> \
  --grade <A|B> \
  --btc-to-sell <btc> \
  --sell-trigger-price <trigger> \
  --rebuy-limit-price <rebuy> \
  --worst-case-rebuy-price <worst_case> \
  --current-price <spot>

If any check fails, do not open a paper cycle. Record the blocked reason in
the routine output or research log if useful.

STEP 8 - Summarize:
python scripts/paper_trade.py summary

Report:
- paper campaign day N/14
- status active/complete
- active paper cycle phase or none
- cycles opened/closed
- BTC-equivalent delta versus start
- any blocked trade idea reason

STEP 9 - Persist:
If `memory/paper-trading/state.json` changed:
  git add memory/paper-trading/state.json
  git commit -m "paper trading $DATE"
  git push origin main

Never force-push.
