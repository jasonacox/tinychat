"""Shared fixtures for TinyChat tests."""

import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set working directory so static files can be found
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    """Provide an async HTTP test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")
