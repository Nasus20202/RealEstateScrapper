from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.llm_analysis import LLMAnalysis


class LLMAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, listing_id: int, content_hash: str) -> LLMAnalysis | None:
        stmt = select(LLMAnalysis).where(
            LLMAnalysis.listing_id == listing_id,
            LLMAnalysis.content_hash == content_hash,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, analysis: LLMAnalysis) -> LLMAnalysis:
        self.session.add(analysis)
        await self.session.flush()
        return analysis
