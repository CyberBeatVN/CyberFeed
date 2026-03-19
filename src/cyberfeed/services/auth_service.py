"""Authentication service: register, login, token management."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.core.exceptions import AuthenticationError, ValidationError
from cyberfeed.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from cyberfeed.models.user import User

logger = structlog.get_logger()


class AuthService:
    async def register(
        self,
        db: AsyncSession,
        username: str,
        password: str,
        email: str | None = None,
    ) -> tuple[User, str, str]:
        """Register a new user. First user becomes admin.

        Returns (user, access_token, refresh_token).
        """
        # Validate
        if len(username) < 3:
            raise ValidationError("Username must be at least 3 characters")
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters")

        # Check uniqueness
        existing = await db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            raise ValidationError("Username already taken")

        if email:
            existing_email = await db.execute(select(User).where(User.email == email))
            if existing_email.scalar_one_or_none():
                raise ValidationError("Email already registered")

        # First user = admin
        user_count = await db.execute(select(func.count(User.id)))
        is_first_user = (user_count.scalar() or 0) == 0

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role="admin" if is_first_user else "reader",
            is_active=True,
        )
        db.add(user)
        await db.flush()

        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        logger.info("User registered", username=username, role=user.role)
        return user, access_token, refresh_token

    async def login(self, db: AsyncSession, username: str, password: str) -> tuple[User, str, str]:
        """Authenticate user. Returns (user, access_token, refresh_token)."""
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            logger.warning("Failed login attempt", username=username)
            raise AuthenticationError("Invalid username or password")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        user.last_login_at = datetime.now(UTC)
        await db.flush()

        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        return user, access_token, refresh_token

    async def refresh_tokens(self, db: AsyncSession, refresh_token_str: str) -> tuple[str, str]:
        """Validate refresh token and issue new token pair."""
        try:
            payload = decode_token(refresh_token_str)
        except Exception as e:
            raise AuthenticationError(f"Invalid refresh token: {e}") from e

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")

        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        access_token = create_access_token({"sub": str(user.id)})
        new_refresh_token = create_refresh_token({"sub": str(user.id)})

        return access_token, new_refresh_token
