from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import Select

from realestate.models.enums import MarketType
from realestate.models.listing import Listing


class ListingFilters(BaseModel):
    city: str | None = None
    districts: list[str] | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    market: str | None = None
    nl_query: str | None = None


def apply_filters(stmt: Select, filters: ListingFilters) -> Select:
    if filters.city:
        stmt = stmt.where(Listing.city == filters.city)
    if filters.districts:
        stmt = stmt.where(Listing.district.in_(filters.districts))
    if filters.min_price is not None:
        stmt = stmt.where(Listing.price >= filters.min_price)
    if filters.max_price is not None:
        stmt = stmt.where(Listing.price <= filters.max_price)
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
    return stmt
