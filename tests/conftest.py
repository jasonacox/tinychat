"""Shared test fixtures for TinyChat."""

import os

# Set required environment variables before importing app modules
# Use explicit assignment (not setdefault) so tests never accidentally
# hit a real LLM backend due to inherited environment variables.
os.environ["OPENAI_API_KEY"] = "test-key-for-testing"
os.environ["OPENAI_API_URL"] = "http://localhost:9999/v1"
os.environ["DEFAULT_MODEL"] = "test-model"
os.environ["AVAILABLE_MODELS"] = "test-model,gpt-4"

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async test client for the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
