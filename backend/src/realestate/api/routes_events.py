from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from realestate.api.deps import get_event_bus_dep
from realestate.events.bus import EventBus

router = APIRouter(tags=["Events"])


def format_sse(event: dict) -> str:
    etype = event.get("type", "message")
    return f"event: {etype}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


async def event_stream(bus: EventBus, *, limit: int | None = None) -> AsyncIterator[str]:
    async with bus.subscribe() as queue:
        count = 0
        while limit is None or count < limit:
            event = await queue.get()
            yield format_sse(event)
            count += 1


@router.get("/events")
async def events(
    limit: int | None = None,
    bus: EventBus = Depends(get_event_bus_dep),  # noqa: B008
) -> StreamingResponse:
    return StreamingResponse(event_stream(bus, limit=limit), media_type="text/event-stream")
