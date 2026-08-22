"""Password hashing, tokens, and pass signatures.

The signing test is the one that matters most: that signature is the entire
basis on which the gate admits anyone, so a change that quietly stopped
detecting tampering would be invisible until somebody walked in on a forged QR.
"""

from datetime import timedelta

import pytest

from app.core import clock, security, signing
from app.core.errors import NotAuthenticated, NotPermitted


# --- passwords ---------------------------------------------------------------


def test_a_password_verifies_against_its_own_hash():
    salt, digest = security.hash_password("guard123")
    assert security.verify_password("guard123", salt, digest) is True


def test_a_wrong_password_does_not():
    salt, digest = security.hash_password("guard123")
    assert security.verify_password("guard124", salt, digest) is False


def test_the_hash_is_not_the_password():
    salt, digest = security.hash_password("guard123")
    assert "guard123" not in digest and "guard123" not in salt


def test_the_same_password_hashes_differently_for_two_users():
    """Fresh salt each time, so identical passwords do not produce identical
    hashes and a leaked store does not reveal who shares one."""
    salt_a, digest_a = security.hash_password("same")
    salt_b, digest_b = security.hash_password("same")
    assert salt_a != salt_b
    assert digest_a != digest_b


def test_a_hash_is_reproducible_when_the_salt_is_supplied():
    salt, digest = security.hash_password("same")
    assert security.hash_password("same", salt) == (salt, digest)


# --- tokens ------------------------------------------------------------------


def test_tokens_are_unique_and_not_guessable_in_length():
    tokens = {security.new_token() for _ in range(500)}
    assert len(tokens) == 500
    assert all(len(t) >= 32 for t in tokens)


def test_no_authorization_header_is_401():
    with pytest.raises(NotAuthenticated):
        security.resolve_token(None)


def test_a_header_without_bearer_is_401():
    with pytest.raises(NotAuthenticated):
        security.resolve_token("some-token-on-its-own")


def test_an_unknown_token_is_401(store):
    with pytest.raises(NotAuthenticated):
        security.resolve_token("Bearer never-issued")


def test_sessions_do_not_move_with_the_demo_clock(store):
    """/dev/advance-clock shifts campus time to demonstrate overstays. If
    sessions read that clock, jumping a day forward would log everybody out
    mid-demonstration for reasons unrelated to what was being shown."""
    before = security.session_now()
    clock.advance(60 * 24)
    try:
        assert security.session_now() - before < timedelta(minutes=1)
    finally:
        clock.reset_offset()


# --- role checks -------------------------------------------------------------


def test_admin_satisfies_a_role_it_is_not_named_in():
    admin = {"id": "u_admin", "name": "Admin", "role": "admin", "username": "admin"}
    assert _decide(admin, ("guard",)) is admin


def test_a_role_outside_the_set_is_403():
    guard = {"id": "u_guard", "name": "Guard", "role": "guard", "username": "guard"}
    with pytest.raises(NotPermitted):
        _decide(guard, ("faculty",))


def _decide(user: dict, roles: tuple):
    """The decision inside require_role, without FastAPI's dependency plumbing."""
    if user["role"] == "admin" or not roles or user["role"] in roles:
        return user
    raise NotPermitted("refused", {})


# --- pass signatures ---------------------------------------------------------


def test_a_signature_verifies_over_its_own_payload():
    payload, signature = signing.sign_pass("v_1", "abc123")
    assert signing.verify_pass(payload, signature) is True


def test_the_payload_carries_only_an_id_and_a_nonce():
    """The pointer-not-payload rule, checked at the one place it is created.
    Anything else in here would be invalidated when a host moved the meeting."""
    payload, _ = signing.sign_pass("v_1", "abc123")
    assert set(payload) == {"visit_id", "nonce"}


def test_a_tampered_payload_fails():
    """Changing the visit id is the attack this exists to stop - it would
    otherwise turn one visitor's pass into another's."""
    _, signature = signing.sign_pass("v_1", "abc123")
    assert signing.verify_pass({"visit_id": "v_2", "nonce": "abc123"}, signature) is False


def test_a_swapped_nonce_fails():
    """A stale nonce means an old QR for a reissued pass."""
    _, signature = signing.sign_pass("v_1", "abc123")
    assert signing.verify_pass({"visit_id": "v_1", "nonce": "def456"}, signature) is False


def test_a_tampered_signature_fails():
    payload, _ = signing.sign_pass("v_1", "abc123")
    assert signing.verify_pass(payload, "0" * 64) is False


def test_rubbish_input_is_refused_rather_than_raising():
    """A scanner sending nonsense must get a clean `false`, not a 500 - the
    scan path has to keep going far enough to write its audit record."""
    assert signing.verify_pass(None, "abc") is False
    assert signing.verify_pass({"visit_id": "v_1"}, None) is False


def test_key_order_does_not_change_the_signature():
    """The payload is canonicalised before signing, so a client that serialises
    its keys in a different order still verifies."""
    a = {"visit_id": "v_1", "nonce": "abc123"}
    b = {"nonce": "abc123", "visit_id": "v_1"}
    assert signing.sign_payload(a) == signing.sign_payload(b)


def test_nonces_are_unique():
    assert len({signing.new_nonce() for _ in range(500)}) == 500
