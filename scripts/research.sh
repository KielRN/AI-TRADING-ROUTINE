#!/usr/bin/env bash
# Research wrapper. `collect` gathers only the currently validated/already-paid
# sources, then the research agent covers missing rubric slots with WebSearch.
#
# This intentionally avoids adding new paid API dependencies.
#
# Usage:
#   bash scripts/research.sh "<query>"
#   bash scripts/research.sh collect

set -euo pipefail

query="${1:-}"
if [[ -z "$query" ]]; then
    echo "usage: bash scripts/research.sh \"<query>\" | collect" >&2
    exit 1
fi

if [[ "$query" == "collect" ]]; then
    shift
    exec python scripts/research_collect.py "$@"
fi

echo "WARNING: numeric research backend not configured. Fall back to WebSearch." >&2
echo "QUERY_FOR_WEBSEARCH: $query"
exit 3
