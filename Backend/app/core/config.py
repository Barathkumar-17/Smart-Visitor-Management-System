"""Settings and every tunable window.

No service or router hardcodes a window; they all read it from here.

The values below are the design's proposals and are UNVALIDATED. They are
worth reviewing: ACK_WINDOW and NO_SCAN_WINDOW decide what the dashboards flag
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
# exists so the app runs with no.env during development. main.py logs a warning
# whenever it is in use; see DEFAULT_HMAC_SECRET_IN_USE.
DEV_HMAC_SECRET = "dev-secret-change-me"

HMAC_SECRET: str = os.getenv("HMAC_SECRET", DEV_HMAC_SECRET)

# True when signing is running on the committed default rather than a real key.
DEFAULT_HMAC_SECRET_IN_USE: bool = HMAC_SECRET == DEV_HMAC_SECRET

# Every "today" comparison and WORKING_HOURS is evaluated in this zone, never
# in UTC.
LOCAL_TZ: str = os.getenv("LOCAL_TZ", "Asia/Kolkata")

# --- Escalation windows -----------------------------------------------------
# Approval chain (job 1). Walk-ins are shorter because someone is standing at
# the gate. Each pair is (to department, then that much more to fallback).

APPROVAL_ESCALATION_PRE_REGISTERED_DEPARTMENT = timedelta(minutes=30)
APPROVAL_ESCALATION_PRE_REGISTERED_FALLBACK = timedelta(minutes=30)

APPROVAL_ESCALATION_WALK_IN_DEPARTMENT = timedelta(minutes=7)
APPROVAL_ESCALATION_WALK_IN_FALLBACK = timedelta(minutes=10)

# Acknowledgement chain (job 2). ACK_WINDOW runs from entry_at; the escalation
# stages after it run from the previous stage.
ACK_WINDOW = timedelta(minutes=12)
ACK_ESCALATION_DEPARTMENT = timedelta(minutes=10)
ACK_ESCALATION_FALLBACK = timedelta(minutes=10)

# --- Other windows ----------------------------------------------------------

NO_SCAN_WINDOW = timedelta(minutes=30)
RESTRICTED_VISIT_DURATION = timedelta(minutes=60)
VOUCH_VALIDITY_DAYS = 100

# --- Rules ------------------------------------------------------------------

# Counts companions ONLY, excluding the accountable visitor.
MAX_LINKED_COMPANIONS = 4

# Decoded photo size cap, fixed at 2 MB: the store is a
# dict in RAM, and an uncapped field turns a demo into an OOM.
MAX_PHOTO_BYTES = 2 * 1024 * 1024

# Local-time hours during which the fallback authority is the admin block;
# outside them it is security. Evaluated in LOCAL_TZ.
WORKING_HOURS_START = 9
WORKING_HOURS_END = 17

# --- Scheduler --------------------------------------------------------------

# Read by the scheduler, which is not implemented. Nothing starts it in this
# build.
SCHEDULER_INTERVAL = timedelta(minutes=2)
