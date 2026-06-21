"""Conftest for enrichment tests.

Sets EMBEDDING_DIM=3 early enough (via pytest_configure, which fires before
test-module import) so that realestate.models.listing._EMBEDDING_DIM picks up
the value of 3 when the module is imported for the first time in this process.

If the model was already imported by a prior test session with dim=1536, we
additionally provide an autouse fixture that patches the in-memory column type
and clears any cached compiled SQL so the bind_processor uses dim=3.
"""

import os

import pytest


def pytest_configure(config):  # noqa: ARG001
    os.environ.setdefault("EMBEDDING_DIM", "3")


@pytest.fixture(autouse=True)
def _patch_embedding_dim():
    """Ensure Listing.embedding column type uses dim=3 for enrichment tests.

    When running the full test suite, other tests may import Listing with
    dim=1536 before this package is collected.  We patch the column type's dim
    attribute and clear SQLAlchemy's compiled-statement cache to avoid stale
    bind processors.
    """
    from realestate.models.listing import Listing

    col_type = Listing.__table__.c.embedding.type
    original_dim = col_type.dim
    col_type.dim = 3
    # Clear SQLAlchemy's compiled-statement LRU cache so a fresh bind_processor
    # is generated with the patched dim.
    try:
        from sqlalchemy.sql.compiler import SQLCompiler

        SQLCompiler._cache.clear()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    yield
    col_type.dim = original_dim
