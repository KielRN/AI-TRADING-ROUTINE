# Cloud Routine Setup

This guide explains the environment that each Claude Code cloud routine runs
inside, why a setup script is required, and exactly what to paste into the
Claude Code Routines UI for the two routines this project uses.

**Status (2026-04-29):** Verified working end-to-end. The setup script,
prerequisites, and env vars below are confirmed to produce a successful
research-and-plan run that pushes back to `main`.

For the wider strategy context, repository layout, and historical design
notes, see [Opus 4.7 Trading Bot — Setup Guide](Opus%204.7%20Trading%20Bot%20%E2%80%94%20Setup%20Guide.md).
This file is the canonical reference for the cloud routine environment
itself.

## How The Cloud Routine Harness Handles Git

The Claude Code cloud routine harness handles repository operations
itself. The setup script is **not** responsible for cloning, and runs
**before** the harness clones the repo:

1. The setup script runs in a pristine container with no repo files
   present. Working directory is empty. Its only job is to install
   Python dependencies.
2. The harness clones the repo into the sandbox to a per-run branch
   (`claude/<sandbox-name>`) using credentials from the Claude GitHub
   App.
3. The agent prompt runs with the repo as cwd. Wrapper scripts read the
   routine's environment secrets directly.
4. At STEP 8 / STEP 9, the agent commits and pushes through the same
   proxy. To push to `main` (not just the sandbox branch), the routine
   environment must have **"Allow unrestricted branch pushes"** toggled
   on.

Two important consequences:

- **`requirements.txt` is not visible to the setup script.** Install
  dependencies by name, not by `-r requirements.txt`.
- **User secrets are not visible to the setup script.** `GITHUB_TOKEN`,
  `COINBASE_API_KEY`, etc., are exposed to the agent but not to the
  setup script. Don't reference them there.

## Why A Setup Script Is Needed

Every cloud routine run starts a fresh sandbox. The Python dependencies
the wrapper scripts need do not survive between runs. The setup script
is responsible for:

1. Installing the Python dependencies the wrapper scripts need, by
   explicit name (since the harness clones the repo *after* this script
   runs, `requirements.txt` is not visible here).

That's it. Cloning and push auth are handled by the harness via the
Claude GitHub App. Do not put `git clone`, `git config`, or any
`${GITHUB_TOKEN}` reference in the setup script — the setup script env
does not have those secrets, and you would just re-clone what the harness
is about to clone anyway.

## Setup Script

Paste this into the **Setup script** field of both routines in the Claude
Code Routines UI. Identical content for both. The setup script runs
before the harness clones the repo, so dependencies must be named
explicitly — `pip install -r requirements.txt` will fail with `No such
file or directory` because `requirements.txt` is not yet present.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Python deps for scripts/coinbase.py, scripts/state.py,
# scripts/research_gate.py, scripts/paper_trade.py,
# scripts/cycle_orders.py, scripts/policy.py.
# Mirror of requirements.txt — keep these in sync when deps change.
# --ignore-installed: the cloud sandbox base image has Debian-installed
# Python packages (notably PyJWT 2.7.0) without pip RECORD files. Without
# this flag, pip refuses to upgrade them and the script aborts.
pip install --no-cache-dir --ignore-installed \
  coinbase-advanced-py \
  httpx \
  python-dotenv \
  requests \
  PyJWT \
  cryptography \
  cffi
```

Do **not** add a `git clone`, `git config`, or any `${GITHUB_TOKEN}`
reference. The harness handles cloning after this script completes, and
user secrets are not exposed to the setup script.

When `requirements.txt` changes, update this list to match. The agent's
runtime can also pip-install missing deps mid-prompt as a fallback, but
that wastes tokens and time on every run.

## One-Time Prerequisites

Before any routine can clone or push, do these once:

1. **Install the Claude GitHub App** on `KielRN/AI-TRADING-ROUTINE` only
   (least privilege). This is what authenticates the harness's git
   operations through the cloud sandbox proxy.
2. **Toggle "Allow unrestricted branch pushes"** on each routine's
   environment. Without this, the proxy lets the agent push to its
   sandbox `claude/<name>` branch but rejects pushes to `main` with a
   `403 Permission denied`, which means STEP 8 / STEP 9 commits silently
   never reach GitHub and the next fresh-clone run loses everything.

## Environment Variables

Set these in the **Secrets / Environment variables** section of each
routine. If the Claude Code UI lets you attach a shared environment to
multiple routines, do that instead of duplicating.

| Variable | Required by | Notes |
| --- | --- | --- |
| `COINBASE_API_KEY` | both | View-only CDP Ed25519 key during the paper trading test |
| `COINBASE_API_SECRET` | both | Paired private key for the CDP key above |
| `TELEGRAM_BOT_TOKEN` | both | Direct-send fallback path |
| `ALLOWED_CHAT_IDS` | both | Comma-separated chat IDs for the trading bot |
| `TELEGRAM_SERVICE_URL` | optional, both | Use the shared Railway notifier instead of direct Telegram |
| `TELEGRAM_SERVICE_API_KEY` | optional, both | Paired with `TELEGRAM_SERVICE_URL` |
| `GITHUB_TOKEN` | optional, both | Not used for git push (the GitHub App handles that). Useful only if a wrapper later wants to call the GitHub REST API directly. Harmless to keep |
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

## Verifying A Run

A healthy research-and-plan run leaves these traces on `main`:

```text
new file:  memory/research-reports/<DATE>-<HOUR>.json
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

A healthy paper-trading run leaves:

```text
memory/paper-trading/state.json updated:
  first run:    status flips from "not_started" to "active";
                starting_btc, starting_usd, starting_btc_price set from
                live values; started_at_utc set; ends_at_utc set 14 days
                later
  later runs:   last_price tick updated; cycles[] updated if a paper
                cycle filled or closed
commit:    "paper trading <DATE>"
```

`state.status == "not_started"` after a paper-trading run means the
setup script crashed, the research gate blocked the routine, or the
wrapper scripts returned errors. Check the run log for the exit reason
in that order.

Confirm the routine actually pushed to `main` (not just to its sandbox
branch) by comparing `git log origin/main` after a routine fires. A
sandbox-only push leaves `main` untouched and the next routine run will
not see the work.

## Common Failure Modes

**`GITHUB_TOKEN: unbound variable`** in the setup script — the setup
script is referencing `${GITHUB_TOKEN}` (or any other user secret). User
secrets aren't exported into the setup script's env. Replace the setup
script with the explicit-deps `pip install` shown in the Setup Script
section above; do not reference user secrets there.

**`Could not open requirements file: requirements.txt`** — the setup
script is referencing `requirements.txt`, but the harness has not yet
cloned the repo when the setup script runs. The setup script must list
dependencies by name (see the Setup Script section). The Claude GitHub
App needs to be installed for the *agent* to access the repo, but that
clone happens after setup, not before.

**`ERROR: Cannot uninstall <pkg>, RECORD file not found. Hint: The
package was installed by debian.`** — the cloud sandbox base image
ships with some Python packages installed via apt (Debian's package
manager), which pip can't cleanly upgrade. Add `--ignore-installed` to
the pip command so it lays down fresh copies in user site-packages
instead of trying to uninstall the Debian copies.

**`git push` fails with `403 Permission denied` / `WWW-Authenticate:
Basic realm="Git Proxy"`** — the cloud sandbox's git proxy rejected the
push. Almost always means **"Allow unrestricted branch pushes"** is off
in the routine's environment (Prereq 2). The agent can still push to its
sandbox `claude/<name>` branch but cannot reach `main`. Toggle it on and
re-run. If it's already on, the GitHub App may have been uninstalled or
its permissions revoked.

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
