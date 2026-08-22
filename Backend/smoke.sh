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
#
# SEEDED IDS, after step 0. Test steps depend on these being stable.
#   visitors  vr_1 Ramesh Kumar (A, DigiLocker)
#             vr_2 Deepa Nair   (C, restricted, already inside)
#             vr_3 Suresh Iyer  (B, vouched, pass issued, 2 companions)
#   visits    v_1 requested (A)   v_2 inside (C)   v_3 issued (B)
#   passes    p_1 for v_3
#   The first visitor this script registers is therefore vr_4, and the first
#   visit it creates is v_4.

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
# breaks the next one. Ids above are deterministic because reset zeroes the id
# counters before reseeding.

step "0    POST /dev/reset -> seeded, clock back to zero"
curl -sS -X POST "$BASE/dev/reset" \
  | jq -e '.reset == true
           and .clock_offset_minutes == 0
           and .seeded.zones == 5
           and .seeded.hosts == 3
           and .seeded.visitors == 3
           and .seeded.visits == 3' > /dev/null
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

# --- Phase 3: registration and verification ---------------------------------
# A tiny valid PNG, so the photo path is exercised with real image bytes rather
# than an arbitrary string that happens to be base64.
PHOTO="iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAIUlEQVR4nGP8z0AKYCJJ9aiGUdBIDGH8//8/8bJDMcwBAI2fBAWYU0mvAAAAAElFTkSuQmCC"

step "3.1  POST /visitors -> registered, tier temporary, ref out not base64"
curl -sS -X POST "$BASE/visitors" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Priya Raman\",\"phone\":\"+91-99999-88888\",\"photo_b64\":\"$PHOTO\"}" \
  | jq -e '.id == "vr_4"
           and .tier == "temporary"
           and .photo_ref != null
           and has("photo_b64") == false
           and has("id_hash") == false' > /dev/null
pass

step "3.2  OTP send then verify -> phone_verified, tier UNCHANGED"
CODE=$(curl -sS -X POST "$BASE/visitors/vr_4/otp/send" | jq -r '.code')
curl -sS -X POST "$BASE/visitors/vr_4/otp/verify" -H 'Content-Type: application/json' \
  -d "{\"code\":\"$CODE\"}" \
  | jq -e '.phone_verified == true and .tier == "temporary"' > /dev/null
pass

step "3.3  GET /photos/{ref} -> the one place base64 comes back out"
REF=$(curl -sS "$BASE/visitors/vr_4" | jq -r '.photo_ref')
curl -sS "$BASE/photos/$REF" \
  | jq -e --arg r "$REF" '.ref == $r and (.photo_b64 | length) > 0' > /dev/null
pass

step "3.4  DigiLocker -> verified and permanent, id_last4 out but never id_hash"
curl -sS -X POST "$BASE/visitors/vr_4/digilocker" \
  | jq -e '.tier == "verified"
           and .verified_by == "digilocker"
           and .is_permanent == true
           and .id_last4 != null
           and has("id_hash") == false' > /dev/null
pass

step "3.5  GET /visitors/lookup finds by phone (declared above /{id})"
curl -sS "$BASE/visitors/lookup?phone=%2B91-99999-88888" \
  | jq -e '.id == "vr_4"' > /dev/null
pass

step "3.6  every seeded visitor carries a resolvable photo"
for v in vr_1 vr_2 vr_3; do
  r=$(curl -sS "$BASE/visitors/$v" | jq -r '.photo_ref')
  curl -sS "$BASE/photos/$r" | jq -e '(.photo_b64 | length) > 0' > /dev/null
done
pass

# --- Phase 4: pass request and approval -------------------------------------

step "4.1  POST /visits with 2 companions -> requested, expected = 3"
curl -sS -X POST "$BASE/visits" -H 'Content-Type: application/json' \
  -d '{"visitor_id":"vr_1","host_id":"h_1","purpose":"Lab tour",
       "scheduled_at":"2026-08-22T15:00:00+05:30","vehicle_plate":"TN-01-AA-1111",
       "companions":[{"name":"Arun"},{"name":"Meena"}]}' \
  | jq -e '.id == "v_4"
           and .status == "requested"
           and .person_count_expected == 3
           and .origin == "pre_registered"' > /dev/null
pass

step "4.2  GET /visits/{id} lists the linked companions"
curl -sS "$BASE/visits/v_4" \
  | jq -e '.id == "v_4" and (.companions | length) == 2' > /dev/null
pass

step "4.3  faculty inbox filters by host and status"
curl -sS "$BASE/visits?host_id=h_1&status=requested" \
  | jq -e 'length >= 1 and all(.[]; .host_id == "h_1" and .status == "requested")' > /dev/null
pass

step "4.4  approve -> requested through approved to issued, in one call"
curl -sS -X POST "$BASE/visits/v_4/approve" -H 'Content-Type: application/json' \
  -d '{"meeting_zone_id":"z_1","allowed_zones":["z_2","z_5"],
       "valid_from":"2026-08-22T15:00:00+05:30",
       "valid_to":"2026-08-22T19:00:00+05:30","vouch":false}' \
  | jq -e '.status == "issued"
           and .approved_by == "faculty:h_1"
           and .meeting_zone_id == "z_1"
           and (.allowed_zones | index("z_1")) != null' > /dev/null
pass

step "4.5  four companions is legal (1 + 4 = 5 total, SPEC section 6)"
curl -sS -X POST "$BASE/visits" -H 'Content-Type: application/json' \
  -d '{"visitor_id":"vr_1","host_id":"h_1","purpose":"Group of five",
       "scheduled_at":"2026-08-23T10:00:00+05:30",
       "companions":[{"name":"a"},{"name":"b"},{"name":"c"},{"name":"d"}]}' \
  | jq -e '.person_count_expected == 5' > /dev/null
pass

step "4.6  person_count path -> used as-is, no companion records"
curl -sS -X POST "$BASE/visits" -H 'Content-Type: application/json' \
  -d '{"visitor_id":"vr_1","host_id":"h_1","purpose":"Large group",
       "scheduled_at":"2026-08-23T11:00:00+05:30","person_count":12}' \
  | jq -e '.person_count_expected == 12' > /dev/null
pass

step "4.7  approve with vouch verifies an unverified visitor (SPEC section 7)"
NEWV=$(curl -sS -X POST "$BASE/visitors" -H 'Content-Type: application/json' \
  -d '{"name":"Kavitha S","phone":"+91-98400-33333"}' | jq -r '.id')
NEWVIS=$(curl -sS -X POST "$BASE/visits" -H 'Content-Type: application/json' \
  -d "{\"visitor_id\":\"$NEWV\",\"host_id\":\"h_2\",\"purpose\":\"Vouched visit\",
       \"scheduled_at\":\"2026-08-22T16:00:00+05:30\"}" | jq -r '.id')
curl -sS -X POST "$BASE/visits/$NEWVIS/approve" -H 'Content-Type: application/json' \
  -d '{"meeting_zone_id":"z_1","allowed_zones":[],
       "valid_from":"2026-08-22T15:00:00+05:30",
       "valid_to":"2026-08-22T19:00:00+05:30","vouch":true}' > /dev/null
curl -sS "$BASE/visitors/$NEWV" \
  | jq -e '.tier == "verified"
           and .verified_by == "vouch"
           and .vouched_by_host_id == "h_2"' > /dev/null
pass

step "4.8  DigiLocker then OVERRIDES that vouch, keeping the audit trail"
curl -sS -X POST "$BASE/visitors/$NEWV/digilocker" \
  | jq -e '.verified_by == "digilocker"
           and .is_permanent == true
           and .vouched_by_host_id == "h_2"' > /dev/null
pass

step "4.9  cancel an issued visit -> cancelled"
curl -sS -X POST "$BASE/visits/v_4/cancel" -H 'Content-Type: application/json' \
  -d '{"reason":"Rescheduled"}' \
  | jq -e '.status == "cancelled" and .approval_reason == "Rescheduled"' > /dev/null
pass

step "4.10 GET /visits/{id}/scans -> empty audit trail until Phase 6"
curl -sS "$BASE/visits/v_4/scans" | jq -e 'type == "array"' > /dev/null
pass

step "4.11 notifications were fired to host and visitor"
curl -sS "$BASE/dev/notifications" \
  | jq -e '.count >= 3
           and ([.notifications[].recipient] | map(startswith("host:")) | any)
           and ([.notifications[].recipient] | map(startswith("visitor:")) | any)' > /dev/null
pass

# --- Phase 5: pass signing --------------------------------------------------
# v_3 is visitor B, seeded at Phase 5 with an issued pass precisely so there is
# something signed to fetch before any live approval has run.

step "5.1  GET /passes/v_3 -> seeded pass, signed, with a 6-digit code"
curl -sS "$BASE/passes/v_3" \
  | jq -e '.visit_id == "v_3"
           and (.code6 | test("^[0-9]{6}$"))
           and .is_revoked == false
           and (.qr.signature | length) == 64' > /dev/null
pass

step "5.2  the QR payload carries ONLY visit_id and nonce (SPEC section 9)"
curl -sS "$BASE/passes/v_3" \
  | jq -e '(.qr.payload | keys) == ["nonce","visit_id"]
           and (((.qr | tostring) | test("valid_to|valid_from|allowed_zones")) | not)' > /dev/null
pass

step "5.3  the same visit returns a byte-identical QR every time"
Q1=$(curl -sS "$BASE/passes/v_3" | jq -cS '.qr')
Q2=$(curl -sS "$BASE/passes/v_3" | jq -cS '.qr')
[ "$Q1" = "$Q2" ] || { printf 'QR changed between calls\n' >&2; exit 1; }
pass

step "5.4  approve now issues a pass of its own"
curl -sS -X POST "$BASE/visits/v_1/approve" -H 'Content-Type: application/json' \
  -d '{"meeting_zone_id":"z_1","allowed_zones":["z_2"],
       "valid_from":"2026-08-22T15:00:00+05:30",
       "valid_to":"2026-08-22T19:00:00+05:30"}' > /dev/null
curl -sS "$BASE/passes/v_1" \
  | jq -e '.visit_id == "v_1" and (.code6 | test("^[0-9]{6}$"))' > /dev/null
pass

step "5.5  active passes hold distinct code6 values (SPEC section 9)"
C1=$(curl -sS "$BASE/passes/v_1" | jq -r '.code6')
C3=$(curl -sS "$BASE/passes/v_3" | jq -r '.code6')
[ "$C1" != "$C3" ] || { printf 'code6 collision between active passes\n' >&2; exit 1; }
pass

step "5.6  revoke sets revoked_at and leaves the visit status alone"
BEFORE=$(curl -sS "$BASE/visits/v_1" | jq -r '.status')
curl -sS -X POST "$BASE/passes/v_1/revoke" -H 'X-Role: security' \
  | jq -e '.is_revoked == true and .revoked_at != null' > /dev/null
curl -sS "$BASE/visits/v_1" | jq -e --arg b "$BEFORE" '.status == $b' > /dev/null
pass

printf '\nAll steps passed.\n'
