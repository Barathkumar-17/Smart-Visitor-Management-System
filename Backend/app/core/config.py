"""Settings and every tunable window. SPEC section 12.

No service or router hardcodes a window; they all read it from here.

The values below are SPEC section 12's proposals and are UNVALIDATED. They are
reviewed at Phase 13, where ACK_WINDOW and NO_SCAN_WINDOW first become visible
on the dashboards and decide whether seeded visitors D and E appear as
exceptions at all.
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

# --- Secrets and locale -----------------------------------------------------

# The pass signature is the ENTIRE basis on which the gate admits anyone: the
# QR carries only a visit id and a nonce, and a matching HMAC is what proves
# this system issued it. Anyone holding this secret can mint a valid QR for any
# visit id - no approval, no host, no account. Forging a pass and walking
# through the gate become the same act.
#
# The fallback below is committed to the repository, so it protects nothing. It
# exists so the app runs with no .env during development. main.py logs a warning
# whenever it is in use; see DEFAULT_HMAC_SECRET_IN_USE.
DEV_HMAC_SECRET = "dev-secret-change-me"

HMAC_SECRET: str = os.getenv("HMAC_SECRET", DEV_HMAC_SECRET)

# True when signing is running on the committed default rather than a real key.
DEFAULT_HMAC_SECRET_IN_USE: bool = HMAC_SECRET == DEV_HMAC_SECRET

# Every "today" comparison and WORKING_HOURS is evaluated in this zone, never
# in UTC. SPEC section 16.7.
LOCAL_TZ: str = os.getenv("LOCAL_TZ", "Asia/Kolkata")

# --- Escalation windows -----------------------------------------------------
# Approval chain (job 1). Walk-ins are shorter because someone is standing at
# the gate. Each pair is (to department, then that much more to fallback).

APPROVAL_ESCALATION_PRE_REGISTERED_DEPARTMENT = timedelta(minutes=30)
APPROVAL_ESCALATION_PRE_REGISTERED_FALLBACK = timedelta(minutes=30)

APPROVAL_ESCALATION_WALK_IN_DEPARTMENT = timedelta(minutes=7)
APPROVAL_ESCALATION_WALK_IN_FALLBACK = timedelta(minutes=10)

# Acknowledgement chain (job 2). ACK_WINDOW runs from entry_at; the escalation
# stages after it run from the previous stage. SPEC section 11.
ACK_WINDOW = timedelta(minutes=12)
ACK_ESCALATION_DEPARTMENT = timedelta(minutes=10)
ACK_ESCALATION_FALLBACK = timedelta(minutes=10)

# --- Other windows ----------------------------------------------------------

NO_SCAN_WINDOW = timedelta(minutes=30)
RESTRICTED_VISIT_DURATION = timedelta(minutes=60)
VOUCH_VALIDITY_DAYS = 100

# --- Rules ------------------------------------------------------------------

# Counts companions ONLY, excluding the accountable visitor. SPEC section 6.
MAX_LINKED_COMPANIONS = 4

# Decoded photo size cap. SPEC section 16.5 fixes it at 2 MB: the store is a
# dict in RAM, and an uncapped field turns a demo into an OOM.
MAX_PHOTO_BYTES = 2 * 1024 * 1024

# Local-time hours during which the fallback authority is the admin block;
# outside them it is security. Evaluated in LOCAL_TZ. SPEC sections 4 and 16.3.
WORKING_HOURS_START = 9
WORKING_HOURS_END = 17

# --- Scheduler --------------------------------------------------------------

# Read by Phase 11, which is deferred. Nothing starts the scheduler in this
# build. SPEC section 16.8.
SCHEDULER_INTERVAL = timedelta(minutes=2)
