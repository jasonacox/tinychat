"""Shared pytest fixtures for TinyChat tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    with TestClient(app) as c:
        yield c
