"""Auth router — login and current-user endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import (
    create_access_token,
    get_current_user,
    verify_password,
)
from api.core.database import get_db
from api.core.models import User
from api.core.schemas import (
    APIResponse,
    LoginRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=APIResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> APIResponse:
    """Authenticate user with email/password and return a JWT."""
    result = await db.execute(select(User).where(User.email == body.email))
    user: User | None = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        logger.warning("Failed login attempt for email=%s", body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
        )

    token = create_access_token(data={"sub": user.id})
    logger.info("User %s logged in successfully", user.email)

    return APIResponse(
        success=True,
        data=TokenResponse(access_token=token).model_dump(),
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )


@router.get("/me", response_model=APIResponse)
async def me(current_user: User = Depends(get_current_user)) -> APIResponse:
    """Return the currently authenticated user's profile."""
    return APIResponse(
        success=True,
        data=UserResponse.model_validate(current_user).model_dump(),
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )
