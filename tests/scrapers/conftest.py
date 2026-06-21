import pytest

import realestate.scrapers.base as base


@pytest.fixture(autouse=True)
def _isolate_registry():
    saved = dict(base._REGISTRY)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)
