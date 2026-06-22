from __future__ import annotations

import json
import logging

from pydantic import BaseModel

from realestate.llm.base import ChatMessage, LLMClient
from realestate.models.listing import Listing

logger = logging.getLogger(__name__)

_ALLOWED_KEYS = {
    "max_price",
    "min_price",
    "min_rooms",
    "max_rooms",
    "min_area",
    "max_area",
    "districts",
    "market",
    "city",
}


class RankedMatch(BaseModel):
    listing_id: int
    score: float
    reason: str


def _safe_json(content: str) -> dict:
    try:
        data = json.loads(content)
    except ValueError, TypeError:
        return {}
    return data if isinstance(data, dict) else {}


async def parse_nl_query(client: LLMClient, text: str) -> dict:
    logger.info("Parsing natural language search query length=%s", len(text))
    messages = [
        ChatMessage(
            role="system",
            content=(
                "Zamień opis preferencji mieszkania na filtry. Zwróć WYŁĄCZNIE JSON o kluczach "
                "spośród: max_price, min_price, min_rooms, max_rooms, min_area, max_area, "
                "districts (lista), market, city. Pomiń nieznane."
            ),
        ),
        ChatMessage(role="user", content=text),
    ]
    result = await client.complete(messages, response_format={"type": "json_object"})
    data = _safe_json(result.content)
    parsed = {k: v for k, v in data.items() if k in _ALLOWED_KEYS}
    logger.info("Parsed natural language search keys=%s", sorted(parsed))
    return parsed


async def match_and_rank(
    client: LLMClient, candidates: list[Listing], nl_preferences: str
) -> list[RankedMatch]:
    logger.info(
        "Ranking listings with LLM candidates=%s preference_length=%s",
        len(candidates),
        len(nl_preferences),
    )
    valid_ids = {c.id for c in candidates}
    lines = [
        f"id={c.id} | {c.title} | cena={c.price if c.price is not None else '-'} | "
        f"{c.district or c.city or '-'} | {c.area_m2 or '-'} m2"
        for c in candidates
    ]
    messages = [
        ChatMessage(
            role="system",
            content=(
                "Oceń dopasowanie ofert do preferencji. Zwróć WYŁĄCZNIE JSON: "
                '{"matches":[{"listing_id":int,"score":0-100,"reason":str}]}.'
            ),
        ),
        ChatMessage(role="user", content=f"Preferencje: {nl_preferences}\n\n" + "\n".join(lines)),
    ]
    result = await client.complete(messages, response_format={"type": "json_object"})
    data = _safe_json(result.content)
    raw = data.get("matches") or []
    matches: list[RankedMatch] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            lid = item.get("listing_id")
            if lid not in valid_ids:
                continue
            try:
                score = max(0.0, min(100.0, float(item.get("score", 0))))
            except TypeError, ValueError:
                score = 0.0
            matches.append(
                RankedMatch(listing_id=lid, score=score, reason=str(item.get("reason", "")))
            )
    matches.sort(key=lambda m: m.score, reverse=True)
    logger.info("LLM ranking finished matches=%s raw_matches=%s", len(matches), len(raw))
    return matches
