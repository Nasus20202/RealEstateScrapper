from __future__ import annotations

from realestate.events.bus import EventBus
from realestate.ingestion.service import IngestionService
from realestate.repositories.user_data import SavedSearchRepository
from realestate.scrapers.base import SearchCriteria


def _criteria_from_filters(filters: dict) -> SearchCriteria | None:
    city = filters.get("city")
    if not isinstance(city, str) or not city:
        return None
    return SearchCriteria(
        city=city,
        min_price=filters.get("min_price"),
        max_price=filters.get("max_price"),
        min_area=filters.get("min_area"),
        max_area=filters.get("max_area"),
        min_rooms=filters.get("min_rooms"),
        max_rooms=filters.get("max_rooms"),
        market=filters.get("market"),
    )


async def run_scheduled_scrape(
    session_factory, fetcher, bus: EventBus, *, geocoder=None, max_pages: int = 1
) -> int:
    async with session_factory() as session:
        searches = await SavedSearchRepository(session).list_all()

    async def on_run(run) -> None:
        bus.publish({
            "type": "scrape", "source_id": run.source_id, "status": run.status.value,
            "new": run.new_count, "updated": run.updated_count,
            "gone": run.gone_count, "unchanged": run.unchanged_count,
        })

    service = IngestionService(session_factory, fetcher, geocoder=geocoder)
    processed = 0
    for search in searches:
        criteria = _criteria_from_filters(search.filters or {})
        if criteria is None:
            continue
        pages = (search.filters or {}).get("max_pages", max_pages)
        await service.ingest(criteria, max_pages=pages, on_run=on_run)
        processed += 1
    return processed
