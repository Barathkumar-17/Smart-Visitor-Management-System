"""FastAPI app and router registration. SPEC section 16.8.

Run with: uvicorn app.main:app --reload

THIS FILE DOES NOT START THE SCHEDULER. Phase 11 is deferred, jobs/scheduler.py
is empty, and adding the startup call is part of that phase, not this one.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.core import clock
from app.core.config import DEFAULT_HMAC_SECRET_IN_USE
from app.core.errors import DomainError, domain_error_handler
from app.routers import dev, passes, reference, visitors, visits
from app.store import seed

# The state machine writes one audit line per status change, naming the actor
# (SPEC section 16.2). No entity in SPEC section 6 stores that string, so the
# log IS the audit trail - and uvicorn leaves the root logger at WARNING, which
# would silently drop every successful transition and keep only the failures.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the seed before the first request.

    SPEC section 13: the prototype must be demoable the moment it starts, so
    the store is never empty. /dev/reset reloads exactly the same data.
    """
    if DEFAULT_HMAC_SECRET_IN_USE:
        logging.getLogger("app.core.config").warning(
            "HMAC_SECRET is the built-in development default. Every pass "
            "signature is forgeable by anyone with this repository. Set "
            "HMAC_SECRET in .env before running this anywhere reachable."
        )
    seed.load()
    yield


app = FastAPI(
    title="Smart Visitor Management System",
    description="Campus visitor management for MIT Campus. In-memory prototype.",
    version="0.1.0",
    lifespan=lifespan,
)

# The single domain exception handler required by SPEC section 15. Registered
# on the base class so every subclass in core/errors.py routes through it.
app.add_exception_handler(DomainError, domain_error_handler)

app.include_router(reference.router)
app.include_router(visitors.router)
app.include_router(visitors.photos_router)
app.include_router(visits.router)
app.include_router(passes.router)
app.include_router(dev.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, Any]:
    """Liveness, plus the current clock so /dev/advance-clock is observable.

    `now` is the canonical aware-UTC value per SPEC section 16.7. `now_local`
    and `clock_offset_minutes` are there to be read by a human during manual
    testing - they are presentation, not new state.
    """
    offset_minutes = clock.offset().total_seconds() / 60
    return {
        "status": "ok",
        "now_local": clock.readable(),
        "clock_offset_minutes": offset_minutes,
        "now": clock.now().isoformat(),
    }
