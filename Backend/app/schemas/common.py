"""Shared response models. SPEC section 5 keeps schemas separate from entities.

Zone and Host have no dedicated schema module in the SPEC section 16.8 tree, so
their read models live here alongside anything else shared.
"""

from pydantic import BaseModel, ConfigDict


class ZoneOut(BaseModel):
    """A checkpoint. Backs GET /zones."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str


class HostOut(BaseModel):
    """A member of staff. Backs GET /hosts.

    `phone` is included deliberately, per SPEC section 10 - it lets the guard
    call the host directly instead of waiting on escalation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    department: str
    email: str | None = None
    phone: str | None = None
