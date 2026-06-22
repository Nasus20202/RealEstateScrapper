import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from realestate.api.routes_events import router as events_router
from realestate.api.routes_listings import router as listings_router
from realestate.api.routes_scrape import router as scrape_router
from realestate.api.routes_user import router as user_router
from realestate.config import get_cors_origins, get_settings
from realestate.db.engine import create_engine, create_session_factory
from realestate.db.health import check_database
from realestate.events.bus import EventBus
from realestate.scheduler.runner import ScrapeScheduler


async def get_db_health() -> bool:
    engine = create_engine(get_settings().database_url)
    try:
        return await check_database(engine)
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: build engine from config (requires DATABASE_URL in real usage).
        settings = get_settings()
        from realestate.logging import configure_logging

        configure_logging(structured=settings.structured_logging)
        engine = create_engine(settings.database_url)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.event_bus = EventBus()
        app.state.scheduler = None
        if settings.db_migrate_on_startup:
            from realestate.db.migrations import run_startup_migrations

            await run_startup_migrations()
        from realestate.ingestion.geocode import get_geocoder
        from realestate.scrapers.browser import BrowserFetcher

        scheduler = ScrapeScheduler(
            app.state.session_factory,
            BrowserFetcher(),
            app.state.event_bus,
            geocoder=get_geocoder(),
        )
        app.state.scheduler = scheduler
        if settings.scheduler_enabled:
            source_crons = {}
            async with app.state.session_factory() as session:
                from realestate.repositories.user_data import AppSettingRepository

                try:
                    source_crons_setting = await AppSettingRepository(session).get("source_crons")
                except SQLAlchemyError:
                    source_crons_setting = None
                if source_crons_setting:
                    source_crons = source_crons_setting.get("v", {})
            if settings.scheduler_cron:
                scheduler.start(cron=settings.scheduler_cron, source_crons=source_crons)
            else:
                scheduler.start(
                    interval_minutes=settings.scheduler_default_interval_minutes,
                    source_crons=source_crons,
                )
        try:
            yield
        finally:
            if app.state.scheduler is not None:
                app.state.scheduler.shutdown()
                await asyncio.sleep(0)  # let AsyncIOScheduler process shutdown callback
            await engine.dispose()

    app = FastAPI(title="Agregator nieruchomości", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health(db_ok: bool = Depends(get_db_health)) -> JSONResponse:  # noqa: B008
        if db_ok:
            return JSONResponse({"status": "ok", "database": True})
        return JSONResponse({"status": "degraded", "database": False}, status_code=503)

    app.include_router(events_router)
    app.include_router(listings_router)
    app.include_router(scrape_router)
    app.include_router(user_router)
    return app


app = create_app()
