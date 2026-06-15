"""Shared test fixtures for TinyChat."""

import os
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set required environment variables before importing the app
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-testing")
os.environ.setdefault("OPENAI_API_URL", "http://localhost:11434/v1")
os.environ.setdefault("ALLOW_SYSTEM_MESSAGES", "true")

from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client backed by the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
