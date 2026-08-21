"""Domain exceptions and the ONE FastAPI exception handler. SPEC sections 8, 15, 16.6.

Routers raise none of these directly; services do. There are no scattered
`raise HTTPException` calls anywhere in the codebase - every domain failure
becomes an exception here and is mapped to its HTTP code in one place.

SCAN ENDPOINTS NEVER USE THIS ENVELOPE. A scan failure returns 200 carrying its
outcome, so the ScanEvent can never be lost to an early exit. SPEC section 8.
"""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base for every domain exception. Carries the HTTP code it maps to."""

    status_code: int = 400

    def __init__(self, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        # Always an object, never a string. Omitted from the response when empty.
        self.detail = detail or {}


class NotFound(DomainError):
    """Any id that does not resolve - visitor, visit, host, zone, pass."""

    status_code = 404


class IllegalTransition(DomainError):
    """transition() rejected a move not in the legal table. SPEC section 8."""

    status_code = 409


class InvalidRequest(DomainError):
    """Structurally valid body that breaks a domain rule."""

    status_code = 400


class CompanionLimitExceeded(DomainError):
    """More than MAX_LINKED_COMPANIONS companions supplied."""

    status_code = 400


class NotPermitted(DomainError):
    """require_role rejected the caller."""

    status_code = 403


class VisitorAlreadyInside(DomainError):
    """Creating a visit or walk-in for a visitor already inside elsewhere.

    Distinct from the `already_inside` SCAN result, which is a 200 outcome on
    the scan path. Same fact, two paths, two responses. SPEC section 8.
    """

    status_code = 409


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """The single handler required by SPEC section 15.

    `code` is the exception class name verbatim so a test can assert on it
    without parsing prose. FastAPI's own 422 validation body is NOT rewritten
    into this envelope - a schema failure and a domain failure are different
    animals and the difference is worth seeing. SPEC section 16.6.
    """
    body: dict[str, Any] = {
        "code": type(exc).__name__,
        "message": exc.message,
    }
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content={"error": body})
