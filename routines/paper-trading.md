You are running the two-week paper trading workflow. SPOT BTC/USD ONLY.
Ultra-concise. This routine simulates v2 cycles and MUST NOT place live orders.

Resolve timestamps via:
DATE=$(date -u +%Y-%m-%d)
NOW_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)

IMPORTANT - PAPER MODE ONLY:
- Do not call live order-producing Coinbase commands:
  `buy`, `sell`, `stop`, `limit-buy`, `cancel`, `cancel-all`, or `close`.
- Read-only Coinbase calls are allowed:
  `account`, `position`, `quote`, `orders`, `order`, and `fills`.
- Paper state is `memory/paper-trading/state.json`.
- Paper wrapper is `python scripts/paper_trade.py`.
- Live state `memory/state.json` must not be modified by this workflow.

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

STEP 3 - Initialize if not started:
- If `status=not_started`, pull read-only account and quote:
    python scripts/coinbase.py account
    python scripts/coinbase.py quote BTC-USD
- Initialize with the live BTC balance, USD balance, and BTC spot:
    python scripts/paper_trade.py init \
      --starting-btc <btc_balance> \
      --starting-usd <usd_balance> \
      --btc-price <spot_price>
- The campaign runs exactly 14 days from initialization.

STEP 4 - Pull current quote:
python scripts/coinbase.py quote BTC-USD

STEP 5 - Advance paper lifecycle:
python scripts/paper_trade.py tick --bid <bid> --ask <ask>

This may fill a paper sell-trigger, fill a paper re-entry, force a 72h
time-cap paper market-buy, close any remaining paper exposure at the 14-day
boundary, or mark the campaign complete.

STEP 6 - Consider a new paper cycle only if:
- Campaign status is active.
- No active paper cycle exists.
- Latest v2 research report is fresh enough for execute.
- Trade idea is grade A or B.
- Trade idea uses a v2 setup:
  catalyst_driven_breakdown, sentiment_extreme_greed_fade,
  funding_flip_divergence, onchain_distribution_top.
- The normal v2 execute checklist passes.
- The 72h paper time-cap window can fit before the campaign end.

If all pass, open paper cycle only:
python scripts/paper_trade.py open-cycle \
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

STEP 7 - Summarize:
python scripts/paper_trade.py summary

Report:
- paper campaign day N/14
- status active/complete
- active paper cycle phase or none
- cycles opened/closed
- BTC-equivalent delta versus start
- any blocked trade idea reason

STEP 8 - Persist:
If `memory/paper-trading/state.json` changed:
  git add memory/paper-trading/state.json
  git commit -m "paper trading $DATE"
  git push origin main

Never force-push.
