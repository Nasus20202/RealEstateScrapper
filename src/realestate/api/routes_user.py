from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.deps import get_session
from realestate.api.schemas import (
    FavoriteIn,
    FavoriteOut,
    SavedSearchIn,
    SavedSearchOut,
    SettingsOut,
    SettingsUpdate,
)
from realestate.config import get_settings
from realestate.models.user_data import SavedSearch
from realestate.repositories.user_data import (
    AppSettingRepository,
    FavoriteRepository,
    SavedSearchRepository,
)
from realestate.scrapers.base import get_scrapers

router = APIRouter()


@router.get("/searches", response_model=list[SavedSearchOut])
async def list_searches(session: AsyncSession = Depends(get_session)):  # noqa: B008
    rows = await SavedSearchRepository(session).list_all()
    return [SavedSearchOut(id=r.id, name=r.name, filters=r.filters, nl_query=r.nl_query,
                           created_at=r.created_at) for r in rows]


@router.post("/searches", response_model=SavedSearchOut, status_code=201)
async def create_search(body: SavedSearchIn, session: AsyncSession = Depends(get_session)):  # noqa: B008
    repo = SavedSearchRepository(session)
    created = await repo.add(SavedSearch(name=body.name, filters=body.filters,
                                         nl_query=body.nl_query, created_at=datetime.now(UTC)))
    await session.commit()
    return SavedSearchOut(id=created.id, name=created.name, filters=created.filters,
                          nl_query=created.nl_query, created_at=created.created_at)


@router.delete("/searches/{search_id}", status_code=204)
async def delete_search(search_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    ok = await SavedSearchRepository(session).delete(search_id)
    await session.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="search not found")
    return Response(status_code=204)


@router.get("/favorites", response_model=list[FavoriteOut])
async def list_favorites(session: AsyncSession = Depends(get_session)):  # noqa: B008
    rows = await FavoriteRepository(session).list_all()
    return [FavoriteOut(id=r.id, listing_id=r.listing_id, created_at=r.created_at) for r in rows]


@router.post("/favorites", response_model=FavoriteOut, status_code=201)
async def add_favorite(body: FavoriteIn, session: AsyncSession = Depends(get_session)):  # noqa: B008
    fav = await FavoriteRepository(session).add(body.listing_id)
    await session.commit()
    return FavoriteOut(id=fav.id, listing_id=fav.listing_id, created_at=fav.created_at)


@router.delete("/favorites/{listing_id}", status_code=204)
async def delete_favorite(listing_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    ok = await FavoriteRepository(session).delete(listing_id)
    await session.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="favorite not found")
    return Response(status_code=204)


async def _build_settings_out(session: AsyncSession) -> SettingsOut:
    settings = get_settings()
    app_repo = AppSettingRepository(session)
    interval = await app_repo.get("scheduler_interval_minutes")
    enabled = await app_repo.get("scheduler_enabled")
    cron = await app_repo.get("scheduler_cron")
    cities = await app_repo.get("default_cities")
    return SettingsOut(
        llm_enabled=settings.llm_enabled,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        llm_embedding_model=settings.llm_embedding_model,
        llm_api_key_set=bool(settings.llm_api_key),
        scheduler_interval_minutes=interval["v"] if interval else None,
        scheduler_enabled=enabled["v"] if enabled else settings.scheduler_enabled,
        scheduler_cron=cron["v"] if cron else settings.scheduler_cron,
        default_cities=cities["v"] if cities else settings.scraper_default_cities,
        sources=list(get_scrapers().keys()),
    )


@router.get("/settings", response_model=SettingsOut)
async def get_settings_endpoint(session: AsyncSession = Depends(get_session)):  # noqa: B008
    return await _build_settings_out(session)


@router.put("/settings", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    app_repo = AppSettingRepository(session)
    if body.scheduler_interval_minutes is not None:
        await app_repo.set("scheduler_interval_minutes", {"v": body.scheduler_interval_minutes})
    if body.scheduler_enabled is not None:
        await app_repo.set("scheduler_enabled", {"v": body.scheduler_enabled})
    if body.scheduler_cron is not None:
        await app_repo.set("scheduler_cron", {"v": body.scheduler_cron.strip() or None})
    if body.default_cities is not None:
        cities = [city.strip() for city in body.default_cities if city.strip()]
        await app_repo.set("default_cities", {"v": cities})
    if body.enabled_source_ids is not None:
        await app_repo.set("enabled_source_ids", {"v": body.enabled_source_ids})
    await session.commit()
    out = await _build_settings_out(session)
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        if out.scheduler_enabled:
            if out.scheduler_cron:
                scheduler.start(cron=out.scheduler_cron)
            elif out.scheduler_interval_minutes:
                scheduler.start(interval_minutes=out.scheduler_interval_minutes)
        else:
            scheduler.pause()
    return out
