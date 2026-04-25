---
description: Disabled v1 manual trade helper
---

This helper is intentionally disabled under the v2 BTC-accumulation playbook.

Do not place manual v1 buy/stop/target trades from this command. The active
strategy is a BTC-denominated step-out cycle: `STOP_LIMIT` sell-trigger plus
paired `LIMIT` buy re-entry, governed by `memory/TRADING-STRATEGY.md` and
`research/RESEARCH-AGENT-DESIGN-V2.md`.

For live action, use the execute workflow after a fresh v2 research report. If
a manual v2 cycle helper is needed later, implement it as a new command that
validates the same cycle checklist as `routines/execute.md`.

