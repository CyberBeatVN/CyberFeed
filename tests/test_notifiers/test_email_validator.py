"""Tests for email notifier validation (no SMTP calls)."""

import pytest

from cyberfeed.notifiers.email import EmailNotifier


@pytest.fixture
def notifier():
    return EmailNotifier(
        smtp_host="localhost",
        smtp_port=587,
        username="test",
        password="test",
        from_addr="test@example.com",
    )


@pytest.mark.asyncio
async def test_valid_email(notifier):
    ok, err = await notifier.validate_recipient("user@example.com")
    assert ok
    assert err == ""


@pytest.mark.asyncio
async def test_invalid_email(notifier):
    ok, err = await notifier.validate_recipient("not-an-email")
    assert not ok
    assert err


@pytest.mark.asyncio
async def test_invalid_email_no_tld(notifier):
    ok, _ = await notifier.validate_recipient("user@localhost")
    assert not ok
