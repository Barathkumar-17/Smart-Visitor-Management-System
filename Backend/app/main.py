"""FastAPI app and router registration. SPEC section 16.8.

Run with: uvicorn app.main:app --reload

THIS FILE DOES NOT START THE SCHEDULER. Phase 11 is deferred, jobs/scheduler.py
is empty, and adding the startup call is part of that phase, not this one.
"""

from typing import Any

from fastapi import FastAPI

from app.core import clock
from app.core.errors import DomainError, domain_error_handler
from app.routers import dev

app = FastAPI(
    title="Smart Visitor Management System",
    description="Campus visitor management for MIT Campus. In-memory prototype.",
    version="0.1.0",
)

# The single domain exception handler required by SPEC section 15. Registered
# on the base class so every subclass in core/errors.py routes through it.
app.add_exception_handler(DomainError, domain_error_handler)

app.include_router(dev.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, Any]:
    """Liveness, plus the current clock so /dev/advance-clock is observable.

uk    `now` is the canonical aware-UTC value per SPEC section 16.7. `now_local`
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
