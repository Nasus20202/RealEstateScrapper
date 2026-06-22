from __future__ import annotations

import asyncio
import logging

import httpx

from realestate.llm.base import ChatMessage, LLMResult

logger = logging.getLogger(__name__)


class OpenAICompatClient:
    """Klient zgodny z OpenAI Chat/Embeddings API (np. OpenRouter)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        embedding_model: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = client
        self._owns_client = client is None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _post(self, path: str, payload: dict) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                logger.info("LLM request path=%s attempt=%s", path, attempt + 1)
                resp = await self._http().post(
                    f"{self.base_url}{path}", json=payload, headers=self._headers
                )
                resp.raise_for_status()
                logger.info("LLM request finished path=%s status=%s", path, resp.status_code)
                return resp.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                logger.warning(
                    "LLM request HTTP error path=%s status=%s attempt=%s",
                    path,
                    exc.response.status_code,
                    attempt + 1,
                )
                if exc.response.status_code < 500 or attempt == self.max_retries:
                    raise
            except httpx.TransportError as exc:
                last_exc = exc
                logger.warning(
                    "LLM request transport error path=%s attempt=%s error=%s",
                    path,
                    attempt + 1,
                    exc,
                )
                if attempt == self.max_retries:
                    raise
            await asyncio.sleep(0)  # oddaj sterowanie; brak realnego backoffu w testach
        assert last_exc is not None
        raise last_exc

    async def complete(
        self, messages: list[ChatMessage], *, response_format: dict | None = None
    ) -> LLMResult:
        logger.info(
            "LLM completion requested model=%s messages=%s response_format=%s",
            self.model,
            len(messages),
            response_format is not None,
        )
        payload: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if response_format is not None:
            payload["response_format"] = response_format
        data = await self._post("/chat/completions", payload)
        content = data["choices"][0]["message"]["content"]
        logger.info("LLM completion finished model=%s content_length=%s", self.model, len(content))
        return LLMResult(content=content, raw=data)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        logger.info("LLM embeddings requested model=%s inputs=%s", self.embedding_model, len(texts))
        payload = {"model": self.embedding_model, "input": texts}
        data = await self._post("/embeddings", payload)
        embeddings = [item["embedding"] for item in data["data"]]
        dim = len(embeddings[0]) if embeddings else 0
        logger.info(
            "LLM embeddings finished model=%s inputs=%s dim=%s",
            self.embedding_model,
            len(embeddings),
            dim,
        )
        return embeddings
