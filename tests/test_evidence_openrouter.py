from pipeline.evidence.openrouter import OpenRouterClient, _parse_json


def test_parse_json_strips_markdown_fence():
    assert _parse_json("```json\n{\"ok\": true}\n```") == {"ok": True}


def test_openrouter_uses_cache_without_api_call():
    client = OpenRouterClient(api_key="secret", model="test/model")
    messages = [{"role": "user", "content": "Return JSON"}]
    prompt_hash = client._hash_payload("synonym-expansion", messages, 2048)
    client._read_cache = lambda cached_hash: (  # type: ignore[method-assign]
        {"created_at": "2026-04-15T00:00:00+00:00", "output": {"ok": True}}
        if cached_hash == prompt_hash
        else None
    )

    result = client.chat_json("synonym-expansion", messages, source_ids=["source:1"])

    assert result is not None
    assert result.output == {"ok": True}
    assert result.source_ids == ["source:1"]
    assert result.prompt_hash == prompt_hash
