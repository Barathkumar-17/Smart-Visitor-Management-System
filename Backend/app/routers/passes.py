"""Pass endpoints."""

from fastapi import APIRouter, Depends

from app.core.security import require_role, require_user
from app.schemas.pass_ import PassOut
from app.services import pass_service

router = APIRouter(prefix="/passes", tags=["passes"])


def _to_out(issued) -> PassOut:
    """Build the response explicitly rather than validating the entity and
    patching afterwards - `qr` is derived, not stored, so it has to be supplied
    at construction or validation fails on a missing required field."""
    return PassOut(
        id=issued.id,
        visit_id=issued.visit_id,
        code6=issued.code6,
        issued_at=issued.issued_at,
        revoked_at=issued.revoked_at,
        is_revoked=issued.is_revoked,
        qr=pass_service.build_qr_payload(issued),
    )


@router.get("/{visit_id}", response_model=PassOut)
async def get_pass(visit_id: str, _user=Depends(require_user())):
    """The signed payload ready for QR encoding, plus code6.

    The same visit returns a BYTE-IDENTICAL qr object every time, including
    after a meeting-point change or a window extension - neither is in the
    payload. PATCH /visits/{id}/meeting-point demonstrates exactly that.
    """
    return _to_out(pass_service.get_pass_for_visit(visit_id))


@router.post("/{visit_id}/revoke", response_model=PassOut)
async def revoke_pass(visit_id: str, user=Depends(require_role("security"))):
    """Revoke a pass. Every scan checks revoked_at.

    Sets revoked_at only. The visit's status is untouched, and someone already
    inside is neither ejected nor prevented from leaving - the design.
    """
    return _to_out(
        pass_service.revoke_pass(visit_id, actor=f"{user['role']}:{user['id']}")
    )
