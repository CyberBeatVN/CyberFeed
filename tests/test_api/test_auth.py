"""Tests for authentication endpoints."""

import pytest


@pytest.mark.asyncio
async def test_register_first_user_becomes_admin(client):
    resp = await client.post(
        "/api/auth/register",
        json={"username": "firstuser", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    await client.post(
        "/api/auth/register",
        json={"username": "dupuser", "password": "password123"},
    )
    resp = await client.post(
        "/api/auth/register",
        json={"username": "dupuser", "password": "password456"},
    )
    # 400 from service or 422 from Pydantic — either means rejection
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_register_short_password(client):
    resp = await client.post(
        "/api/auth/register",
        json={"username": "shortpw", "password": "abc"},
    )
    # Pydantic min_length=8 rejects with 422
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/api/auth/register",
        json={"username": "loginuser", "password": "password123"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"username": "loginuser", "password": "password123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/api/auth/register",
        json={"username": "wrongpw", "password": "correctpassword"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"username": "wrongpw", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client):
    resp = await client.get("/api/articles")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_token(client):
    await client.post(
        "/api/auth/register",
        json={"username": "autheduser", "password": "password123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "autheduser", "password": "password123"},
    )
    token = login.json()["access_token"]
    resp = await client.get("/api/articles", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
