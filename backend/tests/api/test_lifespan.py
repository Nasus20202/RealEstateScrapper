from realestate.api.app import create_app


async def test_lifespan_sets_state_without_scheduler_by_default(pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "false")
    monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.engine is not None
        assert app.state.session_factory is not None
        assert app.state.event_bus is not None
        assert app.state.scheduler is not None
        assert app.state.scheduler.jobs() == []  # domyślnie bez aktywnego joba


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
    # po wyjściu z lifespanu scheduler jest zatrzymany
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
