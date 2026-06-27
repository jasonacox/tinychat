"""Tests for token counting / usage reporting in streaming responses."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.llm_service import LLMService


@pytest.mark.anyio
async def test_stream_options_included_in_payload():
    """stream_options with include_usage=True must be sent to the LLM backend."""
    captured_payload = {}

    async def mock_stream_handler(method, url, **kwargs):
        """Capture the outgoing request payload."""
        captured_payload.update(kwargs.get("json", {}))

        # Return a mock streaming response with no data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {}

        async def empty_lines():
            yield "data: [DONE]"

        mock_response.aiter_lines = empty_lines
        mock_response.aread = AsyncMock(return_value=b"")
        return mock_response

    # Build a minimal async context manager for httpx.AsyncClient.stream
    class FakeStreamCM:
        def __init__(self, method, url, **kwargs):
            self.kwargs = kwargs
            self.method = method
            self.url = url

        async def __aenter__(self):
            return await mock_stream_handler(self.method, self.url, **self.kwargs)

        async def __aexit__(self, *args):
            pass

    messages = [{"role": "user", "content": "Hello"}]

    with patch("httpx.AsyncClient.stream", side_effect=lambda method, url, **kw: FakeStreamCM(method, url, **kw)):
        chunks = []
        async for chunk in LLMService.stream_completion(messages):
            chunks.append(chunk)

    # Verify stream_options is in the captured payload
    assert "stream_options" in captured_payload, "stream_options missing from LLM request payload"
    assert captured_payload["stream_options"] == {"include_usage": True}


@pytest.mark.anyio
async def test_usage_data_forwarded_in_stream():
    """When the LLM returns a usage chunk, it should be forwarded to the client."""
    usage_data = {
        "prompt_tokens": 10,
        "completion_tokens": 25,
        "total_tokens": 35,
    }

    # Simulate SSE lines from the LLM backend
    sse_lines = [
        f'data: {json.dumps({"choices": [{"delta": {"content": "Hi"}}]})}',
        f'data: {json.dumps({"choices": [], "usage": usage_data})}',
        "data: [DONE]",
    ]

    class FakeResponse:
        status_code = 200
        reason_phrase = "OK"
        headers = {}

        async def aiter_lines(self):
            for line in sse_lines:
                yield line

        async def aread(self):
            return b""

    class FakeStreamCM:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *args):
            pass

    messages = [{"role": "user", "content": "Hello"}]

    with patch("httpx.AsyncClient.stream", side_effect=lambda *a, **kw: FakeStreamCM()):
        chunks = []
        async for chunk in LLMService.stream_completion(messages):
            chunks.append(chunk)

    # Parse the SSE data chunks we received
    parsed = []
    for chunk in chunks:
        if chunk.startswith("data: "):
            data_str = chunk.split("data: ", 1)[1].strip()
            parsed.append(json.loads(data_str))

    # Should have a content chunk and a usage chunk
    content_chunks = [p for p in parsed if "content" in p]
    usage_chunks = [p for p in parsed if "usage" in p]

    assert len(content_chunks) == 1
    assert content_chunks[0]["content"] == "Hi"

    assert len(usage_chunks) == 1
    assert usage_chunks[0]["usage"] == usage_data


@pytest.mark.anyio
async def test_stream_works_without_usage_data():
    """The stream should work gracefully when the LLM does not return usage info."""
    # Simulate SSE lines WITHOUT any usage chunk
    sse_lines = [
        f'data: {json.dumps({"choices": [{"delta": {"content": "Hello"}}]})}',
        f'data: {json.dumps({"choices": [{"delta": {"content": " world"}}]})}',
        "data: [DONE]",
    ]

    class FakeResponse:
        status_code = 200
        reason_phrase = "OK"
        headers = {}

        async def aiter_lines(self):
            for line in sse_lines:
                yield line

        async def aread(self):
            return b""

    class FakeStreamCM:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *args):
            pass

    messages = [{"role": "user", "content": "Hello"}]

    with patch("httpx.AsyncClient.stream", side_effect=lambda *a, **kw: FakeStreamCM()):
        chunks = []
        async for chunk in LLMService.stream_completion(messages):
            chunks.append(chunk)

    # Parse the SSE data chunks
    parsed = []
    for chunk in chunks:
        if chunk.startswith("data: "):
            data_str = chunk.split("data: ", 1)[1].strip()
            parsed.append(json.loads(data_str))

    # Should have content chunks but no usage chunk
    content_chunks = [p for p in parsed if "content" in p]
    usage_chunks = [p for p in parsed if "usage" in p]

    assert len(content_chunks) == 2
    assert content_chunks[0]["content"] == "Hello"
    assert content_chunks[1]["content"] == " world"
    assert len(usage_chunks) == 0, "No usage chunk should be emitted when LLM omits usage data"


@pytest.mark.anyio
async def test_chat_stream_endpoint_returns_usage(client):
    """Integration test: the /api/chat/stream endpoint forwards usage data."""
    usage_data = {
        "prompt_tokens": 5,
        "completion_tokens": 12,
        "total_tokens": 17,
    }

    sse_lines = [
        f'data: {json.dumps({"choices": [{"delta": {"content": "Hey"}}]})}',
        f'data: {json.dumps({"choices": [], "usage": usage_data})}',
        "data: [DONE]",
    ]

    class FakeResponse:
        status_code = 200
        reason_phrase = "OK"
        headers = {}

        async def aiter_lines(self):
            for line in sse_lines:
                yield line

        async def aread(self):
            return b""

    class FakeStreamCM:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *args):
            pass

    with patch("httpx.AsyncClient.stream", side_effect=lambda *a, **kw: FakeStreamCM()):
        response = await client.post(
            "/api/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hi"}],
                "model": "test-model",
            },
        )

    assert response.status_code == 200

    # Parse the streaming response body
    body = response.text
    events = []
    for line in body.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            data_str = line[6:]
            try:
                events.append(json.loads(data_str))
            except json.JSONDecodeError:
                pass

    usage_events = [e for e in events if "usage" in e]
    assert len(usage_events) == 1
    assert usage_events[0]["usage"]["total_tokens"] == 17
