#!/usr/bin/env bash
#
# Cumulative regression script. Every phase appends its happy path here and the
# whole file is run, not just the new part.
#
# EVERY STEP ASSERTS. Each response is piped through `jq -e` on a field that
# proves it worked, so a non-zero exit stops the script at the broken step.
#
# Usage:  bash smoke.sh            (server must already be running)
#         BASE=http://host:port bash smoke.sh
#
# Requires: curl, jq

set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"

step() { printf '\n=== %s ===\n' "$*"; }
pass() { printf '    OK\n'; }

# Fail with a readable message rather than a raw curl error when the server is
# not up, which is by far the most common reason this script stops on step 1.
command -v jq > /dev/null 2>&1 || {
  printf 'jq is not on PATH. Install it (winget install jqlang.jq) and open a new terminal.\n' >&2
  exit 1
}
curl -sS -m 5 -o /dev/null "$BASE/health" 2>/dev/null || {
  printf 'No server on %s. Start it with:\n  uvicorn app.main:app --reload\n' "$BASE" >&2
  exit 1
}

# --- Phase 0: skeleton ------------------------------------------------------
# No /dev/reset step - it arrives at Phase 1 and becomes step 0 from then on.

step "0.1  GET /health -> status ok"
curl -sS "$BASE/health" | jq -e '.status == "ok"' > /dev/null
pass

printf '\nAll steps passed.\n'
