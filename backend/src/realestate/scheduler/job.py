from __future__ import annotations

from realestate.config import get_settings
from realestate.events.bus import EventBus
from realestate.ingestion.service import IngestionService
from realestate.repositories.user_data import AppSettingRepository, SavedSearchRepository
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
    session_factory,
    fetcher,
    bus: EventBus,
    *,
    geocoder=None,
    max_pages: int = 1,
    source_ids: list[str] | None = None,
) -> int:
    async with session_factory() as session:
        searches = await SavedSearchRepository(session).list_all()
        settings_repo = AppSettingRepository(session)
        source_setting = await settings_repo.get("enabled_source_ids")
        cities_setting = await settings_repo.get("default_cities")
        source_pages_setting = await settings_repo.get("source_max_pages")
        default_pages_setting = await settings_repo.get("default_max_pages")
    source_ids = source_ids or (source_setting["v"] if source_setting else None)
    source_max_pages = source_pages_setting["v"] if source_pages_setting else {}
    default_cities = (
        cities_setting["v"] if cities_setting else get_settings().scraper_default_cities
    )
    if default_pages_setting:
        try:
            default_max_pages = int(default_pages_setting["v"])
        except TypeError, ValueError:
            default_max_pages = None
    else:
        default_max_pages = None
    if default_max_pages and default_max_pages > 0:
        max_pages = max(max_pages, default_max_pages)

    async def on_run(run) -> None:
        bus.publish(
            {
                "type": "scrape",
                "source_id": run.source_id,
                "status": run.status.value,
                "new": run.new_count,
                "updated": run.updated_count,
                "gone": run.gone_count,
                "unchanged": run.unchanged_count,
            }
        )

    async def on_log(source_id: str, message: str) -> None:
        bus.publish({"type": "scrape_log", "source_id": source_id, "message": message})

    service = IngestionService(session_factory, fetcher, geocoder=geocoder)
    processed = 0
    for search in searches:
        criteria = _criteria_from_filters(search.filters or {})
        if criteria is None:
            continue
        pages = (search.filters or {}).get("max_pages", max_pages)
        await service.ingest(
            criteria,
            source_ids=source_ids,
            max_pages=pages,
            source_max_pages=source_max_pages,
            on_run=on_run,
            on_log=on_log,
        )
        processed += 1
    if processed == 0:
        for city in default_cities:
            await service.ingest(
                SearchCriteria(city=city),
                source_ids=source_ids,
                max_pages=max_pages,
                source_max_pages=source_max_pages,
                mark_missing_gone=False,
                on_run=on_run,
                on_log=on_log,
            )
            processed += 1
    return processed
