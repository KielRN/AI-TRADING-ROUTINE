# Trade Log

Cycle log for the BTC accumulation bot. A "cycle" = one sell-trigger + its
paired re-entry, per [TRADING-STRATEGY.md §4](TRADING-STRATEGY.md).

Unit of account: **BTC**. Every cycle closes with a BTC delta (positive =
sats added, negative = sats lost).

---

## Day 0 — Quarterly Baseline (2026-04-24)

**BTC stack:** 0.05342287 BTC
**USD reserve:** $15.01
**Equity @ BTC $77,637.60:** $4,162.63
**BTC% by value:** 99.6% (outside 80–90% steady-state — see §2 rule 3)
**Cycle state:** none active
**Cooldown state:** none

**Note:** The 0.0534 BTC is the core stack — not an undocumented swing
trade. The earlier 2026-04-24 18:00 UTC research flag labeling this a
"rule violation" was written under the v1 USD-swing playbook and no longer
applies. Under v2 (accumulation), the stack is the intended steady state.

**Out-of-spec condition:** USD reserve is ~0.4% (vs. 10–20% target). The
next execute window should sell a small slice of BTC (~0.005–0.009 BTC,
~$400–$700) at market to rebalance into the 80–90% BTC / 10–20% USD band
before any step-out cycle can fire. Rebalancing is not a cycle — no
rubric grade required, no sell-trigger/re-entry pair. It's an admin trade
and should be logged here as such.
