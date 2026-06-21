from realestate.config import get_embedding_dim
from realestate.llm.base import ChatMessage, LLMClient, LLMResult
from realestate.llm.fake import FakeLLMClient


async def test_fake_client_satisfies_protocol():
    client = FakeLLMClient()
    assert isinstance(client, LLMClient)


async def test_fake_complete_is_deterministic():
    client = FakeLLMClient()
    msgs = [ChatMessage(role="user", content="opis mieszkania")]
    r1 = await client.complete(msgs)
    r2 = await client.complete(msgs)
    assert isinstance(r1, LLMResult)
    assert r1.content == r2.content
    assert r1.content  # niepuste


async def test_fake_complete_with_fixed_completion():
    client = FakeLLMClient(completion='{"summary": "x", "features": {}}')
    r = await client.complete([ChatMessage(role="user", content="cokolwiek")])
    assert r.content == '{"summary": "x", "features": {}}'


async def test_fake_embed_returns_correct_dim_and_deterministic():
    client = FakeLLMClient()
    out1 = await client.embed(["a", "b"])
    out2 = await client.embed(["a", "b"])
    dim = get_embedding_dim()
    assert len(out1) == 2
    assert all(len(v) == dim for v in out1)
    assert out1 == out2  # determinizm
    assert out1[0] != out1[1]  # różne teksty → różne wektory
