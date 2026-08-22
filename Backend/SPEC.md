# SPEC — Smart Visitor Management System, backend

The stable specification. Entities, rules, endpoints, config. Changes rarely.
Build order and phase protocol live in `CLAUDE.md`.

---

## 1. Context

Backend for a **campus visitor management system** for MIT Campus. This is a **working prototype with no database** — all state lives in memory and resets on restart. That is intentional. The goal is a working API surface demonstrating the full visitor lifecycle, not persistence.

It replaces the paper register at the gate. It creates **accountability, not prevention**. Entry can genuinely be decided at the gate, because there is a barrier and a guard there. Inside the campus there are no guards at every door, so checkpoint scans only record and alert — they can never block anyone. Do not build anything that implies blocking beyond the gate.

**All scoring is out of scope.** No trust level, no attention score, no risk ranking. Exceptions are plain boolean flags and lists. A later phase will add scoring on top of the scan history this build produces, so record events thoroughly but never interpret them.

## 2. Stack

- **FastAPI** (Python 3.11+), async
- **Pydantic v2** for request/response schemas
- **Python dataclasses** for in-memory entities
- **APScheduler** for background jobs
- `hmac` + `hashlib` from the standard library for pass signing

No SQLAlchemy. No SQLite. No ORM. No migrations. No `DATABASE_URL`.

---

## 3. The flow

**Two ways in.**

*Pre-registered:* a person registers once — name, address, mobile, email, live photo — and is verified either by **DigiLocker consent** (permanent) or by a **host's vouch** at approval time (100 days). They then request a pass for a specific visit.

*Walk-in:* the guard creates a **temporary registration** at the gate — name, phone confirmed by OTP, live photo, vehicle. This holds the visit but confers no standing. A returning walk-in is found by phone and skips the form. Upgrading to real standing means registering properly later; the phone number links the records.

**Pass request.** Date and time, host and department, vehicle, and who is coming. Up to 4 companions are each registered and linked with a photo; beyond that a headcount is used. **One QR covers the whole group either way** — there are no per-companion passes.

**Approval.** Goes to the named host. If the visitor is unverified this is where the host vouches. On approval a signed QR and a 6-digit fallback code are issued.

If the host is silent, escalation runs — department, then the fallback authority. **Walk-ins escalate on shorter windows** because a person is standing at the gate. The fallback approver sees the photo captured at the gate, must give a reason, and can either deny (terminal state `denied`) or **admit with the meeting point only and a short window**, recorded throughout as an unacknowledged-host entry.

**Gate entry.** The guard scans. The response shows every linked person's photo and details, the vehicle, and for large groups the expected headcount against which the guard enters the actual count. Mismatches are flagged and recorded, never blocked. A visitor already `inside` on another pass is rejected and recorded.

**Arrival acknowledgement.** The host is notified and asked to confirm availability. **The visitor enters and waits — they are never held at the gate.** No acknowledgement within the window escalates to department, then the fallback authority, then the visit closes as `host_unavailable` with security notified. If the host acknowledges a restricted visit, the restriction lifts and normal zones and window apply.

**Inside campus.** Checkpoint scans confirm arrival; they do not gate the meeting. A scan at a zone not on the allowed list notifies security without blocking. A host elsewhere grants that checkpoint from their dashboard — the QR is never reissued, because the zone list is read fresh from the record at every scan. No checkpoint scan within 30 minutes of entry alerts security; the absence of a scan is the signal.

**Exit.** One scan. Photos shown again, plate compared against entry, and the guard enters how many are leaving. Fewer out than in keeps the visit `inside` with a partial-exit flag that security sees, resolved at end-of-day close-out. Otherwise the visit closes.

---

## 4. Decisions

Settled. Build to them without asking. If any conflicts with something you are building, flag it and stop; otherwise proceed.

1. Fallback authority is the **admin block during working hours, security outside them**.
2. The fallback approver **sees the gate photo and must supply a reason**.
3. **End-of-day close-out** by the guard resolves a partial-exit visit.
4. A restricted visit **widens when the host acknowledges**. Only `fallback-decision` ever sets `restricted = True`, so a restricted visit has no host-set zones to restore — the host supplies them at `arrival-ack`. See §10.

---

## 5. Architecture

```
routers/       HTTP only — parse, require_role, call a service, return a schema.
services/      All business rules. The state machine lives here.
               Both routers and scheduler jobs call this layer.
repositories/  The only code that knows storage is a dict.
store/         Dicts, entity dataclasses, id counters, seed loader.

core/config.py    settings and all tunable windows
core/clock.py     now() — the single source of current time
core/security.py  require_role dependency
core/signing.py   sign_pass / verify_pass
core/errors.py    domain exceptions + one FastAPI exception handler
jobs/scheduler.py APScheduler setup and jobs
integrations/     stubs
schemas/          Pydantic models, separate from entities
```

Keep Pydantic schemas separate from dataclass entities. `id_hash` must never appear in any API response.

### Storage seam

All state lives in `store/memory.py` as dicts keyed by id, with an auto-incrementing counter per collection:

```python
visitors, companions, hosts, zones, visits, passes = {}, {}, {}, {}, {}, {}
scan_events, notifications = [], []
```

**Services must never touch these dicts.** Every read and write goes through a repository function — `visit_repo.get(id)`, `visit_repo.list_by_host(host_id, status)`, `visit_repo.save(visit)`. Repositories are the only code that knows storage is a dict; swapping in PostgreSQL later touches that folder alone. Write their signatures as if they were hitting a database.

Guard any mutation touched by both the API and the scheduler with a `threading.Lock` in the repository layer.

### Stubs — signature correct, implementation fake

- `integrations/digilocker.py` — returns a fake ID hash, fake last-4, tier `verified`
- `integrations/otp.py` — `send_otp(phone)` logs and returns a code; `verify_otp(phone, code)` accepts any 6 digits
- `integrations/notifications.py` — logs recipient and message, appends to the `notifications` list so a demo can show what was sent
- `integrations/storage.py` — keeps the base64 photo in memory, returns a fake ref
- **Auth** — `require_role(role)` reads an **`X-Role` header** (`guard` | `faculty` | `security` | `admin` | `visitor`) and returns a hardcoded user of that role. If the header is absent, treat the caller as `admin` so early phases and dev endpoints are not blocked. If present but not the required role, raise `NotPermitted` (403). Real JWT later replaces the header read and nothing else.
- **Offline mode** — out of scope. The client caches and syncs; the backend only needs `entered_offline` (bool) and `authorised_by` (free text) on the visit, both settable at entry.

---

## 6. Entities

**Visitor** — id, name, address, phone, phone_verified, email, photo_ref, tier (`temporary` | `verified`), verified_by (`digilocker` | `vouch` | null), id_hash, id_last4, vouched_by_host_id, verified_until, is_permanent, created_at

`id_hash` and `id_last4` are set only by the DigiLocker stub. `id_hash` must never appear in any API response — see §15. `id_last4` may be shown.

**Vouch expiry is derived, never stored as a state change and never a scheduled job.** A visitor is verified when `is_permanent` is true, or when `verified_until` is in the future per `clock.now()`. Everywhere tier is read, compute it — do not write a visitor back to `temporary`.

**Companion** — id, visit_id, name, photo_ref

**Host** — id, name, department, email, phone

**Zone** — id, code, name

**Visit** — id, visitor_id, host_id, purpose, scheduled_at, vehicle_plate_in, vehicle_plate_out, person_count_expected, person_count_in, person_count_out, meeting_zone_id, allowed_zones, valid_from, valid_to, status, origin (`pre_registered` | `walk_in`), restricted, approved_by, approval_reason, entry_at, host_acked_at, exit_at, closed_reason, entered_offline, authorised_by, approval_escalation_stage (null | `department` | `fallback` | `exhausted`), approval_escalated_at, ack_escalation_stage (null | `department` | `fallback` | `exhausted`), ack_escalated_at, created_at

**Pass** — id, visit_id, code6, signature, nonce, issued_at, revoked_at

**ScanEvent** — id, visit_id, zone_id (null for `entry` and `exit` kinds), kind (`entry` | `zone` | `exit`), result (`ok` | `wrong_zone` | `expired` | `bad_signature` | `wrong_status` | `revoked` | `already_inside`), plate_mismatch (bool), count_mismatch (bool), person_count_recorded (null for `zone` kind), created_at

`ScanEvent` is the audit trail and the most important collection here. Write one for **every** scan attempt, successful or not — a later scoring phase reads this history, and its completeness now determines whether that phase is possible.

`result` describes whether the scan itself succeeded. **Mismatches are recorded alongside it, not inside it:** a gate entry where the plate differs from the pass is still `ok`, with `plate_mismatch = True`. Collapsing the two would make a mismatch indistinguishable from a rejection, and §10 forbids ever blocking on one. `person_count_recorded` stores the count the guard actually entered at entry and exit, which is what the partial-exit rule in §10 compares.

### Group size rule

`MAX_LINKED_COMPANIONS = 4` counts **companions only, excluding the accountable visitor**. A group of 5 total is legal as 1 visitor + 4 companions. From 6 total upward, the accountable visitor is still registered but the others collapse to `person_count_expected` with no Companion records.

### Escalation state

Two independent chains, tracked separately. The **approval chain** (job 1) runs while `requested`; the **acknowledgement chain** (job 2) runs while `inside`. They never overlap, but they are kept in separate fields so a completed approval chain cannot be mistaken for an active acknowledgement one.

Each stage field advances `null → department → fallback → exhausted` and never moves backwards. `exhausted` means the chain finished without a decision — for job 1, the fallback authority was notified and did not respond; for job 2, it is the point at which the visit closes as `host_unavailable`. The matching `*_escalated_at` records when the current stage was entered, so the next window is measured from it.

**Advancing a stage field never changes status.** When the acknowledgement chain reaches `exhausted`, the visit is closed by calling `transition()` — the stage field records what was sent, the transition does the closing. Do not close a visit as a side effect of advancing a stage.

These two pairs of fields are the **one exception** to "derive flags at read time" in §11: they record what was sent, not what is currently true, and cannot be recomputed after the fact.

---

## 7. Verification rules

- DigiLocker → `verified`, `is_permanent = True`. **Overrides an existing vouch at any point.**
- Host vouch at approval, pre-registered visit → `verified`, `verified_until = now + VOUCH_VALIDITY_DAYS`
- Host vouch at approval, walk-in → valid for **that visit only**, no standing granted
- Expiry is **derived, not a job**: a vouched visitor is verified while `verified_until > clock.now()` and `temporary` after. Nothing writes the tier back. **Any** host can vouch again at the next approval for a fresh period.
- **Vouching happens only through a host, only at approval.** No standalone admin vouch endpoint; nobody can be pre-cleared ahead of a visit.
- `verified_by` and `vouched_by_host_id` are queryable, so administration can trace who vouched for a visitor who later causes problems.

---

## 8. State machine

Implemented as one function in `services/visit_service.py`:

```python
def transition(visit: Visit, to_status: str, actor: str) -> Visit
```

**Every** status change goes through it — routers, scan service, scheduler jobs, close-out. No code outside this function assigns `visit.status`. Illegal moves raise `IllegalTransition`.

### Legal transitions

| From | To | Trigger |
|---|---|---|
| requested | approved | Host approves |
| requested | rejected | Host rejects |
| requested | denied | Fallback authority denies after escalation |
| requested | expired | scheduled_at passed, never actioned |
| approved | issued | Pass generated — automatic, same call as approve |
| issued | inside | Gate entry scan succeeds |
| issued | expired | valid_to passed, never scanned in |
| issued | cancelled | Host cancels an issued pass before arrival |
| inside | closed | Exit scan with full count, or end-of-day close-out |
| inside | host_unavailable | Acknowledgement escalation exhausted |

Everything not in this table is illegal.

Specifically illegal, because they are plausible guesses:

- `approved → rejected` — once issued, use revoke, not a status change
- `inside → denied` — denial only happens before entry
- `inside → expired` — overstay is derived, never a status
- `closed → anything` — terminal
- `host_unavailable → closed` — already terminal; it *is* the closure
- Any transition into `requested`

### Terminal states — six

`rejected` (host declined the request before approving), `cancelled` (host called off a visit they had already approved), `denied` (turned away at the gate after escalation failed), `host_unavailable` (nobody responded while the visitor was inside), `expired` (a pass never scanned in), `closed` (normal exit or close-out).

`cancelled` is the host's own action and is distinct from a security **revoke**, which sets `revoked_at` on the pass without changing visit status.

### Domain exceptions and HTTP codes

Defined in `core/errors.py`, mapped in the single handler required by §15. Routers raise none of these directly; services do.

| Exception | Code | Raised when |
|---|---|---|
| `NotFound` | 404 | Any id that does not resolve — visitor, visit, host, zone, pass |
| `IllegalTransition` | 409 | `transition()` rejects a move not in the legal table |
| `InvalidRequest` | 400 | Body is structurally valid but breaks a domain rule — missing reason on `fallback-decision`, missing zones on a fallback-admitted `arrival-ack`, unknown zone code |
| `CompanionLimitExceeded` | 400 | More than `MAX_LINKED_COMPANIONS` companions supplied |
| `NotPermitted` | 403 | `require_role` rejects the caller |
| `VisitorAlreadyInside` | 409 | Creating a visit or walk-in for a visitor already inside elsewhere |

Pydantic validation failures are FastAPI's own 422 and are not domain exceptions.

**Scan failures are not exceptions.** Every scan endpoint returns **200** carrying the outcome, including bad signature, revoked pass, wrong status, expired window and already-inside. A scan that raised would tempt a caller to abandon the request before the ScanEvent is written, and §15 requires the event either way. The response carries an explicit boolean — `admitted` at gate entry, `accepted` at exit, `result` at zone scans — and the ScanEvent carries the matching result value from §6.

Note the deliberate split on already-inside: `VisitorAlreadyInside` at 409 applies to **creating** a visit for someone already inside; the `already_inside` scan result at 200 applies to **scanning them in**. Same fact, two paths, two different responses.

`expired` is distinct from **overstay**, which is a derived flag on a visit that *is* inside and is never a status.

---

## 9. Pass signing

In `core/signing.py`:

- Payload carries **only** `visit_id` and `nonce`. Never visitor data, and **never the time window**.
- `sign_pass` and `verify_pass` both build their canonical string from one shared private `_canonical(payload)` helper. If the two sides serialise differently — key order, timestamp format — every scan fails confusingly.
- `hmac.compare_digest`, never `==`. HMAC-SHA256, secret from `.env`.
- **Neither the zone list nor `valid_to` is in the payload.** Both are read fresh from the visit record at every scan. This is what lets a host change the meeting point via `meeting-point`, and change or extend the window via `arrival-ack`, without ever reissuing the QR. A payload carrying `valid_to` would be invalidated by both of those endpoints — the QR is a pointer, not a copy of the record.
- Offline verification is unaffected: the tablet caches the pass record alongside the key, verifies the signature locally, and reads the window and zones from its cached copy.

### The 6-digit code

`code6` is the fallback lookup for basic phones, accepted by every scan endpoint in place of a signed payload. It must therefore identify exactly one visit.

**Unique among active passes.** A pass is active while `revoked_at` is null and its visit is not in a terminal state (`rejected`, `cancelled`, `denied`, `host_unavailable`, `expired`, `closed`). Generate a random 6-digit code, check it against active passes, regenerate on collision. Codes are freely reused once the owning visit is terminal — a million-wide space with a retry loop needs no more than that.

**A lookup that matches more than one active pass is a bug, not a case to handle.** If uniqueness is enforced at generation it cannot happen; if it does, raise rather than picking one. Silently admitting the wrong visitor is the worst failure this system has.

---

## 10. Endpoints

Every scan endpoint accepts **either** a signed payload **or** the 6-digit code — same service path, two lookups.

### Visitors

**Declare `/visitors/lookup` BEFORE `/visitors/{id}`** in the router, or FastAPI matches `lookup` as an id and the endpoint is unreachable.

```
POST   /visitors                          Register: name, address, phone, email, photo.
                                          Creates tier `temporary`.
GET    /visitors/lookup?phone=            role: guard — returning walk-in skips the form.
                                          MUST be declared before /visitors/{id}.
POST   /visitors/{id}/otp/send            Sends OTP to the phone.
POST   /visitors/{id}/otp/verify          Sets phone_verified.
POST   /visitors/{id}/digilocker          Consent stub → verified, permanent, sets id_hash
                                          and id_last4. Overrides any existing vouch.
GET    /visitors/{id}                     Never returns id_hash. id_last4 is fine.
```

### Visits

```
POST   /visits                            Pre-registered pass request: host_id, purpose,
                                          scheduled_at, vehicle_plate, companions[] (max 4)
                                          or person_count. Status `requested`.
POST   /visits/walk-in                    role: guard
                                          Creates or finds visitor by phone, creates a
                                          temporary registration if new, opens a visit with
                                          origin `walk_in`. Returns immediately.
GET    /visits/{id}
GET    /visits?host_id=&status=&date=     role: faculty — the inbox
POST   /visits/{id}/approve               role: faculty
                                          Body: meeting_zone_id, allowed_zones[], valid_from,
                                          valid_to, vouch (bool).
                                          If vouch, applies section 7 rules.
                                          requested → approved → issued, pass generated,
                                          notification fired.
POST   /visits/{id}/reject                role: faculty — body: reason → `rejected`
                                          Only valid while `requested`.
POST   /visits/{id}/cancel                role: faculty — body: reason → `cancelled`
                                          Calls off a visit already approved and issued.
                                          Valid only while `issued`, never once `inside`.
                                          Notifies the visitor.
POST   /visits/{id}/fallback-decision     role: admin | security
                                          Body: decision (`deny` | `admit_restricted`),
                                          reason (REQUIRED — InvalidRequest if absent).
                                          deny → `denied`.
                                          admit_restricted → uses the SAME transitions as
                                          approve (requested → approved → issued), with
                                          actor = the fallback authority rather than the
                                          host. Issues a pass with allowed_zones =
                                          [meeting_zone] only and a RESTRICTED_VISIT_DURATION
                                          window, sets restricted = True and approved_by.
                                          This is the ONLY path that sets restricted.
PATCH  /visits/{id}/meeting-point         role: faculty
                                          Body: meeting_zone_id (REQUIRED) and optional
                                          allowed_zones[]. Zone IDS, as at approve.
                                          Legal while `issued` or `inside`; anything else
                                          is InvalidRequest.
                                          Omitting allowed_zones keeps the current list
                                          with the OLD meeting zone REMOVED; supplying it
                                          replaces the list. Either way the new meeting
                                          zone is added, as at approve.
                                          MUST NOT reissue the QR. This endpoint exists to
                                          prove the pointer-not-payload design.
POST   /visits/{id}/arrival-ack           role: faculty
                                          Body: allowed_zones[] and valid_to — REQUIRED if
                                          the visit is restricted, ignored otherwise.
                                          Host confirms availability, sets host_acked_at.
                                          A restricted visit is always a fallback admission
                                          (nothing else sets restricted = True), so it has
                                          no original zones to restore — no host ever
                                          approved it. The host MUST supply zones and a
                                          window here. This is the first moment a host is
                                          in the loop. InvalidRequest if omitted.
                                          Lifting sets restricted = False.
                                          Changing valid_to does NOT reissue the QR —
                                          the window is not in the payload, see §9.
POST   /visits/{id}/close                 role: guard
                                          End-of-day close-out. Body: reason
                                          (`left_without_scanning` | `still_inside` |
                                          `partial_exit` | `system_error`).
GET    /visits/{id}/scans                 The audit trail.
```

### Passes

```
GET    /passes/{visit_id}                 Signed payload ready for QR encoding + code6.
POST   /passes/{visit_id}/revoke          role: security. Every scan checks revoked_at.
```

### Scans

```
POST   /scans/gate/entry                  role: guard
       Body: payload+signature OR code6, vehicle_plate, person_count_in,
             entered_offline (bool), authorised_by (optional).
       Checks IN ORDER: signature → not revoked → status is `issued` → within window
       → visitor not already `inside` on another visit.
       On success: issued → inside, entry_at set, ScanEvent written, host notified.
       Response leads with EVERY linked person's photo and details, the vehicle, and the
       expected headcount — the guard's job is comparing faces to a screen.
       Plate or count mismatch sets a flag on the response and the ScanEvent.
       NEVER blocks on a mismatch.
       On any failure, still write a ScanEvent with the failure result.

POST   /scans/gate/exit                   role: guard
       Body: payload+signature OR code6, vehicle_plate_out, person_count_out.
       Photos shown again. Plate compared to entry.
       count_out == count_in  → inside → closed.
       count_out <  count_in  → visit STAYS `inside`, partial_exit flag raised,
                                security notified, resolved later by close-out.

POST   /scans/zone
       Body: zone_code, and payload+signature OR code6.
       Reads allowed_zones FRESH from the visit.
       In list     → `ok`, host notified.
       Not in list → `wrong_zone`, security notified, still returns 200.
       This endpoint NEVER blocks anyone. It records and returns what happened.
```

### Dashboards

```
GET    /dashboard/inside                  role: security
       Currently `inside`, sorted by entry_at ascending (longest inside first).
       Per row: name, photos, host, entry_at, meeting zone, and boolean flags —
       overstaying, no_destination_scan, wrong_zone_scan, partial_exit, restricted,
       host_not_acked. Flags only, no ranking.

GET    /dashboard/exceptions              role: security
       Separate lists, unmerged and unranked: overstaying, no_destination_scan,
       wrong_zone, partial_exit, awaiting_host_ack. A visit may appear in several.

GET    /dashboard/honesty                 role: admin
       Counts, not charts:
       - visits closed without an exit scan
       - visits currently overstaying
       - wrong-zone scans today (LOCAL_TZ day, §11)
       - entries made offline
       - restricted admissions, BROKEN DOWN BY APPROVER
       - walk-ins denied after escalation
       - average host approval and acknowledgement time, by department
       Every field is ALWAYS returned. A count with no possible source in the
       current build returns 0 — never omit it, never hide it. A panel that
       drops the fields it cannot fill defeats its own purpose.

GET    /zones
GET    /hosts                             Includes phone, so the guard can call the host
                                          directly instead of waiting on escalation.
```

### Prototype-only

Mark clearly in code, exclude from the main OpenAPI tags.

```
POST   /dev/reset                         Clear and reseed.
POST   /dev/advance-clock                 Body: minutes. Shifts a module-level offset so a
                                          demo can trigger escalation and overstay instantly
                                          instead of waiting 30 real minutes.
POST   /dev/transition                    Body: visit_id, to_status.
                                          Calls transition() directly. Exists so the state
                                          machine is testable at Phase 2, before any real
                                          endpoint drives it, and to force a visit into a
                                          given state during manual testing later.
GET    /dev/notifications                 Everything the notification stub "sent".
```

For advance-clock to work, **no code may call `datetime.now()` directly**. Every time read goes through `core/clock.now()`.

---

## 11. Background jobs

`jobs/scheduler.py`, every `SCHEDULER_INTERVAL`. All jobs call the **same services** the routers call — never reach into repositories or duplicate rules.

1. **Approval escalation** — `requested` past its window → department → fallback authority. Windows differ by `origin`: walk-ins are shorter because someone is standing at the gate. Route to admin during working hours, security outside them.
2. **Arrival acknowledgement escalation** — `inside` with no `host_acked_at` past the window → department → fallback → close as `host_unavailable`, notify security.
3. **No destination scan** — entered, no `zone` scan after `NO_SCAN_WINDOW` → notify security.
4. **Overstay** — past `valid_to` with no exit → notify security. **Do not change status.** Overstay is derived from `valid_to` and `exit_at`, never stored.
5. **Expiry** — `requested` past `scheduled_at` never actioned, or `issued` past `valid_to` never scanned in → `expired`.

**Precedence between jobs 1 and 5.** Both act on `requested` visits. Expiry must **skip any visit whose `approval_escalation_stage` is `department` or `fallback`** — a request someone is actively being chased to answer must not vanish underneath them. Expiry applies only where `approval_escalation_stage` is `null` (never escalated) or `exhausted` (chased, no decision).

Derive every exception flag at read time from the visit and its scan events. Do not store them as fields — a stored flag and a derived one will drift apart. The **only** exception is the four escalation-stage fields in §6, which record what was sent rather than what is currently true.

### Derived flag definitions

Exact conditions. Every dashboard in §10 uses these and no other definition.

| Flag | True when |
|---|---|
| `host_not_acked` | status is `inside`, `host_acked_at` is null, and `clock.now() > entry_at + ACK_WINDOW` |
| `no_destination_scan` | status is `inside`, no ScanEvent of kind `zone` with result `ok`, and `clock.now() > entry_at + NO_SCAN_WINDOW` |
| `overstaying` | status is `inside`, `exit_at` is null, and `clock.now() > valid_to` |
| `wrong_zone_scan` | any ScanEvent of kind `zone` with result `wrong_zone`, today |
| `partial_exit` | status is `inside` and `person_count_out` is set and less than `person_count_in` |
| `restricted` | the `restricted` field on the visit |

**Escalation timing** measures from the end of the window, not from entry. The first stage fires at `entry_at + ACK_WINDOW` (approval chain: `created_at + APPROVAL_ESCALATION_*`), and each stage after that at `*_escalated_at + the next interval`.

### "Today"

Any rule referencing today — the `wrong_zone_scan` flag, `GET /visits?date=`, and the honesty panel's daily counts — means the **`LOCAL_TZ` calendar day** containing `clock.now()`, per §16.7. Convert to `LOCAL_TZ`, take the date, compare. `/dev/advance-clock` therefore moves what "today" means, which is intended.

`GET /visits?date=` filters on **`scheduled_at`**, interpreted as a `LOCAL_TZ` calendar date.

---

## 12. Config

Every window in `core/config.py`, none hardcoded in services.

| Setting | Value |
|---|---|
| APPROVAL_ESCALATION_PRE_REGISTERED | 30 min to department, 30 more to fallback |
| APPROVAL_ESCALATION_WALK_IN | 7 min to department, 10 more to fallback |
| ACK_WINDOW | 12 min |
| ACK_ESCALATION | 10 min to department, 10 more to fallback |
| NO_SCAN_WINDOW | 30 min |
| RESTRICTED_VISIT_DURATION | 60 min |
| VOUCH_VALIDITY_DAYS | 100 |
| MAX_LINKED_COMPANIONS | 4 |
| WORKING_HOURS | 09:00–17:00 |
| SCHEDULER_INTERVAL | 2 min |

If any value produces behaviour that seems wrong for the flow, flag it — do not silently change it.

---

## 13. Seed data

`store/seed.py`, loaded at startup. The prototype must be demoable the moment it starts.

**Seeded scan events must be written through the same repository the live path uses**, so the seeded shape matches what real scans produce.

- 3 hosts across 2 departments, 5 zones (main block, library, admin block, hostel gate, department office)

**`store/seed.py` is not finished in one go.** Some seeded records need capability that arrives in a later phase — a signed pass needs the signing code, a scan event needs the scan service, a photo ref needs the storage stub. So the seed file is written at phase 1 and extended at phases 3, 5 and 6. Do not try to create records the code cannot yet produce, and do not fake them by writing dicts directly.

**Phase 3 extends the seed with photos.** Every seeded visitor is created at phase 1 with `photo_ref = null`, because `integrations/storage.py` does not exist until phase 3. A literal ref written earlier would be a dangling pointer: `GET /photos/{ref}` would 404 on it, and phase 6's gate-entry response — which §10 requires to lead with faces — would carry refs resolving to nothing. Set them at phase 3, through `storage.put()`, never by hand.

| Visitor | State | Scan events to seed | Added in |
|---|---|---|---|
| A | DigiLocker-verified, visit `requested` | none | Phase 1 |
| C | Fallback-admitted, `inside`, `restricted = True`, `approved_by = "security:u_security"`, `approval_reason` set, `allowed_zones` = meeting zone only, host not acknowledged | entry `ok` at gate | Phase 6 |
| B | Vouched, pass `issued`, 2 linked companions | none — ready to scan in | Phase 5 — needs signing |
| D | `inside`, host not acknowledged, entry_at older than ACK_WINDOW | entry `ok` at gate | Phase 6 — needs scans |
| E | `inside`, wrong-zone scan logged | entry `ok` at gate; zone `wrong_zone` at a zone not in allowed_zones | Phase 6 |
| F | `inside`, overstaying | entry `ok` at gate; zone `ok` at meeting zone; no exit; valid_to in the past | Phase 6 |

Hosts and zones are seeded at phase 1.

**Visitor C exists to make `restricted` reachable.** Nothing in the built scope sets `restricted = True` — the only path is `fallback-decision`, which is deferred. Without C seeded this way, the `restricted` flag on `/dashboard/inside` and the restricted-admissions count on the honesty panel are both permanently dead, and Phase 8's restriction-lifting cannot be tested at all. C is the fixture those three depend on.

Without D, E and F's scan events, `/dashboard/exceptions` renders empty on first load and the demo dies.

---

## 14. Edge cases — decided, do not invent answers

- **`count_out > count_in`** — more people leaving than entered. Record `count_mismatch = True`, close the visit normally. Never block. The count is evidence, not a gate.
- **Zone scan on a visit that is not `inside`** — return 200 with result `wrong_status`, write the ScanEvent, notify nobody. A visit that never entered cannot be confirmed as arrived.
- **`person_count_expected` is the TOTAL**, including the accountable visitor. A visitor plus 4 companions is 5. This is the number the guard's actual count is compared against.
- **`already_inside`** — the scanned visit is left completely untouched, still `issued`. The ScanEvent is written against the **scanned** visit, not the one currently inside.
- **Vouch on a visitor who is already permanently verified** — no-op. Never downgrade `is_permanent`.
- **Revoked pass on a visit already `inside`** — revocation prevents future entry scans; it does not eject anyone or change status. Exit still works.

## 15. Rules

- No business logic in routers. `if visit.status == ...` in a router belongs in a service.
- No code outside `transition()` assigns `visit.status`.
- No service or router touches the store dicts — always through a repository.
- Every scan attempt writes a ScanEvent, successful or not. Failures are data.
- No endpoint returns `id_hash`.
- All time reads go through `core/clock.now()`.
- No scoring, ranking, or risk calculation anywhere.
- Nothing inside the campus blocks anyone. Zone endpoints record and notify only.
- Domain exceptions map to HTTP codes in one handler, not scattered `raise HTTPException`.

---

## 16. Contracts

Shapes that §§1–15 assume but never state. A phase that invents one of these produces working code that the next phase quietly contradicts. Nothing here is a new feature — it is the wire format of decisions already made.

### 16.1 Role resolution

`require_role(*roles)` resolves the caller as:

| `X-Role` header | Result |
|---|---|
| absent | role `admin` |
| present, in the required set | that role |
| present, `admin` | permitted — see the warning below |
| present, not in the required set | `NotPermitted` (403) |

> **PRODUCTION BLOCKER — do not ship this.** `admin` satisfies every role check, including guard-only and faculty-only endpoints, and an absent header is treated as `admin`. Together these mean **any unauthenticated caller can reach every endpoint in the system.** This is deliberate for a prototype: it makes every endpoint callable with no header during early phases and manual testing. Real deployment must change this *behaviour*, not merely swap the header read for a JWT verify. Put this warning in a comment above `require_role` itself, not only here.

An endpoint marked `role: admin | security` accepts either. An endpoint with no role marker accepts anyone, including an absent header.

Hardcoded users returned per role, so `approved_by` and `actor` are stable across a demo:

| role | id | name |
|---|---|---|
| guard | `u_guard` | Gate Guard |
| faculty | `u_faculty` | resolved to the acting host where one is in scope, else Faculty User |
| security | `u_security` | Security Desk |
| admin | `u_admin` | Admin Block |
| visitor | `u_visitor` | Visitor |

Where a faculty endpoint acts on a visit, the acting host is the visit's `host_id` — the header establishes the *role*, the path establishes the *identity*. There is no per-host authentication in this build, so `POST /visits/{id}/approve` does not verify that the caller is the named host. Real auth adds that check and nothing else.

### 16.2 The `actor` argument to `transition()`

`actor` is a free-text audit string, never parsed. Format: `"{role}:{id}"`.

- Router-driven: `"faculty:h_2"`, `"guard:u_guard"`, `"admin:u_admin"`
- Scheduler-driven: `"system:job_ack_escalation"`, `"system:job_expiry"` — the job name, so the audit trail says which job closed a visit
- `POST /dev/transition`: `"dev:forced"`

`approved_by` on the visit uses the same string format.

### 16.3 Department escalation recipient

`Host.department` is a bare string. There is no department entity and none is to be added.

**Escalating to department** notifies every host whose `department` equals the named host's, excluding the named host, via `integrations/notifications`. If no such host exists, **one notification is still written**, addressed to `department:{name}`, and the stage still advances to `department`. The chain must never stall on a data gap — a seeded department with one host would otherwise freeze the escalation forever and the demo would show nothing.

**Escalating to fallback** notifies a fixed recipient string, not a host record: `admin_block` during `WORKING_HOURS` per §16.7, `security_desk` outside them. Working hours are evaluated at the moment the stage advances, not at the moment the visit was created.

### 16.4 `person_count_expected`

Set at visit creation from the body:

| Body | `person_count_expected` | Companion records |
|---|---|---|
| `companions[]` supplied | `len(companions) + 1` | one per companion |
| `person_count` supplied | that number, used as-is | none |
| neither | `1` | none |
| both | `InvalidRequest` (400) | — |

`len(companions) > MAX_LINKED_COMPANIONS` → `CompanionLimitExceeded` (400). `person_count < 1` → `InvalidRequest`.

`person_count` is **not** restricted to groups of 6 or more. §3 describes the headcount path as what happens beyond four companions, but a caller who knows only a number for a party of three has no other field to put it in, and rejecting that adds a rule with no safety value. The field is always the total including the accountable visitor, per §14.

### 16.5 Photos

- **Inbound:** base64 string, field name `photo_b64`, on `POST /visitors`, `POST /visits/walk-in`, and each entry of `companions[]`. Decoded size over **2 MB** → `InvalidRequest`. The store is a dict in RAM; an uncapped field turns a demo into an OOM.
- **Storage:** `integrations/storage.put(b64) -> ref`, refs of the form `photo_{n}`. Entities hold the ref only. Nothing else in the codebase holds base64.
- **Outbound:** every response returns `photo_ref`, **never base64**. A gate-entry response leading with five photos would otherwise be megabytes of JSON on a tablet at a gate.
- **`GET /photos/{ref}`** — returns `{"ref": ..., "photo_b64": ...}`, `NotFound` if absent. No role marker. The guard's screen has to get the pixels from somewhere, and §10 requires the entry response to lead with faces. Built at Phase 3 alongside registration.

### 16.6 Error envelope

The single handler required by §15 returns:

```json
{
  "error": {
    "code": "IllegalTransition",
    "message": "Cannot move visit v_4 from inside to denied",
    "detail": {"visit_id": "v_4", "from": "inside", "to": "denied"}
  }
}
```

- `code` is the exception class name verbatim, so a test can assert on it without parsing prose.
- `detail` is an object, omitted when empty. Never a string.
- FastAPI's own 422 validation body keeps its native shape — do not rewrite it into this envelope. A schema failure and a domain failure are different animals and the difference is worth seeing.
- **Scan endpoints never use this envelope.** They return 200 with the outcome, per §8.

### 16.7 Time

- `core/clock.now()` returns a **timezone-aware UTC** `datetime`. Every stored timestamp is aware UTC.
- All API bodies use **ISO 8601 with offset** (`2026-08-21T14:30:00+05:30`). Naive input is rejected by Pydantic.
- `LOCAL_TZ = "Asia/Kolkata"` in `core/config.py`. `WORKING_HOURS` is evaluated by converting `clock.now()` into `LOCAL_TZ` — a UTC comparison would put the fallback switch at the wrong hour.
- `/dev/advance-clock` shifts a module-level `timedelta` inside `core/clock.py`. Advancing past 17:00 local **does** reroute fallback escalation from admin to security. That is intended and demoable, not a bug — call it out in the Phase 11 test script.
- The offset is additive and cumulative; `/dev/reset` sets it back to zero.

### 16.8 Module layout

Phase 0 creates the tree; later phases add files inside it and rename nothing.

```
requirements.txt              fastapi, uvicorn, pydantic, apscheduler, python-dotenv
.env.example                  HMAC_SECRET, LOCAL_TZ
smoke.sh                      cumulative regression script
app/
  main.py                     FastAPI app, router registration
  core/
    config.py  clock.py  security.py  signing.py  errors.py
  store/
    memory.py  entities.py  seed.py  ids.py
  repositories/
    visitor_repo.py  companion_repo.py  host_repo.py  zone_repo.py
    visit_repo.py  pass_repo.py  scan_repo.py  notification_repo.py
  services/
    visitor_service.py  visit_service.py  pass_service.py
    scan_service.py  escalation_service.py  dashboard_service.py
  schemas/
    visitor.py  visit.py  pass_.py  scan.py  dashboard.py  common.py
  routers/
    visitors.py  visits.py  passes.py  scans.py  dashboard.py  reference.py  dev.py
  integrations/
    digilocker.py  otp.py  notifications.py  storage.py
  jobs/
    scheduler.py              created empty — Phase 11 is deferred, nothing starts it
```

Run with `uvicorn app.main:app --reload`. `main.py` registers routers only; **it does not start the scheduler**, because Phase 11 is deferred. Adding that startup call is part of Phase 11, not Phase 0.

`reference.py` holds `GET /zones` and `GET /hosts`. `pass_.py` carries the underscore because `pass` is a keyword. `ids.py` holds the per-collection counters so no two repositories invent their own scheme.
