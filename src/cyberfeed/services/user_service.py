"""User CRUD and role management (admin operations)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.core.exceptions import NotFoundError, ValidationError
from cyberfeed.models.user import User

VALID_ROLES = {"admin", "editor", "reader"}


class UserService:
    async def get_all(
        self, db: AsyncSession, page: int = 1, per_page: int = 20
    ) -> tuple[list[User], int]:
        offset = (page - 1) * per_page
        result = await db.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(per_page)
        )
        users = list(result.scalars().all())

        total_result = await db.execute(select(func.count(User.id)))
        total = total_result.scalar() or 0

        return users, total

    async def get_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User")
        return user

    async def update_role(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        role: str,
        current_user: User,
    ) -> User:
        if role not in VALID_ROLES:
            raise ValidationError(f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")

        if user_id == current_user.id:
            raise ValidationError("Cannot change your own role")

        user = await self.get_by_id(db, user_id)
        user.role = role
        await db.flush()
        return user

    async def toggle_active(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        is_active: bool,
        current_user: User,
    ) -> User:
        if user_id == current_user.id:
            raise ValidationError("Cannot deactivate your own account")

        user = await self.get_by_id(db, user_id)
        user.is_active = is_active
        await db.flush()
        return user

    async def delete(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        current_user: User,
    ) -> None:
        if user_id == current_user.id:
            raise ValidationError("Cannot delete your own account")

        user = await self.get_by_id(db, user_id)
        await db.delete(user)
