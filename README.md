# Smart Visitor Management System

A working prototype of the software a college gate would run to manage visitors — from the moment someone asks to come in, to the moment they leave.

This is a **backend**: the engine, not the screens. There is no app and no website. You use it by sending it requests.

Nothing is saved to disk. It runs entirely in memory, starts with a realistic campus already loaded, and forgets everything when you stop it. That is deliberate — you cannot break it in any way a restart won't fix.

**Endpoint reference:** [`Backend/API.md`](Backend/API.md) — every endpoint, what it returns, and what each failure means.

---

## The problem it solves

At most campus gates today a visitor writes their name in a paper register, the guard rings the host, and the host either answers or doesn't. Nobody can tell you who is on campus right now. Nobody notices when a visitor wanders somewhere they shouldn't. And when someone forgets to sign out, they stay in that register forever.

**What it does:** creates accountability. Who came in, when, to meet whom, where they went, when they left.

**What it does not do:** stop someone determined to get in. Anyone avoiding this will use a side gate or walk in looking like a student. This manages cooperative visitors, which is almost everyone who comes to a campus. Saying so plainly is a design position, not a gap.

The rule the whole system follows: **firm control at the gate, quiet observation inside.** The gate has a barrier and a guard, so entry can genuinely be decided there. Inside, there is no guard at every door — so checkpoint scans only record and alert, and never pretend to block anyone.

---

## How a visit works

1. **The visitor registers.** Name and phone at minimum, confirmed by a one-time code. Verifying a government ID makes them permanently trusted; otherwise a staff member can vouch for them for 100 days, with the voucher's name kept on the record.

2. **They ask to visit someone.** Who, why, when, how many people, and what vehicle. Up to four companions get their own photo; beyond that it becomes a headcount. One QR covers the whole group.

3. **The host approves.** They pick where the meeting happens, which other areas are allowed, and how long the pass lasts. A QR code and a 6-digit backup number are created at that moment.

4. **They arrive at the gate.** The guard scans, and the screen fills with every face on the pass, the vehicle expected, and how many people there should be. A mismatch is flagged and recorded — never used to turn anyone away.

5. **They move around campus.** Checkpoint scans confirm they got where they were going. A scan somewhere unexpected tells security without stopping anybody. The most useful signal is an **absence** — entered half an hour ago, reached no checkpoint at all.

6. **They leave.** One scan out, and the guard counts the people leaving. If fewer leave than arrived, the visit stays open and security is told, because somebody is still inside.

---

## The one idea worth understanding

**The QR code contains almost nothing** — a visit number and a random string. No name, no zones, no expiry, no photo.

That sounds like a weakness. It is the most important decision in the system.

Because the QR is only a *pointer*, everything about the visit can change while the visitor keeps the same code. A host can move the meeting from the library to their department office, extend the visit by two hours, or widen where the visitor may go, and the image on the visitor's phone stays identical to the one they were sent that morning. Every scan looks up the current truth.

If the QR carried the details instead, each of those changes would mean cancelling the pass and issuing a new one, leaving the visitor at a checkpoint holding a code that no longer works.

The code is also **signed**, so it cannot be forged or altered. You can watch all of this in the demonstration below.

---

## Getting it running

You need **Python 3.11 or newer**. Packages live in a `.venv` folder at the top level, separate from anything else on your machine.

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

- The name is **`app.main:app`**, not `main:app`. Getting it wrong gives *Could not import module "main"*.
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

**There is also a browser page.** Open **http://127.0.0.1:8000/docs** for a clickable list of every endpoint with a *Try it out* button on each.

---

## Logging in

**Every endpoint needs a login.** The only two exceptions are `/health` and the login itself.

There are four accounts, one per role, and they are fixed — there is no sign-up and no user administration.

| Username | Password | Can do |
|---|---|---|
| `guard` | `guard123` | Scan people in and out, close visits |
| `faculty` | `faculty123` | Approve visits, confirm availability, move meetings |
| `security` | `security123` | Read the campus and exception dashboards, revoke passes |
| `admin` | `admin123` | Everything, including the honesty panel and the demo tools |

Paste this helper once — everything below uses it:

```powershell
$B = "http://127.0.0.1:8000"

function Login($user, $pass) {
  $body = @{ username = $user; password = $pass } | ConvertTo-Json
  $t = (Invoke-RestMethod -Method Post "$B/auth/login" -ContentType application/json -Body $body).token
  return @{ Authorization = "Bearer $t" }
}

$guard    = Login guard    guard123
$faculty  = Login faculty  faculty123
$security = Login security security123
$admin    = Login admin    admin123
```

Each call returns a header you attach to later requests. Without one you get `401`; with the wrong role you get `403`.

Tokens last 12 hours and survive a reset. `POST /auth/logout` ends one early.

---

## Who is already in the system

It starts with a campus mid-morning, so there is something to look at immediately. You never have to set anything up.

**Five zones** — `MAIN` Main Block, `LIB` Library, `ADMIN` Admin Block, `HOSTEL` Hostel Gate, `DEPT` Department Office.

**Three staff** — Dr. Anitha Rao and Prof. Vikram Menon (Computer Science), Dr. Sunita Pillai (Mechanical Engineering).

**Six visitors**, each showing a different situation:

| Visitor | Visit | Situation |
|---|---|---|
| Ramesh Kumar | `v_1` | Has asked to visit. Nobody has approved yet |
| Suresh Iyer | `v_3` | Approved, holding a QR, hasn't arrived. Two companions and a van |
| Deepa Nair | `v_2` | Inside on **restricted** terms — meeting point only |
| Fatima Sheikh | `v_4` | Inside 40 minutes; their host still hasn't confirmed |
| George Mathew | `v_5` | Inside, and scanned somewhere they weren't cleared for |
| Nandini Krishnan | `v_6` | Inside, and their pass expired half an hour ago |

**To put everything back exactly as it started:**

```powershell
Invoke-RestMethod -Method Post "$B/dev/reset" -Headers $admin
```

Every name, number and id comes back identical, so nothing you do is permanent. Resetting restores the campus but does **not** log you out.

---

## See it working in four minutes

With the four tokens from the section above in hand, start from a clean campus:

```powershell
Invoke-RestMethod -Method Post "$B/dev/reset" -Headers $admin | Out-Null
```

### One — somebody arrives at the gate

Suresh Iyer, with two people and a van.

```powershell
$qr = (Invoke-RestMethod "$B/passes/v_3" -Headers $guard).qr
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

Three faces to compare, and the host's phone number so the guard can ring them directly.

**Try changing the plate to `TN-99-ZZ-0001`.** They are still admitted — but `vehicle.mismatch` comes back true and security is told.

### Two — the meeting moves, the QR does not

Fatima Sheikh is already inside, expected at the Department Office.

```powershell
"QR before: " + (Invoke-RestMethod "$B/passes/v_4" -Headers $guard).qr.signature

function Scan($code) {
  $q = (Invoke-RestMethod "$B/passes/v_4" -Headers $guard).qr
  $json = @{ zone_code = $code; payload = $q.payload; signature = $q.signature } | ConvertTo-Json -Depth 5
  $x = Invoke-RestMethod -Method Post "$B/scans/zone" -ContentType application/json -Headers $guard -Body $json
  "{0,-6} {1}" -f $code, $x.result
}

Scan "DEPT"          # where they are expected
Scan "LIB"           # where they are not

$patch = @{ meeting_zone_id = "z_2" } | ConvertTo-Json
Invoke-RestMethod -Method Patch "$B/visits/v_4/meeting-point" `
  -ContentType application/json -Headers $faculty -Body $patch | Out-Null

"QR after : " + (Invoke-RestMethod "$B/passes/v_4" -Headers $guard).qr.signature

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

(The signature differs after every reset — what matters is that the two lines match each other.)

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

**None of those warnings is stored anywhere.** They are worked out fresh each time you ask. A saved warning goes stale the moment the situation changes; a calculated one can't.

> Storing the result in `$inside` first is not optional — piping `Invoke-RestMethod` straight into `Select-Object` prints one blank row. That and two other PowerShell traps are explained in [`API.md`](Backend/API.md).

---

## Testing all of it at once

There is a script that exercises every feature in order and stops the instant anything is wrong. It needs Git Bash and `jq` (`winget install jqlang.jq`, then open a fresh terminal).

With the server running, in a second window:

```powershell
cd D:\Projects\SVMS\Backend
bash smoke.sh
```

100 checks. Every one asserts on a specific field, so a wrong answer halts the script at the step that produced it. The last line should read `All steps passed.`

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

Full detail per endpoint is in [`Backend/API.md`](Backend/API.md).

---

## Where this goes next

The design covers more than the current build implements. Three pieces are fully specified and are the natural next work — each extends what is already here rather than replacing any of it.

### Walk-in registration

A second way in, for a visitor who turns up without a pass. The guard registers them at the gate — name, phone confirmed by a code, a photo taken on the spot — enough to open a visit, granting no standing on its own. A returning walk-in is found by phone and skips the form entirely.

Walk-ins would be chased on much shorter timers than booked visits, seven minutes rather than thirty, because a person is physically standing at the gate while the system waits for an answer.

**Most of this already exists.** Registration, phone verification, vouching and the whole scan path are built; what it needs is the endpoint that opens a visit from the gate.

### The background scheduler

Five jobs on a two-minute cycle:

| Job | What it would catch |
|---|---|
| Approval chasing | A request nobody has answered — escalate to the department, then higher |
| Arrival chasing | A visitor inside whose host never confirmed |
| No checkpoint scan | Entered the gate, reached nowhere. **The signal is the absence** |
| Overstay | Past the pass window with no exit scan |
| Expiry | Requests nobody actioned, passes nobody used |

This is the single biggest addition available, and the one that changes what the system *is*: today it records what happened, and with this it starts noticing what didn't. Every job would call the same services the endpoints already call, so it adds a scheduler rather than a second copy of the rules.

### Fallback authority

The decision made when chasing runs out of people to ask — the admin block during working hours, the security desk outside them, chosen at the moment it is needed rather than in advance.

They see the photograph taken at the gate, must give a reason, and can either turn the visitor away or admit them on restricted terms: meeting point only, a short window, flagged for as long as the visit stays open.

### Smaller things worth adding

- **Unit tests** on the decision functions — the state machine, the flag rules, the group-size logic. They are near-pure and need no server to exercise.
- **Persistence.** The storage layer is written as if a database were behind it, so this is a matter of filling in the repositories rather than rewriting the services.
- **An account per host**, so approving a visit can check you are the host named on it rather than merely *a* faculty member.

### What this means when you run it today

Worth knowing before a demonstration: nothing *becomes* a problem while you watch. The visitors who are overstaying or unconfirmed start out that way, so every dashboard is correct and full the moment you open it — but no alarm fires mid-session, because the scheduler is what would fire it.

Two counts on the honesty panel are zero for the same reason, and are shown as zero rather than hidden. Nothing in the system claims otherwise.

---

## Known weaknesses, kept on purpose

Three deliberate shortcuts, listed here rather than left to be discovered. Each one buys something a prototype genuinely needs — it runs with no setup, it demonstrates in a minute, it needs no external service — and each one has to be closed before this becomes a product. None is an oversight, and each is documented at the code that implements it as well as here.

Authentication used to be a fourth and the worst of them: a header you typed, believed without question, defaulting to administrator when absent. **That one is now closed.** Every endpoint requires a real login, and the old header grants nothing.

### 1. The four passwords are written into the repository

`Backend/app/store/seed.py` contains the accounts and their plain-text passwords. They are stored hashed, so dumping the running store gives nothing away — but anyone who can read this code knows all four logins, which makes the login a demonstration of the mechanism rather than actual protection.

Two other limits worth knowing:

- **`admin` still satisfies every role check.** With a real login behind it that is ordinary superuser behaviour rather than a hole, but it means one leaked password is total access.
- **Identity stops at the role.** Logging in as `faculty` proves you are *a* faculty member, not *which* one. Approving a visit still doesn't check that you are the host named on it, because four fixed accounts cannot express thirty individual staff. That needs an account per host.

**Closing it:** accounts in a real store with per-person credentials, passwords set on first use rather than written in source, and the host check tied to the logged-in user.

### 2. The signing key is published in this repository

QR codes are signed so they cannot be forged, and that signature is the entire basis on which the gate admits anyone. The key has a built-in default value visible to anyone holding a copy of this code. On startup you will see:

```
WARNING  HMAC_SECRET is the built-in development default. Every pass
         signature is forgeable by anyone with this repository.
```

**Closing it takes a minute:**

```powershell
cd D:\Projects\SVMS\Backend
Copy-Item .env.example .env
# then put a long random value in HMAC_SECRET
```

Passes signed with the old key stop working, which is correct. `.env.example` ships a placeholder rather than a working value, so copying it without editing cannot leave you quietly insecure.

The design here is sound — the weakness is entirely in key management, which is the part a real deployment has to supply.

### 3. Phone verification accepts any six digits

There is no SMS gateway, so nothing is kept between sending a code and checking it. `POST /visitors/{id}/otp/verify` validates only that the code is six digits long — `000000` works. This is what lets the system be demonstrated with no phone and no account anywhere.

**Closing it** means swapping the two functions in `integrations/otp.py` for a real gateway. Nothing else in the system changes, because nothing else knows how the code is delivered.

### One thing that is deliberately not a shortcut

The identity hash taken from a government ID is stored but **never returned by any endpoint**. Responses list their fields explicitly instead of dumping the whole record, so a field added later cannot leak out by accident. Only the last four digits are returned, which is what a guard checks against a physical card.

---

## Where things are

| File | What it is |
|---|---|
| `README.md` | This file — what it is, how to run it, what to look at |
| `Backend/API.md` | Every endpoint, what it returns, and what each failure means |
| `Backend/smoke.sh` | The 100-check test script |
| `Backend/app/` | The code |

Inside `Backend/app/`: `routers/` receive requests, `services/` hold the rules, `repositories/` are the only code that touches storage, and `store/` holds the in-memory data and the seed. A request goes router → service → repository and never skips a layer.
