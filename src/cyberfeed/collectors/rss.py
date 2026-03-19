"""RSS/Atom feed collector using feedparser."""

import asyncio
from datetime import UTC, datetime

import feedparser
import structlog

from cyberfeed.collectors.base import AbstractCollector, CollectedArticle
from cyberfeed.collectors.registry import CollectorRegistry

logger = structlog.get_logger()


@CollectorRegistry.register
class RSSCollector(AbstractCollector):
    platform_key = "rss"

    async def collect(self, source_config: dict) -> list[CollectedArticle]:
        url = source_config["url"]
        max_entries = source_config.get("max_entries", 50)
        source_name = source_config.get("source_name", url)

        try:
            # feedparser is synchronous — run in thread
            feed = await asyncio.to_thread(feedparser.parse, url)
        except Exception:
            logger.exception("RSS fetch failed", url=url)
            return []

        if feed.bozo and not feed.entries:
            logger.warning("RSS parse error", url=url, error=str(feed.bozo_exception))
            return []

        articles = []
        for entry in feed.entries[:max_entries]:
            try:
                # Description = entry.summary (short excerpt)
                description = ""
                if hasattr(entry, "summary"):
                    description = entry.summary or ""

                # Content = full article body, fallback to summary
                content = ""
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", "")
                elif description:
                    content = description

                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_at = datetime(*entry.published_parsed[:6], tzinfo=UTC)

                tags = []
                if hasattr(entry, "tags"):
                    tags = [t.get("term", "") for t in entry.tags if t.get("term")]

                articles.append(
                    CollectedArticle(
                        title=entry.get("title", "Untitled"),
                        url=entry.get("link", ""),
                        content=content,
                        source_name=source_name,
                        source_platform="rss",
                        published_at=published_at,
                        author=entry.get("author"),
                        image_url=_extract_image(entry),
                        description=description if description and description != content else None,
                        tags=tags,
                        metadata={"feed_url": url},
                    )
                )
            except Exception:
                logger.exception("RSS entry parse error", url=url)
                continue

        logger.info("RSS collected", url=url, count=len(articles))
        return articles

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        url = config.get("url", "")
        if not url:
            return False, "Feed URL is required"
        if not url.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"
        return True, ""

    def get_config_schema(self) -> dict:
        return {
            "url": {"type": "string", "required": True, "label": "Feed URL"},
            "max_entries": {
                "type": "integer",
                "required": False,
                "default": 50,
                "label": "Max entries per fetch",
            },
            "source_name": {
                "type": "string",
                "required": False,
                "label": "Display name (auto-detected if empty)",
            },
        }


def _extract_image(entry) -> str | None:
    """Try to extract an image URL from an RSS entry."""
    # Check media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    # Check media:content
    if hasattr(entry, "media_content") and entry.media_content:
        for media in entry.media_content:
            if media.get("medium") == "image" or media.get("type", "").startswith("image/"):
                return media.get("url")
    # Check enclosures
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image/"):
                return enc.get("href")
    return None
