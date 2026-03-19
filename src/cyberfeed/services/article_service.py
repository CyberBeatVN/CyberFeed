"""Article CRUD, search, deduplication, and pagination."""

import hashlib
import uuid
from datetime import datetime

import nh3
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cyberfeed.collectors.base import CollectedArticle
from cyberfeed.models.article import Article, Category, Tag, article_tags

logger = structlog.get_logger()

# Allowed HTML tags for sanitized content
_ALLOWED_TAGS = {
    "p",
    "br",
    "a",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "code",
    "pre",
    "img",
}
_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href"},
    "img": {"src", "alt"},
}


def _content_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _sanitize(html: str) -> str:
    return nh3.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES)


class ArticleService:
    async def create_from_collected(
        self,
        db: AsyncSession,
        collected: CollectedArticle,
        source_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
    ) -> Article | None:
        """Create article from collected data. Returns None if duplicate."""
        content_hash = _content_hash(collected.url)

        # Dedup check
        existing = await db.execute(select(Article.id).where(Article.content_hash == content_hash))
        if existing.scalar_one_or_none():
            return None

        # Sanitize content
        sanitized_content = _sanitize(collected.content) if collected.content else ""

        # Sanitize description if provided
        sanitized_description = _sanitize(collected.description) if collected.description else None

        article = Article(
            source_id=source_id,
            category_id=category_id,
            title=collected.title[:500],
            url=collected.url[:2048],
            content=sanitized_content,
            summary=sanitized_description,
            summary_method="source" if sanitized_description else None,
            source_name=collected.source_name[:200],
            source_platform=collected.source_platform[:50],
            author=collected.author[:200] if collected.author else None,
            image_url=collected.image_url[:2048] if collected.image_url else None,
            published_at=collected.published_at,
            content_hash=content_hash,
            metadata_json=collected.metadata,
        )
        db.add(article)
        await db.flush()

        # Create/link tags
        if collected.tags:
            await self._link_tags(db, article, collected.tags[:20])

        return article

    async def _link_tags(self, db: AsyncSession, article: Article, tag_names: list[str]) -> None:
        for name in tag_names:
            name = name.lower().strip()[:100]
            if not name:
                continue

            result = await db.execute(select(Tag).where(Tag.name == name))
            tag = result.scalar_one_or_none()
            if not tag:
                tag = Tag(name=name)
                db.add(tag)
                await db.flush()
            article.tags.append(tag)

    async def search(
        self,
        db: AsyncSession,
        *,
        q: str | None = None,
        platform: str | None = None,
        source_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        tag_name: str | None = None,
        is_read: bool | None = None,
        is_bookmarked: bool | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        per_page: int = 20,
        sort: str = "collected_at",
    ) -> tuple[list[Article], int]:
        """Search articles with filters. Returns (articles, total_count)."""
        query = select(Article).options(
            selectinload(Article.tags),
            selectinload(Article.category),
        )
        count_query = select(func.count(Article.id))

        # Apply filters
        if q:
            pattern = f"%{q}%"
            query = query.where(Article.title.ilike(pattern) | Article.content.ilike(pattern))
            count_query = count_query.where(
                Article.title.ilike(pattern) | Article.content.ilike(pattern)
            )
        if platform:
            query = query.where(Article.source_platform == platform)
            count_query = count_query.where(Article.source_platform == platform)
        if source_id:
            query = query.where(Article.source_id == source_id)
            count_query = count_query.where(Article.source_id == source_id)
        if category_slug:
            query = query.join(Category).where(Category.slug == category_slug)
            count_query = count_query.join(Category).where(Category.slug == category_slug)
        if tag_name:
            query = query.join(article_tags).join(Tag).where(Tag.name == tag_name.lower())
            count_query = (
                count_query.join(article_tags).join(Tag).where(Tag.name == tag_name.lower())
            )
        if is_read is not None:
            query = query.where(Article.is_read == is_read)
            count_query = count_query.where(Article.is_read == is_read)
        if is_bookmarked is not None:
            query = query.where(Article.is_bookmarked == is_bookmarked)
            count_query = count_query.where(Article.is_bookmarked == is_bookmarked)
        if from_date:
            query = query.where(Article.collected_at >= from_date)
            count_query = count_query.where(Article.collected_at >= from_date)
        if to_date:
            query = query.where(Article.collected_at <= to_date)
            count_query = count_query.where(Article.collected_at <= to_date)

        # Sort
        sort_column = getattr(Article, sort, Article.collected_at)
        query = query.order_by(sort_column.desc())

        # Paginate
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        result = await db.execute(query)
        articles = list(result.scalars().all())

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        return articles, total

    async def get_by_id(self, db: AsyncSession, article_id: uuid.UUID) -> Article | None:
        result = await db.execute(
            select(Article)
            .where(Article.id == article_id)
            .options(selectinload(Article.tags), selectinload(Article.category))
        )
        return result.scalar_one_or_none()

    async def toggle_bookmark(self, db: AsyncSession, article_id: uuid.UUID) -> Article | None:
        article = await self.get_by_id(db, article_id)
        if article:
            article.is_bookmarked = not article.is_bookmarked
            await db.flush()
        return article

    async def toggle_read(self, db: AsyncSession, article_id: uuid.UUID) -> Article | None:
        article = await self.get_by_id(db, article_id)
        if article:
            article.is_read = not article.is_read
            await db.flush()
        return article

    async def delete(self, db: AsyncSession, article_id: uuid.UUID) -> bool:
        article = await self.get_by_id(db, article_id)
        if article:
            await db.delete(article)
            return True
        return False
