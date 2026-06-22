from __future__ import annotations

from realestate.config import Settings, get_settings
from realestate.llm.base import LLMClient
from realestate.llm.openai_compat import OpenAICompatClient


def build_client_from_settings(settings: Settings) -> OpenAICompatClient:
    return OpenAICompatClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or "",
        model=settings.llm_model or "",
        embedding_model=settings.llm_embedding_model or "",
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def get_llm_client() -> LLMClient | None:
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    return build_client_from_settings(settings)
