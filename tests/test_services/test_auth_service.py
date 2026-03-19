"""Tests for auth service."""

import pytest

from cyberfeed.core.exceptions import AuthenticationError, ValidationError
from cyberfeed.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_register_and_login(db_session):
    svc = AuthService()
    user, access, refresh = await svc.register(db_session, "alice", "password123")
    assert user.username == "alice"
    assert user.role == "admin"  # first user
    assert access
    assert refresh


@pytest.mark.asyncio
async def test_second_user_is_reader(db_session):
    svc = AuthService()
    await svc.register(db_session, "first", "password123")
    user, _, _ = await svc.register(db_session, "second", "password123")
    assert user.role == "reader"


@pytest.mark.asyncio
async def test_register_duplicate_raises(db_session):
    svc = AuthService()
    await svc.register(db_session, "duptest", "password123")
    with pytest.raises(ValidationError):
        await svc.register(db_session, "duptest", "password456")


@pytest.mark.asyncio
async def test_register_short_password_raises(db_session):
    svc = AuthService()
    with pytest.raises(ValidationError):
        await svc.register(db_session, "shortpw", "abc")


@pytest.mark.asyncio
async def test_login_wrong_password_raises(db_session):
    svc = AuthService()
    await svc.register(db_session, "logintest", "correctpass")
    with pytest.raises(AuthenticationError):
        await svc.login(db_session, "logintest", "wrongpass")


@pytest.mark.asyncio
async def test_login_unknown_user_raises(db_session):
    svc = AuthService()
    with pytest.raises(AuthenticationError):
        await svc.login(db_session, "nobody", "password123")
