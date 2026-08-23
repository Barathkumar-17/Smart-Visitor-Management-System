"""Login, logout, and who-am-I.

The only place a password is ever checked. Routers call in here; nothing else
touches user_repo's session functions.
"""

import logging
import re

from app.core import security
from app.core.errors import InvalidRequest, NotAuthenticated
from app.repositories import user_repo
from app.store import ids
from app.store.entities import User

log = logging.getLogger(__name__)


def normalise_phone(phone: str) -> str:
    """The last ten digits, so one phone is always one account.

    A visitor logs in with the phone they registered with, and nobody retypes a
    number the same way twice. +91-98111-22233, 09811122233 and 9811122233 are
    one phone to a human, but three different strings - digits alone is not
    enough, because the country code and a trunk zero survive it.

    Ten digits is the Indian mobile length, which is what this system is built
    around: TN plates, DigiLocker, +91 throughout the seed. A deployment
    elsewhere would need real phone parsing rather than this rule.

    Shorter values are returned as-is so a malformed number still produces a
    stable key rather than an empty one.
    """
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) > 10 else digits


def login(username: str, password: str) -> dict:
    """Check the credentials and hand back a token.

    A wrong username and a wrong password give the SAME error, deliberately.
    Saying "no such user" tells an attacker which half to keep guessing, and
    costs a real user nothing - they know whether they have an account.
    """
    supplied = username.strip().lower()
    user = user_repo.find_by_username(supplied)

    # A visitor's username is their phone in digits-only form, so the same
    # number typed with or without punctuation resolves to one account.
    if user is None:
        digits = normalise_phone(username)
        if digits:
            user = user_repo.find_by_username(digits)

    if user is None or not security.verify_password(password, user.salt, user.password_hash):
        log.warning("failed login for username %r", username)
        raise NotAuthenticated("Username or password is wrong.", {"username": username})

    token = security.new_token()
    expires_at = security.session_now() + security.TOKEN_LIFETIME
    user_repo.save_session(token, user.id, expires_at)

    log.info("login: %s as %s", user.username, user.role)
    return {
        "token": token,
        "role": user.role,
        "name": user.name,
        "username": user.username,
        "expires_at": expires_at,
        "visitor_id": user.visitor_id,
    }


def logout(authorization: str | None) -> dict:
    """Throw the token away. Idempotent - logging out twice is not an error,
    because the caller's intent is satisfied either way."""
    user = security.resolve_token(authorization)
    token = authorization.split(None, 1)[1].strip()
    user_repo.delete_session(token)
    log.info("logout: %s", user["username"])
    return {"logged_out": True, "username": user["username"]}


def register_visitor(
    *,
    name: str,
    phone: str,
    password: str,
    email: str | None = None,
    address: str | None = None,
    photo_b64: str | None = None,
) -> dict:
    """Public sign-up: create the Visitor record AND an account that owns it.

    This is the only way into the system without already being in it. It exists
    because a member of the public has no credentials and nobody to ask for
    any - every other endpoint assumes the caller was handed a login.

    The Visitor is created first. If the photograph is oversized or malformed
    that raises before any account exists, so a rejected sign-up leaves nothing
    behind - the same guarantee visitor_service.register already made.
    """
    from app.services import visitor_service

    username = normalise_phone(phone)
    if not username:
        raise InvalidRequest(
            "A phone number is needed - it doubles as the username.",
            {"phone": phone},
        )

    if user_repo.find_by_username(username) is not None:
        raise InvalidRequest(
            "An account already exists for that phone number. Log in instead.",
            {"phone": phone},
        )

    visitor = visitor_service.register(
        name=name, phone=phone, address=address, email=email, photo_b64=photo_b64
    )

    salt, password_hash = security.hash_password(password)
    user = user_repo.save(
        User(
            id=ids.next_id("user"),
            username=username,
            role="visitor",
            name=name,
            salt=salt,
            password_hash=password_hash,
            visitor_id=visitor.id,
        )
    )

    token = security.new_token()
    expires_at = security.session_now() + security.TOKEN_LIFETIME
    user_repo.save_session(token, user.id, expires_at)

    log.info("visitor sign-up: %s -> %s", user.username, visitor.id)
    return {
        "token": token,
        "role": user.role,
        "name": user.name,
        "username": user.username,
        "expires_at": expires_at,
        "visitor_id": visitor.id,
    }
