from datetime import UTC, datetime

from sqlalchemy import select

from realestate.db.engine import create_session_factory
from realestate.models import Base, ScrapeRun, ScrapeRunStatus


async def test_scrape_run_roundtrip(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as s:
        s.add(ScrapeRun(source_id="otodom", started_at=datetime.now(UTC),
                        status=ScrapeRunStatus.SUCCESS))
        await s.commit()
    async with factory() as s:
        row = (await s.execute(select(ScrapeRun))).scalar_one()
        assert row.source_id == "otodom"
        assert row.status == ScrapeRunStatus.SUCCESS
        assert row.new_count == 0 and row.gone_count == 0
        assert row.finished_at is None
