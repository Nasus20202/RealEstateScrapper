from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from realestate.events.bus import EventBus
from realestate.scheduler.job import run_scheduled_scrape


class ScrapeScheduler:
    def __init__(self, session_factory, fetcher, bus: EventBus, *,
                 scheduler: AsyncIOScheduler | None = None) -> None:
        self.session_factory = session_factory
        self.fetcher = fetcher
        self.bus = bus
        self._scheduler = scheduler or AsyncIOScheduler()

    async def _job(self) -> None:
        await run_scheduled_scrape(self.session_factory, self.fetcher, self.bus)

    def start(self, *, interval_minutes: int) -> None:
        self._scheduler.add_job(self._job, "interval", minutes=interval_minutes,
                                id="scrape", replace_existing=True)
        if not self._scheduler.running:
            self._scheduler.start()

    def reschedule(self, *, interval_minutes: int) -> None:
        self._scheduler.reschedule_job("scrape", trigger="interval", minutes=interval_minutes)

    def jobs(self):
        return self._scheduler.get_jobs()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
