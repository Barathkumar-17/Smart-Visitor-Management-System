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

after the team graduates. Most campus projects die here.
