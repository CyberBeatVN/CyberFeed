"""Async database engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from cyberfeed.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_database() -> None:
    """Create all tables if they don't exist, seed defaults."""
    from cyberfeed.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default categories if none exist
    await _seed_default_categories()


async def _seed_default_categories() -> None:
    from sqlalchemy import func, select

    from cyberfeed.models.article import Category

    async with async_session_factory() as session:
        result = await session.execute(select(func.count(Category.id)))
        if result.scalar():
            return  # Categories already exist

        defaults = [
            Category(
                name="Security",
                slug="security",
                color="#ef4444",
                sort_order=0,
            ),
            Category(
                name="Technology",
                slug="technology",
                color="#3b82f6",
                sort_order=1,
            ),
            Category(
                name="General",
                slug="general",
                color="#6b7280",
                sort_order=2,
            ),
        ]
        session.add_all(defaults)
        await session.commit()
