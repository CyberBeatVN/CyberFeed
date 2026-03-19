"""Notifier interface and payload dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotificationPayload:
    """Notification content to send."""

    subject: str
    body: str
    html_body: str | None = None
    article_url: str | None = None
    article_title: str | None = None


class AbstractNotifier(ABC):
    """Base class for all notification channels."""

    @abstractmethod
    async def send(self, recipient: str, payload: NotificationPayload) -> bool:
        """Send notification. Returns True on success. Must not raise."""

    @abstractmethod
    async def validate_recipient(self, recipient: str) -> tuple[bool, str]:
        """Validate recipient address/ID format. Returns (is_valid, error_message)."""
