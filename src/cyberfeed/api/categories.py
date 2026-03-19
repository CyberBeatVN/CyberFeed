"""Categories API: CRUD with article counts."""

import re
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.api.deps import get_current_user, get_db, require_role
from cyberfeed.core.exceptions import NotFoundError, ValidationError
from cyberfeed.models.article import Article, Category
from cyberfeed.models.user import User
from cyberfeed.schemas.category import CategoryCreate, CategoryReadWithCount, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


@router.get("")
async def list_categories(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(
            Category,
            func.count(Article.id).label("article_count"),
        )
        .outerjoin(Article, Article.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.sort_order, Category.name)
    )
    categories = []
    for row in result.all():
        cat = row[0]
        count = row[1]
        cat_data = CategoryReadWithCount.model_validate(cat)
        cat_data.article_count = count
        categories.append(cat_data)
    return {"categories": categories}


@router.post("")
async def create_category(
    body: CategoryCreate,
    _user: User = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
) -> CategoryReadWithCount:
    slug = _slugify(body.name)
    existing = await db.execute(select(Category).where(Category.slug == slug))
    if existing.scalar_one_or_none():
        raise ValidationError(f"Category with slug '{slug}' already exists")

    category = Category(
        name=body.name,
        slug=slug,
        description=body.description,
        color=body.color,
        icon=body.icon,
        sort_order=body.sort_order,
    )
    db.add(category)
    await db.flush()

    result = CategoryReadWithCount.model_validate(category)
    result.article_count = 0
    return result


@router.patch("/{category_id}")
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    _user: User = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
) -> CategoryReadWithCount:
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise NotFoundError("Category")

    updates = body.model_dump(exclude_unset=True)
    if "name" in updates:
        updates["slug"] = _slugify(updates["name"])
    for key, value in updates.items():
        setattr(category, key, value)
    await db.flush()

    cat_result = CategoryReadWithCount.model_validate(category)
    return cat_result


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    _user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise NotFoundError("Category")
    await db.delete(category)
