from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from realestate.db.engine import create_session_factory
from realestate.models import Base
from realestate.models.enums import ListingStatus, MarketType
from realestate.models.listing import Listing


async def _create_all(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _listing(**kw):
    now = datetime.now(UTC)
    base = dict(
        source_id="otodom", external_id="abc", url="https://x/abc", title="Mieszkanie",
        price=Decimal("750000"), area_m2=52.0, rooms=3, market=MarketType.SECONDARY,
        images=["https://img/1.jpg"], raw_hash="h1", status=ListingStatus.ACTIVE,
        first_seen=now, last_seen=now,
    )
    base.update(kw)
    return Listing(**base)


async def test_listing_roundtrip(engine):
    await _create_all(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(_listing())
        await session.commit()
    async with factory() as session:
        row = (await session.execute(select(Listing))).scalar_one()
        assert row.external_id == "abc"
        assert row.market == MarketType.SECONDARY
        assert row.images == ["https://img/1.jpg"]


async def test_listing_unique_source_external(engine):
    await _create_all(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(_listing())
        session.add(_listing())  # ten sam (source_id, external_id)
        with pytest.raises(IntegrityError):
            await session.commit()
