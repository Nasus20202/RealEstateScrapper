from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.app import create_app
from realestate.db.engine import create_engine
from realestate.models import AppSetting, Base


async def test_lifespan_sets_state_without_scheduler(pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "false")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.engine is not None
        assert app.state.session_factory is not None
        assert app.state.event_bus is not None
        assert app.state.scheduler is not None
        assert app.state.scheduler.jobs() == []  # no active job when disabled


async def test_lifespan_shares_state_with_mcp_mount(pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "false")
    app = create_app()
    mcp_mount = next(route for route in app.routes if getattr(route, "path", None) == "/mcp")

    async with app.router.lifespan_context(app):
        assert mcp_mount.app.state.session_factory is app.state.session_factory
        assert mcp_mount.app.state.event_bus is app.state.event_bus


async def test_lifespan_starts_scheduler_when_enabled(pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "false")
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_DEFAULT_INTERVAL_MINUTES", "999")
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.scheduler is not None
        jobs = app.state.scheduler.jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "scrape"
    # scheduler is stopped after lifespan exit
    assert app.state.scheduler._scheduler.running is False


async def test_lifespan_runs_startup_migrations(pg_url, monkeypatch):
    called = False

    async def fake_run_startup_migrations():
        nonlocal called
        called = True

    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "true")
    monkeypatch.setattr(
        "realestate.db.migrations.run_startup_migrations",
        fake_run_startup_migrations,
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        assert called is True


async def _seed_scheduler_settings(pg_url: str, settings: dict[str, object]) -> None:
    from sqlalchemy import delete, text

    engine = create_engine(pg_url)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(delete(AppSetting))
    async with AsyncSession(engine) as s:
        s.add_all(AppSetting(key=key, value={"v": value}) for key, value in settings.items())
        await s.commit()
    await engine.dispose()


async def test_lifespan_honors_db_cron_even_if_env_disabled(pg_url, monkeypatch):
    await _seed_scheduler_settings(
        pg_url,
        {
            "scheduler_enabled": True,
            "scheduler_cron": "0 * * * *",
            "scheduler_interval_minutes": 0,
        },
    )
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "false")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")

    app = create_app()
    async with app.router.lifespan_context(app):
        jobs = app.state.scheduler.jobs()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.id == "scrape"
        assert isinstance(job.trigger, CronTrigger)
        assert "minute='0'" in repr(job.trigger)


async def test_lifespan_uses_db_interval_without_cron(pg_url, monkeypatch):
    await _seed_scheduler_settings(
        pg_url,
        {"scheduler_enabled": True, "scheduler_cron": None, "scheduler_interval_minutes": 45},
    )
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "false")
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_DEFAULT_INTERVAL_MINUTES", "360")

    app = create_app()
    async with app.router.lifespan_context(app):
        jobs = app.state.scheduler.jobs()
        assert len(jobs) == 1
        assert isinstance(jobs[0].trigger, IntervalTrigger)
        assert jobs[0].trigger.interval.seconds == 45 * 60


async def test_lifespan_respects_db_disabled(pg_url, monkeypatch):
    await _seed_scheduler_settings(pg_url, {"scheduler_enabled": False})
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "false")
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.scheduler.jobs() == []
