import asyncio

from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app
from realestate.api.deps import get_event_bus_dep
from realestate.api.routes_events import format_sse
from realestate.events.bus import EventBus


def test_format_sse_shape():
    out = format_sse({"type": "scrape", "source_id": "otodom"})
    assert out.startswith("event: scrape\n")
    assert '"source_id": "otodom"' in out
    assert out.endswith("\n\n")


async def test_events_stream_emits_published(engine):
    app = create_app()
    bus = EventBus()
    app.dependency_overrides[get_event_bus_dep] = lambda: bus

    async def _publish_later():
        await asyncio.sleep(0.05)
        bus.publish({"type": "scrape", "source_id": "otodom"})
        bus.publish({"type": "scrape", "source_id": "nieruchomosci-online"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        task = asyncio.create_task(_publish_later())
        async with client.stream("GET", "/events", params={"limit": 2}) as resp:
            assert resp.status_code == 200
            body = ""
            async for chunk in resp.aiter_text():
                body += chunk
        await task

    assert "otodom" in body
    assert "nieruchomosci-online" in body
    assert body.count("event: scrape") == 2
