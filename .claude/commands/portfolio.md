---
description: Read-only snapshot of account, position, open orders, and BTC quote
---

Print a clean ad-hoc snapshot. No state changes, no orders, no file writes.

1. python scripts/coinbase.py account
2. python scripts/coinbase.py position
3. python scripts/coinbase.py orders
4. python scripts/coinbase.py quote BTC-USD

Format as a single concise summary:

Portfolio — <today UTC>
Equity: $X | USD: $X | BTC: N.NNNN ($X)
Stack state: BTC by value X.X% | USD reserve X.X% (target 10-20%)
Active cycle: [none | Phase A/B/C/D, sell-trigger $X, rebuy $Y, cap <UTC>]

Open orders:
| TYPE | SIDE | size | stop/limit | status | order_id |

No commentary unless something is broken: a lone sell-trigger, a lone re-entry,
ACTIVE_CYCLE mismatched with live orders, or USD reserve outside target.
