"""Tests for articles API."""

import pytest


async def _get_token(client, username="articleuser", password="password123"):
    await client.post("/api/auth/register", json={"username": username, "password": password})
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_list_articles_empty(client):
    token = await _get_token(client)
    resp = await client.get("/api/articles", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["articles"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_articles_pagination(client):
    token = await _get_token(client, "paguser")
    resp = await client.get(
        "/api/articles?page=1&per_page=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "page" in data
    assert "pages" in data
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_nonexistent_article(client):
    token = await _get_token(client, "noarticle")
    import uuid

    fake_id = uuid.uuid4()
    resp = await client.get(
        f"/api/articles/{fake_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
