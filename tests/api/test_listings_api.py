from datetime import UTC, datetime
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.app import create_app
from realestate.api.deps import get_llm_client_dep, get_session
from realestate.db.engine import create_session_factory
from realestate.models import Base, Listing, LLMAnalysis, PriceHistory
from realestate.models.enums import ListingStatus


async def _seed(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        now = datetime.now(UTC)
        listing = Listing(source_id="otodom", external_id="x1", url="http://x", title="Ładne 2pok",
                          price=Decimal(400000), price_per_m2=Decimal(8000), area_m2=50.0, rooms=2,
                          city="Gdansk", district="Wrzeszcz", raw_hash="h1",
                          status=ListingStatus.ACTIVE, first_seen=now, last_seen=now, images=[])
        s.add(listing)
        await s.flush()
        s.add(PriceHistory(listing_id=listing.id, price=Decimal(410000), observed_at=now))
        s.add(LLMAnalysis(listing_id=listing.id, content_hash="h1", summary="świetne",
                          features={"balkon": True}, model="m", created_at=now))
        await s.commit()
        return listing.id


def _app(engine):
    app = create_app()
    factory = create_session_factory(engine)

    async def _override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_llm_client_dep] = lambda: None  # degradacja
    return app


async def test_list_listings_with_filter(engine):
    await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/listings", params={"max_price": 500000, "min_rooms": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["external_id"] == "x1"
    assert body["items"][0]["title"] == "Ładne 2pok"


async def test_listing_detail(engine):
    listing_id = await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get(f"/listings/{listing_id}")
        missing = await client.get("/listings/999999")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "świetne"
    assert body["features"] == {"balkon": True}
    assert len(body["price_history"]) == 1
    assert missing.status_code == 404
