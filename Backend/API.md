# API reference

Every endpoint, what it does, what comes back, and what it returns when it goes wrong.

Base URL when running locally: `http://127.0.0.1:8000`

For an explanation of what the system *is*, see [the README](../README.md). This file is for someone with the server running who wants to call it.

---

## Authentication

**Every endpoint needs a token.** The only exceptions are `POST /auth/login`, `POST /auth/visitor/register` and `GET /health`.

| Endpoint | What it does | Returns | If it fails |
|---|---|---|---|
| `POST /auth/login` | Exchange a username and password for a token | `200` + `{token, role, name, username, expires_at, visitor_id}` | `401` wrong username **or** password — the message is identical for both, so it never reveals which accounts exist |
| `POST /auth/visitor/register` | **Public.** Sign up as a visitor: creates the visitor record *and* an account that owns it, then logs it in | `201` + the same body as a login, with `visitor_id` set | `400` the phone already has an account, or the photo is over 2 MB |
| `POST /auth/logout` | Invalidate the token you are calling with | `200` + `{logged_out: true}` | `401` no or bad token |
| `GET /auth/me` | Who the token says you are | `200` + `{id, username, name, role}` | `401` |

Four fixed accounts, one per role:

| Username | Password | Role |
|---|---|---|
| `guard` | `guard123` | `guard` |
| `faculty` | `faculty123` | `faculty` |
| `security` | `security123` | `security` |
| `admin` | `admin123` | `admin` |

**Staff accounts are issued; visitor accounts are created.** No endpoint makes a fifth staff account. A visitor signs up at `POST /auth/visitor/register` and gets role `visitor`.

A visitor's **username is their phone**, normalised to the last ten digits — `+91-98111-22233`, `09811122233` and `9811122233` are all one account.

**A visitor account is scoped to itself.** It may read its own visitor record, run its own OTP and DigiLocker, request its own pass and fetch its own QR. Any other visitor's record, visit, pass or scan history is a `403`, and `POST /visits` substitutes the account's own `visitor_id` for whatever the body claims. Every staff endpoint — the inbox, all three scans, the dashboards, `/dev/*` — refuses it.

`admin` satisfies every **staff** role check. It does not make anyone a visitor, and `visitor` satisfies nothing: that role is an ownership boundary, not a privilege level.

Send the token on every other request:

```
Authorization: Bearer <token>
```

Tokens last **12 hours**, survive `/dev/reset`, and run on real wall-clock time — `/dev/advance-clock` moves the campus clock a day forward without logging you out.

`admin` satisfies every role check. The old `X-Role` header does nothing at all; sending it gets you a `401` like sending nothing.

**Status codes.** There are only seven things that come back.

| Code | Meaning | Usually because |
|---|---|---|
| `200` | Fine | — |
| `201` | Created | Only `POST /visitors` and `POST /visits` |
| `400` | Your request broke a rule | `InvalidRequest`, `CompanionLimitExceeded` |
| `401` | We don't know who you are | `NotAuthenticated` — no token, unknown token, expired token |
| `403` | We know, and you may not | `NotPermitted` — valid token, wrong role |
| `404` | No such record | `NotFound` |
| `409` | Right request, wrong moment | `IllegalTransition`, `VisitorAlreadyInside` |
| `422` | Body is malformed | Missing field, or a timestamp with no timezone |

**401 and 403 mean different things** and it is worth keeping them apart when debugging: `401` is a login problem, `403` is a permissions problem. If you get `401` on something that worked a minute ago, your token expired or someone reset the server.

**Every error looks like this**, so you can always find out what happened:

```json
{
  "error": {
    "code": "IllegalTransition",
    "message": "Cannot move visit v_3 from closed to closed",
    "detail": { "visit_id": "v_3", "from": "closed", "to": "closed" }
  }
}
```

The one exception is `422`, which keeps the framework's own format.

**Two things are true of every table below.** Each endpoint also returns `401` without a valid token — it is left out of the failure columns rather than repeated thirty times. And a Role of **any** means any logged-in caller, not "no login needed".

**Scans never return an error for a refusal.** A forged pass, a revoked pass or somebody already inside all come back as `200` with a boolean saying no. This is on purpose: every scan attempt has to reach the permanent record, and an error status invites the caller to drop the request before it is written. Check `admitted` / `ok` / `exited`, not the status code.

---

## Visitor registration

| Endpoint | Role | What it does | Returns | If it fails |
|---|---|---|---|---|
| `POST /visitors` | any | Register someone **else** — needs a token, so it is staff registering a walk-up. A visitor signing up for themselves uses `POST /auth/visitor/register` | `201` + the visitor record | `400` photo over 2 MB · `422` name or phone missing |
| `GET /visitors/{id}` | any | Everything known about one visitor | `200` + the record, including `tier` | `404` no such visitor |
| `GET /visitors/lookup?phone=` | guard | Find a returning visitor by phone | `200` + the record, or `null` if none | — |
| `POST /visitors/{id}/otp/send` | any | Send a one-time code | `200` + `{visitor_id, phone, code}` | `404` |
| `POST /visitors/{id}/otp/verify` | any | Check the code, mark phone confirmed | `200` + `phone_verified: true` | `400` code is not six digits · `404` |
| `POST /visitors/{id}/digilocker` | any | Verify government ID | `200` + `is_permanent: true`, `tier: verified` | `404` |
| `GET /photos/{ref}` | any | Fetch a stored photograph | `200` + the image | `404` no such photo |

> **`otp/verify` accepts any six digits.** It is a stub — nothing is stored between sending and checking, so only the *shape* is validated. See the security note in the README.

---

## Pass requests and approval

| Endpoint | Role | What it does | Returns | If it fails |
|---|---|---|---|---|
| `POST /visits` | any | Request a visit | `201` + the visit, status `requested` | `400` over 4 companions, or `companions` and `person_count` both sent · `404` unknown visitor or host · `409` visitor already inside · `422` timestamp without a timezone |
| `GET /visits` | faculty | The staff inbox. Filter `?host_id=` `?status=` `?date=` | `200` + a list | `403` |
| `GET /visits/{id}` | any | One visit and everyone on it | `200` + the visit plus `companions` | `404` |
| `POST /visits/{id}/approve` | faculty | Set zones and window, issue the QR | `200` + the visit, status `issued` | `400` window ends before it starts, or unknown zone in the list · `404` unknown visit or meeting zone · `409` not `requested` |
| `POST /visits/{id}/reject` | faculty | Turn down a request | `200` + status `rejected` | `409` not `requested` · `422` no reason given |
| `POST /visits/{id}/cancel` | faculty | Call off an approved visit | `200` + status `cancelled` | `409` not `issued` |
| `GET /visits/{id}/scans` | any | Every scan attempted, failures included | `200` + a list, oldest first | `404` |

**Companions.** Up to four named people each get a photo. Beyond that use `person_count`, which is the **total including the visitor** — a visitor plus four companions is `5`. Sending both fields is a `400`.

---

## Passes

| Endpoint | Role | What it does | Returns | If it fails |
|---|---|---|---|---|
| `GET /passes/{visit_id}` | any | The QR payload and the 6-digit backup | `200` + `{qr: {payload, signature}, code6}` | `404` no pass issued yet |
| `POST /passes/{visit_id}/revoke` | security | Stop a pass admitting anyone | `200` + `revoked_at` set | `404` |

The QR holds **only** `visit_id` and `nonce`. Zones and the expiry are read from the visit record at every scan, which is why moving a meeting never reissues the code. Revoking blocks future *entry*; it does not eject anyone already inside, and they can still scan out.

---

## Entry, movement and exit

All three scan endpoints return `200` even when the answer is no.

| Endpoint | Role | What it does | Returns | If it fails |
|---|---|---|---|---|
| `POST /scans/gate/entry` | guard | Scan in at the gate | `200` + `admitted`, every face, vehicle and headcount comparison | `400` neither a payload nor a `code6` |
| `POST /scans/zone` | guard | Scan at a checkpoint | `200` + `ok`, and `allowed_zones` read live | `400` unknown `zone_code`, or no payload and no `code6` |
| `POST /scans/gate/exit` | guard | Scan out, counting people leaving | `200` + `exited`, `partial_exit`, `still_inside` | `400` neither a payload nor a `code6` |
| `POST /visits/{id}/arrival-ack` | faculty | Host confirms they are free | `200` + `host_acked_at` set | `400` visit is not `inside`, or restricted and `allowed_zones`/`valid_to` missing · `404` |
| `PATCH /visits/{id}/meeting-point` | faculty | Move the meeting. **Never reissues the QR** | `200` + new `meeting_zone_id` and `allowed_zones` | `400` visit is not `issued` or `inside` · `404` unknown zone or visit |
| `POST /visits/{id}/close` | guard | End-of-day close-out | `200` + status `closed`, `closed_reason` set | `400` reason outside the four allowed · `409` not `inside` |

**Scan bodies** take either `payload` + `signature` **as two top-level fields**, or `code6` on its own. Pasting the whole `qr` object in one piece is the most common `400` here — the two halves have to be separate.

**Result values** you will see in `result`:

| Value | Where | Means |
|---|---|---|
| `ok` | all three | The scan worked |
| `bad_signature` | all three | Forged, altered, or a superseded code. **No scan event is written** — there is no trustworthy visit to attach it to |
| `wrong_status` | all three | The visit is not in a state where this scan makes sense |
| `revoked` | entry only | Pass was cancelled |
| `expired` | entry only | Outside the pass window |
| `already_inside` | entry only | This visitor is inside on a different visit |
| `wrong_zone` | zone only | Not cleared for this checkpoint. Security notified, nobody stopped |

**Mismatches are separate from the result.** A vehicle or headcount that doesn't match still comes back `ok` with `vehicle.mismatch` or `headcount.mismatch` true. Nothing is ever blocked over a mismatch.

**Close-out reasons** must be one of `left_without_scanning`, `still_inside`, `partial_exit`, `system_error`.

---

## Dashboards

| Endpoint | Role | What it does | Returns | If it fails |
|---|---|---|---|---|
| `GET /dashboard/inside` | security | Who is on campus, longest inside first | `200` + rows with all six flags | `403` guard or faculty |
| `GET /dashboard/exceptions` | security | Five separate unmerged lists | `200` + `{overstaying, no_destination_scan, wrong_zone, partial_exit, awaiting_host_ack}` | `403` |
| `GET /dashboard/honesty` | **admin** | Plain counts of what went wrong | `200` + every field, zeros included | `403` — security is refused here too |

**The six flags**, all worked out at read time and stored nowhere:

| Flag | True when |
|---|---|
| `overstaying` | Inside, no exit, and past `valid_to` |
| `no_destination_scan` | Inside 30+ minutes with no successful checkpoint scan |
| `wrong_zone_scan` | Scanned somewhere not on the pass, today |
| `partial_exit` | Inside, and fewer people signed out than in |
| `restricted` | The visit's `restricted` field |
| `host_not_acked` | Inside 12+ minutes and the host has not confirmed |

Two keys on the exceptions screen are spelled differently from their flags: `wrong_zone` and `awaiting_host_ack` are the same conditions as `wrong_zone_scan` and `host_not_acked`.

---

## Reference data

| Endpoint | Role | What it does | Returns |
|---|---|---|---|
| `GET /zones` | any | The five campus zones | `200` + `id`, `code`, `name` |
| `GET /hosts` | any | Staff, with phone numbers | `200` + `id`, `name`, `department`, `phone` |
| `GET /health` | any | Server is up, and the time it thinks it is | `200` + `status`, `now_local`, `clock_offset_minutes` |

Zone **ids** (`z_2`) go in request bodies. Zone **codes** (`LIB`) go in scan bodies, because that is what a scanner at a door reads.

---

## Development endpoints

None of these would exist in a real deployment. All except `/dev/notifications` and `/dev/whoami` require the `admin` role.

| Endpoint | What it does | Returns |
|---|---|---|
| `POST /dev/reset` | Wipe and reload the starting campus, clock included. **Sessions survive** | `200` + record counts |
| `POST /dev/advance-clock` | Jump time forward by `{"minutes": N}` | `200` + the new time |
| `POST /dev/transition` | Force a visit into any state | `200`, or `409` if the move is illegal |
| `GET /dev/notifications` | Every message the system would have sent | `200` + a list |
| `GET /dev/whoami` | Which role your header is granting | `200` |

`/dev/reset` gives back identical ids every time — `z_1`–`z_5`, `h_1`–`h_3`, `vr_1`–`vr_6`, `v_1`–`v_6` — so any script can rely on them.

---

## PowerShell notes

Windows PowerShell behaves unexpectedly in four ways here. Each one costs real time to work out from scratch.

**1. Variable names ignore case.** `$b` and `$B` are the same variable. If your base URL is `$B`, never use `$b` for a body — the URL silently becomes a hashtable and you get *Invalid URI: The hostname could not be parsed*.

**2. `Select` does not work; `Select-Object` does.** The alias returns blank rows.

**3. Piping `Invoke-RestMethod` straight into `Select-Object` prints one empty row.** It hands the whole list over as a single item. Assign it first:

```powershell
$rows = Invoke-RestMethod "$B/dashboard/inside" -Headers $security   # $security from a login
$rows | Select-Object visitor_name, minutes_inside | Format-Table
```

**4. Every nested call needs the token too.** `(Invoke-RestMethod "$B/passes/v_3")` inside a larger command is a request in its own right, and it will `401` on you while the outer call looks fine.

**Building a scan body**, avoiding all four:

```powershell
$B = "http://127.0.0.1:8000"

$body  = @{ username = "guard"; password = "guard123" } | ConvertTo-Json
$token = (Invoke-RestMethod -Method Post "$B/auth/login" -ContentType application/json -Body $body).token
$guard = @{ Authorization = "Bearer $token" }

$qr = (Invoke-RestMethod "$B/passes/v_3" -Headers $guard).qr
$json = @{ payload = $qr.payload; signature = $qr.signature; person_count_in = 3 } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post "$B/scans/gate/entry" -ContentType application/json `
  -Headers $guard -Body $json
```

---

## Interactive documentation

`http://127.0.0.1:8000/docs` lists every endpoint with a **Try it out** button, fills in the body shape for you, and shows the exact response. For anything you only need to run once, it is faster than the terminal.
