# Smart Visitor Management System

A working prototype of the software a college gate would run to manage visitors — from the moment someone asks to come in, to the moment they leave.

This is a **backend**: the engine, not the screens. There is no app and no website. You use it by sending it requests, and this file shows you exactly how, with commands you can copy and paste.

Nothing is saved to disk. It runs entirely in memory, starts with a realistic campus already loaded, and forgets everything when you stop it. That is deliberate — you cannot break it in any way that a restart won't fix.

---

## The problem it solves

At most campus gates today a visitor writes their name in a paper register, the guard rings the host, and the host either answers or doesn't. Nobody can tell you who is on campus right now. Nobody notices when a visitor wanders somewhere they shouldn't. And when someone forgets to sign out, they stay in that register forever.

**What it does:** creates accountability. Who came in, when, to meet whom, where they went, when they left.

**What it does not do:** stop someone determined to get in. Anyone avoiding this will use a side gate or walk in looking like a student. This manages cooperative visitors, which is almost everyone who comes to a campus. Saying so plainly is a design position, not a gap.

The rule the whole system follows: **firm control at the gate, quiet observation inside.** The gate has a barrier and a guard, so entry can genuinely be decided there. Inside, there is no guard at every door — so checkpoint scans only record and alert, and never pretend to block anyone.

---

## How a visit works

**1. The visitor registers.** Name and phone at minimum. They confirm the phone with a one-time code. If they verify a government ID, they become permanently trusted; otherwise a staff member can vouch for them, which lasts 100 days and keeps the voucher's name on the record.

**2. They ask to visit someone.** They name the staff member, say why, when, how many people are coming and what vehicle they'll arrive in. Up to four companions get their own photo; beyond that it becomes a headcount. One QR covers the whole group.

**3. The host approves.** The host picks where the meeting will happen, which other areas the visitor may enter, and how long the pass is good for. A QR code and a 6-digit backup number are created at that moment.

**4. They arrive at the gate.** The guard scans. The screen fills with every face on the pass, the vehicle expected, and how many people should be in the group. The guard compares that against what is actually standing in front of them. A mismatch is flagged and recorded — never used to turn someone away.

**5. They move around campus.** Checkpoint scans confirm they got where they were going. A scan somewhere they weren't cleared for tells security, without stopping anybody. The most useful signal is an **absence**: entered the gate half an hour ago and reached no checkpoint at all.

**6. They leave.** One scan out, and the guard counts the people leaving. If fewer leave than arrived, the visit stays open and security is told, because somebody is still inside.

---

## The one idea worth understanding

**The QR code contains almost nothing.** It holds a visit number and a random string. No name, no zones, no expiry, no photo.

That sounds like a weakness. It is the most important decision in the system.

Because the QR is only a *pointer*, everything about the visit can change while the visitor keeps the same code. A host can move the meeting from the library to their department office, extend the visit by two hours, or widen where the visitor may go — and the image on the visitor's phone is identical to the one they were sent that morning. Every scan looks up the current truth.

If the QR carried the details instead, each of those changes would mean cancelling the pass and issuing a new one, leaving the visitor at a checkpoint holding a code that no longer works.

The code is also **signed**, so it cannot be forged or altered. You can watch all of this happen — it's the second thing in the demonstration below.

---

## Getting it running

You need **Python 3.11 or newer**. The project keeps its packages in a folder called `.venv` at the top level, separate from anything else on your machine.

```powershell
# from D:\Projects\SVMS
.venv\Scripts\Activate.ps1        # if the folder does not exist yet:
                                  #   python -m venv .venv   then activate

cd Backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

You should see `Uvicorn running on http://127.0.0.1:8000`. Leave that window open — it is the server. Open a **second** PowerShell window for everything below.

**Two things that trip people up:**

- The name is **`app.main:app`**, not `main:app`. Getting it wrong gives you *Could not import module "main"*.
- Run it from the **`Backend`** folder. Anywhere else fails the same way.

Check it's alive:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

```
status                : ok
now_local             : Sat 22 Aug 2026, 04:26:39 PM IST
clock_offset_minutes  : 0
```

**There is also a browser page.** Open **http://127.0.0.1:8000/docs** for a clickable list of every endpoint with a "Try it out" button on each. If typing commands isn't for you, use that — it does exactly the same thing.

---

## Who is already in the system

It starts with a campus mid-morning, so there is something to look at immediately. You never have to set anything up.

**Five zones** — `MAIN` Main Block, `LIB` Library, `ADMIN` Admin Block, `HOSTEL` Hostel Gate, `DEPT` Department Office.

**Three staff** — Dr. Anitha Rao and Prof. Vikram Menon (Computer Science), Dr. Sunita Pillai (Mechanical Engineering).

**Six visitors**, each showing a different situation:

| Visitor | Visit | Situation |
|---|---|---|
| Ramesh Kumar | `v_1` | Has asked to visit. Nobody has approved yet |
| Suresh Iyer | `v_3` | Approved, holding a QR, hasn't arrived. Bringing two people and a van |
| Deepa Nair | `v_2` | Inside on **restricted** terms — meeting point only |
| Fatima Sheikh | `v_4` | Inside 40 minutes; their host still hasn't confirmed they're free |
| George Mathew | `v_5` | Inside, and scanned somewhere they weren't cleared for |
| Nandini Krishnan | `v_6` | Inside, and their pass expired half an hour ago |

**To put everything back exactly as it started**, at any point:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/dev/reset
```

Every name, number and ID comes back identical, so nothing you do is permanent.

---

## See it working in four minutes

Paste this into your second window first — it sets up the shorthand used below.

```powershell
$B = "http://127.0.0.1:8000"
$guard    = @{ "X-Role" = "guard" }
$faculty  = @{ "X-Role" = "faculty" }
$security = @{ "X-Role" = "security" }
$admin    = @{ "X-Role" = "admin" }

Invoke-RestMethod -Method Post "$B/dev/reset" | Out-Null
```

### One — somebody arrives at the gate

Suresh Iyer, with two people and a van.

```powershell
$qr = (Invoke-RestMethod "$B/passes/v_3").qr
$body = @{
  payload = $qr.payload; signature = $qr.signature
  vehicle_plate = "TN-07-XY-9090"; person_count_in = 3
} | ConvertTo-Json -Depth 5

$r = Invoke-RestMethod -Method Post "$B/scans/gate/entry" -ContentType application/json -Headers $guard -Body $body
$r.people | Format-Table role, name, photo_ref
$r | Select-Object admitted, visitor_name, host_name, host_phone, meeting_zone
```

```
role       name           photo_ref
----       ----           ---------
visitor    Suresh Iyer    photo_3
companion  Lakshmi Iyer   photo_4
companion  Mohan Das      photo_5

admitted     : True
visitor_name : Suresh Iyer
host_name    : Dr. Anitha Rao
host_phone   : +91-90000-10001
meeting_zone : DEPT - Department Office
```

Three faces to compare, and the host's phone number so the guard can ring them directly instead of waiting on the system.

**Try changing the plate to `TN-99-ZZ-0001`.** They are still admitted — but `vehicle.mismatch` comes back true and security is told. Mismatches are recorded, never used to block someone.

### Two — the meeting moves, the QR does not

Fatima Sheikh is already inside, expected at the Department Office.

```powershell
"QR before: " + (Invoke-RestMethod "$B/passes/v_4").qr.signature

function Scan($code) {
  $q = (Invoke-RestMethod "$B/passes/v_4").qr
  $json = @{ zone_code = $code; payload = $q.payload; signature = $q.signature } | ConvertTo-Json -Depth 5
  $x = Invoke-RestMethod -Method Post "$B/scans/zone" -ContentType application/json -Headers $guard -Body $json
  "{0,-6} {1}" -f $code, $x.result
}

Scan "DEPT"          # where they are expected
Scan "LIB"           # where they are not

$patch = @{ meeting_zone_id = "z_2" } | ConvertTo-Json
Invoke-RestMethod -Method Patch "$B/visits/v_4/meeting-point" `
  -ContentType application/json -Headers $faculty -Body $patch | Out-Null

"QR after : " + (Invoke-RestMethod "$B/passes/v_4").qr.signature

Scan "LIB"           # now correct
Scan "DEPT"          # now wrong
```

```
QR before: 8acc96ee9f8a0f49e3de5704527acac96c8c4372767216473a8832a317154aeb
DEPT   ok
LIB    wrong_zone
QR after : 8acc96ee9f8a0f49e3de5704527acac96c8c4372767216473a8832a317154aeb
LIB    ok
DEPT   wrong_zone
```

**Compare the two QR lines.** Character for character identical. Their access reversed completely and the code in their hand never changed.

(The signature itself is different every time you reset — what matters is that the two lines match each other.)

### Three — who is on campus

```powershell
$inside = Invoke-RestMethod "$B/dashboard/inside" -Headers $security
$inside | Select-Object visitor_name, minutes_inside, flag_count | Format-Table

Invoke-RestMethod "$B/dashboard/exceptions" -Headers $security
Invoke-RestMethod "$B/dashboard/honesty" -Headers $admin
```

```
visitor_name       minutes_inside  flag_count
------------       --------------  ----------
Nandini Krishnan              150           2
Fatima Sheikh                  40           2
Deepa Nair                     25           2
George Mathew                  20           2
```

Longest inside at the top, each carrying the problem they represent — one overstaying, one whose host never responded, one who scanned in the wrong place, one on restricted terms. The exceptions screen splits those into five separate lists, each row saying in words why it is there.

(Storing the result in `$inside` first is not optional. Piping `Invoke-RestMethod` straight into `Select-Object` hands the whole list over as a single item and prints one blank row — a quirk of Windows PowerShell, not of this system.)

**None of those warnings is stored anywhere.** They are worked out fresh each time you ask. A saved warning goes stale the moment the situation changes; a calculated one can't.

---

## Roles

Every request can say who is asking:

```powershell
-Headers @{ "X-Role" = "guard" }
```

| Role | Does what |
|---|---|
| `guard` | Scans people in and out, closes visits at end of day |
| `faculty` | Approves visits, confirms availability, moves meetings |
| `security` | Reads the campus and exception dashboards |
| `admin` | Everything, including the honesty panel |

Leave the header off entirely and you are treated as `admin`. **That is a deliberate shortcut for demonstrating and a serious problem for real use** — see the warning further down.

---

## Every endpoint

### Registering a visitor

| Endpoint | What it does |
|---|---|
| `POST /visitors` | Register someone. Only name and phone are required |
| `GET /visitors/{id}` | Everything known about one visitor |
| `GET /visitors/lookup?phone=` | Find a returning visitor by phone number |
| `POST /visitors/{id}/otp/send` | Send a one-time code to their phone |
| `POST /visitors/{id}/otp/verify` | Check that code and mark the phone confirmed |
| `POST /visitors/{id}/digilocker` | Verify a government ID — makes them permanently trusted |
| `GET /photos/{ref}` | Fetch a stored photograph |

### Asking for a pass, and approving it

| Endpoint | What it does |
|---|---|
| `POST /visits` | Request a visit. Up to four named companions, or a plain headcount |
| `GET /visits` | The staff inbox. Filter by host, status or date |
| `GET /visits/{id}` | One visit, with everyone on it |
| `POST /visits/{id}/approve` | Approve: set the zones and the time window, and create the QR |
| `POST /visits/{id}/reject` | Turn down a request that hasn't been approved |
| `POST /visits/{id}/cancel` | Call off a visit that was already approved |
| `GET /visits/{id}/scans` | Every scan ever attempted on this visit, failures included |

### The pass itself

| Endpoint | What it does |
|---|---|
| `GET /passes/{visit_id}` | The QR code and the 6-digit backup number |
| `POST /passes/{visit_id}/revoke` | Cancel a pass so it can no longer get anyone in |

### Arriving, moving around, leaving

| Endpoint | What it does |
|---|---|
| `POST /scans/gate/entry` | Scan in. Returns every face, the vehicle and the headcount |
| `POST /scans/zone` | Scan at a checkpoint. Records whether they were cleared for it |
| `POST /scans/gate/exit` | Scan out, counting the people leaving |
| `POST /visits/{id}/arrival-ack` | The host confirms they're free, lifting any restriction |
| `PATCH /visits/{id}/meeting-point` | Move the meeting. **Does not reissue the QR** |
| `POST /visits/{id}/close` | End-of-day close-out for a visit the exit scan couldn't finish |

### The dashboards

| Endpoint | What it does |
|---|---|
| `GET /dashboard/inside` | Who is on campus right now, longest inside first |
| `GET /dashboard/exceptions` | Five separate lists of things needing attention |
| `GET /dashboard/honesty` | Plain counts of what went wrong, honest zeros included |

### Reference

| Endpoint | What it does |
|---|---|
| `GET /zones` | The five campus zones |
| `GET /hosts` | Staff, with phone numbers so a guard can call instead of waiting |
| `GET /health` | Confirms the server is up, and shows the time it thinks it is |

### For demonstrating only

These would not exist in a real deployment.

| Endpoint | What it does |
|---|---|
| `POST /dev/reset` | Wipe everything and reload the starting campus |
| `POST /dev/advance-clock` | Jump the clock forward, to watch time-based rules fire |
| `POST /dev/transition` | Force a visit into any state, for testing |
| `GET /dev/notifications` | Every message the system would have sent |
| `GET /dev/whoami` | Which role your header is granting you |

---

## What the answers look like

Three things worth knowing about the responses.

**A refused scan is not an error.** Present a forged QR and you get a perfectly normal, successful reply that says no:

```
admitted : False
result   : bad_signature
message  : Signature did not verify. This pass was not issued by this system, or has been altered.
```

That matters more than it looks. Every scan attempt is written to the permanent record, failures included. If a refusal came back as an error, a phone on a weak signal could drop the request and the attempted forgery would simply vanish. Recording the attempt *is* the point.

**Something genuinely wrong looks different.** A real mistake gets a proper error with a code you can act on:

```
error.code    : InvalidRequest
error.message : Unknown zone code CANTEEN
```

**Nothing is hidden to make the numbers look better.** The honesty panel returns every field it is meant to, even when the answer is zero, and says why:

```
walk_ins_denied_after_escalation : 0

unavailable:
  walk_ins_denied_after_escalation : Walk-in registration and fallback authority are
                                     both deferred, so no visit can reach denied.
                                     This zero is true, not missing.
```

A zero meaning *"this never happened"* and a zero meaning *"nothing here could have recorded it"* are different facts. The panel keeps them apart. A product built to be sold hides numbers like these; one built for a campus administrator shows them.

---

## Testing all of it at once

There is a script that exercises every feature in order and stops the instant anything is wrong.

It needs Git Bash and `jq` (`winget install jqlang.jq`, then open a fresh terminal). With the server running, in a second window:

```powershell
cd D:\Projects\SVMS\Backend
bash smoke.sh
```

93 checks. Every one asserts on a specific field, so a wrong answer halts the script at the step that produced it rather than scrolling past in a wall of output. The last line should read `All steps passed.`

---

## What is built

| Area | |
|---|---|
| Registration | Phone codes, government ID verification, trusted-visitor status, photographs |
| Requests and approval | Staff inbox, approval with zones and times, rejection, cancellation |
| Passes | Signed QR codes, a 6-digit backup, revocation |
| Gate entry | Five checks in order, faces on screen, vehicle and headcount comparison |
| Host confirmation | Confirming availability and lifting restrictions, without reissuing the QR |
| Checkpoints | Zone scans, wrong-zone detection, moving the meeting mid-visit |
| Leaving | Exit scanning, partial exits, end-of-day close-out |
| Dashboards | Who's inside, five exception lists, the honesty panel |

---

## What is not built

Three parts of the design were deliberately left out. All three are fully specified in `SPEC.md` and none is abandoned. They were cut for one reason: the demonstration is four minutes long, and none of them produces anything you could show in that time.

**Walk-in registration.** A second way in, for someone who turns up without a pass. The guard would register them at the gate — name, phone confirmed by code, a photo taken on the spot — enough to hold the visit but granting no standing at all. Walk-ins would be chased on far shorter timers than booked visits, seven minutes rather than thirty, because a person is physically standing there waiting.

**The background scheduler.** Five jobs running every couple of minutes: chasing a host who hasn't approved, chasing a host who hasn't confirmed a visitor's arrival, noticing someone who entered but reached no checkpoint, noticing overstays, and expiring dead requests. This is the biggest omission and the first thing to add back — it is what turns the system from a register into something that chases people.

**Fallback authority.** What happens when the chasing runs out of people to ask: the admin block during working hours, the security desk outside them. They see the photograph taken at the gate, must give a reason, and can either turn the visitor away or admit them on restricted terms — meeting point only, short window, flagged the whole time.

**What their absence changes, in practice.** Nothing *becomes* a problem while you watch. The visitors who are overstaying or unconfirmed start out that way, so every dashboard is correct and full the moment you open it — but no alarm goes off during a demonstration, and nothing in the system claims otherwise. Two counts on the honesty panel are permanently zero for the same reason: restricted admissions, and walk-ins turned away. Both are shown as zero rather than hidden.

---

## Before this goes anywhere real

Two things must be fixed first. Both are honest shortcuts that make the prototype convenient, and both would make a real deployment indefensible.

### Anyone can call anything

Roles are claimed with a plain header, and nothing checks whether the claim is true. Leaving the header off makes you an administrator, and the `admin` role satisfies every check in the system. There is no login, no password and no token anywhere.

Anyone who can reach the server can approve their own visit, revoke someone's pass, or read the entire visitor list.

Fixing it is more than swapping the header for a login token: the admin-satisfies-everything rule and the absent-header default both have to go, and identity has to become real. Approving a visit currently doesn't check that the caller is the host named on it.

### The signing key is published in this repository

QR codes are signed so they cannot be forged, and that signature is the entire basis on which the gate admits anyone. The key doing the signing has a built-in default value visible to anyone holding a copy of this code. On startup you will see:

```
WARNING  HMAC_SECRET is the built-in development default. Every pass
         signature is forgeable by anyone with this repository.
```

Anyone with the repository can mint a pass that scans as genuine. Forging a pass and walking through the gate become the same act.

**The fix takes a minute:**

```powershell
cd D:\Projects\SVMS\Backend
Copy-Item .env.example .env
# then put a long random value in HMAC_SECRET
```

Passes signed with the old key stop working, which is correct. Note that `.env.example` ships a placeholder rather than a working value, so copying it without editing cannot leave you quietly insecure.

The design here is sound — the weakness is entirely in key management, which is exactly the part a real deployment has to supply.

### One thing that is not a shortcut

The identity hash taken from a government ID is stored but **never returned by any endpoint**. Responses list their fields explicitly instead of dumping the whole record, so a field added later cannot leak out by accident. Only the last four digits are returned, which is what a guard checks against a physical card.

---

## Where things are

| File | What it is |
|---|---|
| `README.md` | This file |
| `Backend/SPEC.md` | The full design — every rule, entity, endpoint and setting |
| `Backend/CLAUDE.md` | How the build proceeded, and every decision taken along the way |
| `Backend/smoke.sh` | The 93-check test script |
| `Backend/app/` | The code |

`SPEC.md` describes the **whole** system, including the three parts that were not built. `CLAUDE.md` records what was built and why the rest was left out. Where the two disagree about scope, `CLAUDE.md` is the one describing the code that actually exists.
