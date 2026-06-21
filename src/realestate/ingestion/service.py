"""IngestionService — orchestrates per-source scrape, normalize, sync, ScrapeRun."""
from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from realestate.ingestion.geocode import build_address_query
from realestate.ingestion.incremental import IncrementalEngine
from realestate.ingestion.normalize import to_listing
from realestate.models.enums import ScrapeRunStatus
from realestate.models.scrape_run import ScrapeRun
from realestate.repositories.scrape_runs import ScrapeRunRepository
from realestate.scrapers.base import ScraperBlocked, SearchCriteria, get_scraper, get_scrapers
from realestate.scrapers.runner import run_search


class IngestionService:
    def __init__(self, session_factory: async_sessionmaker, fetcher, geocoder=None) -> None:
        self.session_factory = session_factory
        self.fetcher = fetcher
        self.geocoder = geocoder

    async def _geocode(self, listings: list) -> None:
        """Best-effort fill listing.lat/lon from the address. Never raises."""
        if self.geocoder is None:
            return
        for listing in listings:
            if listing.lat is not None:
                continue
            query = build_address_query(
                street=listing.street, district=listing.district, city=listing.city
            )
            if not query:
                continue
            try:
                coords = await self.geocoder.geocode(query)
            except Exception:
                coords = None
            if coords:
                listing.lat, listing.lon = coords

    async def ingest(
        self,
        criteria: SearchCriteria,
        *,
        source_ids: list[str] | None = None,
        max_pages: int = 1,
        on_run: Callable[[ScrapeRun], Awaitable[None]] | None = None,
    ) -> list[ScrapeRun]:
        now = datetime.now(UTC)

        if source_ids is not None:
            scrapers = {sid: get_scraper(sid) for sid in source_ids}
        else:
            scrapers = get_scrapers()

        # Real fetchers (BrowserFetcher) are async context managers that launch
        # Playwright in __aenter__; fetch() asserts it was entered. Enter the
        # context once for the whole ingest. Plain test fetchers without
        # __aenter__ are used directly via the null-context branch below.
        async with contextlib.AsyncExitStack() as stack:
            fetcher = self.fetcher
            if hasattr(fetcher, "__aenter__"):
                fetcher = await stack.enter_async_context(fetcher)
            return await self._ingest_with(
                fetcher, scrapers, criteria, now, max_pages=max_pages, on_run=on_run
            )

    async def _ingest_with(
        self,
        fetcher,
        scrapers: dict,
        criteria: SearchCriteria,
        now: datetime,
        *,
        max_pages: int,
        on_run: Callable[[ScrapeRun], Awaitable[None]] | None,
    ) -> list[ScrapeRun]:
        runs: list[ScrapeRun] = []

        for source_id, scraper in scrapers.items():
            run = ScrapeRun(
                source_id=source_id,
                started_at=now,
                status=ScrapeRunStatus.SUCCESS,
            )
            async with self.session_factory() as session:
                try:
                    raws = await run_search(scraper, fetcher, criteria, max_pages=max_pages)
                    listings = [to_listing(r, now=now) for r in raws]
                    await self._geocode(listings)
                    stats = await IncrementalEngine(session).sync_source(
                        source_id, listings, now=now, mark_missing_gone=True
                    )
                    run.new_count = stats.new
                    run.updated_count = stats.updated
                    run.gone_count = stats.gone
                    run.unchanged_count = stats.unchanged
                except ScraperBlocked as e:
                    run.status = ScrapeRunStatus.BLOCKED
                    run.error_message = str(e)
                except Exception as e:
                    run.status = ScrapeRunStatus.FAILED
                    run.error_message = str(e)
                finally:
                    run.finished_at = datetime.now(UTC)
                    await ScrapeRunRepository(session).add(run)
                    await session.commit()

            runs.append(run)
            if on_run is not None:
                try:
                    await on_run(run)
                except Exception:
                    pass

        return runs
