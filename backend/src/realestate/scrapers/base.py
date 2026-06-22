from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SearchCriteria(BaseModel):
    city: str
    min_price: int | None = None
    max_price: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    market: str | None = None


class RawListing(BaseModel):
    source_id: str
    external_id: str
    url: str
    title: str
    price: Decimal | None = None
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
    attributes: dict = Field(default_factory=dict)
    images: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    raw: dict = Field(default_factory=dict)


class ScraperBlocked(Exception):
    """Wykryto blokadę anty-bot / wymóg captcha."""


@runtime_checkable
class Scraper(Protocol):
    source_id: str
    display_name: str

    def build_search_url(self, criteria: SearchCriteria, page: int) -> str: ...
    def parse_search(self, html: str) -> list[RawListing]: ...
    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]: ...


_REGISTRY: dict[str, Scraper] = {}


def register(scraper: Scraper) -> None:
    _REGISTRY[scraper.source_id] = scraper


def get_scrapers() -> dict[str, Scraper]:
    return dict(_REGISTRY)


def get_scraper(source_id: str) -> Scraper:
    return _REGISTRY[source_id]
