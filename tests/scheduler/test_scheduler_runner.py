from realestate.events.bus import EventBus
from realestate.scheduler.runner import ScrapeScheduler


async def test_start_registers_job_with_interval():
    sched = ScrapeScheduler(session_factory=None, fetcher=None, bus=EventBus())
    try:
        sched.start(interval_minutes=15)
        jobs = sched.jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "scrape"
    finally:
        sched.shutdown()


async def test_reschedule_changes_interval():
    sched = ScrapeScheduler(session_factory=None, fetcher=None, bus=EventBus())
    try:
        sched.start(interval_minutes=15)
        sched.reschedule(interval_minutes=60)
        assert len(sched.jobs()) == 1  # nadal jedno zadanie
    finally:
        sched.shutdown()
