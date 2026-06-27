"""
Security tests for the /api/config endpoint and Settings backend parsing.

Ensures that API keys configured in API_BACKENDS are never returned to clients.
"""

import os
import pytest


@pytest.mark.anyio
async def test_config_never_leaks_backend_keys(client):
    """GET /api/config must not include 'key' in any backends entry."""
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()

    backends = data.get("backends", [])
    for backend in backends:
        assert "key" not in backend, (
            f"Backend '{backend.get('name')}' exposed 'key' field in /api/config response"
        )


@pytest.mark.anyio
async def test_config_backends_have_expected_fields(client):
    """Each backend returned by /api/config should have only 'name' and 'models'."""
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()

    for backend in data.get("backends", []):
        assert "name" in backend
        assert "models" in backend
        assert isinstance(backend["models"], list)
        # Explicitly check no secret fields are present
        for forbidden in ("key", "url", "secret", "password", "token"):
            assert forbidden not in backend, (
                f"Backend '{backend.get('name')}' exposed forbidden field '{forbidden}'"
            )


@pytest.mark.anyio
async def test_config_multi_backend_keys_not_leaked(client, monkeypatch):
    """
    When API_BACKENDS is set with real-looking keys, /api/config must not expose them.
    Re-initializes Settings with a multi-backend env var.
    """
    monkeypatch.setenv(
        "API_BACKENDS",
        "TestA|http://localhost:1111/v1|sk-secret-key-a|model-a;"
        "TestB|http://localhost:2222/v1|sk-secret-key-b|model-b",
    )

    # Re-parse backends with the new env var
    from app.config import Settings
    Settings._parse_backends()

    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()

    response_text = response.text
    assert "sk-secret-key-a" not in response_text, "Backend key 'sk-secret-key-a' leaked in response"
    assert "sk-secret-key-b" not in response_text, "Backend key 'sk-secret-key-b' leaked in response"

    for backend in data.get("backends", []):
        assert "key" not in backend
