from datetime import UTC, datetime
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


def _listing(external_id="a", source_id="otodom", status=ListingStatus.ACTIVE, **kw):
    now = datetime.now(UTC)
    base = dict(
        source_id=source_id,
        external_id=external_id,
        url="https://x",
        title="t",
        price=Decimal("500000"),
        raw_hash="h",
        status=status,
        images=[],
        first_seen=now,
        last_seen=now,
    )
    base.update(kw)
    return Listing(**base)


async def test_active_external_ids_returns_only_active(engine):
    factory = await _setup(engine)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(_listing(external_id="a", status=ListingStatus.ACTIVE))
        await repo.add(_listing(external_id="b", status=ListingStatus.ACTIVE))
        await repo.add(_listing(external_id="c", status=ListingStatus.ACTIVE))
        await repo.add(_listing(external_id="d", status=ListingStatus.GONE))
        await s.commit()

    async with factory() as s:
        repo = ListingRepository(s)
        result = await repo.active_external_ids("otodom")
        assert result == {"a", "b", "c"}


async def test_active_external_ids_excludes_other_sources(engine):
    factory = await _setup(engine)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(_listing(external_id="a", source_id="otodom"))
        await repo.add(_listing(external_id="a", source_id="other"))
        await s.commit()

    async with factory() as s:
        repo = ListingRepository(s)
        result = await repo.active_external_ids("otodom")
        assert result == {"a"}


async def test_mark_gone_returns_count_and_updates_status(engine):
    now = datetime.now(UTC)
    factory = await _setup(engine)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(_listing(external_id="a", status=ListingStatus.ACTIVE))
        await repo.add(_listing(external_id="b", status=ListingStatus.ACTIVE))
        await repo.add(_listing(external_id="c", status=ListingStatus.ACTIVE))
        await repo.add(_listing(external_id="d", status=ListingStatus.GONE))
        await s.commit()

    async with factory() as s:
        repo = ListingRepository(s)
        count = await repo.mark_gone("otodom", {"a"}, now=now)
        await s.commit()

    assert count == 2

    async with factory() as s:
        repo = ListingRepository(s)
        active = await repo.active_external_ids("otodom")
        assert active == {"a"}


async def test_mark_gone_empty_keep_ids_marks_all_active(engine):
    """Critical edge case: empty keep_ids must mark ALL active listings as gone."""
    now = datetime.now(UTC)
    factory = await _setup(engine)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(_listing(external_id="a", status=ListingStatus.ACTIVE))
        await repo.add(_listing(external_id="b", status=ListingStatus.ACTIVE))
        await repo.add(_listing(external_id="c", status=ListingStatus.ACTIVE))
        await s.commit()

    async with factory() as s:
        repo = ListingRepository(s)
        count = await repo.mark_gone("otodom", set(), now=now)
        await s.commit()

    assert count == 3

    async with factory() as s:
        repo = ListingRepository(s)
        active = await repo.active_external_ids("otodom")
        assert active == set()


async def test_mark_gone_does_not_affect_other_sources(engine):
    now = datetime.now(UTC)
    factory = await _setup(engine)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(_listing(external_id="a", source_id="otodom", status=ListingStatus.ACTIVE))
        await repo.add(_listing(external_id="a", source_id="other", status=ListingStatus.ACTIVE))
        await s.commit()

    async with factory() as s:
        repo = ListingRepository(s)
        count = await repo.mark_gone("otodom", set(), now=now)
        await s.commit()

    assert count == 1

    async with factory() as s:
        repo = ListingRepository(s)
        other_active = await repo.active_external_ids("other")
        assert other_active == {"a"}
