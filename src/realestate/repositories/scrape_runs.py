from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.scrape_run import ScrapeRun


class ScrapeRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, run: ScrapeRun) -> ScrapeRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def latest_for_source(self, source_id: str) -> ScrapeRun | None:
        stmt = (
            select(ScrapeRun)
            .where(ScrapeRun.source_id == source_id)
            .order_by(ScrapeRun.started_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
