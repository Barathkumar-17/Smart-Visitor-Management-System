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
#   The first visitor this script registers is therefore vr_7, and the first
#   visit it creates is v_7.

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
           and .seeded.visitors == 6
           and .seeded.visits == 6' > /dev/null
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
  | jq -e '.id == "vr_7"
           and .tier == "temporary"
           and .photo_ref != null
           and has("photo_b64") == false
           and has("id_hash") == false' > /dev/null
pass

step "3.2  OTP send then verify -> phone_verified, tier UNCHANGED"
CODE=$(curl -sS -X POST "$BASE/visitors/vr_7/otp/send" | jq -r '.code')
curl -sS -X POST "$BASE/visitors/vr_7/otp/verify" -H 'Content-Type: application/json' \
  -d "{\"code\":\"$CODE\"}" \
  | jq -e '.phone_verified == true and .tier == "temporary"' > /dev/null
pass

step "3.3  GET /photos/{ref} -> the one place base64 comes back out"
REF=$(curl -sS "$BASE/visitors/vr_7" | jq -r '.photo_ref')
curl -sS "$BASE/photos/$REF" \
  | jq -e --arg r "$REF" '.ref == $r and (.photo_b64 | length) > 0' > /dev/null
pass

step "3.4  DigiLocker -> verified and permanent, id_last4 out but never id_hash"
curl -sS -X POST "$BASE/visitors/vr_7/digilocker" \
  | jq -e '.tier == "verified"
           and .verified_by == "digilocker"
           and .is_permanent == true
           and .id_last4 != null
           and has("id_hash") == false' > /dev/null
pass

step "3.5  GET /visitors/lookup finds by phone (declared above /{id})"
curl -sS "$BASE/visitors/lookup?phone=%2B91-99999-88888" \
  | jq -e '.id == "vr_7"' > /dev/null
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
  | jq -e '.id == "v_7"
           and .status == "requested"
           and .person_count_expected == 3
           and .origin == "pre_registered"' > /dev/null
pass

step "4.2  GET /visits/{id} lists the linked companions"
curl -sS "$BASE/visits/v_7" \
  | jq -e '.id == "v_7" and (.companions | length) == 2' > /dev/null
pass

step "4.3  faculty inbox filters by host and status"
curl -sS "$BASE/visits?host_id=h_1&status=requested" \
  | jq -e 'length >= 1 and all(.[]; .host_id == "h_1" and .status == "requested")' > /dev/null
pass

step "4.4  approve -> requested through approved to issued, in one call"
curl -sS -X POST "$BASE/visits/v_7/approve" -H 'Content-Type: application/json' \
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
curl -sS -X POST "$BASE/visits/v_7/cancel" -H 'Content-Type: application/json' \
  -d '{"reason":"Rescheduled"}' \
  | jq -e '.status == "cancelled" and .approval_reason == "Rescheduled"' > /dev/null
pass

step "4.10 GET /visits/{id}/scans -> empty audit trail until Phase 6"
curl -sS "$BASE/visits/v_7/scans" | jq -e 'type == "array"' > /dev/null
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


# --- Phase 6: gate entry ----------------------------------------------------
# The core demo path. v_3 is visitor B, seeded with a signed pass and two
# companions precisely so this scan leads with three faces.
#
# A reset first, because Phase 5 revoked v_1's pass and left v_1 issued.

step "6.0  reset before the gate-entry sequence"
curl -sS -X POST "$BASE/dev/reset" | jq -e '.reset == true' > /dev/null
pass

step "6.1  seeded history: C, D, E and F all entered through the real scan path"
curl -sS "$BASE/visits/v_2/scans" | jq -e 'length == 1 and .[0].kind == "entry" and .[0].result == "ok"' > /dev/null
curl -sS "$BASE/visits/v_4/scans" | jq -e 'length == 1 and .[0].result == "ok"' > /dev/null
curl -sS "$BASE/visits/v_5/scans" \
  | jq -e 'length == 2
           and ([.[] | select(.kind == "zone")] | .[0].result) == "wrong_zone"' > /dev/null
curl -sS "$BASE/visits/v_6/scans" \
  | jq -e 'length == 2
           and ([.[] | select(.kind == "zone")] | .[0].result) == "ok"' > /dev/null
pass

step "6.2  THE DEMO BEAT - valid pass admits, leading with every face"
QR=$(curl -sS "$BASE/passes/v_3" | jq -c '.qr')
PAY=$(printf '%s' "$QR" | jq -c '.payload')
SIG=$(printf '%s' "$QR" | jq -r '.signature')
curl -sS -X POST "$BASE/scans/gate/entry" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "{\"payload\":$PAY,\"signature\":\"$SIG\",\"vehicle_plate\":\"TN-07-XY-9090\",\"person_count_in\":3}" \
  | jq -e '.admitted == true
           and .result == "ok"
           and (.people | length) == 3
           and (.people[0].role == "visitor")
           and all(.people[]; .photo_ref != null)
           and ([.people[].photo_ref] | unique | length) == 3
           and .vehicle.mismatch == false
           and .headcount.expected == 3
           and .headcount.mismatch == false
           and .host_phone != null
           and .scan_event_id != null' > /dev/null
pass

step "6.3  the visit is now inside, with entry_at stamped"
curl -sS "$BASE/visits/v_3" \
  | jq -e '.status == "inside" and .entry_at != null and .person_count_in == 3' > /dev/null
pass

step "6.4  scanning the same pass again -> 200, refused, wrong_status"
curl -sS -X POST "$BASE/scans/gate/entry" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "{\"payload\":$PAY,\"signature\":\"$SIG\"}" \
  | jq -e '.admitted == false and .result == "wrong_status"' > /dev/null
pass

step "6.5  a tampered payload -> 200 with admitted false, NOT an error status"
BADPAY=$(printf '%s' "$PAY" | jq -c '.visit_id = "v_1"')
curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE/scans/gate/entry" \
  -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "{\"payload\":$BADPAY,\"signature\":\"$SIG\"}" | grep -q '^200$' \
  || { printf 'tampered scan did not return 200\n' >&2; exit 1; }
curl -sS -X POST "$BASE/scans/gate/entry" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "{\"payload\":$BADPAY,\"signature\":\"$SIG\"}" \
  | jq -e '.admitted == false and .result == "bad_signature"' > /dev/null
pass

step "6.6  a plate mismatch STILL ADMITS, flagged on response and event"
curl -sS -X POST "$BASE/dev/reset" > /dev/null
QR2=$(curl -sS "$BASE/passes/v_3" | jq -c '.qr')
PAY2=$(printf '%s' "$QR2" | jq -c '.payload')
SIG2=$(printf '%s' "$QR2" | jq -r '.signature')
curl -sS -X POST "$BASE/scans/gate/entry" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "{\"payload\":$PAY2,\"signature\":\"$SIG2\",\"vehicle_plate\":\"TN-99-ZZ-0000\",\"person_count_in\":5}" \
  | jq -e '.admitted == true
           and .result == "ok"
           and .vehicle.mismatch == true
           and .vehicle.expected == "TN-07-XY-9090"
           and .vehicle.presented == "TN-99-ZZ-0000"
           and .headcount.mismatch == true' > /dev/null
curl -sS "$BASE/visits/v_3/scans" \
  | jq -e '[.[] | select(.kind == "entry")] | .[0]
           | .result == "ok" and .plate_mismatch == true and .count_mismatch == true' > /dev/null
pass

step "6.7  the code6 fallback admits exactly as the QR does"
curl -sS -X POST "$BASE/dev/reset" > /dev/null
C6=$(curl -sS "$BASE/passes/v_3" | jq -r '.code6')
curl -sS -X POST "$BASE/scans/gate/entry" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "{\"code6\":\"$C6\",\"person_count_in\":3}" \
  | jq -e '.admitted == true and (.people | length) == 3' > /dev/null
pass

step "6.8  a revoked pass is refused at the gate"
curl -sS -X POST "$BASE/dev/reset" > /dev/null
curl -sS -X POST "$BASE/passes/v_3/revoke" -H 'X-Role: security' > /dev/null
QR3=$(curl -sS "$BASE/passes/v_3" | jq -c '.qr')
curl -sS -X POST "$BASE/scans/gate/entry" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "{\"payload\":$(printf '%s' "$QR3" | jq -c '.payload'),\"signature\":\"$(printf '%s' "$QR3" | jq -r '.signature')\"}" \
  | jq -e '.admitted == false and .result == "revoked"' > /dev/null
pass

step "6.9  every refusal still wrote a ScanEvent (SPEC section 6)"
curl -sS "$BASE/visits/v_3/scans" \
  | jq -e 'length >= 1 and any(.[]; .result == "revoked")' > /dev/null
pass


# --- Phase 8: arrival acknowledgement ---------------------------------------
# v_2 is visitor C, the ONLY restricted visit in this build. Nothing else can
# produce one - fallback-decision is Phase 12 and deferred - so she is the sole
# fixture this whole phase runs against.

step "8.0  reset, so C is restricted and unacknowledged again"
curl -sS -X POST "$BASE/dev/reset" > /dev/null
curl -sS "$BASE/visits/v_2" \
  | jq -e '.restricted == true
           and .host_acked_at == null
           and (.allowed_zones | length) == 1
           and .ack_escalation_stage == null' > /dev/null
pass

step "8.1  a restricted visit refuses an empty acknowledgement (400)"
curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE/visits/v_2/arrival-ack" \
  -H 'Content-Type: application/json' -H 'X-Role: faculty' -d '{}' \
  | grep -q '^400$' || { printf 'empty ack on a restricted visit was not refused\n' >&2; exit 1; }
pass

step "8.2  capture C's QR and code6 BEFORE the acknowledgement"
QR_BEFORE=$(curl -sS "$BASE/passes/v_2" | jq -cS '.qr')
C6_BEFORE=$(curl -sS "$BASE/passes/v_2" | jq -r '.code6')
[ -n "$QR_BEFORE" ] || { printf 'no QR to compare\n' >&2; exit 1; }
pass

step "8.3  acknowledge with zones and a window -> restriction lifts"
curl -sS -X POST "$BASE/visits/v_2/arrival-ack" \
  -H 'Content-Type: application/json' -H 'X-Role: faculty' \
  -d '{"allowed_zones":["z_2","z_5"],"valid_to":"2026-08-22T21:00:00+05:30"}' \
  | jq -e '.restricted == false
           and .host_acked_at != null
           and (.allowed_zones | length) == 3
           and (.allowed_zones | index("z_1")) != null' > /dev/null
pass

step "8.4  THE PROOF - the QR is byte-identical after (SPEC section 9)"
QR_AFTER=$(curl -sS "$BASE/passes/v_2" | jq -cS '.qr')
C6_AFTER=$(curl -sS "$BASE/passes/v_2" | jq -r '.code6')
[ "$QR_BEFORE" = "$QR_AFTER" ] \
  || { printf 'QR changed when the window and zones changed - it must not\n' >&2; exit 1; }
[ "$C6_BEFORE" = "$C6_AFTER" ] \
  || { printf 'code6 changed - the pass was reissued, which it must not be\n' >&2; exit 1; }
pass

step "8.5  ack_escalation_stage is STILL null - nothing escalates in this build"
curl -sS "$BASE/visits/v_2" \
  | jq -e '.ack_escalation_stage == null and .ack_escalated_at == null' > /dev/null
pass

step "8.6  an unrestricted visit is acknowledged with no body at all"
curl -sS -X POST "$BASE/visits/v_4/arrival-ack" \
  -H 'Content-Type: application/json' -H 'X-Role: faculty' -d '{}' \
  | jq -e '.host_acked_at != null and .restricted == false' > /dev/null
pass

step "8.7  acknowledging a visit nobody has arrived on is refused"
curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE/visits/v_1/arrival-ack" \
  -H 'Content-Type: application/json' -H 'X-Role: faculty' -d '{}' \
  | grep -q '^400$' || { printf 'ack on a non-inside visit was not refused\n' >&2; exit 1; }
pass

step "8.8  security was told the restriction lifted"
curl -sS "$BASE/dev/notifications" \
  | jq -e 'any(.notifications[]; .recipient == "security_desk"
                                 and (.message | test("Restriction lifted")))' > /dev/null
pass

# --- Phase 9: zone scans and moving the meeting point ------------------------
# Runs on v_4, visitor D, who is inside with a pass in her hand after Phase 8.
# This is demo beat two: the QR must not change while everything around it does.

step "9.1  capture D's QR and code6 BEFORE anything moves"
QR9_BEFORE=$(curl -sS "$BASE/passes/v_4" | jq -cS '.qr')
C69_BEFORE=$(curl -sS "$BASE/passes/v_4" | jq -r '.code6')
[ -n "$QR9_BEFORE" ] || { printf 'no QR to compare\n' >&2; exit 1; }
pass

step "9.2  a scan at her meeting point is ok, and the host is told"
curl -sS -X POST "$BASE/scans/zone" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "$(curl -sS "$BASE/passes/v_4" | jq -c '{zone_code:"DEPT", payload:.qr.payload, signature:.qr.signature}')" \
  | jq -e '.ok == true and .result == "ok"
           and .scanned_zone == "DEPT - Department Office"
           and (.allowed_zones | length) == 2
           and .scan_event_id != null' > /dev/null
pass

step "9.3  a scan somewhere she is not cleared for is wrong_zone, still 200"
curl -sS -X POST "$BASE/scans/zone" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "$(curl -sS "$BASE/passes/v_4" | jq -c '{zone_code:"LIB", payload:.qr.payload, signature:.qr.signature}')" \
  | jq -e '.ok == false and .result == "wrong_zone" and .scan_event_id != null' > /dev/null
curl -sS "$BASE/dev/notifications" \
  | jq -e 'any(.notifications[]; .recipient == "security_desk"
                                 and (.message | test("Wrong-zone scan: visit v_4")))' > /dev/null
pass

step "9.4  the host moves the meeting to the library"
curl -sS -X PATCH "$BASE/visits/v_4/meeting-point" \
  -H 'Content-Type: application/json' -H 'X-Role: faculty' \
  -d '{"meeting_zone_id":"z_2"}' \
  | jq -e '.meeting_zone_id == "z_2"
           and (.allowed_zones | index("z_2")) != null
           and (.allowed_zones | index("z_5")) == null' > /dev/null
pass

step "9.5  THE PROOF - the QR is byte-identical after the move (SPEC section 9)"
QR9_AFTER=$(curl -sS "$BASE/passes/v_4" | jq -cS '.qr')
C69_AFTER=$(curl -sS "$BASE/passes/v_4" | jq -r '.code6')
[ "$QR9_BEFORE" = "$QR9_AFTER" ] \
  || { printf 'QR changed when the meeting point moved - it must not\n' >&2; exit 1; }
[ "$C69_BEFORE" = "$C69_AFTER" ] \
  || { printf 'code6 changed - the pass was reissued, which it must not be\n' >&2; exit 1; }
pass

step "9.6  the SAME unchanged QR now scans ok at the new zone"
curl -sS -X POST "$BASE/scans/zone" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "$(curl -sS "$BASE/passes/v_4" | jq -c '{zone_code:"LIB", payload:.qr.payload, signature:.qr.signature}')" \
  | jq -e '.ok == true and .result == "ok" and .meeting_zone == "LIB - Library"' > /dev/null
pass

step "9.7  and the OLD meeting point now flags"
curl -sS -X POST "$BASE/scans/zone" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "$(curl -sS "$BASE/passes/v_4" | jq -c '{zone_code:"DEPT", payload:.qr.payload, signature:.qr.signature}')" \
  | jq -e '.ok == false and .result == "wrong_zone"' > /dev/null
pass

step "9.8  the code6 fallback resolves at a checkpoint too"
curl -sS -X POST "$BASE/scans/zone" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "$(curl -sS "$BASE/passes/v_4" | jq -c '{zone_code:"MAIN", code6:.code6}')" \
  | jq -e '.ok == true and .result == "ok"' > /dev/null
pass

step "9.9  a zone scan on a visit nobody entered on is wrong_status, and silent"
N9_BEFORE=$(curl -sS "$BASE/dev/notifications" | jq '.notifications | length')
curl -sS -X POST "$BASE/scans/zone" -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "$(curl -sS "$BASE/passes/v_3" | jq -c '{zone_code:"DEPT", payload:.qr.payload, signature:.qr.signature}')" \
  | jq -e '.ok == false and .result == "wrong_status" and .scan_event_id != null' > /dev/null
N9_AFTER=$(curl -sS "$BASE/dev/notifications" | jq '.notifications | length')
[ "$N9_BEFORE" = "$N9_AFTER" ] \
  || { printf 'a wrong_status zone scan notified somebody - SPEC 14 says nobody\n' >&2; exit 1; }
pass

step "9.10  an unknown zone code is the one 400 on this endpoint"
curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE/scans/zone" \
  -H 'Content-Type: application/json' -H 'X-Role: guard' \
  -d "$(curl -sS "$BASE/passes/v_4" | jq -c '{zone_code:"CANTEEN", payload:.qr.payload, signature:.qr.signature}')" \
  | grep -q '^400$' || { printf 'unknown zone code was not rejected\n' >&2; exit 1; }
pass

step "9.11  every one of those scans is on the audit trail, zone id and all"
curl -sS "$BASE/visits/v_4/scans" \
  | jq -e '([.[] | select(.kind == "zone")] | length) >= 5
           and ([.[] | select(.result == "wrong_zone")] | length) >= 2
           and all(.[] | select(.kind == "zone");
                   .zone_id != null and .person_count_recorded == null)' > /dev/null
pass

printf '\nAll steps passed.\n'
