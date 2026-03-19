"""Shared pytest fixtures."""

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Use in-memory SQLite for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from cyberfeed.database import engine, init_database
from cyberfeed.main import app
from cyberfeed.models.base import Base


@pytest_asyncio.fixture
async def db_engine():
    """Isolated in-memory engine for service-level unit tests."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(autouse=True)
async def _init_app_db():
    """Ensure app-level DB tables exist before each test."""
    await init_database()
    yield
    # Drop and recreate so each test starts clean
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """ASGI test client sharing the app's in-memory DB."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_client(client):
    """Client with a registered + logged-in admin user."""
    # Register first user (becomes admin)
    await client.post(
        "/api/auth/register",
        json={"username": "testadmin", "password": "testpassword123"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpassword123"},
    )
    token = resp.json().get("access_token")
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
