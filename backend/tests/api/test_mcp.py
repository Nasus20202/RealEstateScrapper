from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app


def test_mcp_app_is_mounted():
    app = create_app()

    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/mcp" in paths


@pytest.mark.asyncio
async def test_mcp_server_exposes_realestate_tools():
    app = create_app()

    tools = await app.state.mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert {"search_listings", "get_listing", "listing_stats"}.issubset(tool_names)


@pytest.mark.asyncio
async def test_mcp_mount_accepts_streamable_http_requests_without_api_prefix():
    app = create_app()

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/mcp/", headers={"Accept": "text/event-stream"})

    assert response.status_code != 404
    assert response.status_code in {200, 400}


@pytest.mark.asyncio
async def test_mcp_mount_accepts_streamable_http_requests_with_api_root_path():
    with patch("realestate.api.app.get_api_root_path", return_value="/api"):
        app = create_app()

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/mcp/", headers={"Accept": "text/event-stream"})

    assert response.status_code != 404
    assert response.status_code in {200, 400}
