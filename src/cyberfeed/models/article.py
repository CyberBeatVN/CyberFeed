"""Article, Category, Tag models and junction tables."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyberfeed.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cyberfeed.models.source import Source

# M2M junction: Article <-> Tag
article_tags = Table(
    "article_tags",
    Base.metadata,
    Column("article_id", ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Category(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    color: Mapped[str | None] = mapped_column(String(7))
    icon: Mapped[str | None] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    articles: Mapped[list[Article]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<Category {self.name}>"


class Tag(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    articles: Mapped[list[Article]] = relationship(secondary=article_tags, back_populates="tags")

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


class Article(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "articles"

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_method: Mapped[str | None] = mapped_column(String(20))
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    author: Mapped[str | None] = mapped_column(String(200))
    image_url: Mapped[str | None] = mapped_column(String(2048))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bookmarked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    # Relationships
    source: Mapped[Source | None] = relationship(back_populates="articles")
    category: Mapped[Category | None] = relationship(back_populates="articles")
    tags: Mapped[list[Tag]] = relationship(secondary=article_tags, back_populates="articles")

    def __repr__(self) -> str:
        return f"<Article {self.title[:50]}>"
