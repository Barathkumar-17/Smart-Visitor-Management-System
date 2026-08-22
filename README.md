# Smart Visitor Management System

A digital visitor register for MIT Campus. Replaces the paper book at the gate with a searchable record linked to the faculty member being visited.

**What it does:** creates accountability. Who came in, when, to meet whom, where they went, and when they left.

**What it does not do:** stop a determined intruder. Anyone avoiding the system will use a side gate or walk in looking like a student. This manages cooperative visitors, which is 99% of the people who come to a campus. Saying that plainly is a design position, not a gap — systems that claim to stop intruders fail the first hard question.

---

## The idea in one line

Hard control at the gate, soft observation inside.

The gate has a barrier and a guard, so entry can actually be decided there. Inside the campus there are no guards at every door, so checkpoint scans only record and alert. They cannot block anyone, and the system never pretends otherwise. The real detection is the **absence** of a scan — entered the gate twenty minutes ago, never reached the host.

---

## How a visit works

**Registration, once.** A visitor registers with name, address, phone, email and a live photo, verified either through **DigiLocker consent** (permanent) or by a **host's vouch** at approval time (100 days, with the voucher's name on the record). A walk-in gets a temporary registration created by the guard at the gate — phone confirmed by OTP — which holds the visit but confers no standing.

**Pass request.** Date, time, host, vehicle, and who is coming. Up to four companions are each registered with a photo; beyond that a headcount is used. One QR covers the whole group.

**Approval.** The named host approves, choosing the meeting location, the allowed zones and the time window. A signed QR and a 6-digit fallback code are issued. If the host stays silent it escalates — department, then the admin block during working hours or the security desk outside them. That fallback approver sees the photo taken at the gate and can deny, or admit with the meeting point only and a short window.

**Gate.** The guard scans. Every linked person's photo appears for a visual check, alongside the vehicle and expected headcount. Mismatches are flagged and recorded, never blocked. The visitor enters and waits — they are never held at the barrier while a professor is chased.

**Inside.** Checkpoint QR stickers at each zone confirm arrival. A scan somewhere unexpected notifies security without blocking. If the host is in another building they grant that checkpoint from their dashboard, and the QR is never reissued.

**Exit.** One scan at the gate. Photos shown again, plate compared, and the guard enters how many are leaving. Fewer out than in keeps the visit open and flagged.

---

## What makes it different

**The QR is a pointer, not a payload.** It carries only a visit id and a nonce — signed with HMAC-SHA256, so it is unforgeable, and meaningless to any other scanner. Everything mutable, including the allowed zones and the time window, is read fresh from the record at every scan. A host can move the meeting from their office to the library and the visitor's unchanged QR simply starts working at the new location. Nothing is reissued.

**Nothing physical is issued.** No slips, no cards, no lanyards. Printers jam and cards need collecting, and both fail during a crowd.

**The honesty panel.** An admin dashboard that counts the system's own failures: visits closed without an exit scan, alerts nobody acted on, entries admitted without host acknowledgement broken down by approver, and faculty response time per department. Fields with nothing to report return an honest zero rather than being hidden. A product built to be sold hides those numbers; one built for a campus admin shows them.

**Built for the guard.** One button, faces shown large, under ten seconds per visitor. The guard decides every day whether the system gets used or bypassed, so the guard's screen matters more than the admin's.

---

## Running it

Python 3.11 or newer. The virtual environment lives at the repository root, one
level above the application code.

```bash
# from D:\Projects\SVMS
.venv\Scripts\python.exe -m pip install -r Backend\requirements.txt

cd Backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/docs>.

Two things that trip people up:

- The module path is **`app.main:app`**, not `main:app` — the application is a
  package. `uvicorn main:app` fails with *Could not import module "main"*.
- Run it from **`Backend/`**, the directory containing `app/`. Anywhere else and
  the import fails the same way.

The store is seeded at startup, so every endpoint has data to return on the
first request. Nothing needs importing or configuring first.

### The regression script

`Backend/smoke.sh` replays every phase's happy path in order and asserts on a
field per step, so a broken response stops the run at the step that broke rather
than scrolling past. It needs [jq](https://jqlang.github.io/jq/) on `PATH`.

```bash
# with the server already running, in a second terminal
cd Backend
bash smoke.sh
```

### Resetting

`POST /dev/reset` clears the store, reseeds it and returns the clock offset to
zero. Seeded ids are deterministic across a reset — `z_1`–`z_5`, `h_1`–`h_3`,
`vr_1`, `vr_2`, `v_1`, `v_2` — so test scripts can rely on them.

`POST /dev/advance-clock` shifts time forward so overstay and escalation windows
can be demonstrated in seconds instead of waited out. Every time read in the
system goes through one clock module, so nothing ignores the offset.

---

## What is built

This is a **working prototype with no database**. All state lives in memory and
is lost on restart. That is deliberate — the goal is a complete, demonstrable API
surface for the visitor lifecycle, not persistence.

Built: registration and verification, the pass request and approval flow, the
state machine, pass signing, gate entry, arrival acknowledgement, zone scans,
exit and close-out, and the dashboards. Everything below the gate-entry line
is what a visitor actually touches; the rest is the record it leaves behind.

---

## What is not built, and what it would do

Three pieces of the specification are deliberately unbuilt. All three are fully
described in `SPEC.md`, none is abandoned, and each is summarised here so the
gap between the specification and the running code is visible rather than
discovered.

They were cut for one reason: the demonstration is about four minutes long, and
none of the three produces anything showable in that time. What gets built was
decided by what fits on screen, not by what completes the product.

### Walk-in registration at the gate

A second way in, for someone who arrives without a pass. The guard creates a
**temporary registration** on the spot — name, phone confirmed by OTP, a live
photo, vehicle — which holds the visit but confers no standing at all. A
returning walk-in is found by phone and skips the form entirely, and the phone
number is what links a temporary record to a proper registration later.

Walk-ins escalate on **much shorter windows** than pre-registered visits — seven
minutes to the department rather than thirty — because a person is physically
standing at the gate while the system waits for an answer. A host who vouches
for a walk-in at approval grants standing for **that visit only**, unlike a
pre-registered vouch, which is good for a hundred days.

The verification rules for this path are implemented; only the endpoint that
creates the visit is missing.

### The background scheduler

Five jobs, running every couple of minutes. This is the most significant thing
being left out, and the first to add back.

| Job | What it does |
|---|---|
| Approval escalation | A request nobody has answered goes to the department, then to the fallback authority. |
| Acknowledgement escalation | A visitor is inside and the host has not confirmed: department, then fallback, then the visit closes as `host_unavailable` with security notified. |
| No destination scan | Entered the gate but reached no checkpoint within the window — security is told. This is the detection that matters most, because the signal is an **absence**. |
| Overstay | Past the pass window with no exit scan. Notifies; never changes status. |
| Expiry | A request nobody actioned, or a pass never scanned in, becomes `expired`. |

Escalation is what turns the system from a register into something that chases
people, and its absence is why nothing in a running session ever *becomes* an
exception.

### Fallback authority

The decision made when escalation runs out of people to ask. The fallback
approver is the **admin block during working hours and the security desk outside
them**, evaluated at the moment the stage advances rather than when the visit was
created.

They see the photograph taken at the gate, **must supply a reason**, and can
either deny — a terminal outcome — or admit on restricted terms: the meeting
point only, a short window, and the visit flagged as an unacknowledged-host
entry for as long as it stays open.

This is the **only** path in the entire system that marks a visit `restricted`,
which is why it cannot be built without the walk-in flow or the scheduler that
reaches it.

### What their absence changes

Two consequences, stated plainly because both are visible when using the system:

**Exception flags never appear during a session.** The dashboards read flags the
scheduler's jobs would raise, so the seed carries visitors already in those
states — one unacknowledged, one who scanned somewhere they should not have, one
overstaying. Every list is correct and populated on first load, but nothing
becomes an exception while you watch, and nothing in the system claims otherwise.

**Two honesty-panel counts are permanently zero** — restricted admissions broken
down by approver, and walk-ins denied after escalation. Both are returned as
zero rather than hidden, because a panel that drops the fields it cannot fill
defeats its own purpose.

---

## Security — read this before deploying anywhere

Two deliberate shortcuts make this prototype convenient and would make a real
deployment indefensible. Both are documented in `SPEC.md` and commented at the
code that implements them.

### 1. Every endpoint is reachable without authentication

`require_role()` reads an `X-Role` header and trusts it. There is no token, no
signature and no verification of any kind.

- An **absent** header is treated as `admin`.
- The `admin` role satisfies **every** role check, including guard-only and
  faculty-only endpoints.

Together those mean **any unauthenticated caller can reach every endpoint in the
system** — approve their own visit, revoke a pass, read the dashboards. This is
intentional for a prototype: it makes everything callable with `curl` and no
setup during development.

Fixing it is not a matter of swapping the header read for a JWT verify. The
`admin`-satisfies-everything rule and the absent-header default both have to go
as well, and per-host identity has to become real — `POST /visits/{id}/approve`
currently does not check that the caller is the host named on the visit.

### 2. Pass signatures use a committed default secret

The QR carries a visit id and a nonce, signed with HMAC-SHA256. That signature is
the entire basis on which the gate admits anyone: the backend recomputes it and
compares, and a match means the system issued that QR and nobody altered it.

The secret comes from `HMAC_SECRET` in `.env`. **When no `.env` is present the
application falls back to a development default that is committed to this
repository.** Anyone who can read the repo can then mint a valid QR for any visit
id — no approval, no host, no account. Forging a pass and walking through the
gate become the same act.

The application logs a warning at startup whenever that default is in use. Set a
real secret before running this anywhere reachable:

```bash
cp Backend/.env.example Backend/.env
# then put an actual random value in HMAC_SECRET
```

Note that `.env.example` ships a placeholder, not a working value, so copying it
without editing will not silently leave you insecure.

This is why the QR is described above as unforgeable: the design is sound, and
the weakness is entirely in the key management, which is exactly the part a real
deployment has to supply.

### Not a shortcut, but worth knowing

`id_hash` — the identity hash from DigiLocker — is stored but **never returned by
any endpoint**. Response schemas list their fields explicitly rather than dumping
the record, so a field added to an entity later cannot leak through by accident.
`id_last4` is returned, and is what a guard checks against a physical card.

---

## The documents

| File | What it is |
|---|---|
| `SPEC.md` | The specification. Entities, rules, endpoints, config, seed data. The source of truth. |
| `CLAUDE.md` | How the build proceeds — phase order, what each phase delivers, and a decision log recording every departure from the spec and why. |
| `Backend/smoke.sh` | Cumulative regression script, one asserting step per phase feature. |
