"""Tests for IncrementalEngine.sync_source — TDD, real PostgreSQL via testcontainers."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from realestate.db.engine import create_session_factory
from realestate.ingestion.incremental import IncrementalEngine, SyncStats
from realestate.ingestion.normalize import to_listing
from realestate.models import Base
from realestate.models.enums import ListingStatus
from realestate.models.listing import PriceHistory
from realestate.repositories.listings import ListingRepository
from realestate.scrapers.base import RawListing

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return create_session_factory(engine)


def _raw(external_id="ext-1", price=Decimal("500000"), **kw):
    base = dict(
        source_id="otodom",
        external_id=external_id,
        url="https://example.com/1",
        title="Test Listing",
        price=price,
        area_m2=50.0,
        rooms=3,
        images=[],
    )
    base.update(kw)
    return RawListing(**base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_new_listing_inserted_with_price_history(engine):
    """Insert a new listing: new==1, row exists in DB, price_history has one entry."""
    factory = await _setup(engine)
    now = datetime.now(UTC)
    raw = _raw()

    async with factory() as session:
        eng = IncrementalEngine(session)
        stats = await eng.sync_source("otodom", [to_listing(raw, now=now)], now=now)
        await session.commit()

    assert stats == SyncStats(new=1, updated=0, unchanged=0, gone=0)

    async with factory() as session:
        repo = ListingRepository(session)
        listing = await repo.get_by_external("otodom", "ext-1")
        assert listing is not None
        assert listing.status == ListingStatus.ACTIVE
        assert listing.price == Decimal("500000")

        ph_result = await session.execute(
            select(PriceHistory).where(PriceHistory.listing_id == listing.id)
        )
        history = ph_result.scalars().all()
        assert len(history) == 1
        assert history[0].price == Decimal("500000")
        assert history[0].observed_at == now


async def test_unchanged_listing_updates_last_seen_no_new_history(engine):
    """Re-sync same listing (same hash): unchanged==1, last_seen updated, no new price_history."""
    factory = await _setup(engine)
    t1 = datetime.now(UTC)
    t2 = t1 + timedelta(hours=1)
    raw = _raw()

    async with factory() as session:
        eng = IncrementalEngine(session)
        await eng.sync_source("otodom", [to_listing(raw, now=t1)], now=t1)
        await session.commit()

    async with factory() as session:
        eng = IncrementalEngine(session)
        stats = await eng.sync_source("otodom", [to_listing(raw, now=t2)], now=t2)
        await session.commit()

    assert stats == SyncStats(new=0, updated=0, unchanged=1, gone=0)

    async with factory() as session:
        repo = ListingRepository(session)
        listing = await repo.get_by_external("otodom", "ext-1")
        assert listing is not None
        assert listing.last_seen == t2

        ph_result = await session.execute(
            select(PriceHistory).where(PriceHistory.listing_id == listing.id)
        )
        history = ph_result.scalars().all()
        # Only the original PriceHistory from first insert
        assert len(history) == 1


async def test_updated_listing_adds_price_history_and_clears_embedding(engine):
    """Sync with changed price: updated==1, new PriceHistory added, embedding=None."""
    factory = await _setup(engine)
    t1 = datetime.now(UTC)
    t2 = t1 + timedelta(hours=1)
    raw1 = _raw(price=Decimal("500000"))
    raw2 = _raw(price=Decimal("450000"))

    async with factory() as session:
        eng = IncrementalEngine(session)
        await eng.sync_source("otodom", [to_listing(raw1, now=t1)], now=t1)
        await session.commit()

    # Manually set embedding to non-None to verify it gets cleared
    async with factory() as session:
        repo = ListingRepository(session)
        listing = await repo.get_by_external("otodom", "ext-1")
        listing.embedding = [0.1] * 1536
        await session.commit()

    async with factory() as session:
        eng = IncrementalEngine(session)
        stats = await eng.sync_source("otodom", [to_listing(raw2, now=t2)], now=t2)
        await session.commit()

    assert stats == SyncStats(new=0, updated=1, unchanged=0, gone=0)

    async with factory() as session:
        repo = ListingRepository(session)
        listing = await repo.get_by_external("otodom", "ext-1")
        assert listing is not None
        assert listing.price == Decimal("450000")
        assert listing.last_seen == t2
        assert listing.embedding is None

        ph_result = await session.execute(
            select(PriceHistory)
            .where(PriceHistory.listing_id == listing.id)
            .order_by(PriceHistory.observed_at)
        )
        history = ph_result.scalars().all()
        assert len(history) == 2
        assert history[0].price == Decimal("500000")
        assert history[1].price == Decimal("450000")
        assert history[1].observed_at == t2


async def test_vanished_listing_marked_gone(engine):
    """Listing absent from next sync with mark_missing_gone=True gets status==GONE."""
    factory = await _setup(engine)
    t1 = datetime.now(UTC)
    t2 = t1 + timedelta(hours=1)
    raw_a = _raw(external_id="ext-a")
    raw_b = _raw(external_id="ext-b")

    # Insert both listings
    async with factory() as session:
        eng = IncrementalEngine(session)
        listings = [to_listing(raw_a, now=t1), to_listing(raw_b, now=t1)]
        await eng.sync_source("otodom", listings, now=t1)
        await session.commit()

    # Sync only ext-a, ext-b should become GONE
    async with factory() as session:
        eng = IncrementalEngine(session)
        stats = await eng.sync_source(
            "otodom", [to_listing(raw_a, now=t2)], now=t2, mark_missing_gone=True
        )
        await session.commit()

    assert stats.gone >= 1

    async with factory() as session:
        repo = ListingRepository(session)
        listing_b = await repo.get_by_external("otodom", "ext-b")
        assert listing_b is not None
        assert listing_b.status == ListingStatus.GONE


async def test_mark_missing_gone_false_does_not_mark_gone(engine):
    """mark_missing_gone=False leaves absent listings as ACTIVE."""
    factory = await _setup(engine)
    t1 = datetime.now(UTC)
    t2 = t1 + timedelta(hours=1)
    raw_a = _raw(external_id="ext-a")
    raw_b = _raw(external_id="ext-b")

    async with factory() as session:
        eng = IncrementalEngine(session)
        listings = [to_listing(raw_a, now=t1), to_listing(raw_b, now=t1)]
        await eng.sync_source("otodom", listings, now=t1)
        await session.commit()

    # Sync only ext-a, but don't mark missing as gone
    async with factory() as session:
        eng = IncrementalEngine(session)
        stats = await eng.sync_source(
            "otodom", [to_listing(raw_a, now=t2)], now=t2, mark_missing_gone=False
        )
        await session.commit()

    assert stats.gone == 0

    async with factory() as session:
        repo = ListingRepository(session)
        listing_b = await repo.get_by_external("otodom", "ext-b")
        assert listing_b is not None
        assert listing_b.status == ListingStatus.ACTIVE


async def test_gone_listing_reactivated_on_unchanged_hash_resync(engine):
    """GONE listing that reappears byte-identical must be reactivated (status=ACTIVE).

    Regression guard: the unchanged-hash branch must reactivate, not only the
    changed-hash branch.  No new PriceHistory row should be added (price unchanged).
    Counter must report unchanged==1 (content did not change).
    """
    factory = await _setup(engine)
    t1 = datetime.now(UTC)
    t2 = t1 + timedelta(hours=1)
    t3 = t2 + timedelta(hours=1)
    raw = _raw()

    # Step 1: insert listing
    async with factory() as session:
        eng = IncrementalEngine(session)
        await eng.sync_source("otodom", [to_listing(raw, now=t1)], now=t1)
        await session.commit()

    # Step 2: mark it GONE (sync with empty list, mark_missing_gone=True)
    async with factory() as session:
        eng = IncrementalEngine(session)
        stats = await eng.sync_source("otodom", [], now=t2, mark_missing_gone=True)
        await session.commit()
    assert stats.gone == 1

    async with factory() as session:
        repo = ListingRepository(session)
        listing = await repo.get_by_external("otodom", "ext-1")
        assert listing is not None
        assert listing.status == ListingStatus.GONE

    # Step 3: re-sync with the SAME listing (identical raw_hash) — must reactivate
    async with factory() as session:
        eng = IncrementalEngine(session)
        stats = await eng.sync_source("otodom", [to_listing(raw, now=t3)], now=t3)
        await session.commit()

    assert stats == SyncStats(new=0, updated=0, unchanged=1, gone=0)

    async with factory() as session:
        repo = ListingRepository(session)
        listing = await repo.get_by_external("otodom", "ext-1")
        assert listing is not None
        assert listing.status == ListingStatus.ACTIVE  # reactivated

        ph_result = await session.execute(
            select(PriceHistory).where(PriceHistory.listing_id == listing.id)
        )
        history = ph_result.scalars().all()
        # Only the original PriceHistory — no new entry on unchanged-hash re-sync
        assert len(history) == 1


async def test_updated_listing_preserves_first_seen(engine):
    """Re-sync with changed content must preserve first_seen while advancing last_seen."""
    factory = await _setup(engine)
    t1 = datetime.now(UTC)
    t2 = t1 + timedelta(hours=1)
    raw1 = _raw(price=Decimal("500000"))
    raw2 = _raw(price=Decimal("450000"))

    async with factory() as session:
        eng = IncrementalEngine(session)
        await eng.sync_source("otodom", [to_listing(raw1, now=t1)], now=t1)
        await session.commit()

    # Capture first_seen before the update
    async with factory() as session:
        repo = ListingRepository(session)
        listing = await repo.get_by_external("otodom", "ext-1")
        assert listing is not None
        original_first_seen = listing.first_seen

    async with factory() as session:
        eng = IncrementalEngine(session)
        stats = await eng.sync_source("otodom", [to_listing(raw2, now=t2)], now=t2)
        await session.commit()

    assert stats == SyncStats(new=0, updated=1, unchanged=0, gone=0)

    async with factory() as session:
        repo = ListingRepository(session)
        listing = await repo.get_by_external("otodom", "ext-1")
        assert listing is not None
        assert listing.first_seen == original_first_seen  # preserved
        assert listing.last_seen == t2  # advanced
