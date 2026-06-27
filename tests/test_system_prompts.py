"""Tests for system prompt presets and related API behavior."""

import json
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_config_endpoint_returns_success(client):
    """GET /api/config should return 200 with expected configuration keys."""
    response = await client.get("/api/config")
    assert response.status_code == 200

    data = response.json()
    assert "available_models" in data
    assert "default_model" in data
    assert "default_temperature" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_config_endpoint_contains_model_list(client):
    """GET /api/config should include a non-empty list of available models."""
    response = await client.get("/api/config")
    data = response.json()

    assert isinstance(data["available_models"], list)
    assert len(data["available_models"]) > 0


@pytest.mark.asyncio
async def test_chat_stream_with_system_message(client):
    """POST /api/chat/stream with a system message prepended should stream successfully.

    When ALLOW_SYSTEM_MESSAGES=true (set in conftest), the server should accept
    a messages array containing a system role message followed by a user message
    and return a streaming response.
    """

    async def fake_stream(messages, temperature, model):
        """Simulate LLM streaming a single chunk."""
        yield f"data: {json.dumps({'content': 'Hello from the assistant'})}\n\n"

    with patch("app.api.v1.chat.LLMService.stream_completion", side_effect=fake_stream):
        response = await client.post(
            "/api/chat/stream",
            json={
                "messages": [
                    {"role": "system", "content": "You are a helpful coding assistant."},
                    {"role": "user", "content": "Say hello"},
                ],
            },
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Parse the streamed SSE body
    body = response.text
    assert "Hello from the assistant" in body


@pytest.mark.asyncio
async def test_chat_stream_system_message_passed_to_llm(client):
    """The system message should be included in messages forwarded to the LLM service."""

    captured_messages = []

    async def capturing_stream(messages, temperature, model):
        captured_messages.extend(messages)
        yield f"data: {json.dumps({'content': 'ok'})}\n\n"

    with patch("app.api.v1.chat.LLMService.stream_completion", side_effect=capturing_stream):
        with patch("app.api.v1.chat.LLMService.inject_document_context", side_effect=lambda msgs: msgs):
            await client.post(
                "/api/chat/stream",
                json={
                    "messages": [
                        {"role": "system", "content": "You are a pirate."},
                        {"role": "user", "content": "Ahoy"},
                    ],
                },
            )

    # The system message should have been preserved (ALLOW_SYSTEM_MESSAGES=true)
    system_msgs = [m for m in captured_messages if m.get("role") == "system"]
    assert len(system_msgs) >= 1
    assert any("pirate" in m["content"] for m in system_msgs)
