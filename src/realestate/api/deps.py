from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from realestate.llm.base import LLMClient
from realestate.llm.factory import get_llm_client


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = get_session_factory(request)
    async with factory() as session:
        yield session


def get_llm_client_dep() -> LLMClient | None:
    return get_llm_client()


def get_fetcher_dep():
    from realestate.scrapers.browser import BrowserFetcher

    return BrowserFetcher()
