from sqlalchemy import select

from realestate.db.engine import create_session_factory
from realestate.models import Base
from realestate.models.source import Source


async def test_source_roundtrip(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(Source(source_id="otodom", display_name="Otodom"))
        await session.commit()
    async with factory() as session:
        row = (await session.execute(select(Source))).scalar_one()
        assert row.source_id == "otodom"
        assert row.enabled is True
        assert row.config == {}
