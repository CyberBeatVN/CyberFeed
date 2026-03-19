"""Orchestrates feed collection: fetches from collectors and stores articles."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.collectors.registry import CollectorRegistry
from cyberfeed.models.source import Source
from cyberfeed.services.article_service import ArticleService
from cyberfeed.services.source_service import SourceService

logger = structlog.get_logger()

article_service = ArticleService()
source_service = SourceService()


@dataclass
class CollectResult:
    new_count: int = 0
    duplicate_count: int = 0
    errors: list[str] = field(default_factory=list)


class CollectorService:
    async def collect_source(self, db: AsyncSession, source: Source) -> CollectResult:
        """Collect articles from a single source."""
        result = CollectResult()

        try:
            collector = CollectorRegistry.get(source.platform)
        except KeyError:
            msg = f"Unknown platform: {source.platform}"
            result.errors.append(msg)
            logger.error(msg, source_id=str(source.id))
            return result

        config = source_service.get_decrypted_config(source)

        # Add source_name to config if not set
        if "source_name" not in config or not config["source_name"]:
            config["source_name"] = source.name

        try:
            collected_articles = await collector.collect(config)
        except Exception as e:
            msg = f"Collection failed: {e}"
            result.errors.append(msg)
            source.error_count += 1
            source.last_error = msg
            logger.exception("Collection failed", source_id=str(source.id))
            return result

        # Get default category from source's linked categories
        category_id = None
        if source.categories:
            category_id = source.categories[0].id

        for collected in collected_articles:
            if not collected.url:
                continue
            try:
                article = await article_service.create_from_collected(
                    db, collected, source_id=source.id, category_id=category_id
                )
                if article:
                    result.new_count += 1
                else:
                    result.duplicate_count += 1
            except Exception as e:
                result.errors.append(f"Store error: {e}")
                logger.exception("Article store error", url=collected.url)

        # Update source status
        source.last_collected_at = datetime.now(UTC)
        if not result.errors:
            source.error_count = 0
            source.last_error = None
        else:
            source.error_count += 1
            source.last_error = "; ".join(result.errors[:3])

        # Auto-disable after 5 consecutive errors
        if source.error_count >= 5:
            source.is_active = False
            logger.warning(
                "Source auto-disabled after 5 consecutive errors",
                source_id=str(source.id),
                name=source.name,
            )

        logger.info(
            "Collection complete",
            source=source.name,
            new=result.new_count,
            duplicates=result.duplicate_count,
            errors=len(result.errors),
        )
        return result
