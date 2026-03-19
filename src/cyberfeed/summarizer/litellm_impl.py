"""LiteLLM summarizer: calls LLM API for summarization."""

import json

import structlog

from cyberfeed.core.exceptions import SummarizerError
from cyberfeed.summarizer.base import AbstractSummarizer, SummaryResult

logger = structlog.get_logger()


class LiteLLMSummarizer(AbstractSummarizer):
    """Summarizer using LiteLLM for unified LLM access."""

    def __init__(
        self,
        model: str,
        api_key: str,
        api_base: str | None = None,
        timeout: int = 30,
        max_tokens: int = 300,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base or None
        self.timeout = timeout
        self.max_tokens = max_tokens

    async def summarize(self, text: str, max_length: int = 200) -> SummaryResult:
        """Summarize text using LiteLLM acompletion."""
        try:
            import litellm

            # Truncate input to avoid context window issues
            truncated = text[:4000] if len(text) > 4000 else text

            prompt = (
                f"Summarize the following article in {max_length} words or less. "
                "Focus on key facts and findings. Be concise and objective. "
                "Also suggest up to 5 relevant tags as lowercase keywords.\n\n"
                f"Article:\n{truncated}\n\n"
                'Respond in JSON: {"summary": "...", "suggested_tags": ["tag1", "tag2"]}'
            )

            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                api_base=self.api_base,
                timeout=self.timeout,
                max_tokens=self.max_tokens,
                temperature=0.3,
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0

            # Parse JSON response
            try:
                data = json.loads(content)
                summary = data.get("summary", content)
                suggested_tags = data.get("suggested_tags", [])
            except json.JSONDecodeError:
                summary = content
                suggested_tags = []

            return SummaryResult(
                summary=summary,
                method="litellm",
                model=self.model,
                tokens_used=tokens_used,
                suggested_tags=suggested_tags[:5],
            )

        except Exception as e:
            await logger.awarning("LiteLLM summarization failed", error=str(e))
            raise SummarizerError(f"LLM summarization failed: {e}") from e
