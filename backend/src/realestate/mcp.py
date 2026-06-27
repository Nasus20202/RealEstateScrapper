from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastmcp import FastMCP
from fastmcp.dependencies import CurrentRequest
from sqlalchemy import and_, func, select
from starlette.requests import Request

from realestate.api.schemas import ListingDetailOut, ListingOut, StatsOverviewOut
from realestate.models.dedup import DedupMember
from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing, PriceHistory
from realestate.models.llm_analysis import LLMAnalysis
from realestate.search.filters import ListingFilters
from realestate.search.service import SearchService

CURRENT_REQUEST = CurrentRequest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def create_mcp_server() -> FastMCP:
    mcp = FastMCP("Real Estate Backend")

    @mcp.tool
    async def search_listings(
        city: str | None = None,
        district: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        min_area: float | None = None,
        max_area: float | None = None,
        min_rooms: int | None = None,
        max_rooms: int | None = None,
        market: str | None = None,
        query: str | None = None,
        limit: int = 10,
        offset: int = 0,
        request: Request = CURRENT_REQUEST,
    ) -> dict[str, Any]:
        """Search active property listings with optional natural-language ranking."""
        limit = max(1, min(limit, 50))
        offset = max(0, offset)
        filters = ListingFilters(
            cities=[city] if city else None,
            districts=[district] if district else None,
            min_price=min_price,
            max_price=max_price,
            min_area=min_area,
            max_area=max_area,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            market=market,
            nl_query=query,
        )
        async with request.app.state.session_factory() as session:
            service = SearchService(session)
            items, total = await service.search(filters, limit=limit, offset=offset)
        return _jsonable(
            {
                "items": [ListingOut.from_listing(item.listing) for item in items],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    @mcp.tool
    async def get_listing(
        listing_id: int,
        request: Request = CURRENT_REQUEST,
    ) -> dict[str, Any] | None:
        """Get a listing with price history, LLM summary, and duplicate listing IDs."""
        async with request.app.state.session_factory() as session:
            listing = await session.get(Listing, listing_id)
            if listing is None:
                return None

            history = (
                (
                    await session.execute(
                        select(PriceHistory)
                        .where(PriceHistory.listing_id == listing_id)
                        .order_by(PriceHistory.observed_at)
                    )
                )
                .scalars()
                .all()
            )
            analysis = (
                await session.execute(
                    select(LLMAnalysis)
                    .where(LLMAnalysis.listing_id == listing_id)
                    .order_by(LLMAnalysis.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            member = (
                await session.execute(
                    select(DedupMember).where(DedupMember.listing_id == listing_id)
                )
            ).scalar_one_or_none()
            dup_ids: list[int] = []
            if member is not None:
                dup_ids = list(
                    (
                        await session.execute(
                            select(DedupMember.listing_id).where(
                                DedupMember.group_id == member.group_id,
                                DedupMember.listing_id != listing_id,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

        base = ListingOut.from_listing(listing)
        return _jsonable(
            ListingDetailOut(
                **base.model_dump(),
                price_history=history,
                summary=analysis.summary if analysis else None,
                features=analysis.features if analysis else None,
                duplicate_listing_ids=dup_ids,
            )
        )

    @mcp.tool
    async def listing_stats(request: Request = CURRENT_REQUEST) -> dict[str, Any]:
        """Return high-level counts and price statistics for active listings."""
        conditions = [Listing.status == ListingStatus.ACTIVE]
        async with request.app.state.session_factory() as session:
            row = (
                (
                    await session.execute(
                        select(
                            func.count(Listing.id).label("active_count"),
                            func.count(Listing.id).label("total_count"),
                            func.count(Listing.price).label("priced_count"),
                            func.count(Listing.lat)
                            .filter(Listing.lon.is_not(None))
                            .label("located_count"),
                            func.count(Listing.id)
                            .filter(func.cardinality(Listing.images) > 0)
                            .label("with_images_count"),
                            func.count(Listing.description).label("with_description_count"),
                            func.avg(Listing.price).filter(and_(*conditions)).label("avg_price"),
                            func.avg(Listing.price_per_m2)
                            .filter(and_(*conditions))
                            .label("avg_price_per_m2"),
                            func.avg(Listing.area_m2)
                            .filter(and_(*conditions))
                            .label("avg_area_m2"),
                            func.avg(Listing.rooms).filter(and_(*conditions)).label("avg_rooms"),
                            func.min(Listing.price).filter(and_(*conditions)).label("min_price"),
                            func.max(Listing.price).filter(and_(*conditions)).label("max_price"),
                            func.max(Listing.last_seen)
                            .filter(and_(*conditions))
                            .label("latest_seen"),
                        ).where(*conditions)
                    )
                )
                .mappings()
                .one()
            )
        return _jsonable(StatsOverviewOut(**row))

    return mcp
