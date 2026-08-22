"""Scan endpoints. SPEC sections 8 and 10.

EVERY ENDPOINT HERE RETURNS 200, including refusals. A bad signature, a revoked
pass, a wrong status, a lapsed window and an already-inside visitor all come
back as 200 with an explicit boolean and a result string - never as an error
status. SPEC section 8 is explicit about why: a scan that raised would tempt a
caller to abandon the request before the ScanEvent was written, and section 15
requires that event either way.

The one exception is a structurally unusable body - neither a payload nor a
code6 - which is InvalidRequest (400), because there is nothing to scan.
"""

from fastapi import APIRouter, Depends

from app.core.security import require_role
from app.schemas.scan import GateEntryRequest, GateEntryResponse
from app.services import scan_service

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("/gate/entry", response_model=GateEntryResponse)
async def gate_entry(body: GateEntryRequest, _user=Depends(require_role("guard"))):
    """The gate scan. SPEC section 10.

    Five checks in order - signature, not revoked, status issued, within
    window, not already inside - then admission. The response leads with every
    linked person so the guard can compare faces to the screen.

    A plate or headcount mismatch is flagged and recorded but NEVER blocks.
    """
    result = scan_service.gate_entry(
        payload=body.payload.model_dump() if body.payload else None,
        signature=body.signature,
        code6=body.code6,
        vehicle_plate=body.vehicle_plate,
        person_count_in=body.person_count_in,
        entered_offline=body.entered_offline,
        authorised_by=body.authorised_by,
    )
    return GateEntryResponse(**result)
