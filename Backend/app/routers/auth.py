"""Login, sign-up and logout.

THREE endpoints are reachable without a token: POST /auth/login,
POST /auth/visitor/register, and GET /health. Everything else needs one.

Staff never sign up. The four accounts are seeded fixtures and there is no
endpoint that creates a fifth. Visitors are the opposite case - a member of the
public arrives with no credentials and nobody to ask for any, so they create
their own account and it owns exactly one Visitor record.
"""

from fastapi import APIRouter, Depends, Header

from app.core.security import require_user
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    VisitorRegisterRequest,
    WhoAmI,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Exchange a username and password for a token.

    Returns 401 for a wrong username OR a wrong password - the same message for
    both, so the response never reveals which accounts exist.
    """
    return auth_service.login(body.username, body.password)


@router.post("/visitor/register", response_model=LoginResponse, status_code=201)
async def register_visitor_account(body: VisitorRegisterRequest):
    """Public sign-up for a visitor. No token required - this is the way in.

    Creates the Visitor record and an account that owns it, then logs that
    account straight in, so the caller never has to follow this with a login.

    Returns 400 when the phone already has an account, or when the photograph
    is over the 2 MB limit - and in the second case no account is created.
    """
    return auth_service.register_visitor(
        name=body.name,
        phone=body.phone,
        password=body.password,
        email=body.email,
        address=body.address,
        photo_b64=body.photo_b64,
    )


@router.post("/logout")
async def logout(authorization: str | None = Header(default=None)):
    """Invalidate the token you are calling with."""
    return auth_service.logout(authorization)


@router.get("/me", response_model=WhoAmI)
async def me(user=Depends(require_user())):
    """Who the token says you are. Useful when a 403 is unexpected."""
    return user
