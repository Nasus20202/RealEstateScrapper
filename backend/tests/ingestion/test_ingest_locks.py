"""Per-source ingestion locks: same source serializes, different sources stay parallel.

Guards against PostgreSQL DeadlockDetectedError when overlapping scrapes
(scheduler + manual triggers, or several city scrapes) ingest the same source
concurrently. DB-free: exercises _run_source_locked with a fake _ingest_source.
"""

import asyncio
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import async_sessionmaker

from realestate.ingestion.service import IngestionService, _get_source_lock
from realestate.scrapers.base import SearchCriteria


def _svc_with_tracker(state: dict) -> IngestionService:
    svc = IngestionService(cast(async_sessionmaker, None), None)

    async def fake_ingest(source_id, scraper, criteria, now, **kwargs):
        state["in_flight"] += 1
        state["max"] = max(state["max"], state["in_flight"])
        await asyncio.sleep(0.02)
        state["in_flight"] -= 1
        return [source_id]

    svc._ingest_source = fake_ingest  # type: ignore[method-assign]
    return svc


async def test_same_source_is_serialized():
    state = {"in_flight": 0, "max": 0}
    svc = _svc_with_tracker(state)
    criteria = SearchCriteria(city="Gdańsk")
    now = datetime.now(UTC)
    results = await asyncio.gather(
        *[
            svc._run_source_locked(
                "otodom",
                None,
                criteria,
                now,
                max_pages=1,
                source_max_pages=None,
                mark_missing_gone=False,
                on_run=None,
                on_log=None,
            )
            for _ in range(4)
        ]
    )
    assert state["max"] == 1
    assert all(r == ["otodom"] for r in results)


async def test_different_sources_stay_parallel():
    state = {"in_flight": 0, "max": 0}
    svc = _svc_with_tracker(state)
    criteria = SearchCriteria(city="Gdańsk")
    now = datetime.now(UTC)
    results = await asyncio.gather(
        *[
            svc._run_source_locked(
                sid,
                None,
                criteria,
                now,
                max_pages=1,
                source_max_pages=None,
                mark_missing_gone=False,
                on_run=None,
                on_log=None,
            )
            for sid in ["otodom", "morizon", "adresowo", "domesta"]
        ]
    )
    assert state["max"] == 4
    assert sorted(r[0] for r in results) == ["adresowo", "domesta", "morizon", "otodom"]


async def test_lock_identity_is_stable_per_source():
    l1, l2 = await asyncio.gather(_get_source_lock("otodom"), _get_source_lock("otodom"))
    l3 = await _get_source_lock("hossa")
    assert l1 is l2
    assert l1 is not l3
