"""Summarizer interface and result dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SummaryResult:
    """Result of a summarization operation."""

    summary: str
    method: str  # "litellm", "extractive"
    model: str | None = None  # e.g. "gpt-4o-mini", None for extractive
    tokens_used: int = 0  # 0 for extractive
    suggested_tags: list[str] = field(default_factory=list)


class AbstractSummarizer(ABC):
    """Base class for all summarizers."""

    @abstractmethod
    async def summarize(self, text: str, max_length: int = 200) -> SummaryResult:
        """Summarize the given text. Returns SummaryResult."""
