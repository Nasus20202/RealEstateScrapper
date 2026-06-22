from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app, get_db_health


async def test_cors_header_present_for_cross_origin_request():
    app = create_app()
    app.dependency_overrides[get_db_health] = lambda: True
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/health", headers={"Origin": "http://localhost:8080"})
    assert resp.status_code == 200
    # default CORS_ALLOW_ORIGINS="*" -> allow-origin echoes "*"
    assert resp.headers.get("access-control-allow-origin") in ("*", "http://localhost:8080")


async def test_cors_preflight_allows_methods():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.options(
            "/listings",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.status_code in (200, 204)
    assert "access-control-allow-origin" in resp.headers
