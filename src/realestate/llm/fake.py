from __future__ import annotations

import hashlib
import json
import random

from realestate.config import get_embedding_dim
from realestate.llm.base import ChatMessage, LLMResult


class FakeLLMClient:
    """Deterministyczny klient LLM do testów (bez sieci)."""

    def __init__(self, *, completion: str | None = None) -> None:
        self._fixed = completion

    def _completion(self, messages: list[ChatMessage]) -> str:
        if self._fixed is not None:
            return self._fixed
        last = messages[-1].content if messages else ""
        # Deterministyczny "wynik wzbogacenia" jako JSON.
        return json.dumps(
            {
                "summary": f"Streszczenie: {last[:40]}",
                "features": {"liczba_znakow": len(last)},
            },
            ensure_ascii=False,
        )

    async def complete(
        self, messages: list[ChatMessage], *, response_format: dict | None = None
    ) -> LLMResult:
        return LLMResult(content=self._completion(messages))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        dim = get_embedding_dim()
        out: list[list[float]] = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
            rng = random.Random(seed)
            out.append([rng.random() for _ in range(dim)])
        return out
