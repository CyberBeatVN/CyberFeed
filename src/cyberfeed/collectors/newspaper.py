"""Newspaper article extractor using newspaper4k."""

import asyncio

import structlog

from cyberfeed.collectors.base import AbstractCollector, CollectedArticle
from cyberfeed.collectors.registry import CollectorRegistry

logger = structlog.get_logger()


@CollectorRegistry.register
class NewspaperCollector(AbstractCollector):
    platform_key = "newspaper"

    async def collect(self, source_config: dict) -> list[CollectedArticle]:
        url = source_config["url"]
        max_articles = source_config.get("max_articles", 10)
        language = source_config.get("language", "en")
        source_name = source_config.get("source_name", url)

        try:
            articles = await asyncio.wait_for(
                asyncio.to_thread(
                    self._collect_sync, url, max_articles, language, source_name
                ),
                timeout=60,
            )
        except TimeoutError:
            logger.error("Newspaper collection timed out after 60s", url=url)
            return []
        except Exception:
            logger.exception("Newspaper collection failed", url=url)
            return []

        logger.info("Newspaper collected", url=url, count=len(articles))
        return articles

    def _collect_sync(
        self, url: str, max_articles: int, language: str, source_name: str
    ) -> list[CollectedArticle]:
        from newspaper import Config, build

        config = Config()
        config.browser_user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        config.request_timeout = 15
        config.language = language
        config.fetch_images = False
        config.memoize_articles = False

        paper = build(url, config=config)

        discovered = len(paper.articles)
        logger.debug("Newspaper discovered articles", url=url, count=discovered)
        if discovered == 0:
            logger.warning(
                "Newspaper found 0 articles — site may block scraping",
                url=url,
            )

        articles = []

        for newspaper_article in paper.articles[:max_articles]:
            try:
                newspaper_article.download()
                newspaper_article.parse()

                if not newspaper_article.title or not newspaper_article.url:
                    continue

                articles.append(
                    CollectedArticle(
                        title=newspaper_article.title,
                        url=newspaper_article.url,
                        content=newspaper_article.text or "",
                        source_name=source_name,
                        source_platform="newspaper",
                        published_at=newspaper_article.publish_date,
                        author=", ".join(newspaper_article.authors) or None,
                        image_url=newspaper_article.top_image or None,
                        description=getattr(newspaper_article, "meta_description", None) or None,
                        tags=list(newspaper_article.keywords or []),
                        metadata={"source_url": url},
                    )
                )
            except Exception:
                logger.exception("Newspaper article parse error", article_url=newspaper_article.url)
                continue

        return articles

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        url = config.get("url", "")
        if not url:
            return False, "Newspaper site URL is required"
        if not url.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"
        return True, ""

    def get_config_schema(self) -> dict:
        return {
            "url": {"type": "string", "required": True, "label": "Newspaper site URL"},
            "max_articles": {
                "type": "integer",
                "required": False,
                "default": 10,
                "label": "Max articles per fetch",
            },
            "language": {
                "type": "string",
                "required": False,
                "default": "en",
                "label": "Language code",
            },
            "source_name": {
                "type": "string",
                "required": False,
                "label": "Display name",
            },
        }
