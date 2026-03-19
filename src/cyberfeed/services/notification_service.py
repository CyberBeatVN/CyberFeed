"""Notification service: rule matching, dispatch, notifier management."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.config import get_settings
from cyberfeed.models.article import Article
from cyberfeed.models.notification import NotificationRule
from cyberfeed.notifiers.base import AbstractNotifier, NotificationPayload

logger = structlog.get_logger()


class NotificationService:
    """Manages notification rules and dispatches notifications."""

    def __init__(self):
        self._notifiers: dict[str, AbstractNotifier] = {}
        settings = get_settings()

        if settings.TELEGRAM_ENABLED and settings.TELEGRAM_BOT_TOKEN:
            from cyberfeed.notifiers.telegram import TelegramNotifier

            self._notifiers["telegram"] = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN)

        if settings.EMAIL_ENABLED and settings.SMTP_HOST:
            from cyberfeed.notifiers.email import EmailNotifier

            self._notifiers["email"] = EmailNotifier(
                smtp_host=settings.SMTP_HOST,
                smtp_port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                from_addr=settings.SMTP_FROM,
                use_tls=settings.SMTP_USE_TLS,
            )

    def available_channels(self) -> list[str]:
        return list(self._notifiers.keys())

    def get_notifier(self, channel: str) -> AbstractNotifier | None:
        return self._notifiers.get(channel)

    # ---- Rule CRUD ----

    async def get_rules_for_user(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[NotificationRule]:
        result = await db.execute(
            select(NotificationRule)
            .where(NotificationRule.user_id == user_id)
            .order_by(NotificationRule.created_at)
        )
        return list(result.scalars().all())

    async def get_rule(
        self, db: AsyncSession, rule_id: uuid.UUID, user_id: uuid.UUID
    ) -> NotificationRule | None:
        result = await db.execute(
            select(NotificationRule).where(
                NotificationRule.id == rule_id,
                NotificationRule.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_rule(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        channel: str,
        destination: str,
        keywords: list[str] | None = None,
        category_ids: list[uuid.UUID] | None = None,
        source_platforms: list[str] | None = None,
        is_active: bool = True,
    ) -> NotificationRule:
        rule = NotificationRule(
            user_id=user_id,
            channel=channel,
            destination=destination,
            keywords=keywords or [],
            category_ids=[str(c) for c in (category_ids or [])],
            source_platforms=source_platforms or [],
            is_active=is_active,
        )
        db.add(rule)
        await db.flush()
        return rule

    async def update_rule(
        self, db: AsyncSession, rule: NotificationRule, **kwargs
    ) -> NotificationRule:
        for key, value in kwargs.items():
            if key == "category_ids" and value is not None:
                value = [str(c) for c in value]
            setattr(rule, key, value)
        await db.flush()
        return rule

    async def delete_rule(self, db: AsyncSession, rule_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        rule = await self.get_rule(db, rule_id, user_id)
        if not rule:
            return False
        await db.delete(rule)
        await db.flush()
        return True

    # ---- Matching & Dispatch ----

    def _matches_rule(self, article: Article, rule: NotificationRule) -> bool:
        """Check if an article matches a notification rule."""
        # Platform filter
        if rule.source_platforms and article.source_platform not in rule.source_platforms:
            return False

        # Category filter
        if rule.category_ids:
            if not article.category_id:
                return False
            if str(article.category_id) not in rule.category_ids:
                return False

        # Keyword filter (any keyword in title or content)
        if rule.keywords:
            text = f"{article.title or ''} {article.content or ''}".lower()
            if not any(kw.lower() in text for kw in rule.keywords):
                return False

        return True

    def _build_payload(self, article: Article) -> NotificationPayload:
        """Build notification payload from an article."""
        body = article.summary or (article.content or "")[:500]
        return NotificationPayload(
            subject=f"New article: {article.title or 'Untitled'}",
            body=body,
            article_url=article.url,
            article_title=article.title,
        )

    async def dispatch_for_articles(self, db: AsyncSession, articles: list[Article]) -> int:
        """Match articles against all active rules and send notifications.

        Returns total notifications sent.
        """
        # Get all active rules
        result = await db.execute(
            select(NotificationRule).where(NotificationRule.is_active.is_(True))
        )
        rules = list(result.scalars().all())
        if not rules:
            return 0

        sent_count = 0
        for article in articles:
            for rule in rules:
                if not self._matches_rule(article, rule):
                    continue

                notifier = self.get_notifier(rule.channel)
                if not notifier:
                    continue

                payload = self._build_payload(article)
                success = await notifier.send(rule.destination, payload)
                if success:
                    sent_count += 1
                    from datetime import UTC, datetime

                    rule.last_sent_at = datetime.now(UTC)

        await db.flush()
        return sent_count

    async def test_notification(self, channel: str, destination: str) -> tuple[bool, str]:
        """Send a test notification."""
        notifier = self.get_notifier(channel)
        if not notifier:
            return False, f"Channel '{channel}' is not enabled"

        is_valid, error = await notifier.validate_recipient(destination)
        if not is_valid:
            return False, error

        payload = NotificationPayload(
            subject="CyberFeed Test Notification",
            body="This is a test notification from CyberFeed. "
            "If you see this, notifications are working!",
        )
        success = await notifier.send(destination, payload)
        if success:
            return True, "Test notification sent successfully"
        return False, "Failed to send test notification"
