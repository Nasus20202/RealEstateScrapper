from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.enrichment.prompts import build_enrichment_messages
from realestate.llm.base import LLMClient
from realestate.models.listing import Listing
from realestate.models.llm_analysis import LLMAnalysis
from realestate.repositories.llm_analysis import LLMAnalysisRepository

logger = logging.getLogger(__name__)


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
            logger.info("Skipping listing enrichment listing_id=%s reason=no_client", listing.id)
            return False
        repo = LLMAnalysisRepository(self.session)
        existing = await repo.get(listing.id, listing.raw_hash)
        if existing is not None and listing.embedding is not None:
            logger.info("Skipping listing enrichment listing_id=%s reason=up_to_date", listing.id)
            return False

        logger.info(
            "Enriching listing listing_id=%s has_existing_analysis=%s has_embedding=%s",
            listing.id,
            existing is not None,
            listing.embedding is not None,
        )
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

        logger.info("Generating listing embedding listing_id=%s", listing.id)
        vectors = await self.client.embed([_embedding_text(listing, summary)])
        listing.embedding = vectors[0]
        logger.info("Generated listing embedding listing_id=%s dim=%s", listing.id, len(vectors[0]))

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
        logger.info("Listing enrichment finished listing_id=%s", listing.id)
        return True

    async def enrich_many(self, listings: list[Listing], *, now: datetime) -> int:
        logger.info("Starting listing enrichment batch listings=%s", len(listings))
        n = 0
        for listing in listings:
            if await self.enrich_listing(listing, now=now):
                n += 1
        logger.info("Finished listing enrichment batch enriched=%s listings=%s", n, len(listings))
        return n
