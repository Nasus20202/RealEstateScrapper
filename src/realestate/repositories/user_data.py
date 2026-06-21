from datetime import UTC, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.user_data import AppSetting, Favorite, SavedSearch


class SavedSearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[SavedSearch]:
        rows = (await self.session.execute(
            select(SavedSearch).order_by(SavedSearch.created_at.desc())
        )).scalars().all()
        return list(rows)

    async def get(self, search_id: int) -> SavedSearch | None:
        return await self.session.get(SavedSearch, search_id)

    async def add(self, search: SavedSearch) -> SavedSearch:
        self.session.add(search)
        await self.session.flush()
        return search

    async def delete(self, search_id: int) -> bool:
        obj = await self.session.get(SavedSearch, search_id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True


class FavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Favorite]:
        rows = (await self.session.execute(
            select(Favorite).order_by(Favorite.created_at.desc())
        )).scalars().all()
        return list(rows)

    async def exists(self, listing_id: int) -> bool:
        row = (await self.session.execute(
            select(Favorite.id).where(Favorite.listing_id == listing_id)
        )).scalar_one_or_none()
        return row is not None

    async def add(self, listing_id: int) -> Favorite:
        existing = (await self.session.execute(
            select(Favorite).where(Favorite.listing_id == listing_id)
        )).scalar_one_or_none()
        if existing is not None:
            return existing
        fav = Favorite(listing_id=listing_id, created_at=datetime.now(UTC))
        self.session.add(fav)
        await self.session.flush()
        return fav

    async def delete(self, listing_id: int) -> bool:
        result = await self.session.execute(
            sa_delete(Favorite).where(Favorite.listing_id == listing_id)
        )
        await self.session.flush()
        return result.rowcount > 0


class AppSettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> dict | None:
        obj = await self.session.get(AppSetting, key)
        return obj.value if obj is not None else None

    async def set(self, key: str, value: dict) -> None:
        stmt = pg_insert(AppSetting).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value})
        await self.session.execute(stmt)
        await self.session.flush()

    async def all(self) -> dict[str, dict]:
        rows = (await self.session.execute(select(AppSetting))).scalars().all()
        return {row.key: row.value for row in rows}
