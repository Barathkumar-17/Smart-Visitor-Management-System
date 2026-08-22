"""Login and logout.

POST /auth/login is the ONLY endpoint reachable without a token, along with
GET /health. Everything else in the system needs one.
"""

from fastapi import APIRouter, Depends, Header

from app.core.security import require_user
from app.schemas.auth import LoginRequest, LoginResponse, WhoAmI
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Exchange a username and password for a token.

    Returns 401 for a wrong username OR a wrong password - the same message for
    both, so the response never reveals which accounts exist.
    """
    return auth_service.login(body.username, body.password)


@router.post("/logout")
async def logout(authorization: str | None = Header(default=None)):
    """Invalidate the token you are calling with."""
    return auth_service.logout(authorization)


@router.get("/me", response_model=WhoAmI)
async def me(user=Depends(require_user())):
    """Who the token says you are. Useful when a 403 is unexpected."""
    return user
