"""Source CRUD with config encryption."""

import json
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.collectors.registry import CollectorRegistry
from cyberfeed.core.security import decrypt_value, encrypt_value
from cyberfeed.models.source import Source

logger = structlog.get_logger()


class SourceService:
    def _encrypt_sensitive_fields(self, platform: str, config: dict) -> dict:
        """Encrypt fields marked as 'encrypted' in the collector's config schema."""
        try:
            collector = CollectorRegistry.get(platform)
            schema = collector.get_config_schema()
        except KeyError:
            return config

        encrypted_config = config.copy()
        for key, field_def in schema.items():
            if field_def.get("encrypted") and key in encrypted_config and encrypted_config[key]:
                encrypted_config[key] = encrypt_value(encrypted_config[key])
        return encrypted_config

    def _decrypt_sensitive_fields(self, platform: str, config: dict) -> dict:
        """Decrypt fields marked as 'encrypted' in the collector's config schema."""
        try:
            collector = CollectorRegistry.get(platform)
            schema = collector.get_config_schema()
        except KeyError:
            return config

        decrypted_config = config.copy()
        for key, field_def in schema.items():
            if field_def.get("encrypted") and key in decrypted_config and decrypted_config[key]:
                try:
                    decrypted_config[key] = decrypt_value(decrypted_config[key])
                except Exception:
                    logger.warning("Failed to decrypt field", field=key)
        return decrypted_config

    def _mask_sensitive_fields(self, platform: str, config: dict) -> dict:
        """Replace encrypted field values with '***' for API responses."""
        try:
            collector = CollectorRegistry.get(platform)
            schema = collector.get_config_schema()
        except KeyError:
            return config

        masked = config.copy()
        for key, field_def in schema.items():
            if field_def.get("encrypted") and key in masked and masked[key]:
                masked[key] = "***"
        return masked

    async def check_duplicate_url(self, db: AsyncSession, platform: str, url: str) -> bool:
        """Check if a source with the same platform and URL already exists."""
        if not url:
            return False
        result = await db.execute(select(Source).where(Source.platform == platform))
        for src in result.scalars().all():
            existing_config = json.loads(src.config_json) if src.config_json else {}
            if existing_config.get("url") == url:
                return True
        return False

    async def probe_url(self, url: str) -> dict:
        """Probe a URL to check reachability and detect feed type."""
        import re

        import httpx

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"
                        )
                    },
                )
                resp.raise_for_status()
        except Exception as e:
            return {"reachable": False, "is_rss": False, "error": str(e), "title": None}

        content_type = resp.headers.get("content-type", "")
        body = resp.text[:5000]

        is_rss = (
            "application/rss" in content_type
            or "application/atom" in content_type
            or "application/xml" in content_type
            or "text/xml" in content_type
            or body.lstrip().startswith("<?xml")
            or "<rss" in body[:500]
            or "<feed" in body[:500]
        )

        title = None
        if not is_rss:
            match = re.search(r"<title[^>]*>([^<]+)</title>", body, re.IGNORECASE)
            if match:
                title = match.group(1).strip()

        return {"reachable": True, "is_rss": is_rss, "error": None, "title": title}

    async def create(
        self,
        db: AsyncSession,
        name: str,
        platform: str,
        config: dict,
        collect_interval_min: int = 30,
    ) -> Source | None:
        # Check for duplicate URL
        url = config.get("url", "")
        if url and await self.check_duplicate_url(db, platform, url):
            return None

        encrypted_config = self._encrypt_sensitive_fields(platform, config)
        source = Source(
            name=name,
            platform=platform,
            config_json=json.dumps(encrypted_config),
            collect_interval_min=max(5, min(collect_interval_min, 1440)),
        )
        db.add(source)
        await db.flush()
        return source

    async def get_all(
        self, db: AsyncSession, platform: str | None = None, is_active: bool | None = None
    ) -> list[Source]:
        query = select(Source)
        if platform:
            query = query.where(Source.platform == platform)
        if is_active is not None:
            query = query.where(Source.is_active == is_active)
        result = await db.execute(query.order_by(Source.created_at.desc()))
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, source_id: uuid.UUID) -> Source | None:
        result = await db.execute(select(Source).where(Source.id == source_id))
        return result.scalar_one_or_none()

    async def get_active_sources(self, db: AsyncSession) -> list[Source]:
        return await self.get_all(db, is_active=True)

    def get_decrypted_config(self, source: Source) -> dict:
        """Get source config with sensitive fields decrypted."""
        config = json.loads(source.config_json) if source.config_json else {}
        return self._decrypt_sensitive_fields(source.platform, config)

    def get_masked_config(self, source: Source) -> dict:
        """Get source config with sensitive fields masked for API display."""
        config = json.loads(source.config_json) if source.config_json else {}
        return self._mask_sensitive_fields(source.platform, config)

    async def update(self, db: AsyncSession, source: Source, **kwargs: dict) -> Source:
        if kwargs.get("config"):
            encrypted = self._encrypt_sensitive_fields(source.platform, kwargs.pop("config"))
            source.config_json = json.dumps(encrypted)
        for key, value in kwargs.items():
            if hasattr(source, key) and value is not None:
                setattr(source, key, value)
        await db.flush()
        return source

    async def delete(self, db: AsyncSession, source_id: uuid.UUID) -> bool:
        source = await self.get_by_id(db, source_id)
        if source:
            await db.delete(source)
            return True
        return False
