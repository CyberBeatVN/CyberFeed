"""Scheduled background jobs for collection, summarization, and notifications."""

from datetime import UTC, datetime, timedelta

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from cyberfeed.config import get_settings
from cyberfeed.database import async_session_factory
from cyberfeed.models.article import Article
from cyberfeed.models.source import Source
from cyberfeed.services.collector_service import CollectorService
from cyberfeed.services.notification_service import NotificationService
from cyberfeed.services.summary_service import SummaryService

logger = structlog.get_logger()

collector_service = CollectorService()
summary_service = SummaryService()
notification_service = NotificationService()


async def collect_all_sources() -> None:
    """Check all active sources and collect those that are due."""
    async with async_session_factory() as db:
        try:
            result = await db.execute(select(Source).where(Source.is_active.is_(True)))
            sources = list(result.scalars().all())

            now = datetime.now(UTC)
            for source in sources:
                # Check if source is due for collection
                if source.last_collected_at:
                    next_collect = source.last_collected_at + timedelta(
                        minutes=source.collect_interval_min
                    )
                    if now < next_collect:
                        continue

                logger.info("Collecting source", name=source.name, platform=source.platform)
                await collector_service.collect_source(db, source)

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Scheduled collection failed")


async def summarize_pending() -> None:
    """Summarize articles that don't have a summary yet."""
    async with async_session_factory() as db:
        try:
            result = await db.execute(
                select(Article)
                .where(Article.summary.is_(None))
                .order_by(Article.collected_at.desc())
                .limit(10)
            )
            articles = list(result.scalars().all())
            if articles:
                processed, failed = await summary_service.summarize_batch(db, articles)
                await db.commit()
                logger.info(
                    "Summarization batch complete",
                    processed=processed,
                    failed=failed,
                )
        except Exception:
            await db.rollback()
            logger.exception("Scheduled summarization failed")


async def dispatch_notifications() -> None:
    """Match new articles against notification rules and send notifications."""
    async with async_session_factory() as db:
        try:
            # Find articles collected in the last 3 minutes (overlap with interval)
            cutoff = datetime.now(UTC) - timedelta(minutes=3)
            result = await db.execute(
                select(Article)
                .where(Article.collected_at >= cutoff)
                .order_by(Article.collected_at.desc())
            )
            articles = list(result.scalars().all())
            if articles:
                sent = await notification_service.dispatch_for_articles(db, articles)
                await db.commit()
                if sent:
                    logger.info("Notifications dispatched", sent=sent)
        except Exception:
            await db.rollback()
            logger.exception("Scheduled notification dispatch failed")


def setup_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    settings = get_settings()
    scheduler = AsyncIOScheduler()

    # Collect sources every 5 minutes (checks individual intervals)
    scheduler.add_job(
        collect_all_sources,
        "interval",
        minutes=5,
        id="collect_all_sources",
        replace_existing=True,
    )

    # Summarize pending articles every 5 minutes (if LLM enabled)
    if settings.LLM_ENABLED:
        scheduler.add_job(
            summarize_pending,
            "interval",
            minutes=5,
            id="summarize_pending",
            replace_existing=True,
        )

    # Dispatch notifications every 2 minutes
    if settings.TELEGRAM_ENABLED or settings.EMAIL_ENABLED:
        scheduler.add_job(
            dispatch_notifications,
            "interval",
            minutes=2,
            id="dispatch_notifications",
            replace_existing=True,
        )

    logger.info(
        "Scheduler configured",
        llm_enabled=settings.LLM_ENABLED,
        notifications_enabled=settings.TELEGRAM_ENABLED or settings.EMAIL_ENABLED,
    )

    return scheduler
