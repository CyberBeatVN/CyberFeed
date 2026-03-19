"""Source model for feed collector configurations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyberfeed.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cyberfeed.models.article import Article, Category

# M2M junction: Source <-> Category
source_categories = Table(
    "source_categories",
    Base.metadata,
    Column("source_id", ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Source(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    config_json: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    collect_interval_min: Mapped[int] = mapped_column(Integer, default=30)
    last_collected_at: Mapped[str | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    articles: Mapped[list[Article]] = relationship(back_populates="source")
    categories: Mapped[list[Category]] = relationship(secondary=source_categories)

    def __repr__(self) -> str:
        return f"<Source {self.name} ({self.platform})>"
