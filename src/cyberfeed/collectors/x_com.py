"""X.com (Twitter) collector — supports RSS bridge and official API v2."""

import asyncio
from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from cyberfeed.collectors.base import AbstractCollector, CollectedArticle
from cyberfeed.collectors.registry import CollectorRegistry

logger = structlog.get_logger()


@CollectorRegistry.register
class XComCollector(AbstractCollector):
    platform_key = "x.com"

    async def collect(self, source_config: dict) -> list[CollectedArticle]:
        method = source_config.get("method", "rss_bridge")
        if method == "rss_bridge":
            return await self._collect_via_rss(source_config)
        elif method == "api":
            return await self._collect_via_api(source_config)
        else:
            logger.error("Unknown X.com collection method", method=method)
            return []

    async def _collect_via_rss(self, config: dict) -> list[CollectedArticle]:
        """Collect via RSSHub or similar RSS bridge service."""
        rsshub_url = config.get("rsshub_url", "")
        max_entries = config.get("max_entries", 50)
        source_name = config.get("source_name", "X.com")

        if not rsshub_url:
            logger.error("X.com RSS bridge: rsshub_url not configured")
            return []

        try:
            feed = await asyncio.to_thread(feedparser.parse, rsshub_url)
        except Exception:
            logger.exception("X.com RSS bridge fetch failed", url=rsshub_url)
            return []

        articles = []
        for entry in feed.entries[:max_entries]:
            try:
                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_at = datetime(*entry.published_parsed[:6], tzinfo=UTC)

                articles.append(
                    CollectedArticle(
                        title=entry.get("title", "")[:500],
                        url=entry.get("link", ""),
                        content=entry.get("summary", ""),
                        source_name=source_name,
                        source_platform="x.com",
                        published_at=published_at,
                        author=entry.get("author"),
                        tags=[],
                        metadata={"method": "rss_bridge", "rsshub_url": rsshub_url},
                    )
                )
            except Exception:
                logger.exception("X.com RSS entry parse error")
                continue

        logger.info("X.com RSS bridge collected", url=rsshub_url, count=len(articles))
        return articles

    async def _collect_via_api(self, config: dict) -> list[CollectedArticle]:
        """Collect via X API v2 (requires Bearer token)."""
        bearer_token = config.get("bearer_token", "")
        query = config.get("query", "")
        max_results = min(config.get("max_results", 100), 100)
        source_name = config.get("source_name", "X.com")

        if not bearer_token or not query:
            logger.error("X.com API: bearer_token and query are required")
            return []

        headers = {"Authorization": f"Bearer {bearer_token}"}
        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "created_at,author_id,text",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    "https://api.twitter.com/2/tweets/search/recent",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("X.com API error", status=e.response.status_code)
            return []
        except Exception:
            logger.exception("X.com API request failed")
            return []

        articles = []
        for tweet in data.get("data", []):
            try:
                created_at = None
                if tweet.get("created_at"):
                    created_at = datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00"))

                articles.append(
                    CollectedArticle(
                        title=tweet.get("text", "")[:200],
                        url=f"https://x.com/i/status/{tweet['id']}",
                        content=tweet.get("text", ""),
                        source_name=source_name,
                        source_platform="x.com",
                        published_at=created_at,
                        author=tweet.get("author_id"),
                        tags=[],
                        metadata={"method": "api", "tweet_id": tweet["id"]},
                    )
                )
            except Exception:
                logger.exception("X.com API tweet parse error")
                continue

        logger.info("X.com API collected", query=query, count=len(articles))
        return articles

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        method = config.get("method", "")
        if method not in ("rss_bridge", "api"):
            return False, "Method must be 'rss_bridge' or 'api'"

        if method == "rss_bridge":
            url = config.get("rsshub_url", "")
            if not url:
                return False, "RSSHub URL is required for rss_bridge method"
            if not url.startswith(("http://", "https://")):
                return False, "URL must start with http:// or https://"
        elif method == "api":
            if not config.get("bearer_token"):
                return False, "Bearer token is required for API method"
            if not config.get("query"):
                return False, "Search query is required for API method"

        return True, ""

    def get_config_schema(self) -> dict:
        return {
            "method": {
                "type": "select",
                "required": True,
                "options": ["rss_bridge", "api"],
                "label": "Collection method",
            },
            "rsshub_url": {
                "type": "string",
                "required": False,
                "label": "RSSHub URL (for rss_bridge method)",
            },
            "bearer_token": {
                "type": "password",
                "required": False,
                "label": "X API Bearer Token (for api method)",
                "encrypted": True,
            },
            "query": {
                "type": "string",
                "required": False,
                "label": "Search query (for api method)",
            },
            "max_entries": {
                "type": "integer",
                "required": False,
                "default": 50,
                "label": "Max entries per fetch",
            },
            "source_name": {
                "type": "string",
                "required": False,
                "default": "X.com",
                "label": "Display name",
            },
        }
