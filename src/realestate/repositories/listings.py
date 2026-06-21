from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing


class ListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_external(self, source_id: str, external_id: str) -> Listing | None:
        stmt = select(Listing).where(
            Listing.source_id == source_id,
            Listing.external_id == external_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, listing: Listing) -> Listing:
        self.session.add(listing)
        await self.session.flush()
        return listing

    async def list_active(self, limit: int = 100, offset: int = 0) -> list[Listing]:
        stmt = (
            select(Listing)
            .where(Listing.status == ListingStatus.ACTIVE)
            .order_by(Listing.last_seen.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_active(self) -> int:
        stmt = select(func.count()).select_from(Listing).where(
            Listing.status == ListingStatus.ACTIVE
        )
        return (await self.session.execute(stmt)).scalar_one()
