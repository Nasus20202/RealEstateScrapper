from sqlalchemy import text


async def test_engine_connects(engine):
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
