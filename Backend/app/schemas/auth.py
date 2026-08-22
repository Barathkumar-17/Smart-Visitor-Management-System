"""Login request and response models."""

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, description="guard, faculty, security or admin")
    password: str = Field(min_length=1)


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


class WhoAmI(BaseModel):
    id: str
    username: str
    name: str
    role: str
