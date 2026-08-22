#!/usr/bin/env bash
#
# Cumulative regression script. Every phase appends its happy path here and the
# whole file is run, not just the new part.
#
# EVERY STEP ASSERTS. Each response is piped through "jq -e" on a field that
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

# --- Step 0: reset ----------------------------------------------------------
# Always first, from Phase 1 onward, so a failed run cannot leave state that
# breaks the next one. Ids below are deterministic because reset zeroes the
# id counters before reseeding.

step "0    POST /dev/reset -> seeded, clock back to zero"
curl -sS -X POST "$BASE/dev/reset" \
  | jq -e '.reset == true
           and .clock_offset_minutes == 0
           and .seeded.zones == 5
           and .seeded.hosts == 3
           and .seeded.visitors == 2
           and .seeded.visits == 2' > /dev/null
pass

# --- Phase 0: skeleton ------------------------------------------------------

step "0.1  GET /health -> status ok"
curl -sS "$BASE/health" | jq -e '.status == "ok"' > /dev/null
pass

# --- Phase 1: entities and repositories -------------------------------------

step "1.1  GET /zones -> five seeded zones, MAIN present"
curl -sS "$BASE/zones" \
  | jq -e 'length == 5 and (map(.code) | index("MAIN")) != null' > /dev/null
pass

step "1.2  GET /hosts -> three hosts across two departments, phone included"
curl -sS "$BASE/hosts" \
  | jq -e 'length == 3
           and ([.[].department] | unique | length) == 2
           and all(.[]; .phone != null)' > /dev/null
pass

step "1.3  GET /visitors/vr_1 -> visitor A, DigiLocker-verified, NO id_hash"
curl -sS "$BASE/visitors/vr_1" \
  | jq -e '.id == "vr_1"
           and .tier == "verified"
           and .verified_by == "digilocker"
           and .id_last4 == "4321"
           and has("id_hash") == false' > /dev/null
pass

step "1.4  GET /visitors/vr_2 -> visitor C, tier derives as temporary"
curl -sS "$BASE/visitors/vr_2" \
  | jq -e '.id == "vr_2" and .tier == "temporary"' > /dev/null
pass

# --- Phase 2: state machine -------------------------------------------------
# The full legal lifecycle on v_1, one row of the SPEC section 8 table per step.
# v_2 is deliberately untouched: that is visitor C, and Phase 8 needs her still
# inside and unacknowledged.

step "2.1  v_1 requested -> approved"
curl -sS -X POST "$BASE/dev/transition" -H 'Content-Type: application/json' \
  -d '{"visit_id":"v_1","to_status":"approved"}' \
  | jq -e '.from == "requested" and .to == "approved"' > /dev/null
pass

step "2.2  v_1 approved -> issued"
curl -sS -X POST "$BASE/dev/transition" -H 'Content-Type: application/json' \
  -d '{"visit_id":"v_1","to_status":"issued"}' \
  | jq -e '.to == "issued"' > /dev/null
pass

step "2.3  v_1 issued -> inside"
curl -sS -X POST "$BASE/dev/transition" -H 'Content-Type: application/json' \
  -d '{"visit_id":"v_1","to_status":"inside"}' \
  | jq -e '.to == "inside" and .is_terminal == false' > /dev/null
pass

step "2.4  v_1 inside -> closed, and closed is terminal"
curl -sS -X POST "$BASE/dev/transition" -H 'Content-Type: application/json' \
  -d '{"visit_id":"v_1","to_status":"closed"}' \
  | jq -e '.to == "closed"
           and .is_terminal == true
           and (.legal_moves_now | length) == 0' > /dev/null
pass

step "2.5  reset, so later phases do not inherit a closed v_1"
curl -sS -X POST "$BASE/dev/reset" | jq -e '.reset == true' > /dev/null
pass

printf '\nAll steps passed.\n'
