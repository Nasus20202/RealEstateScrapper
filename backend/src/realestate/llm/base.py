from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMResult(BaseModel):
    content: str
    raw: dict | None = None


@runtime_checkable
class LLMClient(Protocol):
    async def complete(
        self, messages: list[ChatMessage], *, response_format: dict | None = None
    ) -> LLMResult: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
