from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, Listing
from realestate.models.enums import ListingStatus, MarketType
from realestate.search.filters import ListingFilters
from realestate.search.service import SearchService


async def _listing(
    s,
    *,
    ext,
    price,
    area,
    rooms,
    district,
    status=ListingStatus.ACTIVE,
    source_id="otodom",
):
    now = datetime.now(UTC)
    ppm2 = Decimal(price) / Decimal(str(area)) if area else None
    listing = Listing(
        source_id=source_id,
        external_id=ext,
        url="u",
        title=f"oferta {ext}",
        price=Decimal(price),
        price_per_m2=ppm2,
        area_m2=area,
        rooms=rooms,
        district=district,
        city="Gdansk",
        market=MarketType.SECONDARY,
        raw_hash="h" + ext,
        status=status,
        first_seen=now,
        last_seen=now,
        images=[],
    )
    s.add(listing)
    await s.flush()
    return listing


async def test_hard_filters_and_rule_ranking(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        await _listing(s, ext="cheap", price=400000, area=50, rooms=2, district="Wrzeszcz")
        await _listing(s, ext="expensive", price=900000, area=50, rooms=3, district="Oliwa")
        await _listing(s, ext="toobig", price=300000, area=120, rooms=5, district="Wrzeszcz")
        await _listing(
            s,
            ext="gone",
            price=350000,
            area=50,
            rooms=2,
            district="Wrzeszcz",
            status=ListingStatus.GONE,
        )
        svc = SearchService(s)
        filters = ListingFilters(max_price=500000, min_rooms=2, districts=["Wrzeszcz", "Oliwa"])
        items, total = await svc.search(filters, limit=10, offset=0)
        ids = [r.listing.external_id for r in items]
        # cheap (400k, 2pok, Wrzeszcz) pasuje; expensive odpada (cena); toobig odpada (5pok>... nie,
        # min_rooms=2 ok, ale cena 300k ok, district Wrzeszcz ok) -> faktycznie pasuje!
        assert "cheap" in ids
        assert "toobig" in ids
        assert "expensive" not in ids  # cena > max
        assert "gone" not in ids  # nieaktywne
        assert total == 2
        # ranking regułowy: price_per_m2 rosnąco -> toobig (2500) przed cheap (8000)
        assert ids[0] == "toobig"


async def test_pagination(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        for i in range(5):
            await _listing(s, ext=f"l{i}", price=300000 + i, area=50, rooms=2, district="X")
        svc = SearchService(s)
        items, total = await svc.search(ListingFilters(), limit=2, offset=0)
        assert total == 5 and len(items) == 2
        items2, _ = await svc.search(ListingFilters(), limit=2, offset=4)
        assert len(items2) == 1


async def test_source_filter(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        await _listing(
            s,
            ext="oto",
            price=400000,
            area=50,
            rooms=2,
            district="Wrzeszcz",
            source_id="otodom",
        )
        await _listing(
            s,
            ext="hos",
            price=400000,
            area=50,
            rooms=2,
            district="Wrzeszcz",
            source_id="hossa",
        )
        svc = SearchService(s)
        items, total = await svc.search(ListingFilters(source_ids=["hossa"]), limit=10, offset=0)
        assert total == 1
        assert items[0].listing.external_id == "hos"
