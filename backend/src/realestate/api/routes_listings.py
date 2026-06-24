from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, and_, bindparam, case, cast, desc, func, select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.deps import get_llm_client_dep, get_session
from realestate.api.schemas import (
    ListingDetailOut,
    ListingOut,
    ListingsResponse,
    MapHexOut,
    PriceHistoryOut,
    StatsBucketOut,
    StatsGroupOut,
    StatsOut,
    StatsOverviewOut,
    StatsProviderOut,
)
from realestate.models.dedup import DedupMember
from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing, PriceHistory
from realestate.models.llm_analysis import LLMAnalysis
from realestate.models.scrape_run import ScrapeRun
from realestate.models.source import Source
from realestate.search.filters import ListingFilters
from realestate.search.service import SearchService

router = APIRouter()
logger = logging.getLogger(__name__)


def _count_when(condition, *extra):
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


def _filtered_count_when(conditions):
    return func.coalesce(func.sum(case((and_(*conditions), 1), else_=0)), 0)


def _stats_conditions(
    *,
    city: str | None,
    district: list[str] | None,
    source_id: list[str] | None,
    min_price: int | None,
    max_price: int | None,
    min_rooms: int | None,
    max_rooms: int | None,
    market: str | None,
) -> list:
    conditions = [Listing.status == ListingStatus.ACTIVE]
    if city:
        conditions.append(Listing.city == city)
    if district:
        conditions.append(Listing.district.in_(district))
    if source_id:
        conditions.append(Listing.source_id.in_(source_id))
    if min_price is not None:
        conditions.append(Listing.price >= min_price)
    if max_price is not None:
        conditions.append(Listing.price <= max_price)
    if min_rooms is not None:
        conditions.append(Listing.rooms >= min_rooms)
    if max_rooms is not None:
        conditions.append(Listing.rooms <= max_rooms)
    if market:
        conditions.append(Listing.market == market)
    return conditions


async def _stats_groups(
    session: AsyncSession,
    group_expr,
    *,
    conditions: list | None = None,
    limit: int = 20,
) -> list[StatsGroupOut]:
    wheres = conditions if conditions is not None else [Listing.status == ListingStatus.ACTIVE]
    rows = (
        (
            await session.execute(
                select(
                    group_expr.label("key"),
                    func.count(Listing.id).label("count"),
                    _count_when(Listing.price.is_not(None)).label("priced_count"),
                    _count_when(Listing.lat.is_not(None) & Listing.lon.is_not(None)).label(
                        "located_count"
                    ),
                    func.avg(Listing.price).label("avg_price"),
                    func.avg(Listing.price_per_m2).label("avg_price_per_m2"),
                    func.avg(Listing.area_m2).label("avg_area_m2"),
                    func.avg(Listing.rooms).label("avg_rooms"),
                    func.min(Listing.price).label("min_price"),
                    func.max(Listing.price).label("max_price"),
                )
                .where(*wheres)
                .group_by(group_expr)
                .order_by(desc("count"))
                .limit(limit)
            )
        )
        .mappings()
        .all()
    )
    return [StatsGroupOut(**row) for row in rows]


@router.get("/stats", response_model=StatsOut)
async def stats(  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    city: str | None = Query(default=None),  # noqa: B008
    district: list[str] | None = Query(default=None),  # noqa: B008
    source_id: list[str] | None = Query(default=None),  # noqa: B008
    min_price: int | None = Query(default=None),  # noqa: B008
    max_price: int | None = Query(default=None),  # noqa: B008
    min_rooms: int | None = Query(default=None),  # noqa: B008
    max_rooms: int | None = Query(default=None),  # noqa: B008
    market: str | None = Query(default=None),  # noqa: B008
) -> StatsOut:
    conditions = _stats_conditions(
        city=city,
        district=district,
        source_id=source_id,
        min_price=min_price,
        max_price=max_price,
        min_rooms=min_rooms,
        max_rooms=max_rooms,
        market=market,
    )

    overview_row = (
        (
            await session.execute(
                select(
                    _filtered_count_when(conditions).label("active_count"),
                    func.count(Listing.id).label("total_count"),
                    _filtered_count_when([*conditions, Listing.price.is_not(None)]).label(
                        "priced_count"
                    ),
                    _filtered_count_when(
                        [*conditions, Listing.lat.is_not(None), Listing.lon.is_not(None)]
                    ).label("located_count"),
                    _filtered_count_when([*conditions, func.cardinality(Listing.images) > 0]).label(
                        "with_images_count"
                    ),
                    _filtered_count_when([*conditions, Listing.description.is_not(None)]).label(
                        "with_description_count"
                    ),
                    func.avg(Listing.price).filter(and_(*conditions)).label("avg_price"),
                    func.avg(Listing.price_per_m2)
                    .filter(and_(*conditions))
                    .label("avg_price_per_m2"),
                    func.avg(Listing.area_m2).filter(and_(*conditions)).label("avg_area_m2"),
                    func.avg(Listing.rooms).filter(and_(*conditions)).label("avg_rooms"),
                    func.min(Listing.price).filter(and_(*conditions)).label("min_price"),
                    func.max(Listing.price).filter(and_(*conditions)).label("max_price"),
                    func.max(Listing.last_seen).filter(and_(*conditions)).label("latest_seen"),
                ).where(*conditions)
            )
        )
        .mappings()
        .one()
    )

    room_rows = (
        (
            await session.execute(
                select(
                    case(
                        (Listing.rooms.is_(None), "Brak"),
                        else_=cast(Listing.rooms, String),
                    ).label("key"),
                    func.count(Listing.id).label("count"),
                )
                .where(*conditions)
                .group_by("key")
                .order_by("key")
            )
        )
        .mappings()
        .all()
    )

    price_bucket = case(
        (Listing.price.is_(None), "Brak ceny"),
        (Listing.price < 400_000, "< 400k"),
        (Listing.price < 600_000, "400k-600k"),
        (Listing.price < 800_000, "600k-800k"),
        (Listing.price < 1_000_000, "800k-1M"),
        (Listing.price < 1_500_000, "1M-1.5M"),
        else_=">= 1.5M",
    )
    price_order = case(
        (Listing.price.is_(None), 0),
        (Listing.price < 400_000, 1),
        (Listing.price < 600_000, 2),
        (Listing.price < 800_000, 3),
        (Listing.price < 1_000_000, 4),
        (Listing.price < 1_500_000, 5),
        else_=6,
    )
    price_rows = (
        (
            await session.execute(
                select(
                    price_bucket.label("key"),
                    func.count(Listing.id).label("count"),
                    price_order.label("order"),
                )
                .where(*conditions)
                .group_by(price_bucket, price_order)
                .order_by("order")
            )
        )
        .mappings()
        .all()
    )

    latest_run = (
        select(
            ScrapeRun.source_id,
            func.max(ScrapeRun.started_at).label("last_run_at"),
        )
        .group_by(ScrapeRun.source_id)
        .subquery()
    )
    latest_run_detail = (
        select(
            latest_run.c.source_id,
            latest_run.c.last_run_at,
            ScrapeRun.status.label("last_run_status"),
        )
        .join(
            ScrapeRun,
            (ScrapeRun.source_id == latest_run.c.source_id)
            & (ScrapeRun.started_at == latest_run.c.last_run_at),
        )
        .subquery()
    )

    provider_rows = (
        (
            await session.execute(
                select(
                    Listing.source_id.label("listing_source_id"),
                    Source.display_name,
                    Source.enabled,
                    func.count(Listing.id).label("count"),
                    _count_when(Listing.price.is_not(None)).label("priced_count"),
                    _count_when(Listing.lat.is_not(None) & Listing.lon.is_not(None)).label(
                        "located_count"
                    ),
                    func.avg(Listing.price).label("avg_price"),
                    func.avg(Listing.price_per_m2).label("avg_price_per_m2"),
                    func.avg(Listing.area_m2).label("avg_area_m2"),
                    func.avg(Listing.rooms).label("avg_rooms"),
                    func.min(Listing.price).label("min_price"),
                    func.max(Listing.price).label("max_price"),
                    latest_run_detail.c.last_run_at,
                    latest_run_detail.c.last_run_status,
                )
                .outerjoin(Source, Source.source_id == Listing.source_id)
                .outerjoin(
                    latest_run_detail,
                    latest_run_detail.c.source_id == Listing.source_id,
                )
                .where(*conditions)
                .group_by(
                    Listing.source_id,
                    Source.display_name,
                    Source.enabled,
                    latest_run_detail.c.last_run_at,
                    latest_run_detail.c.last_run_status,
                )
            )
        )
        .mappings()
        .all()
    )
    providers = [
        StatsProviderOut(
            source_id=row["listing_source_id"],
            display_name=row["display_name"] or row["listing_source_id"],
            enabled=row["enabled"] if row["enabled"] is not None else True,
            count=row["count"],
            priced_count=row["priced_count"],
            located_count=row["located_count"],
            avg_price=row["avg_price"],
            avg_price_per_m2=row["avg_price_per_m2"],
            avg_area_m2=row["avg_area_m2"],
            avg_rooms=row["avg_rooms"],
            min_price=row["min_price"],
            max_price=row["max_price"],
            last_run_at=row["last_run_at"],
            last_run_status=row["last_run_status"],
        )
        for row in provider_rows
    ]
    providers.sort(key=lambda p: p.count, reverse=True)

    return StatsOut(
        overview=StatsOverviewOut(**overview_row),
        by_district=await _stats_groups(
            session,
            func.coalesce(Listing.district, "Brak dzielnicy"),
            conditions=conditions,
            limit=30,
        ),
        by_source=await _stats_groups(session, Listing.source_id, conditions=conditions, limit=20),
        by_city=await _stats_groups(
            session,
            func.coalesce(Listing.city, "Brak miasta"),
            conditions=conditions,
            limit=20,
        ),
        by_market=await _stats_groups(
            session,
            func.coalesce(cast(Listing.market, String), "Brak"),
            conditions=conditions,
            limit=10,
        ),
        by_rooms=[StatsBucketOut(key=str(row["key"]), count=row["count"]) for row in room_rows],
        price_buckets=[StatsBucketOut(key=row["key"], count=row["count"]) for row in price_rows],
        by_provider=providers,
    )


def _map_filter_params(
    *,
    city: str | None,
    district: list[str] | None,
    source_id: list[str] | None,
    min_price: int | None,
    max_price: int | None,
    min_area: float | None,
    max_area: float | None,
    min_rooms: int | None,
    max_rooms: int | None,
    market: str | None,
    north: float | None = None,
    south: float | None = None,
    east: float | None = None,
    west: float | None = None,
) -> tuple[list[str], dict]:
    clauses = ["status = 'active'", "geom IS NOT NULL"]
    params: dict = {}
    if city:
        clauses.append("city = :city")
        params["city"] = city
    if district:
        clauses.append("district IN :districts")
        params["districts"] = tuple(district)
    if source_id:
        clauses.append("source_id IN :source_ids")
        params["source_ids"] = tuple(source_id)
    if min_price is not None:
        clauses.append("price >= :min_price")
        params["min_price"] = min_price
    if max_price is not None:
        clauses.append("price <= :max_price")
        params["max_price"] = max_price
    if min_area is not None:
        clauses.append("area_m2 >= :min_area")
        params["min_area"] = min_area
    if max_area is not None:
        clauses.append("area_m2 <= :max_area")
        params["max_area"] = max_area
    if min_rooms is not None:
        clauses.append("rooms >= :min_rooms")
        params["min_rooms"] = min_rooms
    if max_rooms is not None:
        clauses.append("rooms <= :max_rooms")
        params["max_rooms"] = max_rooms
    if market:
        clauses.append("market = :market")
        params["market"] = market
    if None not in (north, south, east, west):
        clauses.append("geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)")
        params.update({"north": north, "south": south, "east": east, "west": west})
    return clauses, params


def _listing_map_conditions(
    *,
    city: str | None,
    district: list[str] | None,
    source_id: list[str] | None,
    min_price: int | None,
    max_price: int | None,
    min_area: float | None,
    max_area: float | None,
    min_rooms: int | None,
    max_rooms: int | None,
    market: str | None,
    north: float | None,
    south: float | None,
    east: float | None,
    west: float | None,
):
    conditions = [
        Listing.status == ListingStatus.ACTIVE,
        Listing.lat.is_not(None),
        Listing.lon.is_not(None),
    ]
    if city:
        conditions.append(Listing.city == city)
    if district:
        conditions.append(Listing.district.in_(district))
    if source_id:
        conditions.append(Listing.source_id.in_(source_id))
    if min_price is not None:
        conditions.append(Listing.price >= min_price)
    if max_price is not None:
        conditions.append(Listing.price <= max_price)
    if min_area is not None:
        conditions.append(Listing.area_m2 >= min_area)
    if max_area is not None:
        conditions.append(Listing.area_m2 <= max_area)
    if min_rooms is not None:
        conditions.append(Listing.rooms >= min_rooms)
    if max_rooms is not None:
        conditions.append(Listing.rooms <= max_rooms)
    if market:
        conditions.append(Listing.market == market)
    if None not in (north, south, east, west):
        conditions.extend(
            [
                Listing.lat <= north,
                Listing.lat >= south,
                Listing.lon <= east,
                Listing.lon >= west,
            ]
        )
    return conditions


@router.get("/listings/map/hexes", response_model=list[MapHexOut])
async def listing_map_hexes(
    session: AsyncSession = Depends(get_session),  # noqa: B008
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
    north: float | None = None,
    south: float | None = None,
    east: float | None = None,
    west: float | None = None,
    size_m: int = 850,
) -> list[MapHexOut]:
    clauses, params = _map_filter_params(
        city=city,
        district=district,
        source_id=source_id,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
        min_rooms=min_rooms,
        max_rooms=max_rooms,
        market=market,
        north=north,
        south=south,
        east=east,
        west=west,
    )
    size_m = max(250, min(size_m, 3000))
    params["size_m"] = size_m
    stmt = text(
        f"""
        WITH filtered AS (
            SELECT geom, price, price_per_m2
            FROM listings
            WHERE {" AND ".join(clauses)}
        ), bounds AS (
            SELECT ST_Expand(ST_Extent(ST_Transform(geom, 3857))::geometry, :size_m) AS geom
            FROM filtered
        ), hexes AS (
            SELECT ST_SetSRID(h.geom, 3857) AS geom
            FROM bounds b
            CROSS JOIN LATERAL ST_HexagonGrid(:size_m, b.geom) AS h
            WHERE b.geom IS NOT NULL
        )
        SELECT
            md5(ST_AsEWKB(hexes.geom)::text) AS id,
            ST_AsGeoJSON(ST_Transform(hexes.geom, 4326)) AS geometry,
            count(filtered.geom)::int AS count,
            avg(filtered.price) AS avg_price,
            avg(filtered.price_per_m2) AS avg_price_per_m2
        FROM hexes
        JOIN filtered ON ST_Intersects(ST_Transform(filtered.geom, 3857), hexes.geom)
        GROUP BY hexes.geom
        ORDER BY count DESC
        LIMIT 700
        """
    )
    if district:
        stmt = stmt.bindparams(bindparam("districts", expanding=True))
    if source_id:
        stmt = stmt.bindparams(bindparam("source_ids", expanding=True))
    try:
        rows = (await session.execute(stmt, params)).mappings().all()
    except DBAPIError, ProgrammingError:
        logger.exception("Listing map hex query failed")
        return []
    import json

    return [
        MapHexOut(
            id=row["id"],
            geometry=json.loads(row["geometry"]),
            count=row["count"],
            avg_price=row["avg_price"],
            avg_price_per_m2=row["avg_price_per_m2"],
        )
        for row in rows
    ]


@router.get("/listings/map/points", response_model=ListingsResponse)
async def listing_map_points(
    session: AsyncSession = Depends(get_session),  # noqa: B008
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
    north: float | None = None,
    south: float | None = None,
    east: float | None = None,
    west: float | None = None,
    limit: int = 400,
) -> ListingsResponse:
    conditions = _listing_map_conditions(
        city=city,
        district=district,
        source_id=source_id,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
        min_rooms=min_rooms,
        max_rooms=max_rooms,
        market=market,
        north=north,
        south=south,
        east=east,
        west=west,
    )
    limit = max(50, min(limit, 1500))
    total = (await session.execute(select(func.count(Listing.id)).where(*conditions))).scalar_one()
    rows = (
        (
            await session.execute(
                select(Listing).where(*conditions).order_by(Listing.last_seen.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return ListingsResponse(items=[ListingOut.from_listing(row) for row in rows], total=total)


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
    logger.info(
        "Listing search requested q=%s city=%s districts=%s sources=%s "
        "limit=%s offset=%s sort=%s:%s",
        bool(q),
        city,
        district,
        source_id,
        limit,
        offset,
        sort_by,
        sort_dir,
    )
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
    logger.info(
        "Listing search finished q=%s total=%s returned=%s limit=%s offset=%s",
        bool(q),
        total,
        len(items),
        limit,
        offset,
    )
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
