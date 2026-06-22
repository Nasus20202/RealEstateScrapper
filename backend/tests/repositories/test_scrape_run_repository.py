from datetime import UTC, datetime, timedelta

from realestate.db.engine import create_session_factory
from realestate.models import Base
from realestate.models.enums import ScrapeRunStatus
from realestate.models.scrape_run import ScrapeRun
from realestate.repositories.scrape_runs import ScrapeRunRepository


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return create_session_factory(engine)


def _run(source_id="otodom", started_at=None, **kw):
    if started_at is None:
        started_at = datetime.now(UTC)
    base = dict(
        source_id=source_id,
        started_at=started_at,
        status=ScrapeRunStatus.SUCCESS,
    )
    base.update(kw)
    return ScrapeRun(**base)


async def test_add_and_latest_for_source(engine):
    factory = await _setup(engine)
    now = datetime.now(UTC)
    older = now - timedelta(hours=1)

    async with factory() as s:
        repo = ScrapeRunRepository(s)
        await repo.add(_run(source_id="otodom", started_at=older))
        await repo.add(_run(source_id="otodom", started_at=now))
        await s.commit()

    async with factory() as s:
        repo = ScrapeRunRepository(s)
        latest = await repo.latest_for_source("otodom")
        assert latest is not None
        assert latest.started_at == now


async def test_latest_for_source_returns_none_when_empty(engine):
    factory = await _setup(engine)

    async with factory() as s:
        repo = ScrapeRunRepository(s)
        result = await repo.latest_for_source("otodom")
        assert result is None


async def test_latest_for_source_ignores_other_sources(engine):
    factory = await _setup(engine)
    now = datetime.now(UTC)

    async with factory() as s:
        repo = ScrapeRunRepository(s)
        await repo.add(_run(source_id="other", started_at=now))
        await s.commit()

    async with factory() as s:
        repo = ScrapeRunRepository(s)
        result = await repo.latest_for_source("otodom")
        assert result is None


async def test_add_returns_run_with_id(engine):
    factory = await _setup(engine)

    async with factory() as s:
        repo = ScrapeRunRepository(s)
        run = await repo.add(_run())
        assert run.id is not None
        await s.commit()
