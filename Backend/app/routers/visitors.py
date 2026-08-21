"""Visitor endpoints. SPEC section 10.

ROUTE ORDER MATTERS HERE. When GET /visitors/lookup arrives at Phase 3 it MUST
be declared ABOVE GET /visitors/{id}, or FastAPI matches the literal string
"lookup" as an id and the endpoint becomes permanently unreachable. There is a
marker below at the exact spot it belongs.
"""

from fastapi import APIRouter

from app.schemas.visitor import VisitorOut
from app.services import visitor_service

router = APIRouter(prefix="/visitors", tags=["visitors"])


# --- Phase 3 declares GET /visitors/lookup HERE, above the {id} route --------


@router.get("/{visitor_id}", response_model=VisitorOut)
async def get_visitor(visitor_id: str):
    """One visitor. NEVER returns id_hash - see VisitorOut. SPEC section 15."""
    return visitor_service.get_visitor(visitor_id)
