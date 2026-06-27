from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import Select, String, cast, func, or_

from realestate.models.enums import MarketType
from realestate.models.listing import Listing


class ListingFilters(BaseModel):
    cities: list[str] | None = None
    districts: list[str] | None = None
    source_ids: list[str] | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_price_per_m2: int | None = None
    max_price_per_m2: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    market: str | None = None
    text: str | None = None
    nl_query: str | None = None
    sort_by: str = "date"
    sort_dir: str = "desc"


def apply_filters(stmt: Select, filters: ListingFilters) -> Select:
    if filters.cities:
        stmt = stmt.where(Listing.city.in_(filters.cities))
    if filters.districts:
        stmt = stmt.where(Listing.district.in_(filters.districts))
    if filters.source_ids:
        stmt = stmt.where(Listing.source_id.in_(filters.source_ids))
    if filters.min_price is not None:
        stmt = stmt.where(Listing.price >= filters.min_price)
    if filters.max_price is not None:
        stmt = stmt.where(Listing.price <= filters.max_price)
    if filters.min_price_per_m2 is not None:
        stmt = stmt.where(Listing.price_per_m2 >= filters.min_price_per_m2)
    if filters.max_price_per_m2 is not None:
        stmt = stmt.where(Listing.price_per_m2 <= filters.max_price_per_m2)
    if filters.min_area is not None:
        stmt = stmt.where(Listing.area_m2 >= filters.min_area)
    if filters.max_area is not None:
        stmt = stmt.where(Listing.area_m2 <= filters.max_area)
    if filters.min_rooms is not None:
        stmt = stmt.where(Listing.rooms >= filters.min_rooms)
    if filters.max_rooms is not None:
        stmt = stmt.where(Listing.rooms <= filters.max_rooms)
    if filters.market:
        try:
            stmt = stmt.where(Listing.market == MarketType(filters.market))
        except ValueError:
            pass
    if filters.text:
        pattern = f"%{filters.text.strip().lower()}%"
        if pattern != "%%":
            stmt = stmt.where(
                or_(
                    func.lower(Listing.title).like(pattern),
                    func.lower(func.coalesce(Listing.description, "")).like(pattern),
                    func.lower(func.coalesce(Listing.city, "")).like(pattern),
                    func.lower(func.coalesce(Listing.district, "")).like(pattern),
                    func.lower(func.coalesce(Listing.street, "")).like(pattern),
                    func.lower(cast(Listing.attributes, String)).like(pattern),
                )
            )
    return stmt
