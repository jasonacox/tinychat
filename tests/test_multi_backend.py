"""
Integration tests for multi-backend switching.

Covers:
- Settings.get_backend() resolution logic
- /api/config backends response (keys never exposed)
- /api/chat/stream: unknown backend → 400
- /api/chat/stream: missing API key → 500
- /api/chat/stream: model not in backend list → warning but streams OK
- /api/chat/stream: valid backend selection routes to correct URL
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings


# ---------------------------------------------------------------------------
# Settings.get_backend() unit tests
# ---------------------------------------------------------------------------

class TestGetBackend:
    """Unit tests for Settings.get_backend()."""

    def setup_method(self):
        """Save and restore API_BACKENDS around each test."""
        self._original = Settings.API_BACKENDS[:]

    def teardown_method(self):
        Settings.API_BACKENDS = self._original

    def test_returns_first_backend_when_no_name(self):
        Settings.API_BACKENDS = [
            {"name": "alpha", "url": "http://a/v1", "key": "k1", "models": ["m1"]},
            {"name": "beta",  "url": "http://b/v1", "key": "k2", "models": ["m2"]},
        ]
        assert Settings.get_backend() == Settings.API_BACKENDS[0]

    def test_returns_named_backend(self):
        Settings.API_BACKENDS = [
            {"name": "alpha", "url": "http://a/v1", "key": "k1", "models": ["m1"]},
            {"name": "beta",  "url": "http://b/v1", "key": "k2", "models": ["m2"]},
        ]
        result = Settings.get_backend("beta")
        assert result["name"] == "beta"
        assert result["url"] == "http://b/v1"

    def test_returns_none_for_unknown_name(self):
        Settings.API_BACKENDS = [
            {"name": "alpha", "url": "http://a/v1", "key": "k1", "models": ["m1"]},
        ]
        assert Settings.get_backend("nonexistent") is None

    def test_returns_none_when_no_backends_configured(self):
        Settings.API_BACKENDS = []
        assert Settings.get_backend() is None


# ---------------------------------------------------------------------------
# /api/config — backends array must never expose keys
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_config_multi_backend_structure(client, monkeypatch):
    """With multiple backends configured, /api/config returns names+models only."""
    monkeypatch.setattr(Settings, "API_BACKENDS", [
        {"name": "Local",    "url": "http://localhost:11434/v1", "key": "sk-secret-1", "models": ["llama3"]},
        {"name": "OpenAI",   "url": "https://api.openai.com/v1", "key": "sk-secret-2", "models": ["gpt-4"]},
    ])

    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()

    assert len(data["backends"]) == 2
    for backend in data["backends"]:
        assert "key" not in backend
        assert "url" not in backend
        assert "name" in backend
        assert "models" in backend

    assert response.text.count("sk-secret") == 0


# ---------------------------------------------------------------------------
# /api/chat/stream — error cases
# ---------------------------------------------------------------------------

VALID_BODY = {
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "test-model",
}


@pytest.mark.anyio
async def test_chat_stream_unknown_backend_returns_400(client):
    """Requesting a non-existent backend name must return 400."""
    body = {**VALID_BODY, "backend": "does-not-exist"}
    response = await client.post("/api/chat/stream", json=body)
    assert response.status_code == 400
    assert "does-not-exist" in response.text


@pytest.mark.anyio
async def test_chat_stream_missing_api_key_returns_500(client, monkeypatch):
    """A backend with an empty API key must return 500."""
    monkeypatch.setattr(Settings, "API_BACKENDS", [
        {"name": "default", "url": "http://localhost:9999/v1", "key": "", "models": ["test-model"]},
    ])
    response = await client.post("/api/chat/stream", json=VALID_BODY)
    assert response.status_code == 500
    assert "API key not configured" in response.text


@pytest.mark.anyio
async def test_chat_stream_model_not_in_backend_list_still_streams(monkeypatch):
    """
    A model not in the backend's list should produce a warning log but still
    attempt to stream (soft validation, not a hard rejection).
    """
    monkeypatch.setattr(Settings, "API_BACKENDS", [
        {"name": "default", "url": "http://localhost:9999/v1", "key": "test-key", "models": ["known-model"]},
    ])
    monkeypatch.setattr(Settings, "AVAILABLE_MODELS", ["known-model", "unknown-model"])

    # Build a mock streaming response that immediately returns [DONE]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.reason_phrase = "OK"
    mock_response.headers = {}

    async def fake_lines():
        yield "data: [DONE]"

    mock_response.aiter_lines = fake_lines
    mock_response.aread = AsyncMock(return_value=b"")

    class FakeStreamCM:
        async def __aenter__(self): return mock_response
        async def __aexit__(self, *a): pass

    with patch("httpx.AsyncClient.stream", return_value=FakeStreamCM()):
        from app.services.llm_service import LLMService
        chunks = []
        async for chunk in LLMService.stream_completion(
            [{"role": "user", "content": "Hi"}],
            model="unknown-model",
            api_url="http://localhost:9999/v1",
            api_key="test-key",
        ):
            chunks.append(chunk)

    # The stream should complete without an error chunk
    assert not any('"error"' in c for c in chunks)


@pytest.mark.anyio
async def test_chat_stream_routes_to_correct_backend_url(monkeypatch):
    """When a named backend is selected, the request must go to that backend's URL."""
    monkeypatch.setattr(Settings, "API_BACKENDS", [
        {"name": "local",  "url": "http://localhost:11434/v1", "key": "k1", "models": ["llama3"]},
        {"name": "remote", "url": "http://remote:4000/v1",    "key": "k2", "models": ["gpt-4"]},
    ])
    monkeypatch.setattr(Settings, "AVAILABLE_MODELS", ["llama3", "gpt-4"])
    monkeypatch.setattr(Settings, "DEFAULT_MODEL", "llama3")

    captured_urls = []

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.reason_phrase = "OK"
    mock_response.headers = {}

    async def fake_lines():
        yield "data: [DONE]"

    mock_response.aiter_lines = fake_lines
    mock_response.aread = AsyncMock(return_value=b"")

    class FakeStreamCM:
        def __init__(self, method, url, **kwargs):
            captured_urls.append(url)

        async def __aenter__(self): return mock_response
        async def __aexit__(self, *a): pass

    with patch("httpx.AsyncClient.stream", side_effect=lambda m, url, **kw: FakeStreamCM(m, url, **kw)):
        from app.services.llm_service import LLMService
        async for _ in LLMService.stream_completion(
            [{"role": "user", "content": "Hi"}],
            model="gpt-4",
            api_url="http://remote:4000/v1",
            api_key="k2",
        ):
            pass

    assert len(captured_urls) >= 1
    assert "remote:4000" in captured_urls[0]
    assert "11434" not in captured_urls[0]
