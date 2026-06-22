from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def check_database(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            ext = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            return ext.scalar_one_or_none() == 1
    except Exception:
        return False
