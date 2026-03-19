"""Seed initial RSS sources for testing."""

import asyncio
import json

from cyberfeed.database import async_session_factory, init_database
from cyberfeed.models.source import Source

SEED_SOURCES = [
    {
        "name": "Hacker News",
        "platform": "rss",
        "config": {"url": "https://hnrss.org/frontpage", "max_entries": 30},
    },
    {
        "name": "The Register - Security",
        "platform": "rss",
        "config": {"url": "https://www.theregister.com/security/headlines.atom", "max_entries": 20},
    },
    {
        "name": "Krebs on Security",
        "platform": "rss",
        "config": {"url": "https://krebsonsecurity.com/feed/", "max_entries": 10},
    },
    {
        "name": "BleepingComputer",
        "platform": "rss",
        "config": {"url": "https://www.bleepingcomputer.com/feed/", "max_entries": 20},
    },
    {
        "name": "TechCrunch",
        "platform": "rss",
        "config": {"url": "https://techcrunch.com/feed/", "max_entries": 20},
    },
]


async def main():
    await init_database()

    async with async_session_factory() as db:
        for source_data in SEED_SOURCES:
            source = Source(
                name=source_data["name"],
                platform=source_data["platform"],
                config_json=json.dumps(source_data["config"]),
                collect_interval_min=30,
            )
            db.add(source)
            print(f"  Added: {source_data['name']}")

        await db.commit()
        print(f"\nSeeded {len(SEED_SOURCES)} sources.")


if __name__ == "__main__":
    asyncio.run(main())
