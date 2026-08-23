"""Login request and response models."""

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(
        min_length=1,
        description="guard, faculty, security, admin - or a visitor's phone number",
    )
    password: str = Field(min_length=1)


class VisitorRegisterRequest(BaseModel):
    """Public sign-up. The ONLY body that reaches the system without a token.

    The phone doubles as the username, so it must be unique. A password is
    required because unlike the four seeded accounts there is nobody to hand
    out credentials - the visitor chooses their own and logs back in with them.
    """

    name: str = Field(min_length=1)
    phone: str = Field(min_length=4)
    password: str = Field(min_length=6, description="At least six characters.")
    email: str | None = None
    address: str | None = None
    photo_b64: str | None = None


class LoginResponse(BaseModel):
    """What a successful login returns.

    The token is opaque - it carries no information and cannot be decoded. The
    role is returned alongside it purely so a caller knows what it may do
    without having to try an endpoint and read the 403.
    """

    token: str = Field(description="Send as: Authorization: Bearer <token>")
    role: str
    name: str
    username: str
    expires_at: datetime

    # Only set for role "visitor" - the Visitor record this account speaks for,
    # so the client knows which id to use without a second lookup.
    visitor_id: str | None = None


class WhoAmI(BaseModel):
    id: str
    username: str
    name: str
    role: str
    visitor_id: str | None = None
