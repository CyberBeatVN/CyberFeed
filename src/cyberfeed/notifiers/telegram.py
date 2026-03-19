"""Telegram notifier using python-telegram-bot."""

import structlog

from cyberfeed.notifiers.base import AbstractNotifier, NotificationPayload

logger = structlog.get_logger()


class TelegramNotifier(AbstractNotifier):
    """Send notifications via Telegram bot."""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    async def send(self, recipient: str, payload: NotificationPayload) -> bool:
        """Send a Telegram message to the given chat_id."""
        try:
            from telegram import Bot

            bot = Bot(token=self.bot_token)

            # Format message
            text = f"<b>{payload.subject}</b>\n\n{payload.body}"
            if payload.article_url:
                text += f'\n\n<a href="{payload.article_url}">Read more</a>'

            # Truncate to Telegram limit
            if len(text) > 4096:
                text = text[:4090] + "..."

            await bot.send_message(
                chat_id=recipient,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
            return True

        except Exception as e:
            await logger.awarning("Telegram send failed", error=str(e), chat_id=recipient)
            return False

    async def validate_recipient(self, recipient: str) -> tuple[bool, str]:
        """Validate Telegram chat_id format (numeric string)."""
        try:
            int(recipient)
            return True, ""
        except ValueError:
            return False, "Chat ID must be a numeric value"
