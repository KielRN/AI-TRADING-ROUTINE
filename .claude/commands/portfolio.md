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
Position: [none | entry $X, current $X, unrealized ±X% (±X.XR), stop $X]

Open orders:
| TYPE | SIDE | size | stop/limit | order_id |

No commentary unless something is broken (open position without a stop, or
a stop above current price for a long).
