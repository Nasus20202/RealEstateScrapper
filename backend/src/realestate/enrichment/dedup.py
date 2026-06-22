from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.llm.base import ChatMessage, LLMClient
from realestate.models.dedup import DedupGroup, DedupMember
from realestate.models.listing import Listing

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Otrzymasz listę ofert nieruchomości z różnych portali. Zgrupuj te, które "
    "opisują TĘ SAMĄ fizyczną nieruchomość. Zwróć wyłącznie JSON: "
    '{"groups": [[id, id, ...], ...]} — tylko grupy o 2+ elementach.'
)


def build_dedup_messages(listings: list[Listing]) -> list[ChatMessage]:
    lines = []
    for listing in listings:
        lines.append(
            f"id={listing.id} | {listing.title} | {listing.city or '-'}/"
            f"{listing.district or '-'} | {listing.area_m2 or '-'} m2 | "
            f"cena={listing.price if listing.price is not None else '-'} | "
            f"{listing.url}"
        )
    return [
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(role="user", content="\n".join(lines)),
    ]


class DedupService:
    def __init__(self, session: AsyncSession, client: LLMClient | None) -> None:
        self.session = session
        self.client = client

    async def find_duplicate_groups(self, listings: list[Listing]) -> list[list[int]]:
        if self.client is None or len(listings) < 2:
            logger.info(
                "Skipping duplicate detection listings=%s client_available=%s",
                len(listings),
                self.client is not None,
            )
            return []
        valid_ids = {listing.id for listing in listings}
        logger.info("Running duplicate detection listings=%s", len(listings))
        result = await self.client.complete(
            build_dedup_messages(listings), response_format={"type": "json_object"}
        )
        try:
            data = json.loads(result.content)
        except ValueError, TypeError:
            logger.warning("Duplicate detection returned invalid JSON")
            return []
        if not isinstance(data, dict):
            logger.warning("Duplicate detection returned non-object JSON")
            return []
        raw_groups = data.get("groups") or []
        groups: list[list[int]] = []
        for grp in raw_groups:
            if not isinstance(grp, list):
                continue
            members = [gid for gid in grp if gid in valid_ids]
            if len(members) >= 2:
                groups.append(members)
        logger.info(
            "Duplicate detection finished groups=%s raw_groups=%s",
            len(groups),
            len(raw_groups),
        )
        return groups

    async def persist_groups(self, groups: list[list[int]], *, now: datetime) -> int:
        logger.info("Persisting duplicate groups groups=%s", len(groups))
        created = 0
        for members in groups:
            group = DedupGroup(created_at=now)
            group.members = [DedupMember(listing_id=lid) for lid in members]
            self.session.add(group)
            created += 1
        await self.session.flush()
        logger.info("Persisted duplicate groups created=%s", created)
        return created

    async def run(self, listings: list[Listing], *, now: datetime) -> int:
        groups = await self.find_duplicate_groups(listings)
        return await self.persist_groups(groups, now=now)
