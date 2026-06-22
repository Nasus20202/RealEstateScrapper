from datetime import UTC, datetime
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.app import create_app
from realestate.api.deps import get_llm_client_dep, get_session
from realestate.db.engine import create_session_factory
from realestate.models import Base, Listing
from realestate.models.enums import ListingStatus


async def _seed(engine) -> int:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        now = datetime.now(UTC)
        listing = Listing(source_id="otodom", external_id="x1", url="u", title="t",
                          price=Decimal(1), raw_hash="h", status=ListingStatus.ACTIVE,
                          first_seen=now, last_seen=now, images=[])
        s.add(listing)
        await s.commit()
        return listing.id


def _app(engine):
    app = create_app()
    factory = create_session_factory(engine)

    async def _override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_llm_client_dep] = lambda: None
    return app


async def test_saved_searches_crud(engine):
    await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        created = await client.post("/searches", json={"name": "tanie",
                                                        "filters": {"max_price": 500000},
                                                        "nl_query": "blisko morza"})
        assert created.status_code == 201
        sid = created.json()["id"]
        listed = await client.get("/searches")
        assert any(x["id"] == sid for x in listed.json())
        deleted = await client.delete(f"/searches/{sid}")
        assert deleted.status_code == 204
        # ponowne usunięcie nieistniejącego → 404
        assert (await client.delete(f"/searches/{sid}")).status_code == 404


async def test_favorites_idempotent(engine):
    listing_id = await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r1 = await client.post("/favorites", json={"listing_id": listing_id})
        r2 = await client.post("/favorites", json={"listing_id": listing_id})
        assert r1.status_code == 201 and r2.status_code == 201
        listed = await client.get("/favorites")
        assert len(listed.json()) == 1
        d = await client.delete(f"/favorites/{listing_id}")
        assert d.status_code == 204
        assert (await client.delete(f"/favorites/{listing_id}")).status_code == 404


async def test_settings_get_and_put_masks_secret(engine):
    await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        got = await client.get("/settings")
        assert got.status_code == 200
        body = got.json()
        assert "llm_api_key" not in body
        assert "llm_api_key_set" in body
        assert body["scheduler_interval_minutes"] is None
        assert body["scheduler_enabled"] is False
        assert body["scheduler_cron"] is None
        assert body["default_cities"] == ["Gdańsk", "Gdynia", "Sopot"]
        put = await client.put(
            "/settings",
            json={
                "scheduler_interval_minutes": 30,
                "scheduler_enabled": True,
                "scheduler_cron": "15 */6 * * *",
                "default_cities": ["Gdańsk", "Gdynia"],
            },
        )
        assert put.status_code == 200
        updated = put.json()
        assert updated["scheduler_interval_minutes"] == 30
        assert updated["scheduler_enabled"] is True
        assert updated["scheduler_cron"] == "15 */6 * * *"
        assert updated["default_cities"] == ["Gdańsk", "Gdynia"]
