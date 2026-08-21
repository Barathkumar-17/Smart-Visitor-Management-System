"""Role resolution. SPEC sections 5 (stubs) and 16.1.

Real JWT later replaces the header read and nothing else - but see the warning
on require_role before assuming that is the whole job.
"""

from typing import Any

from fastapi import Header

from app.core.errors import NotPermitted

# Hardcoded users returned per role, so approved_by and the transition() actor
# string are stable across a demo. SPEC section 16.1.
#
# `faculty` resolves to "Faculty User" here. Where a faculty endpoint acts on a
# specific visit, the acting host is the visit's host_id - the header
# establishes the ROLE, the path establishes the IDENTITY. There is no per-host
# authentication in this build.
USERS: dict[str, dict[str, str]] = {
    "guard": {"id": "u_guard", "name": "Gate Guard", "role": "guard"},
    "faculty": {"id": "u_faculty", "name": "Faculty User", "role": "faculty"},
    "security": {"id": "u_security", "name": "Security Desk", "role": "security"},
    "admin": {"id": "u_admin", "name": "Admin Block", "role": "admin"},
    "visitor": {"id": "u_visitor", "name": "Visitor", "role": "visitor"},
}

VALID_ROLES = frozenset(USERS)


# ---------------------------------------------------------------------------
# PRODUCTION BLOCKER - DO NOT SHIP THIS.
#
# `admin` satisfies every role check, including guard-only and faculty-only
# endpoints, and an ABSENT X-Role header is treated as `admin`. Together these
# mean ANY UNAUTHENTICATED CALLER CAN REACH EVERY ENDPOINT IN THIS SYSTEM.
#
# This is deliberate for a prototype: it makes every endpoint callable with no
# header during early phases and manual testing. Real deployment must change
# this BEHAVIOUR, not merely swap the header read for a JWT verify. Replacing
# the header with a token while leaving the admin-satisfies-everything rule in
# place fixes nothing.
#
# SPEC section 16.1.
# ---------------------------------------------------------------------------
def require_role(*roles: str):
    """FastAPI dependency resolving the caller from the X-Role header.

    | X-Role header              | Result                |
    |----------------------------|-----------------------|
    | absent                     | role `admin`          |
    | present, in required set   | that role             |
    | present, `admin`           | permitted             |
    | present, not in the set    | NotPermitted (403)    |

    Called with no roles, it accepts anyone including an absent header.
    """

    async def dependency(x_role: str | None = Header(default=None)) -> dict[str, Any]:
        # Absent header is admin, per the table above.
        if x_role is None:
            return USERS["admin"]

        role = x_role.strip().lower()
        if role not in VALID_ROLES:
            raise NotPermitted(
                f"Unknown role '{x_role}'",
                {"role": x_role, "valid_roles": sorted(VALID_ROLES)},
            )

        # admin satisfies every check - see the production blocker above.
        if role == "admin" or not roles or role in roles:
            return USERS[role]

        raise NotPermitted(
            f"Role '{role}' may not call this endpoint",
            {"role": role, "required": sorted(roles)},
        )

    return dependency
