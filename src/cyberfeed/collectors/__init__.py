"""Feed collector modules."""

from cyberfeed.collectors.base import AbstractCollector, CollectedArticle
from cyberfeed.collectors.registry import CollectorRegistry

__all__ = ["AbstractCollector", "CollectedArticle", "CollectorRegistry"]
