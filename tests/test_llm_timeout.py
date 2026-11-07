"""
Tests for the configurable LLM request timeout (LLM_TIMEOUT).

Local models can take longer than 30s to process a long prompt before the
first token; the timeout must be configurable and a timeout must produce an
actionable error instead of "Unexpected error: " (httpx timeouts stringify
to an empty message).
"""

import json

import httpx
import pytest

from app.config import Settings
from app.services import llm_service
from app.services.llm_service import LLMService


class FakeAsyncClient:
    """Stands in for httpx.AsyncClient: records the timeout, times out on stream()."""
    timeouts = []

    def __init__(self, timeout=None, **kwargs):
        FakeAsyncClient.timeouts.append(timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, **kwargs):
        raise httpx.ReadTimeout("")


async def _collect(**kwargs):
    out = []
    async for chunk in LLMService.stream_completion(
        [{"role": "user", "content": "Hi"}], 0.5, "test-model",
        api_url="http://llm.local/v1", api_key="k", **kwargs
    ):
        out.append(json.loads(chunk.split("data: ", 1)[1]))
    return out


@pytest.mark.anyio
async def test_llm_timeout_is_configurable(monkeypatch):
    FakeAsyncClient.timeouts.clear()
    monkeypatch.setattr(llm_service.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(Settings, "LLM_TIMEOUT", 240.0)
    await _collect()
    assert FakeAsyncClient.timeouts == [240.0]


@pytest.mark.anyio
async def test_timeout_error_is_actionable(monkeypatch):
    monkeypatch.setattr(llm_service.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(Settings, "LLM_TIMEOUT", 45.0)
    chunks = await _collect()
    assert len(chunks) == 1
    err = chunks[0]["error"]
    assert "45 seconds" in err and "LLM_TIMEOUT" in err and "ReadTimeout" in err


def test_default_timeout_is_30_seconds():
    assert Settings.LLM_TIMEOUT == 30.0
