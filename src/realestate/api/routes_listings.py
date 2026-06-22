from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.deps import get_llm_client_dep, get_session
from realestate.api.schemas import (
    ListingDetailOut,
    ListingOut,
    ListingsResponse,
    PriceHistoryOut,
)
from realestate.models.dedup import DedupMember
from realestate.models.listing import Listing, PriceHistory
from realestate.models.llm_analysis import LLMAnalysis
from realestate.search.filters import ListingFilters
from realestate.search.service import SearchService

router = APIRouter()


@router.get("/listings", response_model=ListingsResponse)
async def list_listings(
    session: AsyncSession = Depends(get_session),  # noqa: B008
    client=Depends(get_llm_client_dep),  # noqa: B008
    city: str | None = None,
    district: list[str] | None = Query(default=None),  # noqa: B008
    source_id: list[str] | None = Query(default=None),  # noqa: B008
    min_price: int | None = None,
    max_price: int | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    min_rooms: int | None = None,
    max_rooms: int | None = None,
    market: str | None = None,
    q: str | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> ListingsResponse:
    filters = ListingFilters(
        city=city,
        districts=district,
        min_price=min_price,
        max_price=max_price,
        source_ids=source_id,
        min_area=min_area,
        max_area=max_area,
        min_rooms=min_rooms,
        max_rooms=max_rooms,
        market=market,
        nl_query=q,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    svc = SearchService(session, client=client)
    items, total = await svc.search_hybrid(filters, limit=limit, offset=offset)
    return ListingsResponse(
        items=[ListingOut.from_listing(r.listing, score=r.score, reason=r.reason) for r in items],
        total=total,
    )


@router.get("/listings/{listing_id}", response_model=ListingDetailOut)
async def get_listing(
    listing_id: int,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ListingDetailOut:
    listing = await session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")

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

    dup_ids: list[int] = []
    member = (
        await session.execute(select(DedupMember).where(DedupMember.listing_id == listing_id))
    ).scalar_one_or_none()
    if member is not None:
        rows = (
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
        dup_ids = list(rows)

    base = ListingOut.from_listing(listing)
    return ListingDetailOut(
        **base.model_dump(),
        price_history=[PriceHistoryOut(price=h.price, observed_at=h.observed_at) for h in history],
        summary=analysis.summary if analysis else None,
        features=analysis.features if analysis else None,
        duplicate_listing_ids=dup_ids,
    )
