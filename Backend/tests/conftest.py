"""Shared fixtures.

The store is a module-level dict, so tests share it unless they reset. Every
test that touches it takes the `store` fixture, which reseeds before the test
and again afterwards, leaving the next one a clean campus.
"""

import pytest

from app.store import seed


@pytest.fixture
def store():
    """A freshly seeded store, restored again on the way out."""
    seed.reset()
    yield
    seed.reset()
