"""Shared fixtures for TinyChat tests."""

import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402


@pytest.fixture
async def client(monkeypatch):
    """Provide an async HTTP test client for the FastAPI app."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.chdir(project_root)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
