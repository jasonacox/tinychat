"""
Smoke tests for TinyChat server — validates that the export/import feature
did not break core server functionality.

Tests:
- Static index.html is served at GET /
- Config endpoint returns valid JSON with expected keys
- The HTML includes the export/import UI elements
"""

import pytest


@pytest.mark.asyncio
async def test_index_served(client):
    """GET / should return 200 with HTML content."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<html" in response.text.lower()


@pytest.mark.asyncio
async def test_config_endpoint_returns_valid_json(client):
    """GET /api/config should return JSON with expected keys."""
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "available_models" in data
    assert "default_model" in data
    assert "version" in data
    assert isinstance(data["available_models"], list)


@pytest.mark.asyncio
async def test_html_contains_export_button(client):
    """The index page should include the export button."""
    response = await client.get("/")
    assert response.status_code == 200
    assert 'class="export-btn"' in response.text
    assert "exportConversations()" in response.text


@pytest.mark.asyncio
async def test_html_contains_import_button(client):
    """The index page should include the import button and hidden file input."""
    response = await client.get("/")
    assert response.status_code == 200
    assert 'class="import-btn"' in response.text
    assert 'id="importInput"' in response.text
    assert "importConversations(event)" in response.text


@pytest.mark.asyncio
async def test_html_includes_export_import_script(client):
    """The index page should load the export-import JavaScript module."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "export-import.js" in response.text
