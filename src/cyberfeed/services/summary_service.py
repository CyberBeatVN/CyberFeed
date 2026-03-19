"""Summary service: orchestrates LLM + extractive fallback with circuit breaker."""

import time

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.config import get_settings
from cyberfeed.models.article import Article
from cyberfeed.summarizer.base import SummaryResult
from cyberfeed.summarizer.extractive import ExtractiveSummarizer

logger = structlog.get_logger()


class SummaryService:
    """Summarization orchestrator with LLM circuit breaker."""

    def __init__(self):
        settings = get_settings()
        self._llm_enabled = settings.LLM_ENABLED
        self._fallback = ExtractiveSummarizer()
        self._primary = None

        # Circuit breaker state
        self._failure_count = 0
        self._max_failures = 5
        self._cooldown_seconds = 600  # 10 minutes
        self._circuit_open_until = 0.0

        if self._llm_enabled:
            from cyberfeed.summarizer.litellm_impl import LiteLLMSummarizer

            self._primary = LiteLLMSummarizer(
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                api_base=settings.LLM_API_BASE or None,
                timeout=settings.LLM_TIMEOUT,
                max_tokens=settings.LLM_MAX_TOKENS,
            )

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open (LLM calls blocked)."""
        if self._failure_count < self._max_failures:
            return False
        if time.monotonic() > self._circuit_open_until:
            # Cooldown expired, reset
            self._failure_count = 0
            return False
        return True

    def _record_failure(self):
        """Record an LLM failure for circuit breaker."""
        self._failure_count += 1
        if self._failure_count >= self._max_failures:
            self._circuit_open_until = time.monotonic() + self._cooldown_seconds

    def _record_success(self):
        """Reset circuit breaker on success."""
        self._failure_count = 0

    async def summarize(
        self, db: AsyncSession, article: Article, *, force: bool = False
    ) -> Article:
        """Summarize an article. Updates article in-place."""
        if article.summary and not force:
            return article

        text = article.content or article.title or ""
        if not text.strip():
            return article

        result: SummaryResult | None = None

        # Try LLM if enabled and circuit is closed
        if self._primary and not self._is_circuit_open():
            try:
                result = await self._primary.summarize(text)
                self._record_success()
            except Exception:
                self._record_failure()
                await logger.awarning(
                    "LLM summarization failed, using fallback",
                    failures=self._failure_count,
                    circuit_open=self._is_circuit_open(),
                )

        # Fallback to extractive
        if result is None:
            result = await self._fallback.summarize(text)

        article.summary = result.summary
        article.summary_method = result.method
        await db.flush()

        return article

    async def summarize_batch(self, db: AsyncSession, articles: list[Article]) -> tuple[int, int]:
        """Summarize a batch of articles. Returns (processed, failed)."""
        processed = 0
        failed = 0
        for article in articles:
            try:
                await self.summarize(db, article, force=False)
                processed += 1
            except Exception:
                failed += 1
                await logger.awarning("Batch summarization failed", article_id=str(article.id))
        return processed, failed
