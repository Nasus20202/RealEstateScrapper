from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from realestate.api.routes_listings import router as listings_router
from realestate.api.routes_scrape import router as scrape_router
from realestate.api.routes_user import router as user_router
from realestate.config import get_settings
from realestate.db.engine import create_engine, create_session_factory
from realestate.db.health import check_database


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
        engine = create_engine(get_settings().database_url)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="Agregator nieruchomości", lifespan=lifespan)

    @app.get("/health")
    async def health(db_ok: bool = Depends(get_db_health)) -> JSONResponse:  # noqa: B008
        if db_ok:
            return JSONResponse({"status": "ok", "database": True})
        return JSONResponse({"status": "degraded", "database": False}, status_code=503)

    app.include_router(listings_router)
    app.include_router(scrape_router)
    app.include_router(user_router)
    return app


app = create_app()
