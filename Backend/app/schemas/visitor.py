"""Visitor request and response models.

Read model at Phase 1; registration and verification bodies arrive at Phase 3.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VisitorOut(BaseModel):
    """A visitor as returned by the API.

    id_hash IS DELIBERATELY ABSENT and must never be added. SPEC section 15
    forbids any endpoint returning it; id_last4 is the field that may be shown.
    Listing fields explicitly rather than dumping the dataclass is what keeps
    that true - a future field on the entity cannot leak through by accident.

    `tier` is a derived property on the entity, recomputed on every read, so a
    lapsed vouch shows as `temporary` here without anything having written to
    the record. SPEC section 6.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    phone: str
    address: str | None = None
    email: str | None = None
    photo_ref: str | None = None
    phone_verified: bool
    tier: str
    verified_by: str | None = None
    id_last4: str | None = None
    vouched_by_host_id: str | None = None
    verified_until: datetime | None = None
    is_permanent: bool
    created_at: datetime
