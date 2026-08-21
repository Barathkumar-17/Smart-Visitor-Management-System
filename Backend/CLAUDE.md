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
NEXT_PHASE: 0 — Skeleton
PHASES_COMPLETE: none
PHASES_IN_SCOPE: 0,1,2,3,4,5,6,8,9,10,13
ASSUMPTIONS_CONFIRMED: yes — SPEC §4 and §16 are settled
CONFIG_STATUS: unvalidated proposals — reviewed at Phase 13, where ACK_WINDOW and NO_SCAN_WINDOW become visible on the dashboards
LAST_UPDATED: not yet started
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
