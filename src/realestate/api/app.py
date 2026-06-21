import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
        engine = create_engine(settings.database_url)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.event_bus = EventBus()
        app.state.scheduler = None
        if settings.scheduler_enabled:
            from realestate.scrapers.browser import BrowserFetcher

            scheduler = ScrapeScheduler(
                app.state.session_factory, BrowserFetcher(), app.state.event_bus
            )
            scheduler.start(interval_minutes=settings.scheduler_default_interval_minutes)
            app.state.scheduler = scheduler
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
