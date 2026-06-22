from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class EventBus:
    """In-process pub/sub po asyncio.Queue. Jeden proces, brak trwałości."""

    def __init__(self, *, max_queue: int = 100) -> None:
        self._max_queue = max_queue
        self._subscribers: set[asyncio.Queue] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @asynccontextmanager
    async def subscribe(self):
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def publish(self, event: dict) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue
