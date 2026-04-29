# Cloud Routine Setup

This guide explains the environment that each Claude Code cloud routine runs
inside, why a setup script is required, and exactly what to paste into the
Claude Code Routines UI for the two routines this project uses.

## Why A Setup Script Is Needed

Every cloud routine run starts a fresh sandbox with an empty working
directory. The repo, the Python dependencies, and the git push credentials
do not survive between runs. The setup script is responsible for:

1. Cloning (or refreshing) this repo into the working directory.
2. Configuring a git identity and a tokenized push URL so the routine can
   commit memory updates back to GitHub at the end of each run.
3. Installing the Python dependencies the wrapper scripts need.

Without this script, every routine run will resume into an empty
`/home/user`, fail the very first wrapper call, and exit without touching
any memory file. That was the original failure mode that left
`memory/paper-trading/state.json` stuck on `not_started`.

## Setup Script

Paste this into the **Setup script** field of both routines in the Claude
Code Routines UI. Identical content for both — keeps the two environments
in sync.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Refresh-or-clone the repo into the working dir
if [ -d ".git" ]; then
  git fetch origin
  git checkout main
  git reset --hard origin/main
else
  git clone --branch main \
    "https://x-access-token:${GITHUB_TOKEN}@github.com/KielRN/AI-TRADING-ROUTINE.git" .
fi

# Identity for the STEP 8 / STEP 9 commits the routines do at the end
git config user.email "bot@ai-trading-routine.local"
git config user.name  "AI Trading Bot"

# Make sure pushes use the token, not an interactive prompt
git remote set-url origin \
  "https://x-access-token:${GITHUB_TOKEN}@github.com/KielRN/AI-TRADING-ROUTINE.git"

# Python deps for scripts/coinbase.py, scripts/state.py, scripts/research_gate.py,
# scripts/paper_trade.py, scripts/cycle_orders.py, scripts/policy.py
pip install --no-cache-dir -r requirements.txt
```

The script tracks `main` only. All routine code, strategy docs, and memory
must be merged into `main` before the next scheduled run will see them.

## Environment Variables

Set these in the **Secrets / Environment variables** section of each
routine. If the Claude Code UI lets you attach a shared environment to
multiple routines, do that instead of duplicating.

| Variable | Required by | Notes |
| --- | --- | --- |
| `GITHUB_TOKEN` | both | Fine-grained PAT scoped only to `KielRN/AI-TRADING-ROUTINE`, `Contents: Read and write` |
| `COINBASE_API_KEY` | both | View-only CDP Ed25519 key during the paper trading test |
| `COINBASE_API_SECRET` | both | Paired private key for the CDP key above |
| `TELEGRAM_BOT_TOKEN` | both | Direct-send fallback path |
| `ALLOWED_CHAT_IDS` | both | Comma-separated chat IDs for the trading bot |
| `TELEGRAM_SERVICE_URL` | optional, both | Use the shared Railway notifier instead of direct Telegram |
| `TELEGRAM_SERVICE_API_KEY` | optional, both | Paired with `TELEGRAM_SERVICE_URL` |
| `CHARTINSPECT_API_KEY` | research only | Falls back to WebSearch if missing |
| `YOUTUBE_API_KEY` | research only | Falls back to WebSearch if missing |
| `FRED_API_KEY` | research only | Falls back to WebSearch if missing |

The routine prompts call out at start-of-run: every required key must
already be exported. There is no `.env` file in the repo, and the routines
must not create one.

### Coinbase Key Hardening For Paper Trading

While the campaign is in paper mode, the Coinbase key in the cloud env
should be **view-only**. Paper trading only needs:

```text
account, position, quote, orders, order, fills
```

All read-only. Generating a separate read/write CDP key only when live
cycle opening is enabled keeps the blast radius small if the cloud env is
ever compromised.

## Routine-To-Setup Mapping

Two routines are active. Each gets the same setup script and the same
secret environment.

```text
BTC paper - research-and-plan
  schedule: 0 7,19 * * *
  prompt:   routines/research-and-plan.md
  outputs:  memory/research-reports/, memory/RESEARCH-LOG.md
  push:     git push origin main at STEP 8

BTC paper - paper-trading
  schedule: 30 7,12,19 * * *
  prompt:   routines/paper-trading.md
  outputs:  memory/paper-trading/state.json
  push:     git push origin main at STEP 9
```

## Verifying The First Run

After saving the setup script and secrets, trigger **research-and-plan**
manually first. A healthy run leaves these traces on `main`:

```text
new file: memory/research-reports/<DATE>-<HOUR>.json
appended:  memory/RESEARCH-LOG.md
commit:    "research <DATE> <HOUR>:00"
```

Pull locally and confirm:

```powershell
cd E:\AI-TRADING-ROUTINE
git checkout main
git pull origin main
git log --oneline main -3
ls memory\research-reports
```

Then trigger **paper-trading** within 45 minutes of the research run. A
healthy first paper run leaves:

```text
memory/paper-trading/state.json:
  status changes from "not_started" to "active"
  starting_btc, starting_usd, starting_btc_price set from live values
  started_at_utc set, ends_at_utc set 14 days later
commit:    "paper trading <DATE>"
```

`state.status == "not_started"` after the run means the setup script
crashed, the research gate blocked the routine, or the wrapper scripts
returned errors. Check the run log for the exit reason in that order.

## Common Failure Modes

**`Could not open requirements file: requirements.txt`** — the setup
script ran in an empty working directory because the clone step was
skipped or failed. Check that `GITHUB_TOKEN` is set and that the token has
not expired.

**`fatal: Authentication failed for ...github.com/...`** — `GITHUB_TOKEN`
is invalid, expired, or scoped to the wrong repo. Regenerate as a
fine-grained PAT with `Contents: Read and write` on
`KielRN/AI-TRADING-ROUTINE` only.

**`KEY not set in environment`** from a wrapper — a required Coinbase or
Telegram variable is missing from the routine's secret environment. The
routine prompt sends one Telegram alert and exits.

**`research stale/missing, paper open blocked`** — the paper-trading
routine ran but no research report under
`memory/research-reports/<DATE>-<HOUR>.json` is fresher than 45 minutes.
Either research-and-plan didn't run, or its output never made it back to
`main`. The 12:30 paper run is expected to hit this every day — only the
07:30 and 19:30 paper runs should pair with a fresh research report.

**Schedule timezone drift** — the Routines UI shows times in local time.
The routine prompts work in UTC. If the gap between research and paper
ever exceeds 45 minutes after a DST change, only the 07:30 / 19:30 paper
runs will be affected; adjust the cron entries to keep paper within 45
minutes of research.

## When Live Trading Goes On

Before flipping `paper-trading` off and enabling `execute` / `manage` /
`panic-check` cloud routines for live BTC trading:

- Replace the view-only Coinbase key with a read/write CDP key in the
  cloud secrets.
- Confirm `memory/state.json` is in a clean state, with
  `drawdown_halt: false` and no orphan active cycle.
- Re-read [TRADING-STRATEGY.md](memory/TRADING-STRATEGY.md). Live cycles
  must satisfy every hard rule in §2.
- Add the live routines to the Claude Code Routines UI with the same setup
  script and the upgraded Coinbase key.

The setup script itself does not change between paper and live — only the
Coinbase key permissions and the set of active routines.
