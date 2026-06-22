from datetime import UTC, datetime, timedelta
from decimal import Decimal

from realestate.db.engine import create_session_factory
from realestate.models import Base
from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing
from realestate.repositories.listings import ListingRepository


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return create_session_factory(engine)


def _listing(external_id="a", **kw):
    now = datetime.now(UTC)
    base = dict(
        source_id="otodom",
        external_id=external_id,
        url="https://x",
        title="t",
        price=Decimal("500000"),
        raw_hash="h",
        status=ListingStatus.ACTIVE,
        images=[],
        first_seen=now,
        last_seen=now,
    )
    base.update(kw)
    return Listing(**base)


async def test_add_and_get_by_external(engine):
    factory = await _setup(engine)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(_listing(external_id="x1"))
        await s.commit()
    async with factory() as s:
        repo = ListingRepository(s)
        found = await repo.get_by_external("otodom", "x1")
        assert found is not None and found.external_id == "x1"
        missing = await repo.get_by_external("otodom", "nope")
        assert missing is None


async def test_list_active_and_count(engine):
    factory = await _setup(engine)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(_listing(external_id="a1"))
        await repo.add(_listing(external_id="a2"))
        await repo.add(_listing(external_id="g1", status=ListingStatus.GONE))
        await s.commit()
    async with factory() as s:
        repo = ListingRepository(s)
        assert await repo.count_active() == 2
        rows = await repo.list_active()
        assert {r.external_id for r in rows} == {"a1", "a2"}


async def test_list_active_ordering(engine):
    factory = await _setup(engine)
    now = datetime.now(UTC)
    two_hours_ago = now - timedelta(hours=2)
    one_hour_ago = now - timedelta(hours=1)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(
            _listing(
                external_id="oldest",
                first_seen=two_hours_ago,
                last_seen=two_hours_ago,
            )
        )
        await repo.add(
            _listing(
                external_id="newest",
                first_seen=now,
                last_seen=now,
            )
        )
        await repo.add(
            _listing(
                external_id="middle",
                first_seen=one_hour_ago,
                last_seen=one_hour_ago,
            )
        )
        await s.commit()
    async with factory() as s:
        repo = ListingRepository(s)
        rows = await repo.list_active()
        assert [r.external_id for r in rows] == ["newest", "middle", "oldest"]
