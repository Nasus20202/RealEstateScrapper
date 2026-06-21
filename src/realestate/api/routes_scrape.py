from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.deps import get_fetcher_dep, get_session, get_session_factory
from realestate.api.schemas import ScrapeRequest, ScrapeResponse, ScrapeRunOut
from realestate.ingestion.service import IngestionService
from realestate.repositories.scrape_runs import ScrapeRunRepository
from realestate.scrapers.base import SearchCriteria

router = APIRouter()


@router.post("/scrape", response_model=ScrapeResponse)
async def trigger_scrape(
    body: ScrapeRequest,
    session_factory=Depends(get_session_factory),  # noqa: B008
    fetcher=Depends(get_fetcher_dep),  # noqa: B008
) -> ScrapeResponse:
    criteria = SearchCriteria(
        city=body.city,
        min_price=body.min_price,
        max_price=body.max_price,
        min_area=body.min_area,
        max_area=body.max_area,
        min_rooms=body.min_rooms,
        max_rooms=body.max_rooms,
        market=body.market,
    )
    service = IngestionService(session_factory, fetcher)
    runs = await service.ingest(criteria, source_ids=body.source_ids, max_pages=body.max_pages)
    return ScrapeResponse(runs=[ScrapeRunOut.from_run(r) for r in runs])


@router.get("/scrape/runs", response_model=list[ScrapeRunOut])
async def list_runs(
    limit: int = 50, session: AsyncSession = Depends(get_session)  # noqa: B008
) -> list[ScrapeRunOut]:
    runs = await ScrapeRunRepository(session).list_recent(limit=limit)
    return [ScrapeRunOut.from_run(r) for r in runs]


@router.get("/scrape/runs/{run_id}", response_model=ScrapeRunOut)
async def get_run(
    run_id: int, session: AsyncSession = Depends(get_session)  # noqa: B008
) -> ScrapeRunOut:
    run = await ScrapeRunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return ScrapeRunOut.from_run(run)
