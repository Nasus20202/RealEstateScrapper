from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from realestate.models.listing import Listing


class SavedSearchIn(BaseModel):
    name: str
    filters: dict = {}
    nl_query: str | None = None


class SavedSearchOut(BaseModel):
    id: int
    name: str
    filters: dict
    nl_query: str | None
    created_at: datetime


class FavoriteIn(BaseModel):
    listing_id: int


class FavoriteOut(BaseModel):
    id: int
    listing_id: int
    created_at: datetime


class SettingsOut(BaseModel):
    llm_enabled: bool
    llm_base_url: str
    llm_model: str | None
    llm_embedding_model: str | None
    llm_api_key_set: bool
    scheduler_interval_minutes: int | None
    scheduler_enabled: bool
    scheduler_cron: str | None
    default_cities: list[str]
    sources: list[str]


class SettingsUpdate(BaseModel):
    scheduler_interval_minutes: int | None = None
    scheduler_enabled: bool | None = None
    scheduler_cron: str | None = None
    default_cities: list[str] | None = None
    enabled_source_ids: list[str] | None = None


class ListingOut(BaseModel):
    id: int
    source_id: str
    external_id: str
    url: str
    title: str
    price: Decimal | None = None
    price_per_m2: Decimal | None = None
    area_m2: float | None = None
    rooms: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    city: str | None = None
    district: str | None = None
    street: str | None = None
    lat: float | None = None
    lon: float | None = None
    market: str | None = None
    description: str | None = None
    attributes: dict = {}
    images: list[str] = []
    posted_at: datetime | None = None
    status: str
    score: float | None = None
    reason: str | None = None

    @classmethod
    def from_listing(cls, listing: Listing, *, score=None, reason=None) -> ListingOut:
        return cls(
            id=listing.id, source_id=listing.source_id, external_id=listing.external_id,
            url=listing.url, title=listing.title, price=listing.price,
            price_per_m2=listing.price_per_m2, area_m2=listing.area_m2, rooms=listing.rooms,
            floor=listing.floor, total_floors=listing.total_floors, city=listing.city,
            district=listing.district, street=listing.street,
            lat=listing.lat, lon=listing.lon,
            market=listing.market.value if listing.market else None,
            description=listing.description,
            attributes=listing.attributes or {},
            images=list(listing.images or []), posted_at=listing.posted_at,
            status=listing.status.value, score=score, reason=reason,
        )


class PriceHistoryOut(BaseModel):
    price: Decimal
    observed_at: datetime


class ListingDetailOut(ListingOut):
    price_history: list[PriceHistoryOut] = []
    summary: str | None = None
    features: dict | None = None
    duplicate_listing_ids: list[int] = []


class ListingsResponse(BaseModel):
    items: list[ListingOut]
    total: int


class ScrapeRunOut(BaseModel):
    id: int
    source_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    new_count: int
    updated_count: int
    gone_count: int
    unchanged_count: int
    error_message: str | None = None

    @classmethod
    def from_run(cls, run) -> ScrapeRunOut:
        return cls(
            id=run.id,
            source_id=run.source_id,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status.value,
            new_count=run.new_count,
            updated_count=run.updated_count,
            gone_count=run.gone_count,
            unchanged_count=run.unchanged_count,
            error_message=run.error_message,
        )


class ScrapeRequest(BaseModel):
    city: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    market: str | None = None
    source_ids: list[str] | None = None
    max_pages: int = 1


class ScrapeResponse(BaseModel):
    runs: list[ScrapeRunOut]
