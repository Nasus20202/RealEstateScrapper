from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.enrichment.prompts import build_enrichment_messages
from realestate.llm.base import LLMClient
from realestate.models.listing import Listing
from realestate.models.llm_analysis import LLMAnalysis
from realestate.repositories.llm_analysis import LLMAnalysisRepository


def _embedding_text(listing: Listing, summary: str) -> str:
    return " ".join(
        x
        for x in [
            listing.title,
            listing.district or listing.city or "",
            summary,
            listing.description or "",
        ]
        if x
    )


class EnrichmentService:
    def __init__(
        self, session: AsyncSession, client: LLMClient | None, *, model_name: str = "unknown"
    ) -> None:
        self.session = session
        self.client = client
        self.model_name = model_name

    async def enrich_listing(self, listing: Listing, *, now: datetime) -> bool:
        if self.client is None:
            return False
        repo = LLMAnalysisRepository(self.session)
        existing = await repo.get(listing.id, listing.raw_hash)
        if existing is not None and listing.embedding is not None:
            return False

        result = await self.client.complete(
            build_enrichment_messages(listing), response_format={"type": "json_object"}
        )
        try:
            data = json.loads(result.content)
            if not isinstance(data, dict):
                data = {}
        except ValueError, TypeError:
            data = {}
        summary = str(data.get("summary", ""))
        features = data.get("features", {})
        if not isinstance(features, dict):
            features = {}

        vectors = await self.client.embed([_embedding_text(listing, summary)])
        listing.embedding = vectors[0]

        if existing is None:
            await repo.add(
                LLMAnalysis(
                    listing_id=listing.id,
                    content_hash=listing.raw_hash,
                    summary=summary,
                    features=features,
                    model=self.model_name,
                    created_at=now,
                )
            )
        else:
            existing.summary = summary
            existing.features = features
            existing.created_at = now

        await self.session.flush()
        return True

    async def enrich_many(self, listings: list[Listing], *, now: datetime) -> int:
        n = 0
        for listing in listings:
            if await self.enrich_listing(listing, now=now):
                n += 1
        return n
