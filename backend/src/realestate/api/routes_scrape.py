from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.deps import (
    get_event_bus_dep,
    get_fetcher_dep,
    get_geocoder_dep,
    get_llm_client_dep,
    get_session,
    get_session_factory,
)
from realestate.api.schemas import (
    EnrichmentRequest,
    ScrapeRequest,
    ScrapeRunOut,
)
from realestate.config import get_settings
from realestate.enrichment.service import EnrichmentService
from realestate.events.bus import EventBus
from realestate.ingestion.service import IngestionService
from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing
from realestate.repositories.scrape_runs import ScrapeRunRepository
from realestate.repositories.user_data import AppSettingRepository
from realestate.scrapers.base import SearchCriteria

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Scraping"])


async def _background_scrape(
    session_factory,
    fetcher,
    geocoder,
    cities: list[str],
    body: ScrapeRequest,
    source_max_pages: dict[str, int],
    bus: EventBus,
) -> None:
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
        bus.publish(
            {
                "type": "scrape_log",
                "source_id": source_id,
                "message": message,
            }
        )

    try:
        service = IngestionService(session_factory, fetcher, geocoder=geocoder)
        for city in cities:
            await on_log("app", f"Kolejka scrapingu dla miasta: {city}")
            criteria = SearchCriteria(
                city=city,
                min_price=body.min_price,
                max_price=body.max_price,
                min_area=body.min_area,
                max_area=body.max_area,
                min_rooms=body.min_rooms,
                max_rooms=body.max_rooms,
                market=body.market,
            )
            await service.ingest(
                criteria,
                source_ids=body.source_ids,
                max_pages=body.max_pages,
                source_max_pages=source_max_pages,
                mark_missing_gone=len(cities) == 1,
                on_run=on_run,
                on_log=on_log,
            )
    except Exception:
        logger.exception("Background scrape failed")


async def _background_enrich(
    session_factory,
    client,
    model_name: str,
    only_missing_embeddings: bool,
    limit: int | None,
) -> None:
    try:
        async with session_factory() as session:
            stmt = select(Listing).where(Listing.status == ListingStatus.ACTIVE)
            if only_missing_embeddings:
                stmt = stmt.where(Listing.embedding.is_(None))
            stmt = stmt.order_by(Listing.last_seen.desc(), Listing.id.desc())
            if limit is not None:
                stmt = stmt.limit(max(0, limit))
            listings = list((await session.execute(stmt)).scalars().all())
            await EnrichmentService(
                session,
                client,
                model_name=model_name,
            ).enrich_many(listings, now=datetime.now(UTC))
            await session.commit()
    except Exception:
        logger.exception("Background enrichment failed")


@router.post("/scrape", status_code=204)
async def trigger_scrape(
    body: ScrapeRequest,
    background_tasks: BackgroundTasks,
    session_factory=Depends(get_session_factory),  # noqa: B008
    fetcher=Depends(get_fetcher_dep),  # noqa: B008
    geocoder=Depends(get_geocoder_dep),  # noqa: B008
    bus: EventBus = Depends(get_event_bus_dep),  # noqa: B008
) -> Response:
    cities = (
        [body.city.strip()]
        if body.city and body.city.strip()
        else get_settings().scraper_default_cities
    )

    async with session_factory() as session:
        source_pages_setting = await AppSettingRepository(session).get("source_max_pages")
    source_max_pages = {
        **(source_pages_setting["v"] if source_pages_setting else {}),
        **(body.source_max_pages or {}),
    }

    background_tasks.add_task(
        _background_scrape,
        session_factory=session_factory,
        fetcher=fetcher,
        geocoder=geocoder,
        cities=cities,
        body=body,
        source_max_pages=source_max_pages,
        bus=bus,
    )

    return Response(status_code=204)


@router.post("/scrape/enrich", status_code=204)
async def enrich_listings(
    body: EnrichmentRequest,
    background_tasks: BackgroundTasks,
    session_factory=Depends(get_session_factory),  # noqa: B008
    client=Depends(get_llm_client_dep),  # noqa: B008
) -> Response:
    if client is None:
        raise HTTPException(status_code=400, detail="LLM client not configured")

    background_tasks.add_task(
        _background_enrich,
        session_factory=session_factory,
        client=client,
        model_name=get_settings().llm_model or "unknown",
        only_missing_embeddings=body.only_missing_embeddings,
        limit=body.limit,
    )

    return Response(status_code=204)


@router.get("/scrape/runs", response_model=list[ScrapeRunOut])
async def list_runs(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[ScrapeRunOut]:
    runs = await ScrapeRunRepository(session).list_recent(limit=limit)
    return [ScrapeRunOut.from_run(r) for r in runs]


@router.get("/scrape/runs/{run_id}", response_model=ScrapeRunOut)
async def get_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ScrapeRunOut:
    run = await ScrapeRunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return ScrapeRunOut.from_run(run)
