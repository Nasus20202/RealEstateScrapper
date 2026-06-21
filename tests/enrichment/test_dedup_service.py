from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.enrichment.dedup import DedupService
from realestate.llm.base import ChatMessage, LLMResult
from realestate.models import Base, DedupGroup, DedupMember, Listing
from realestate.models.enums import ListingStatus


class _GroupingClient:
    def __init__(self, groups):
        self._groups = groups

    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        import json
        return LLMResult(content=json.dumps({"groups": self._groups}))

    async def embed(self, texts):  # pragma: no cover - nieużywane
        return [[0.0] for _ in texts]


async def _listing(s, ext) -> Listing:
    now = datetime.now(UTC)
    listing = Listing(source_id="otodom", external_id=ext, url="u", title="t",
                      raw_hash="h", status=ListingStatus.ACTIVE,
                      first_seen=now, last_seen=now, images=[])
    s.add(listing)
    await s.flush()
    return listing


async def test_find_and_persist_groups(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "a")
        l2 = await _listing(s, "b")
        l3 = await _listing(s, "c")
        client = _GroupingClient([[l1.id, l2.id]])  # l3 sam, nie grupowany
        svc = DedupService(s, client)
        created = await svc.run([l1, l2, l3], now=datetime.now(UTC))
        assert created == 1
        groups = (await s.execute(select(func.count()).select_from(DedupGroup))).scalar_one()
        members = (await s.execute(select(func.count()).select_from(DedupMember))).scalar_one()
        assert groups == 1 and members == 2


async def test_filters_singletons_and_unknown_ids(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "a")
        l2 = await _listing(s, "b")
        client = _GroupingClient([[l1.id], [l2.id, 99999]])  # singleton + obce id
        svc = DedupService(s, client)
        groups = await svc.find_duplicate_groups([l1, l2])
        assert groups == []  # [l1] singleton odpada; [l2,99999] -> [l2] singleton odpada


async def test_noop_without_client(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "a")
        l2 = await _listing(s, "b")
        svc = DedupService(s, None)
        assert await svc.run([l1, l2], now=datetime.now(UTC)) == 0
