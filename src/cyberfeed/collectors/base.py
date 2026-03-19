"""Abstract base class for all feed collectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CollectedArticle:
    """Normalized article from any collector."""

    title: str
    url: str
    content: str
    source_name: str
    source_platform: str
    published_at: datetime | None = None
    author: str | None = None
    image_url: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class AbstractCollector(ABC):
    """Base class for all feed collectors. Each platform implements this."""

    platform_key: str

    @abstractmethod
    async def collect(self, source_config: dict) -> list[CollectedArticle]:
        """Fetch articles from the source. Must not raise — return empty on error."""

    @abstractmethod
    async def validate_config(self, config: dict) -> tuple[bool, str]:
        """Validate source configuration. Returns (is_valid, error_message)."""

    @abstractmethod
    def get_config_schema(self) -> dict:
        """Return config field definitions for dynamic form rendering."""
