"""
Tests for temperature handling in /api/chat/stream.

temperature=0.0 is valid (deterministic output) and must reach the LLM API
unchanged instead of being replaced by DEFAULT_TEMPERATURE.
"""

import pytest

from app.config import Settings
from app.services.llm_service import LLMService


def _capture_stream(monkeypatch):
    captured = {}

    async def fake_stream(messages, temperature, model, api_url=None, api_key=None):
        captured["temperature"] = temperature
        yield 'data: {"content": "ok"}\n\n'

    monkeypatch.setattr(LLMService, "stream_completion", staticmethod(fake_stream))
    monkeypatch.setattr(Settings, "DEFAULT_TEMPERATURE", 0.7)
    return captured


@pytest.mark.anyio
@pytest.mark.parametrize("requested,expected", [(0.0, 0.0), (0.2, 0.2), (1.5, 1.5)])
async def test_requested_temperature_is_used(client, monkeypatch, requested, expected):
    captured = _capture_stream(monkeypatch)
    resp = await client.post("/api/chat/stream", json={
        "messages": [{"role": "user", "content": "Hi"}],
        "temperature": requested,
    })
    assert resp.status_code == 200
    assert captured["temperature"] == expected


@pytest.mark.anyio
async def test_missing_temperature_uses_default(client, monkeypatch):
    captured = _capture_stream(monkeypatch)
    resp = await client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "Hi"}]})
    assert resp.status_code == 200
    assert captured["temperature"] == 0.7
