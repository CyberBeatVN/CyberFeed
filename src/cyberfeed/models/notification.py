"""Notification rule model."""

import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from cyberfeed.models.base import Base, TimestampMixin, UUIDMixin


class NotificationRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notification_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    destination: Mapped[str] = mapped_column(String(500), nullable=False)
    keywords: Mapped[list | None] = mapped_column(JSON, default=list)
    category_ids: Mapped[list | None] = mapped_column(JSON, default=list)
    source_platforms: Mapped[list | None] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sent_at: Mapped[str | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<NotificationRule {self.channel} -> {self.destination[:20]}>"
