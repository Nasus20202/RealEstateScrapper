from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from realestate.config import get_settings
from realestate.db.engine import create_engine
from realestate.db.health import check_database


async def get_db_health() -> bool:
    engine = create_engine(get_settings().database_url)
    try:
        return await check_database(engine)
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Agregator nieruchomości")

    @app.get("/health")
    async def health(db_ok: bool = Depends(get_db_health)) -> JSONResponse:
        if db_ok:
            return JSONResponse({"status": "ok", "database": True})
        return JSONResponse({"status": "degraded", "database": False}, status_code=503)

    return app


app = create_app()
