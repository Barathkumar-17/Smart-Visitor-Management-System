"""Authentication and role checks.

HOW A CALLER IS IDENTIFIED. They post a username and password to
POST /auth/login, get a token back, and send it on every later request as
`Authorization: Bearer <token>`. No token, an unknown token or an expired one
is 401. A valid token whose role does not cover the endpoint is 403.

There is no way to claim a role without proving it. The previous version of
this file read an `X-Role` header and believed whatever it said, which meant an
unauthenticated caller could reach every endpoint in the system. That header is
gone and is not accepted in any form.

WHAT IS STILL A SHORTCUT, and it is a real one: the four accounts and their
passwords are written into the seed, so anyone reading this repository knows
every credential. That is deliberate for something meant to be run and
demonstrated in a minute, and it is exactly what has to change first if this is
ever deployed. Hashing the stored passwords does not fix it - the plain text is
in seed.py either way.

`admin` satisfies every role check. With real authentication behind it that is
ordinary superuser behaviour rather than the hole it used to be, because the
caller now has to prove they are the admin.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Header

from app.core.errors import NotAuthenticated, NotPermitted

# How long a token stays valid. Long enough that a demonstration never has to
# stop and log in again, short enough that it is not effectively forever.
TOKEN_LIFETIME = timedelta(hours=12)


def session_now() -> datetime:
    """REAL wall-clock time, deliberately NOT core.clock.

    Everything else in this system reads core.clock, which /dev/advance-clock
    can shift by hours to demonstrate overstays and expiring passes. Sessions
    must not move with it: jumping the campus clock a day forward to show an
    overstay would otherwise log everybody out mid-demonstration, which is both
    confusing and nothing to do with what was being shown.

    A login is a real event in the real world. The campus clock is a fiction
    for the visit rules, and this is the one place that fiction must not reach.
    """
    return datetime.now(timezone.utc)


# PBKDF2 rounds. Deliberately modest: this is a prototype logging four fixed
# accounts in, not a service defending a password database.
_PBKDF2_ROUNDS = 120_000

# "visitor" is a self-service account, created by POST /auth/visitor/register
# rather than seeded. It is deliberately NOT covered by admin's blanket pass in
# require_role: admin satisfying a staff role is superuser behaviour, but a
# visitor role is an ownership boundary, not a privilege level.
ROLES = ("guard", "faculty", "security", "admin", "visitor")


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Return (salt, hash). A fresh random salt unless one is supplied.

    Passwords are never stored or compared in plain text, even here. It costs
    two lines and means the store can be dumped without handing over accounts.
    """
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ROUNDS
    )
    return salt, digest.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Constant-time comparison, so a wrong password cannot be found one
    character at a time by measuring how long the answer takes."""
    _, actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hash)


def new_token() -> str:
    """A random opaque token. Not a JWT and carries no claims - the session
    record is the source of truth, so revoking one is a dict delete."""
    return secrets.token_urlsafe(32)


def _token_from_header(authorization: str | None) -> str:
    if not authorization:
        raise NotAuthenticated(
            "No credentials. Log in at POST /auth/login and send the token as "
            "'Authorization: Bearer <token>'.",
            {"header": "Authorization"},
        )

    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise NotAuthenticated(
            "Authorization header must read 'Bearer <token>'.",
            {"received": authorization[:20]},
        )
    return parts[1].strip()


def resolve_token(authorization: str | None) -> dict[str, Any]:
    """Turn an Authorization header into the caller, or raise 401.

    Imported inside the function to keep the import graph one-way: repositories
    never import core, and core is imported by everything.
    """
    from app.repositories import user_repo

    token = _token_from_header(authorization)
    session = user_repo.get_session(token)

    if session is None:
        raise NotAuthenticated("Unknown or expired token. Log in again.", {})

    if session["expires_at"] <= session_now():
        user_repo.delete_session(token)
        raise NotAuthenticated(
            "Token expired. Log in again.",
            {"expired_at": session["expires_at"].isoformat()},
        )

    user = user_repo.get(session["user_id"])
    if user is None:
        # The store was reset under a live token.
        user_repo.delete_session(token)
        raise NotAuthenticated("The account for this token no longer exists.", {})

    return {
        "id": user.id,
        "name": user.name,
        "role": user.role,
        "username": user.username,
        "visitor_id": getattr(user, "visitor_id", None),
    }


def require_user():
    """Any logged-in caller. Used where the endpoint has no role restriction
    but still must not be open to the world."""

    async def dependency(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        return resolve_token(authorization)

    return dependency


def require_role(*roles: str):
    """A logged-in caller holding one of `roles`.

    | Situation                       | Result               |
    |---------------------------------|----------------------|
    | no Authorization header         | NotAuthenticated 401 |
    | unknown or expired token        | NotAuthenticated 401 |
    | valid token, role in the set    | permitted            |
    | valid token, role `admin`       | permitted            |
    | valid token, role not in the set| NotPermitted 403     |

    Where a faculty endpoint acts on a specific visit, the ACTING host is still
    the visit's host_id rather than the logged-in user. Logging in proves the
    role; the path establishes which host. Tying the two together needs a user
    account per host, which four fixed accounts cannot express.
    """

    async def dependency(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        user = resolve_token(authorization)

        if user["role"] == "admin" or not roles or user["role"] in roles:
            return user

        raise NotPermitted(
            f"Role '{user['role']}' may not call this endpoint",
            {"role": user["role"], "required": sorted(roles)},
        )

    return dependency


def require_staff():
    """Any logged-in caller who is NOT a self-service visitor.

    `require_user` means "anyone with a token", and before visitor accounts
    existed that was the same thing as "anyone we trust". It is not any more.
    Endpoints that were written as require_user because every caller was staff
    should say so explicitly rather than silently widening the moment a new
    role appears.
    """

    async def dependency(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        user = resolve_token(authorization)
        if user["role"] == "visitor":
            raise NotPermitted(
                "This endpoint is for staff. A visitor account cannot call it.",
                {"role": user["role"]},
            )
        return user

    return dependency


def assert_owns_visitor(user: dict[str, Any], visitor_id: str) -> None:
    """Stop a visitor account reaching another visitor's record.

    Staff are unaffected - a guard has to be able to look at whoever is at the
    gate. This only constrains role "visitor", which can see itself and nothing
    else. Without it, registering an account would be enough to read every
    visitor, every visit and every pass in the system.
    """
    if user.get("role") != "visitor":
        return
    if user.get("visitor_id") != visitor_id:
        raise NotPermitted(
            "A visitor account may only read its own record.",
            {"role": "visitor"},
        )
