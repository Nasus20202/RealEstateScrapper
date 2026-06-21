from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app, get_db_health


async def test_health_ok():
    app = create_app()
    app.dependency_overrides[get_db_health] = lambda: True
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": True}


async def test_health_degraded_when_db_down():
    app = create_app()
    app.dependency_overrides[get_db_health] = lambda: False
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["database"] is False
