---
description: Manual trade helper with playbook-rule validation. Usage — /trade --usd SIZE --stop PRICE --target PRICE
---

Execute a manual BTC spot buy with full rule validation. Refuse if any rule fails.

Args: --usd <amount> --stop <price> [--target <price>] [--playbook <setup>]
If missing, ask.

1. Pull state: account, position, quote BTC-USD (capture best ask = entry P).
2. Validate buy-side gate (EVALUATION-COINBASE-BTC.md §2 + §3):
   □ Current BTC position is 0
   □ Entries in rolling 7d + 1 ≤ 2 (check TRADE-LOG tail)
   □ SIZE_USD × (P - stop)/P ≤ 1.0% × equity (max risk)
   □ stop ≥ 0.5% below entry
   □ target ≥ 2R from entry
   □ playbook setup named (ask if missing)
   □ No cooldown in effect
   □ DRAWDOWN_HALT != true
   If any fail, STOP and print the failed checks.
3. Print order JSON + validation results, ask "execute? (y/n)".
4. On confirm:
   python scripts/coinbase.py buy --usd <size>
   Poll for fill. Compute base_size from fill price.
   python scripts/coinbase.py stop --base <base_size> --stop-price <stop> --limit <stop*0.995>
5. Log to memory/TRADE-LOG.md with full thesis, entry, stop, target, R:R.
6. bash scripts/telegram.sh "[TRADE manual] ..."
