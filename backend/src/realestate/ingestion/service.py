"""IngestionService — orchestrates per-source scrape, normalize, sync, ScrapeRun."""

from __future__ import annotations

import asyncio
import contextlib
import logging
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

logger = logging.getLogger(__name__)

_DETAIL_SOURCES = {
    "otodom",
    "nieruchomosci-online",
    "adresowo",
    "hossa",
    "develia",
    "domesta",
    "pb-gorski",
    "murapol",
    "atal",
    "robyg",
    "ekolan",
}


class IngestionService:
    def __init__(self, session_factory: async_sessionmaker, fetcher, geocoder=None) -> None:
        self.session_factory = session_factory
        self.fetcher = fetcher
        self.geocoder = geocoder

    async def _geocode(self, listings: list) -> None:
        """Best-effort fill listing.lat/lon from the address. Never raises."""
        if self.geocoder is None:
            logger.info("Skipping geocoding listings=%s reason=no_geocoder", len(listings))
            return
        attempted = 0
        matched = 0
        skipped_existing = 0
        skipped_no_query = 0
        logger.info("Starting geocoding listings=%s", len(listings))
        for listing in listings:
            if listing.lat is not None:
                skipped_existing += 1
                continue
            query = build_address_query(
                street=listing.street,
                district=listing.district,
                city=listing.city,
            )
            if not query:
                skipped_no_query += 1
                continue
            attempted += 1
            try:
                coords = await self.geocoder.geocode(query)
            except Exception:
                logger.exception("Geocoding failed for %s", query)
                coords = None
            if coords:
                listing.lat, listing.lon = coords
                matched += 1
        logger.info(
            "Finished geocoding listings=%s attempted=%s matched=%s "
            "skipped_existing=%s skipped_no_query=%s",
            len(listings),
            attempted,
            matched,
            skipped_existing,
            skipped_no_query,
        )

    async def ingest(
        self,
        criteria: SearchCriteria,
        *,
        source_ids: list[str] | None = None,
        max_pages: int = 1,
        source_max_pages: dict[str, int] | None = None,
        mark_missing_gone: bool = True,
        on_run: Callable[[ScrapeRun], Awaitable[None]] | None = None,
        on_log: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> list[ScrapeRun]:
        now = datetime.now(UTC)

        if source_ids is not None:
            scrapers = {sid: get_scraper(sid) for sid in source_ids}
        else:
            scrapers = get_scrapers()

        tasks = [
            self._ingest_source(
                source_id,
                scraper,
                criteria,
                now,
                max_pages=max_pages,
                source_max_pages=source_max_pages,
                mark_missing_gone=mark_missing_gone,
                on_run=on_run,
                on_log=on_log,
            )
            for source_id, scraper in scrapers.items()
        ]
        results = await asyncio.gather(*tasks)
        return [run for source_runs in results for run in source_runs]

    def _new_fetcher(self):
        from realestate.scrapers.browser import BrowserFetcher

        if isinstance(self.fetcher, BrowserFetcher):
            return type(self.fetcher)()
        return self.fetcher

    async def _ingest_with(
        self,
        fetcher,
        scrapers: dict,
        criteria: SearchCriteria,
        now: datetime,
        *,
        max_pages: int,
        source_max_pages: dict[str, int] | None,
        mark_missing_gone: bool,
        on_run: Callable[[ScrapeRun], Awaitable[None]] | None,
        on_log: Callable[[str, str], Awaitable[None]] | None,
    ) -> list[ScrapeRun]:
        runs: list[ScrapeRun] = []

        for source_id, scraper in scrapers.items():

            async def emit(message: str, *, _source_id: str = source_id) -> None:
                logger.info(
                    "scrape_log",
                    extra={
                        "event": "scrape_log",
                        "source_id": _source_id,
                        "scrape_message": message,
                    },
                )
                if on_log is not None:
                    try:
                        await on_log(_source_id, message)
                    except Exception:
                        logger.exception("Scrape log callback failed source=%s", _source_id)

            logger.info(
                "Starting scrape source=%s city=%s max_pages=%s",
                source_id,
                criteria.city,
                max_pages,
            )
            await emit(f"Start: {criteria.city}, maks. stron: {max_pages}")
            run = ScrapeRun(
                source_id=source_id,
                started_at=now,
                status=ScrapeRunStatus.SUCCESS,
            )
            async with self.session_factory() as session:
                raws: list = []
                blocked_err: str | None = None
                failed_err: str | None = None
                try:
                    try:
                        raws = await run_search(
                            scraper,
                            fetcher,
                            criteria,
                            max_pages=max_pages,
                            fetch_details=source_id in _DETAIL_SOURCES,
                            on_log=emit,
                        )
                    except ScraperBlocked as e:
                        # Block can carry partial results scraped before the
                        # block; we still persist them so a transient block
                        # doesn't discard an otherwise good batch.
                        blocked_err = str(e)
                        raws = getattr(e, "partial", []) or []
                        logger.warning("Scraper blocked source=%s error=%s", source_id, e)
                        await emit(f"Blokada scrapera: {e}")
                    except Exception as e:
                        failed_err = str(e)
                        logger.exception("Scrape failed source=%s", source_id)
                        await emit(f"Błąd: {e}")

                    if raws:
                        logger.info("Parsed %s raw listings source=%s", len(raws), source_id)
                        await emit(f"Normalizuję {len(raws)} ofert")
                        listings = [to_listing(r, now=now) for r in raws]
                        await emit("Geokoduję adresy")
                        await self._geocode(listings)
                        await emit("Zapisuję do bazy")
                        stats = await IncrementalEngine(session).sync_source(
                            source_id, listings, now=now, mark_missing_gone=mark_missing_gone
                        )
                        run.new_count = stats.new
                        run.updated_count = stats.updated
                        run.gone_count = stats.gone
                        run.unchanged_count = stats.unchanged

                    if blocked_err is not None:
                        run.status = ScrapeRunStatus.BLOCKED
                        run.error_message = blocked_err
                    elif failed_err is not None:
                        run.status = ScrapeRunStatus.FAILED
                        run.error_message = failed_err
                finally:
                    run.finished_at = datetime.now(UTC)
                    await ScrapeRunRepository(session).add(run)
                    await session.commit()

            runs.append(run)
            logger.info(
                "Finished scrape source=%s status=%s new=%s updated=%s gone=%s unchanged=%s",
                source_id,
                run.status.value,
                run.new_count,
                run.updated_count,
                run.gone_count,
                run.unchanged_count,
            )
            await emit(
                f"Koniec: {run.status.value}; nowe={run.new_count}, "
                f"aktualizacje={run.updated_count}, zniknęły={run.gone_count}, "
                f"bez zmian={run.unchanged_count}"
            )
            if on_run is not None:
                try:
                    await on_run(run)
                except Exception:
                    logger.exception("Scrape on_run callback failed source=%s", source_id)
                    pass

        return runs

    async def _ingest_source(
        self,
        source_id: str,
        scraper,
        criteria: SearchCriteria,
        now: datetime,
        *,
        max_pages: int,
        source_max_pages: dict[str, int] | None,
        mark_missing_gone: bool,
        on_run: Callable[[ScrapeRun], Awaitable[None]] | None,
        on_log: Callable[[str, str], Awaitable[None]] | None,
    ) -> list[ScrapeRun]:
        async with contextlib.AsyncExitStack() as stack:
            fetcher = self._new_fetcher()
            if hasattr(fetcher, "__aenter__"):
                fetcher = await stack.enter_async_context(fetcher)
            return await self._ingest_with(
                fetcher,
                {source_id: scraper},
                criteria,
                now,
                max_pages=max(
                    1,
                    int((source_max_pages or {}).get(source_id, max_pages)),
                ),
                source_max_pages=source_max_pages,
                mark_missing_gone=mark_missing_gone,
                on_run=on_run,
                on_log=on_log,
            )
