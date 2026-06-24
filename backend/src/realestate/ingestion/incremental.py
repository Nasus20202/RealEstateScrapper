"""Silnik inkrementalny — upsert listings, historia cen, oznaczanie GONE."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing, PriceHistory
from realestate.repositories.listings import ListingRepository


@dataclass
class SyncStats:
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    gone: int = 0


class IncrementalEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sync_source(
        self,
        source_id: str,
        listings: list[Listing],
        *,
        now: datetime,
        mark_missing_gone: bool = True,
    ) -> SyncStats:
        repo = ListingRepository(self.session)
        stats = SyncStats()
        seen_ids: set[str] = set()

        for incoming in listings:
            seen_ids.add(incoming.external_id)
            existing = await repo.get_by_external(source_id, incoming.external_id)

            if existing is None:
                # New listing: add to session
                self.session.add(incoming)
                if incoming.price is not None:
                    ph = PriceHistory(
                        price=incoming.price,
                        observed_at=now,
                        listing=incoming,
                    )
                    self.session.add(ph)
                stats.new += 1

            elif existing.raw_hash == incoming.raw_hash:
                # Unchanged: bump last_seen and reactivate if it was GONE
                existing.last_seen = now
                existing.status = ListingStatus.ACTIVE
                stats.unchanged += 1

            else:
                # Changed: capture old price BEFORE overwriting
                old_price = existing.price

                # Copy all mutable fields from incoming to existing
                existing.title = incoming.title
                existing.price = incoming.price
                existing.price_per_m2 = incoming.price_per_m2
                existing.area_m2 = incoming.area_m2
                existing.rooms = incoming.rooms
                existing.floor = incoming.floor
                existing.total_floors = incoming.total_floors
                existing.city = incoming.city
                existing.district = incoming.district
                existing.street = incoming.street
                existing.lat = incoming.lat
                existing.lon = incoming.lon
                existing.market = incoming.market
                existing.description = incoming.description
                existing.attributes = incoming.attributes
                existing.images = incoming.images
                existing.posted_at = incoming.posted_at
                existing.raw_hash = incoming.raw_hash
                existing.last_seen = now
                existing.status = ListingStatus.ACTIVE  # reactivate if was GONE
                existing.embedding = None

                # Record price history if price changed
                if incoming.price is not None and incoming.price != old_price:
                    ph = PriceHistory(
                        price=incoming.price,
                        observed_at=now,
                        listing=existing,
                    )
                    self.session.add(ph)

                stats.updated += 1

        if mark_missing_gone:
            cities = {lst.city for lst in listings if lst.city}
            stats.gone = await repo.mark_gone(source_id, seen_ids, now=now, cities=cities or None)

        await self.session.flush()
        return stats
