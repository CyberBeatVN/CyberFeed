"""Collector registry for plugin discovery and management."""

from typing import ClassVar

from cyberfeed.collectors.base import AbstractCollector


class CollectorRegistry:
    """Central registry for collector plugins."""

    _collectors: ClassVar[dict[str, type[AbstractCollector]]] = {}

    @classmethod
    def register(cls, collector_class: type[AbstractCollector]) -> type[AbstractCollector]:
        """Register a collector class. Can be used as decorator."""
        cls._collectors[collector_class.platform_key] = collector_class
        return collector_class

    @classmethod
    def get(cls, platform_key: str) -> AbstractCollector:
        """Get a collector instance by platform key."""
        if platform_key not in cls._collectors:
            raise KeyError(f"Unknown collector platform: {platform_key}")
        return cls._collectors[platform_key]()

    @classmethod
    def available_platforms(cls) -> list[dict]:
        """List available platforms with their config schemas."""
        return [
            {
                "key": key,
                "config_schema": cls._collectors[key]().get_config_schema(),
            }
            for key in sorted(cls._collectors)
        ]


def register_all_collectors() -> None:
    """Import all collector modules to trigger registration."""
    import cyberfeed.collectors.newspaper
    import cyberfeed.collectors.rss
    import cyberfeed.collectors.x_com  # noqa: F401
