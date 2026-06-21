from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing
from realestate.search.filters import ListingFilters, apply_filters


class RankedListing(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    listing: Listing
    score: float | None = None
    reason: str | None = None


class SearchService:
    def __init__(self, session: AsyncSession, client=None) -> None:
        self.session = session
        self.client = client

    async def search(
        self, filters: ListingFilters, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[RankedListing], int]:
        base = apply_filters(
            select(Listing).where(Listing.status == ListingStatus.ACTIVE), filters
        )
        total = (await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        stmt = (
            base.order_by(
                Listing.price_per_m2.asc().nulls_last(),
                Listing.last_seen.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [RankedListing(listing=row) for row in rows], total
