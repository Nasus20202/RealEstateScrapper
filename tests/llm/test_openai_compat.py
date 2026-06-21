# tests/llm/test_openai_compat.py
import httpx

from realestate.llm.base import ChatMessage
from realestate.llm.openai_compat import OpenAICompatClient


def _client(handler) -> OpenAICompatClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return OpenAICompatClient(
        base_url="https://example.test/v1",
        api_key="secret-key",
        model="some/chat-model",
        embedding_model="some/embed-model",
        client=http,
    )


async def test_complete_sends_expected_request_and_parses_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        import json as _json
        captured["body"] = _json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Witaj"}}]},
        )

    client = _client(handler)
    result = await client.complete(
        [ChatMessage(role="user", content="czesc")],
        response_format={"type": "json_object"},
    )
    assert result.content == "Witaj"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["auth"] == "Bearer secret-key"
    assert captured["body"]["model"] == "some/chat-model"
    assert captured["body"]["messages"] == [{"role": "user", "content": "czesc"}]
    assert captured["body"]["response_format"] == {"type": "json_object"}


async def test_embed_sends_expected_request_and_parses_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        import json as _json
        captured["body"] = _json.loads(request.content)
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]},
        )

    client = _client(handler)
    out = await client.embed(["a", "b"])
    assert out == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "https://example.test/v1/embeddings"
    assert captured["body"]["model"] == "some/embed-model"
    assert captured["body"]["input"] == ["a", "b"]


async def test_complete_retries_on_server_error_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = _client(handler)
    result = await client.complete([ChatMessage(role="user", content="x")])
    assert result.content == "ok"
    assert calls["n"] == 2
