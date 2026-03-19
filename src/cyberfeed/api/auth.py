"""Auth API: register, login, refresh, logout."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.api.deps import get_db
from cyberfeed.schemas.user import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)
from cyberfeed.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()


@router.post("/register")
async def register(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user, access_token, refresh_token = await auth_service.register(
        db, body.username, body.password, body.email
    )
    return {
        "user": UserRead.model_validate(user),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    _user, access_token, refresh_token = await auth_service.login(db, body.username, body.password)
    # Set httpOnly cookie for web UI
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=900,  # 15 min
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    access_token, refresh_token = await auth_service.refresh_tokens(db, body.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie("access_token")
