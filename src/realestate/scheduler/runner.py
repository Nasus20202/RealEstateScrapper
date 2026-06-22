from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from realestate.events.bus import EventBus
from realestate.scheduler.job import run_scheduled_scrape


class ScrapeScheduler:
    def __init__(self, session_factory, fetcher, bus: EventBus, *,
                 geocoder=None, scheduler: AsyncIOScheduler | None = None) -> None:
        self.session_factory = session_factory
        self.fetcher = fetcher
        self.bus = bus
        self.geocoder = geocoder
        self._scheduler = scheduler or AsyncIOScheduler()

    async def _job(self) -> None:
        await run_scheduled_scrape(
            self.session_factory, self.fetcher, self.bus, geocoder=self.geocoder
        )

    def start(self, *, interval_minutes: int | None = None, cron: str | None = None) -> None:
        if cron:
            trigger = CronTrigger.from_crontab(cron)
            self._scheduler.add_job(self._job, trigger, id="scrape", replace_existing=True)
        else:
            self._scheduler.add_job(self._job, "interval", minutes=interval_minutes or 360,
                                    id="scrape", replace_existing=True)
        if not self._scheduler.running:
            self._scheduler.start()

    def reschedule(self, *, interval_minutes: int) -> None:
        self._scheduler.reschedule_job("scrape", trigger="interval", minutes=interval_minutes)

    def pause(self) -> None:
        job = self._scheduler.get_job("scrape")
        if job is not None:
            job.pause()

    def jobs(self):
        return self._scheduler.get_jobs()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
