"""Tests for Telegram notifier validation (no API calls)."""

import pytest

from cyberfeed.notifiers.telegram import TelegramNotifier


@pytest.fixture
def notifier():
    return TelegramNotifier(bot_token="fake:token")


@pytest.mark.asyncio
async def test_valid_chat_id(notifier):
    ok, err = await notifier.validate_recipient("123456789")
    assert ok
    assert err == ""


@pytest.mark.asyncio
async def test_negative_chat_id(notifier):
    ok, err = await notifier.validate_recipient("-100123456")
    assert ok
    assert err == ""


@pytest.mark.asyncio
async def test_invalid_chat_id(notifier):
    ok, err = await notifier.validate_recipient("not_a_number")
    assert not ok
    assert err
