"""Background jobs - NOT IMPLEMENTED.

Reserved for the five-job scheduler described in the README: approval chasing,
arrival chasing, no-checkpoint detection, overstay and expiry. Nothing starts
this and main.py deliberately does not import it, so the file staying empty
cannot break anything.

When it is filled in, every job must call the same services the routers call
rather than reaching into repositories - otherwise the rules exist twice.

It will need a scheduler library; APScheduler is the obvious fit and is NOT in
requirements.txt, because installing it while nothing starts it only raises the
question of why the app has a scheduler that never runs.
"""
