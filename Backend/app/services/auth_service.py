"""Login, logout, and who-am-I.

The only place a password is ever checked. Routers call in here; nothing else
touches user_repo's session functions.
"""

import logging

from app.core import security
from app.core.errors import NotAuthenticated
from app.repositories import user_repo

log = logging.getLogger(__name__)


def login(username: str, password: str) -> dict:
    """Check the credentials and hand back a token.

    A wrong username and a wrong password give the SAME error, deliberately.
    Saying "no such user" tells an attacker which half to keep guessing, and
    costs a real user nothing - they know whether they have an account.
    """
    user = user_repo.find_by_username(username.strip().lower())

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
    }


def logout(authorization: str | None) -> dict:
    """Throw the token away. Idempotent - logging out twice is not an error,
    because the caller's intent is satisfied either way."""
    user = security.resolve_token(authorization)
    token = authorization.split(None, 1)[1].strip()
    user_repo.delete_session(token)
    log.info("logout: %s", user["username"])
    return {"logged_out": True, "username": user["username"]}
