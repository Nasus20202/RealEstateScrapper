import asyncio

from realestate.events.bus import EventBus


async def test_subscribe_receives_published_event():
    bus = EventBus()
    async with bus.subscribe() as queue:
        assert bus.subscriber_count == 1
        bus.publish({"type": "scrape", "source_id": "otodom"})
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event == {"type": "scrape", "source_id": "otodom"}
    assert bus.subscriber_count == 0  # wyrejestrowano po wyjściu


async def test_multiple_subscribers_all_receive():
    bus = EventBus()
    async with bus.subscribe() as q1, bus.subscribe() as q2:
        bus.publish({"n": 1})
        assert (await asyncio.wait_for(q1.get(), 1)) == {"n": 1}
        assert (await asyncio.wait_for(q2.get(), 1)) == {"n": 1}


async def test_publish_with_no_subscribers_is_noop():
    bus = EventBus()
    bus.publish({"n": 1})  # nie rzuca
    assert bus.subscriber_count == 0


async def test_full_queue_drops_without_error():
    bus = EventBus(max_queue=1)
    async with bus.subscribe() as queue:
        bus.publish({"n": 1})
        bus.publish({"n": 2})  # kolejka pełna -> drop, brak wyjątku
        assert (await asyncio.wait_for(queue.get(), 1)) == {"n": 1}
        assert queue.empty()
