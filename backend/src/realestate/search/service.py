from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing
from realestate.search.filters import ListingFilters, apply_filters
from realestate.search.llm_search import match_and_rank

logger = logging.getLogger(__name__)

_SORT_COLS = {
    "price_per_m2": Listing.price_per_m2,
    "price": Listing.price,
    "area": Listing.area_m2,
    "date": Listing.last_seen,
}


def _build_order(filters: ListingFilters):
    col = _SORT_COLS.get(filters.sort_by, Listing.last_seen)
    primary = col.desc().nulls_last() if filters.sort_dir == "desc" else col.asc().nulls_last()
    return [primary, Listing.id.desc()]


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
        logger.info(
            "Running filtered listing search sort=%s:%s limit=%s offset=%s",
            filters.sort_by,
            filters.sort_dir,
            limit,
            offset,
        )
        base = apply_filters(select(Listing).where(Listing.status == ListingStatus.ACTIVE), filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        stmt = base.order_by(*_build_order(filters)).limit(limit).offset(offset)
        rows = (await self.session.execute(stmt)).scalars().all()
        logger.info("Filtered listing search returned=%s total=%s", len(rows), total)
        return [RankedListing(listing=row) for row in rows], total

    async def search_hybrid(
        self,
        filters: ListingFilters,
        *,
        limit: int = 50,
        offset: int = 0,
        top_k: int = 50,
    ) -> tuple[list[RankedListing], int]:
        if self.client is None or not filters.nl_query:
            logger.info(
                "Hybrid search falling back to filtered search client_available=%s has_query=%s",
                self.client is not None,
                bool(filters.nl_query),
            )
            return await self.search(filters, limit=limit, offset=offset)

        logger.info(
            "Hybrid search embedding query length=%s top_k=%s limit=%s offset=%s",
            len(filters.nl_query),
            top_k,
            limit,
            offset,
        )
        try:
            qvec = (await self.client.embed([filters.nl_query]))[0]
        except Exception:
            logger.exception("Hybrid search embedding failed; falling back to filtered search")
            return await self.search(filters, limit=limit, offset=offset)
        logger.info("Hybrid search query embedding generated dim=%s", len(qvec))
        base = apply_filters(select(Listing).where(Listing.status == ListingStatus.ACTIVE), filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        cand_stmt = (
            base.where(Listing.embedding.isnot(None))
            .order_by(Listing.embedding.cosine_distance(qvec))
            .limit(top_k)
        )
        candidates = list((await self.session.execute(cand_stmt)).scalars().all())
        logger.info(
            "Hybrid search vector candidates=%s total=%s top_k=%s",
            len(candidates),
            total,
            top_k,
        )

        try:
            matches = await match_and_rank(self.client, candidates, filters.nl_query)
        except Exception:
            logger.exception("Hybrid search rerank failed; returning vector-ranked candidates")
            page = candidates[offset : offset + limit]
            return [RankedListing(listing=c) for c in page], total
        logger.info("Hybrid search reranked matches=%s", len(matches))
        by_id = {c.id: c for c in candidates}
        ranked: list[RankedListing] = []
        used: set[int] = set()
        for m in matches:
            listing = by_id.get(m.listing_id)
            if listing is None:
                continue
            ranked.append(RankedListing(listing=listing, score=m.score, reason=m.reason))
            used.add(m.listing_id)
        for c in candidates:
            if c.id not in used:
                ranked.append(RankedListing(listing=c, score=None, reason=None))

        page = ranked[offset : offset + limit]
        logger.info("Hybrid search returned=%s ranked=%s total=%s", len(page), len(ranked), total)
        return page, total
