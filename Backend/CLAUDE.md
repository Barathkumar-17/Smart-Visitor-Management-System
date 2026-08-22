# Smart Visitor Management System — build protocol

**Read `SPEC.md` in full before building any phase.** It holds the flow, entities, verification rules, state machine, signing, endpoints, config and seed data. This file holds only how the build proceeds.

---

## At the start of every session

1. Read `SPEC.md`.
2. Read the **Current state** block below to see which phase is next.
3. Confirm which phase you are about to build, wait for my go-ahead, then build **that phase only**, give me the test script, and stop.

Never build a phase the Current state block does not list as next. When I approve a phase, update that block in the same turn.

---

## Current state

Rewrite these six lines in place every time. Do not add lines, remove lines, or reword the labels — a fresh session greps for them.

```
NEXT_PHASE: 8 — Arrival ack
PHASES_COMPLETE: 0,1,2,3,4,5,6
PHASES_IN_SCOPE: 0,1,2,3,4,5,6,8,9,10,13
ASSUMPTIONS_CONFIRMED: yes — SPEC §4 and §16 are settled
CONFIG_STATUS: unvalidated proposals — reviewed at Phase 13, where ACK_WINDOW and NO_SCAN_WINDOW become visible on the dashboards
LAST_UPDATED: 2026-08-22 — Phase 6 tested and approved
```

Keep this block accurate. It is the only thing telling a fresh session where the build actually is.

### Scope — phases 7, 11 and 12 are deferred

**This is deliberate, not an oversight. Do not build them, and do not build ahead into them.**

The demonstration is 3–4 minutes long. That is roughly six beats, so what gets built is decided by what fits on screen, not by what completes the product. `SPEC.md` describes the whole system and stays unchanged; the build stops short of it.

| Deferred | Why |
|---|---|
| 7 — Walk-in | A good feature and fully specified, but it costs Phase 12 as well and buys nothing showable in four minutes. Describe it from the architecture; don't demo it. |
| 11 — Scheduler | Escalation is the most impressive thing being dropped. First thing to add back if time allows. |
| 12 — Fallback authority | Only reachable through 7 or 11. Pointless alone. |

Two consequences to build around, not around which to improvise:

**Exception flags are never raised live.** Phase 13's dashboards read flags that Phase 11's jobs would normally set. Seeded visitors C, D, E and F carry those states from the start, so the dashboards look correct — but nothing becomes an exception during a session. Do not fake a job to compensate. Do not claim in any output that flags update automatically.

**`restricted` comes only from seed data.** The only path that sets it is `fallback-decision`, which is deferred. Seeded visitor C is a fallback-admitted restricted visit, and she is the fixture Phase 8's restriction-lifting test and the `restricted` dashboard flag both depend on. Do not add a shortcut endpoint to create one.

**Two honesty-panel counts return a permanent zero** — restricted admissions by approver, and walk-ins denied after escalation. Return them as zero, never omit them. See SPEC §10.

**Acknowledgement never escalates.** Phase 8 lets a host confirm availability, but silence does nothing, because the chasing job is Phase 11. `arrival-ack` still writes `host_acked_at` and still lifts restrictions. The `ack_escalation_stage` fields in SPEC §6 are still created and still default to null — they are simply never advanced.

The escalation chain, walk-in flow and fallback authority all remain in `SPEC.md` as written. They are the next work, not abandoned work.

### The demo path

Phases 6, 9 and 13 are the only ones that appear on screen. Everything else is scaffolding for them.

| Beat | Phase |
|---|---|
| Scan a QR at the gate, faces appear, visitor admitted | 6 |
| Host moves the meeting; the same unchanged QR now works at the new zone and flags the old one | 9 |
| Who is inside, the exceptions lists, the honesty panel | 13 |

When building those three, weight effort toward what is visible in a response: the faces and details in the gate-entry payload, the fact that the QR is byte-identical before and after the meeting-point change, and dashboards that are populated on first load. A correct endpoint that returns an unreadable blob fails the only test that matters here.

---

## How this is built

**Feature by feature, never all at once.** I build nothing; you write the code, I test it manually and push it, then we move on.

After each phase: stop. Do not begin phase N+1 while phase N is unverified by me.

Each phase must leave the app **runnable and demoable**. Never leave a phase where the server won't start or a live endpoint returns a stub.

### What to deliver each phase

1. A one-line summary of what this phase adds
2. The files created or changed
3. The working code
4. A **manual test script** — numbered `curl` commands I can paste in order, each with the exact response I should expect: status code, and the fields that matter. **From Phase 1 onward**, step 0 is always `POST /dev/reset` so a failed test doesn't leave state that breaks the next one — reset does not exist at Phase 0. Include **at least one failure case** per phase, not just the happy path.
5. **Append this phase's happy path to `smoke.sh`** — the cumulative script. Step 0 is `/dev/reset`, then every prior phase's happy path in order, then this phase's. **Every step asserts** — pipe the response through `jq -e` on a field that proves it worked, so a non-zero exit stops the script at the broken step. A script that only prints output is not a regression net; I will not spot a wrong field in eighty lines of JSON. I run the whole file, not just the new part.
6. **List anything in this phase that differed from `SPEC.md`.** If nothing differed, say so explicitly. Do not skip this item.
7. One line on what this phase's tests do **not** cover, and which later phase covers it
8. Then stop and wait

I run the tests. Do not write automated tests unless I ask for them.

---

## Build order

**Which spec sections each phase needs.** Read all of `SPEC.md` at session start regardless — this index is for knowing where to look back, not permission to skim.

| Phase | Sections |
|---|---|
| 0 Skeleton | §5, §12, §16.1, §16.6, §16.7, §16.8 |
| 1 Entities & repos | §5 storage seam, §6, §13, §16.5, §16.8 |
| 2 State machine | §8, §16.2, §16.6 |
| 3 Registration | §7, §10 Visitors, §16.5 |
| 4 Request & approval | §6 group size, §7, §10 Visits, §16.4 |
| 5 Signing | §9, §13 |
| 6 Gate entry | §6 ScanEvent, §10 Scans, §13, §14 |
| ~~7 Walk-in~~ | **deferred** |
| 8 Arrival ack | §4.4, §9, §10 arrival-ack |
| 9 Zone scans | §9, §10 Scans + meeting-point, §14 |
| 10 Exit & close-out | §4.3, §10 Scans + close, §14 |
| ~~11 Scheduler~~ | **deferred** |
| ~~12 Fallback~~ | **deferred** |
| 13 Dashboards | §10 Dashboards, §11 derive-at-read-time |

Phase numbers keep their original values so `SPEC.md`, this index and the decision log stay aligned. After Phase 6, the next phase is 8.

**Phase 0 — Skeleton.** FastAPI app that starts, `requirements.txt`, `.env.example`, config, clock, error handler, `require_role` reading `X-Role` per SPEC §16.1, empty store dicts, health endpoint, `/dev/advance-clock`. Also creates the full module tree from SPEC §16.8 — empty files with a docstring are fine — and `smoke.sh` with an asserting `/health` call. **`main.py` does not start the scheduler**; Phase 11 is deferred and `jobs/scheduler.py` stays empty.
*Verifies:* `pip install -r requirements.txt` then `uvicorn app.main:app --reload` starts clean, `/health` responds, advancing the clock shifts `clock.now()`, and a wrong `X-Role` gives 403 on a role-guarded test route.

**Phase 1 — Entities and repositories.** All seven dataclasses, the repository layer with its lock, `GET /zones`, `GET /hosts`, `GET /visitors/{id}`, `POST /dev/reset`. Seed only what this phase can produce: hosts, zones, visitors A and C — see SPEC §13.
*Verifies:* seeded data is readable through the API and reset restores it.

**Phase 2 — State machine.** `transition()` with the full legal-move table from SPEC §8, every domain exception in SPEC §8's table mapped to its HTTP code in one handler, and `POST /dev/transition` so the machine is drivable before any real endpoint exists.
*Verifies:* via `/dev/transition` against a seeded visit, every legal move succeeds and each specifically-illegal move in SPEC §8 returns 409. Everything later depends on this, so it must be solid before moving on.

**Phase 3 — Registration and verification.** `POST /visitors`, OTP send and verify, DigiLocker stub, `GET /photos/{ref}` per SPEC §16.5, the full rule set in SPEC §7 including override, expiry and re-vouch.
*Verifies:* a visitor can be registered, OTP-verified and DigiLocker-verified; DigiLocker correctly overrides an existing vouch; responses carry `photo_ref` and never base64; and an oversized photo is rejected.

**Phase 4 — Pass request and approval.** `POST /visits`, the faculty inbox, approve with vouch, reject, cancel. Companion cap per SPEC §6.
*Verifies:* a visit moves requested → approved → issued; an unverified visitor becomes vouched on approval; 4 companions is legal and 5 is rejected; reject works only while `requested` and cancel only while `issued`.

**Phase 5 — Pass signing.** `core/signing.py`, `GET /passes/{visit_id}`, revoke, `code6` generation with the uniqueness rule in SPEC §9. Extend the seed with visitor B, whose issued pass needs signing.
*Verifies:* a signed payload verifies, a tampered one fails, a revoked pass is rejected, visitor B appears seeded with a valid pass, and no two active passes share a `code6`.

**Phase 6 — Gate entry.** `POST /scans/gate/entry` with all five checks in order, ScanEvent on success and failure, photos and companion details in the response, mismatch flags, the already-inside rule.
Extend the seed with visitors C, D, E and F and their scan events, written through the same service the live path uses. C is the fallback-admitted restricted visit per SPEC §13 — without her, `restricted` is unreachable in this build.
*Verifies:* a valid pass admits; a tampered one returns **200 with `admitted: false`**, not an error; a second entry while inside is likewise 200 and refused; all three write ScanEvents; a plate mismatch still admits with `plate_mismatch: true`; and D, E and F appear seeded with the correct scan history. **This is the core demo path — it must be visibly working before anything else is added.**

**Phase 7 — Walk-in. DEFERRED — do not build.** See the scope section above. Specified in SPEC §3, §7 and §10 for when it is picked up.

**Phase 8 — Arrival acknowledgement.** `POST /visits/{id}/arrival-ack`, restriction lifting.
*Verifies:* against seeded visitor C, who is the only restricted visit in this build — acknowledging clears `host_not_acked`; a restricted visit without zones in the body returns 400; with zones it widens and clears `restricted`; and extending `valid_to` does **not** change the QR, per SPEC §9.
*Note:* silence does not escalate, because the chasing job is deferred Phase 11. Create the `ack_escalation_stage` fields and leave them null.

**Phase 9 — Zone scans.** `POST /scans/zone`, `PATCH /visits/{id}/meeting-point`.
*Verifies:* an allowed zone returns ok; a disallowed one returns `wrong_zone` with a 200 and a notification; and changing the meeting point takes effect on the **next scan using the same unchanged QR**.

**Phase 10 — Exit and close-out.** `POST /scans/gate/exit` with count-out per SPEC §10, `POST /visits/{id}/close`.
*Verifies:* a full exit sets `exit_at` and closes the visit; a short count keeps it `inside` with `partial_exit`; close-out resolves it; and the visitor leaves `/dashboard/inside`.

**Phase 11 — Scheduler. DEFERRED — do not build.** See the scope section above. Specified in SPEC §11. This is the first thing to add back if time allows.

**Phase 12 — Fallback authority. DEFERRED — do not build.** See the scope section above. Only reachable via Phase 7 or 11, so it cannot be built alone.

**Phase 13 — Dashboards.** Inside, exceptions, honesty. Every flag derived at read time using the exact definitions in SPEC §11 — no other arithmetic.
*Verifies:* the seeded records appear under the correct flags with no stored flag fields anywhere; every list is populated on first load after `/dev/reset`; C shows `restricted`, D shows `host_not_acked`, E shows `wrong_zone_scan`, F shows `overstaying`; and the honesty panel returns every field, including honest zeros for restricted admissions and denied walk-ins.
**Also review the config windows here.** `ACK_WINDOW` and `NO_SCAN_WINDOW` become visible for the first time — they decide whether D and E appear as exceptions at all. SPEC §12's values are unvalidated proposals; report anything that flags too eagerly or not at all.

If a phase needs something from a later phase, say so and ask rather than building ahead.

---

## Keeping the spec accurate

`SPEC.md` is the source of truth. It goes stale if decisions made in chat are not written back into it, and a stale spec is worse than no spec — the next session will confidently use the old value.

- **If anything I say during a phase contradicts `SPEC.md`, stop and say so.** Name the section that is now stale and ask whether to update it, before continuing. You read the whole spec every session; I am looking at one file of code. You are better placed to catch the conflict than I am.
- **When I confirm a change, update `SPEC.md` in the same turn** as the code change. Never carry a new value only in conversation.
- **Log every change** in the decision log below — one line, phase number, old value and new.

The end-of-phase spec check is item 6 of the phase deliverables above, not an optional habit.

The two places drift causes real damage: the **config values** in SPEC §12, where a wrong number produces plausible but incorrect behaviour with no error at all; and the **decisions** in SPEC §4, which quietly change the moment I answer a question in chat without updating the file.

---

## Decision log

Newest at the bottom. Format: `[phase] what changed — was X, now Y`

- `[pre-build]` Initial specification written.
- `[pre-build]` Added `POST /visits/{id}/cancel` and terminal state `cancelled` — the `issued → rejected` row had no endpoint behind it. Distinct from security revoke.
- `[pre-build]` Expiry job now skips visits mid-escalation — jobs 1 and 5 both act on `requested` and collided.
- `[pre-build]` Test scripts start with `/dev/reset` from Phase 1 onward — reset does not exist at Phase 0.
- `[pre-build]` Seed data staged across phases 1, 5 and 6 — was written as if all six visitors could be created at Phase 1.
- `[pre-build]` `arrival-ack` now takes optional zones; required for fallback-admitted visits, which have no original zones to restore.
- `[pre-build]` Config proposal caveat moved from this log into the Current state block, with the review attached to Phase 11's verification.
- `[pre-build]` Added four escalation-stage fields to Visit — the job 1 / job 5 precedence rule had no field behind it and was not mechanically checkable.
- `[pre-build]` Added exception-to-HTTP-code table in SPEC §8. Scan failures return 200 carrying the outcome, never an error status, so a ScanEvent can never be lost to an early exit.
- `[pre-build]` Added `plate_mismatch`, `count_mismatch` and `person_count_recorded` to ScanEvent — the mismatch flag §10 requires had nowhere to live.
- `[pre-build]` Removed `valid_to` from the signed payload — `arrival-ack` and `fallback-decision` both change the window, which would have invalidated the signature and forced a reissue.
- `[pre-build]` `arrival-ack` simplified: only `fallback-decision` sets `restricted`, so the host-approved branch described a state nothing produced. Zones now always required when restricted.
- `[pre-build]` Added `POST /dev/transition` — Phase 2 had no way to drive the state machine before Phase 4's endpoints existed.
- `[pre-build]` `require_role` reads an `X-Role` header, defaulting to `admin` when absent. Previously had no input contract at all.
- `[pre-build]` Added `id_hash` and `id_last4` to Visitor — three sections forbade returning a field no entity had.
- `[pre-build]` Vouch expiry is derived at read time, not a job and not a stored downgrade.
- `[pre-build]` Added SPEC §14, six decided edge cases the model would otherwise invent answers to.
- `[pre-build]` `/visitors/lookup` must be declared before `/visitors/{id}` or FastAPI shadows it.
- `[pre-build]` Added SPEC §16 — eight contracts every phase assumed and none stated.
- `[pre-build]` `admin` explicitly satisfies every role check, and an absent header is `admin`. **Flagged in SPEC §16.1 as a production blocker, not just a stub** — as written, any unauthenticated caller reaches every endpoint.
- `[pre-build]` Defined the `actor` string format for `transition()` — was typed `str` with no contract.
- `[pre-build]` Department escalation recipient defined, and made non-stalling when a department has one host.
- `[pre-build]` `person_count_expected` derivation stated; `companions[]` and `person_count` are mutually exclusive.
- `[pre-build]` Photos: refs out, base64 in, 2 MB cap, new `GET /photos/{ref}` at Phase 3.
- `[pre-build]` Error envelope shape fixed; FastAPI's 422 keeps its native shape.
- `[pre-build]` Clock is aware UTC; `WORKING_HOURS` evaluated in `LOCAL_TZ`; advance-clock deliberately reroutes fallback.
- `[pre-build]` Module tree fixed at SPEC §16.8, created empty at Phase 0.
- `[pre-build]` Cumulative `smoke.sh` added to phase deliverables — thirteen phases had no regression net.
- `[pre-build]` Current state block replaced with a fixed five-line greppable template.
- `[pre-build]` Build scope cut to phases 0–6, 8, 9, 10 and 13. Phases 7 (walk-in), 11 (scheduler) and 12 (fallback authority) deferred — the demonstration is 3–4 minutes and they buy nothing showable in that time. SPEC.md is unchanged and still describes the whole system.
- `[pre-build]` Consequences of that cut recorded in the scope section: exception flags come only from seeded state, and acknowledgement never escalates. Neither is to be faked.
- `[pre-build]` `code6` uniqueness defined — unique among active passes, regenerate on collision, raise rather than guess on a multi-match. Was undefined, and a collision would silently admit the wrong visitor.
- `[pre-build]` Derived flag definitions table added to SPEC §11 — `host_not_acked` and the rest had no stated arithmetic, and Phase 13 would have invented it.
- `[pre-build]` "Today" defined as the LOCAL_TZ calendar day everywhere; `GET /visits?date=` filters `scheduled_at`.
- `[pre-build]` Seeded visitor C repurposed from an orphaned walk-in into a fallback-admitted restricted visit — makes `restricted` reachable with Phase 12 deferred, and fixes Phase 8 having nothing to test against.
- `[pre-build]` Honesty panel always returns every field, zero where the build cannot produce a value.
- `[pre-build]` `requirements.txt`, `.env.example` and the run command added to SPEC §16.8; `main.py` explicitly does NOT start the scheduler while Phase 11 is deferred.
- `[pre-build]` CONFIG_STATUS review moved from Phase 11 to Phase 13, where ACK_WINDOW and NO_SCAN_WINDOW actually become visible.
- `[pre-build]` Phase 10's simplification offer removed — it was the only soft instruction in the document and it landed on `partial_exit`, which both dashboards show.
- `[pre-build]` `smoke.sh` steps must assert with `jq -e`; a printing-only script is not a regression net.
- `[pre-build]` End-of-phase spec check promoted from prose into the numbered phase deliverables.
- `[0]` `/health` returns a body — was unspecified in SPEC, now `{status, now_local, clock_offset_minutes, now}`. Phase 0's verification needs the clock visible through the API and no other endpoint exposes time.
- `[0]` Clock reads gained readable output — was ISO aware-UTC only, now `clock.now_local()` and `clock.readable()` alongside it. `/health` and `/dev/advance-clock` return both. The ISO `now` is unchanged and remains canonical per SPEC §16.7; the added fields are display only and must never be parsed. `now_local()` also serves Phase 11's `WORKING_HOURS` check and Phase 13's "today" comparisons.
- `[0]` `require_role` rejects an unrecognised `X-Role` with `NotPermitted` — SPEC §16.1's table has no row for it. Treating an unknown role as valid would be worse.
- `[0]` `smoke.sh` preflights `jq` and the server, failing with a readable message instead of a raw curl error.
- `[1]` Added an eighth dataclass, `Notification` — SPEC §6 lists seven, but §5 requires the notification stub to append to a `notifications` list and `notification_repo.py` needs a shape to store. §6 never named it; nothing there is stale.
- `[1]` `Visitor.tier` is a derived property, not a stored field — §6 lists it as a field *and* requires computing it everywhere. A property satisfies both and makes a stale tier unreadable.
- `[1]` `reference.py` reads through repositories with no service layer — `/zones` and `/hosts` have no business rules, and §15 explicitly contemplates a router reaching storage through a repository. `/visitors/{id}` does go through `visitor_service`, which Phase 3 fills.
- `[1]` Seeded visitors carry `photo_ref = null` — setting one needs the Phase 3 storage stub, and a literal ref would be a dangling pointer that `GET /photos/{ref}` would 404 on. **SPEC §13's staging table names Phases 1, 5 and 6 only; the seed also needs extending at Phase 3.**
- `[1]` Seeded visitor A's `id_hash`/`id_last4` are set directly, though the DigiLocker stub is Phase 3 — CLAUDE.md requires A at Phase 1 and §13 defines her as DigiLocker-verified. Inert data, unlike a photo ref, which would be a broken link.
- `[1]` Seeded ids are deterministic across `/dev/reset` — counters reset before reseeding, so z_1..z_5, h_1..h_3, vr_1, vr_2, v_1, v_2 are stable. Test scripts depend on it.
- `[2]` An unknown target status returns 409 `IllegalTransition`, not 400 — SPEC §8 was silent. One rule: anything the legal table rejects is a 409, typo or not. `/dev/transition` types `to_status` as a plain `str` so FastAPI's 422 cannot mask that path.
- `[2]` `transition()`'s `actor` is logged, never stored — no entity in §6 has a field for it, so the server log is the audit trail. `main.py` gained `logging.basicConfig(INFO)` because uvicorn leaves root at WARNING and was silently dropping every successful transition, keeping only failures.
- `[2]` SPEC §13 updated — seed is now written at phase 1 and extended at phases **3**, 5 and 6. Photos need the Phase 3 storage stub; a ref written earlier would be a dangling pointer.
- `[2]` `visit_service` derives terminal statuses from the transition table and raises at import if they disagree with `visit_repo.TERMINAL_STATUSES`, which `pass_repo` needs for the code6 rule. Repos cannot import services, so the two sets stay separate but cannot drift.
- `[3]` Added `POST /dev/vouch` — prototype-only, not in SPEC §10's dev list. §7 bans a standalone vouch endpoint on the PRODUCTION surface; at Phase 3 nothing else can create a vouch, so the §7 override rule was untestable. Same precedent as `/dev/transition`. Delete when Phase 4's approve makes it redundant.
- `[3]` `GET /visitors/lookup` built at Phase 3 — it is in §10's Visitors block (Phase 3's assigned section) though it primarily serves the deferred walk-in flow. Building it now also locks in the declare-above-`/{id}` ordering permanently.
- `[3]` `MAX_PHOTO_BYTES` added to `core/config.py` — §12's table omits it, but §16.5 fixes the 2 MB cap and §12 forbids hardcoding limits in services.
- `[3]` `photo` added to `ids.PREFIXES` so refs are `photo_{n}` per §16.5 and are deterministic across `/dev/reset`.
- `[3]` `GET /photos/{ref}` lives on a second router inside `routers/visitors.py` — §16.8 fixes the router file list, so it gets a prefix-free `APIRouter` rather than a new module.
- `[3]` `POST /visitors/{id}/otp/send` returns the code — §10 does not say what it returns, and a demo has no phone to read it off. A real gateway returns a receipt and the field disappears.
- `[3]` DigiLocker override RETAINS `vouched_by_host_id` and `verified_until` — §7 requires both queryable so administration can trace who vouched for a visitor who later causes problems. Erasing them on upgrade would destroy that record.
- `[3]` `POST /visitors` requires only `name` and `phone`; address, email and photo are optional. §3 describes a full registration, but blocking a partial record adds a rule with no safety value.
- `[3]` `.gitignore` added at the repository root and 35 tracked `__pycache__` files untracked. Not a SPEC matter; recorded because it changes what a fresh clone contains.
- `[4]` `approve` does NOT create a Pass record — §10 ends approve with "pass generated", but a Pass needs the signature and `code6` only Phase 5 can produce. The visit reaches `issued`; Phase 5 fills the pass in behind it.
- `[4]` `allowed_zones` and `meeting_zone_id` take zone IDS, not codes. §8 mentions an "unknown zone code" but `meeting_zone_id` is plainly an id and the seed uses ids; mixing both in one body would be worse. Scan endpoints still take CODES, since a scanner reads a code.
- `[4]` The meeting zone is auto-added to `allowed_zones` on approve — approving someone to a meeting point they may not enter would flag a wrong-zone scan for doing exactly what they were told.
- `[4]` Reject and cancel reasons are stored in `approval_reason`. SPEC does not say where; `closed_reason` has a constrained vocabulary in §10 reserved for close-out.
- `[4]` `GET /visits/{id}/scans` built at Phase 4 returning an empty list — it is in §10's Visits block, and an honest empty array beats a 404 until Phase 6 writes the first ScanEvent.
- `[4]` Naive datetimes are rejected with 422 by a Pydantic validator on `scheduled_at`, `valid_from` and `valid_to` — §16.7 requires an offset, and a naive value would silently shift a window by 5.5 hours in this deployment.
- `[5]` `POST /dev/vouch` deleted — Phase 4's `approve` is the real vouch path, so the temporary route added at Phase 3 is redundant and §7 bans a standalone vouch endpoint. Nothing outward-facing changed; it was never in the schema.
- `[5]` `HMAC_SECRET` keeps its built-in development default so the app runs with no `.env`, but startup logs a warning whenever that default is in use, and `.env.example` now carries an obvious placeholder rather than a working value. Confirmed in chat.
- `[5]` `resolve_scan()` treats a valid signature over a stale nonce as `bad_signature` — SPEC is silent, and admitting on a superseded QR after a reissue would be worse than refusing.
- `[5]` `issue_pass` is idempotent: a visit that already has a pass gets the same one back, never a reissue, so nothing can silently invalidate a QR a visitor already carries.
- `[5]` Visitor B's seed runs through the real `apply_vouch`, `transition` and `issue_pass` rather than being written by hand — §13 requires that of scan events, and the same reasoning applies to her pass.
- `[5]` `smoke.sh` rewritten rather than appended: seeding B claims `vr_3`/`v_3` so every later id shifted, and the Phase 3 vouch step used the now-deleted `/dev/vouch`. The vouch and DigiLocker-override assertions moved into the Phase 4 block, where `approve` provides them properly.
- `[5]` README gained Running, What is built, Security and Documents sections; the two production blockers (open auth, default HMAC secret) are written up there in full.
- `[6]` Seeded entries for C, D, E and F run through the real `gate_entry` with the clock temporarily rewound, restored in a `finally`. Setting `entry_at` by hand would mean seeded records did not come from the live code path, which §13 forbids.
- `[6]` E's and F's zone events call `scan_service._record()` — the shared writer both live paths use. The logic that DECIDES `wrong_zone` arrives with the endpoint at Phase 9; splitting it there keeps Phase 9's rule out of Phase 6.
- `[6]` The gate window check is skipped when `valid_from`/`valid_to` are null — a visit forced to `issued` through `/dev/transition` never went through approve and has no window to violate.
- `[6]` `vehicle_plate_in` is overwritten with the plate that ACTUALLY arrived, so Phase 10's exit compares against what entered. The declared plate is captured first for the response and survives on the ScanEvent as `plate_mismatch`.
- `[6]` Bug found in testing: `vehicle.expected` echoed the presented plate because the record was overwritten before the response was built, so a mismatch displayed two identical values. Fixed by capturing the expected plate first.
