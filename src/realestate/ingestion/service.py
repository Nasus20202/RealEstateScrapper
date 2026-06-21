"""IngestionService — orchestrates per-source scrape, normalize, sync, ScrapeRun."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from realestate.ingestion.incremental import IncrementalEngine
from realestate.ingestion.normalize import to_listing
from realestate.models.enums import ScrapeRunStatus
from realestate.models.scrape_run import ScrapeRun
from realestate.repositories.scrape_runs import ScrapeRunRepository
from realestate.scrapers.base import ScraperBlocked, SearchCriteria, get_scraper, get_scrapers
from realestate.scrapers.runner import run_search


class IngestionService:
    def __init__(self, session_factory: async_sessionmaker, fetcher) -> None:
        self.session_factory = session_factory
        self.fetcher = fetcher

    async def ingest(
        self,
        criteria: SearchCriteria,
        *,
        source_ids: list[str] | None = None,
        max_pages: int = 1,
    ) -> list[ScrapeRun]:
        now = datetime.now(UTC)

        if source_ids is not None:
            scrapers = {sid: get_scraper(sid) for sid in source_ids}
        else:
            scrapers = get_scrapers()

        runs: list[ScrapeRun] = []

        for source_id, scraper in scrapers.items():
            run = ScrapeRun(
                source_id=source_id,
                started_at=now,
                status=ScrapeRunStatus.SUCCESS,
            )
            async with self.session_factory() as session:
                try:
                    raws = await run_search(scraper, self.fetcher, criteria, max_pages=max_pages)
                    listings = [to_listing(r, now=now) for r in raws]
                    stats = await IncrementalEngine(session).sync_source(
                        source_id, listings, now=now, mark_missing_gone=True
                    )
                    run.new_count = stats.new
                    run.updated_count = stats.updated
                    run.gone_count = stats.gone
                    run.unchanged_count = stats.unchanged
                    run.status = ScrapeRunStatus.SUCCESS
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

        return runs
