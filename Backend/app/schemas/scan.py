"""Scan request/response models.

The read model arrives at Phase 4 so GET /visits/{id}/scans has a shape; the
request bodies for the three scan endpoints arrive at Phase 6.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScanEventOut(BaseModel):
    """One entry in the audit trail. SPEC section 6.

    `result` says whether the SCAN succeeded. The mismatch flags sit ALONGSIDE
    it, never inside it: a gate entry whose plate differs is still result `ok`
    with plate_mismatch true, because SPEC section 10 forbids ever blocking on
    a mismatch and collapsing the two would hide that distinction.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    visit_id: str
    kind: str
    result: str
    zone_id: str | None = None
    plate_mismatch: bool
    count_mismatch: bool
    person_count_recorded: int | None = None
    created_at: datetime
