from datetime import UTC, datetime

from realestate.llm.base import ChatMessage, LLMResult
from realestate.models import Listing
from realestate.models.enums import ListingStatus
from realestate.search.llm_search import RankedMatch, match_and_rank, parse_nl_query


class _Client:
    def __init__(self, content):
        self._content = content

    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        return LLMResult(content=self._content)

    async def embed(self, texts):  # pragma: no cover
        return [[0.0] for _ in texts]


def _listing(lid):
    now = datetime.now(UTC)
    listing = Listing(
        id=lid,
        source_id="otodom",
        external_id=str(lid),
        url="u",
        title=f"oferta {lid}",
        raw_hash="h",
        status=ListingStatus.ACTIVE,
        first_seen=now,
        last_seen=now,
        images=[],
    )
    return listing


async def test_parse_nl_query_filters_to_allowed_keys():
    client = _Client('{"max_price": 500000, "min_rooms": 2, "nonsense": 1}')
    out = await parse_nl_query(client, "tanie 2 pokoje")
    assert out == {"max_price": 500000, "min_rooms": 2}


async def test_parse_nl_query_bad_json_returns_empty():
    client = _Client("to nie json")
    assert await parse_nl_query(client, "x") == {}


async def test_match_and_rank_orders_and_filters():
    client = _Client(
        '{"matches": [{"listing_id": 1, "score": 40, "reason": "ok"}, '
        '{"listing_id": 2, "score": 95, "reason": "super"}, '
        '{"listing_id": 999, "score": 80, "reason": "obcy"}]}'
    )
    cands = [_listing(1), _listing(2)]
    out = await match_and_rank(client, cands, "blisko morza")
    assert [m.listing_id for m in out] == [2, 1]  # descending by score, 999 filtered out
    assert all(isinstance(m, RankedMatch) for m in out)
    assert out[0].score == 95


async def test_match_and_rank_bad_json_returns_empty():
    client = _Client("nie json")
    assert await match_and_rank(client, [_listing(1)], "x") == []
