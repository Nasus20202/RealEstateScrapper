from datetime import UTC, datetime
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.app import create_app
from realestate.api.deps import get_llm_client_dep, get_session
from realestate.db.engine import create_session_factory
from realestate.models import Base, Listing, LLMAnalysis, PriceHistory, Source
from realestate.models.enums import ListingStatus
from tests.db.test_migrations import upgrade_to_head


async def _seed(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        now = datetime.now(UTC)
        source = Source(source_id="otodom", display_name="Otodom", enabled=True, config={})
        s.add(source)
        listing = Listing(
            source_id="otodom",
            external_id="x1",
            url="http://x",
            title="Ładne 2pok",
            price=Decimal(400000),
            price_per_m2=Decimal(8000),
            area_m2=50.0,
            rooms=2,
            city="Gdansk",
            district="Wrzeszcz",
            raw_hash="h1",
            description="opis",
            attributes={"tags": ["BALCONY"]},
            status=ListingStatus.ACTIVE,
            first_seen=now,
            last_seen=now,
            images=[],
        )
        s.add(listing)
        await s.flush()
        s.add(PriceHistory(listing_id=listing.id, price=Decimal(410000), observed_at=now))
        s.add(
            LLMAnalysis(
                listing_id=listing.id,
                content_hash="h1",
                summary="świetne",
                features={"balkon": True},
                model="m",
                created_at=now,
            )
        )
        await s.commit()
        return listing.id


def _app(engine):
    app = create_app()
    factory = create_session_factory(engine)

    async def _override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_llm_client_dep] = lambda: None  # degradation
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
    assert body["description"] == "opis"
    assert body["attributes"] == {"tags": ["BALCONY"]}
    assert len(body["price_history"]) == 1
    assert missing.status_code == 404


async def test_list_listings_with_source_filter(engine):
    await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/listings", params={"source_id": "hossa"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0


async def test_stats_summary(engine):
    await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["overview"]["active_count"] == 1
    assert Decimal(body["overview"]["avg_price"]) == Decimal("400000")
    assert body["by_district"][0]["key"] == "Wrzeszcz"
    assert body["by_source"][0]["key"] == "otodom"
    assert body["by_rooms"][0]["key"] == "2"
    assert len(body["by_provider"]) == 1
    p = body["by_provider"][0]
    assert p["source_id"] == "otodom"
    assert p["display_name"] == "Otodom"
    assert p["enabled"] is True
    assert p["count"] == 1
    assert Decimal(p["avg_price"]) == Decimal("400000")


async def test_stats_with_filters(engine):
    await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/stats", params={"city": "Gdansk"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["overview"]["active_count"] == 1

        resp2 = await client.get("/stats", params={"city": "Warszawa"})
        body2 = resp2.json()
        assert body2["overview"]["active_count"] == 0

        resp3 = await client.get("/stats", params={"min_price": 500000})
        body3 = resp3.json()
        assert body3["overview"]["active_count"] == 0

        resp4 = await client.get("/stats", params={"source_id": "otodom"})
        body4 = resp4.json()
        assert body4["overview"]["active_count"] == 1


async def _seed_map_listings(engine):
    async with AsyncSession(engine, expire_on_commit=False) as s:
        now = datetime.now(UTC)
        s.add(Source(source_id="otodom", display_name="Otodom", enabled=True, config={}))
        s.add_all(
            [
                Listing(
                    source_id="otodom",
                    external_id="gda-1",
                    url="http://gda-1",
                    title="Wrzeszcz map listing",
                    price=Decimal(600000),
                    price_per_m2=Decimal(12000),
                    area_m2=50,
                    rooms=2,
                    city="Gdansk",
                    district="Wrzeszcz",
                    lat=54.382,
                    lon=18.604,
                    raw_hash="map-1",
                    status=ListingStatus.ACTIVE,
                    first_seen=now,
                    last_seen=now,
                    images=[],
                ),
                Listing(
                    source_id="otodom",
                    external_id="gda-2",
                    url="http://gda-2",
                    title="Oliwa map listing",
                    price=Decimal(900000),
                    price_per_m2=Decimal(15000),
                    area_m2=60,
                    rooms=3,
                    city="Gdansk",
                    district="Oliwa",
                    lat=54.411,
                    lon=18.569,
                    raw_hash="map-2",
                    status=ListingStatus.ACTIVE,
                    first_seen=now,
                    last_seen=now,
                    images=[],
                ),
                Listing(
                    source_id="otodom",
                    external_id="gdy-1",
                    url="http://gdy-1",
                    title="Gdynia map listing",
                    price=Decimal(700000),
                    price_per_m2=Decimal(14000),
                    area_m2=50,
                    rooms=2,
                    city="Gdynia",
                    district="Orlowo",
                    lat=54.477,
                    lon=18.552,
                    raw_hash="map-3",
                    status=ListingStatus.ACTIVE,
                    first_seen=now,
                    last_seen=now,
                    images=[],
                ),
                Listing(
                    source_id="otodom",
                    external_id="missing-coordinates",
                    url="http://missing-coordinates",
                    title="No map listing",
                    price=Decimal(300000),
                    price_per_m2=Decimal(10000),
                    city="Gdansk",
                    district="Wrzeszcz",
                    raw_hash="map-4",
                    status=ListingStatus.ACTIVE,
                    first_seen=now,
                    last_seen=now,
                    images=[],
                ),
            ]
        )
        await s.commit()


async def test_map_points_filters_by_bbox_on_coordinates(engine, pg_url, monkeypatch):
    await upgrade_to_head(pg_url, monkeypatch)
    await _seed_map_listings(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get(
            "/listings/map/points",
            params={"south": 54.35, "north": 54.43, "west": 18.53, "east": 18.63, "limit": 50},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {item["external_id"] for item in body["items"]} == {"gda-1", "gda-2"}


async def test_map_hexes_uses_postgis_geom_and_filters(engine, pg_url, monkeypatch):
    await upgrade_to_head(pg_url, monkeypatch)
    await _seed_map_listings(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get(
            "/listings/map/hexes",
            params={"city": "Gdansk", "south": 54.35, "north": 54.43, "west": 18.53, "east": 18.63},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body
    assert sum(hexagon["count"] for hexagon in body) == 2
    assert {hexagon["geometry"]["type"] for hexagon in body} == {"Polygon"}
    weighted_avg = (
        sum(Decimal(str(hexagon["avg_price"])) * hexagon["count"] for hexagon in body) / 2
    )
    assert weighted_avg == Decimal("750000.0")


async def test_postgis_trigger_syncs_geom_for_insert_and_coordinate_update(
    engine, pg_url, monkeypatch
):
    await upgrade_to_head(pg_url, monkeypatch)
    await _seed_map_listings(engine)
    async with engine.begin() as conn:
        inserted = await conn.execute(
            text(
                """
                SELECT ST_AsText(geom)
                FROM listings
                WHERE external_id = 'gda-1'
                """
            )
        )
        assert inserted.scalar_one() == "POINT(18.604 54.382)"

        await conn.execute(
            text(
                """
                UPDATE listings
                SET lat = 54.5, lon = 18.4
                WHERE external_id = 'gda-1'
                """
            )
        )
        updated = await conn.execute(
            text(
                """
                SELECT ST_AsText(geom)
                FROM listings
                WHERE external_id = 'gda-1'
                """
            )
        )
        assert updated.scalar_one() == "POINT(18.4 54.5)"

        await conn.execute(
            text(
                """
                UPDATE listings
                SET lat = NULL, lon = 18.4
                WHERE external_id = 'gda-1'
                """
            )
        )
        cleared = await conn.execute(text("SELECT geom FROM listings WHERE external_id = 'gda-1'"))
        assert cleared.scalar_one() is None
