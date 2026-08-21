"""Registration and verification rules. SPEC section 7.

Phase 1 adds only the read. Registration, OTP, DigiLocker and the vouch rules
arrive at Phase 3.
"""

from app.repositories import visitor_repo
from app.store.entities import Visitor


def get_visitor(visitor_id: str) -> Visitor:
    """One visitor, or NotFound (404).

    Thin today, but it is the seam Phase 3 fills - and it keeps the router free
    of any knowledge of where visitors are kept, per SPEC section 5.
    """
    return visitor_repo.get_or_404(visitor_id)
