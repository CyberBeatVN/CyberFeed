"""User management API (admin only)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.api.deps import get_db, require_role
from cyberfeed.models.user import User
from cyberfeed.schemas.user import UserRead, UserUpdate
from cyberfeed.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])
user_service = UserService()


@router.get("")
async def list_users(
    page: int = 1,
    per_page: int = 20,
    _user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    users, total = await user_service.get_all(db, page, per_page)
    return {
        "users": [UserRead.model_validate(u) for u in users],
        "total": total,
    }


@router.get("/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    _user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await user_service.get_by_id(db, user_id)
    return UserRead.model_validate(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    if body.role:
        user = await user_service.update_role(db, user_id, body.role, current_user)
    elif body.is_active is not None:
        user = await user_service.toggle_active(db, user_id, body.is_active, current_user)
    else:
        user = await user_service.get_by_id(db, user_id)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await user_service.delete(db, user_id, current_user)
