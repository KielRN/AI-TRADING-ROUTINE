#!/usr/bin/env bash
# Research wrapper. V1 is a stub — exits 3 to signal "no backend configured"
# and let the routine fall back to Claude's native WebSearch tool, matching
# the parent doc's fallback contract.
#
# V2 will replace the internals with the numeric pipeline defined in
# RESEARCH-AGENT-DESIGN.md (§3). The wrapper contract stays the same so no
# routine prompts need editing.
#
# Usage: bash scripts/research.sh "<query>"

set -euo pipefail

query="${1:-}"
if [[ -z "$query" ]]; then
    echo "usage: bash scripts/research.sh \"<query>\"" >&2
    exit 1
fi

# V1: always fall through to WebSearch. Agent is instructed to handle exit 3.
echo "WARNING: research backend not configured. Fall back to WebSearch." >&2
echo "QUERY_FOR_WEBSEARCH: $query"
exit 3
