"""Domain exceptions and the ONE FastAPI exception handler.

Routers raise none of these directly; services do. There are no scattered
`raise HTTPException` calls anywhere in the codebase - every domain failure
becomes an exception here and is mapped to its HTTP code in one place.

SCAN ENDPOINTS NEVER USE THIS ENVELOPE. A scan failure returns 200 carrying its
outcome, so the ScanEvent can never be lost to an early exit.
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
    """transition() rejected a move not in the legal table."""

    status_code = 409


class InvalidRequest(DomainError):
    """Structurally valid body that breaks a domain rule."""

    status_code = 400


class CompanionLimitExceeded(DomainError):
    """More than MAX_LINKED_COMPANIONS companions supplied."""

    status_code = 400


class NotAuthenticated(DomainError):
    """No token, an unknown token, or an expired one.

    Distinct from NotPermitted: this means we do not know WHO you are, not that
    we know and you may not. Conflating the two makes a login bug look like a
    permissions bug.
    """

    status_code = 401


class NotPermitted(DomainError):
    """A known caller whose role does not cover this endpoint."""

    status_code = 403


class VisitorAlreadyInside(DomainError):
    """Creating a visit or walk-in for a visitor already inside elsewhere.

    Distinct from the `already_inside` SCAN result, which is a 200 outcome on
    the scan path. Same fact, two paths, two responses.
    """

    status_code = 409


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """The single handler required by the design.

    `code` is the exception class name verbatim so a test can assert on it
    without parsing prose. FastAPI's own 422 validation body is NOT rewritten
    into this envelope - a schema failure and a domain failure are different
    animals and the difference is worth seeing.
    """
    body: dict[str, Any] = {
        "code": type(exc).__name__,
        "message": exc.message,
    }
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content={"error": body})
