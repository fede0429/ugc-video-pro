"""
web/routes_auth.py
==================
Authentication API router for UGC Video Pro.

Endpoints:
    POST /login    — email + password → access + refresh tokens
    POST /register — invite code + user info → create account + tokens
    POST /refresh  — refresh token → new access token
    GET  /me       — current user profile
    PUT  /password — change current user's password
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from web.database import get_db
from web.user_permissions_store import get_permissions, resolve_landing
from web.models_db import InviteCode, User, UserRole
from web.schemas import (
    LoginRequest,
    MessageResponse,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


# ── Helpers ───────────────────────────────────────────────────────────────────────────

def _make_tokens(user: User) -> TokenResponse:
    """Build the token pair for a successfully authenticated user."""
    access_token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role.value, "email": user.email},
    )
    refresh_token = create_refresh_token(subject=user.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ── POST /login ────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    Validate credentials and return JWT access + refresh tokens.

    Raises:
        401: Wrong email or password
        403: Account deactivated
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    logger.info(f"User logged in: {user.email}")
    return _make_tokens(user)


# ── POST /register ──────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account using an invite code",
)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    Create a new user account if the provided invite code is valid.

    Raises:
        400: Invalid / expired / already-used invite code
        409: Email already registered
    """
    # Check email uniqueness
    existing_user = await db.execute(select(User).where(User.email == body.email))
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address already registered",
        )

    # Validate invite code
    code_result = await db.execute(
        select(InviteCode).where(InviteCode.code == body.invite_code.strip().upper())
    )
    invite: InviteCode | None = code_result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite code",
        )
    if not invite.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite code has been deactivated",
        )
    if invite.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite code has already been used",
        )
    if invite.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite code has expired",
        )

    # Create user
    new_user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.email.split("@")[0],
        role=UserRole.user,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()  # Get the user.id before marking invite used

    # Mark invite code used
    invite.used_by = new_user.id
    invite.used_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(new_user)

    logger.info(f"New user registered: {new_user.email} (via invite {invite.code})")
    return _make_tokens(new_user)


# ── POST /refresh ───────────────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access token",
)
async def refresh_token(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    Validate the refresh token and issue a new access + refresh token pair.

    Raises:
        401: Invalid or expired refresh token
    """
    payload = decode_token(body.refresh_token, expected_type="refresh")
    user_id: str = payload["sub"]

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account deactivated",
        )

    return _make_tokens(user)


# ── GET /me ─────────────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current authenticated user's profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)


# ── PUT /password ───────────────────────────────────────────────────────────────────

@router.put(
    "/password",
    response_model=MessageResponse,
    summary="Change current user's password",
)
async def change_password(
    body: PasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """
    Verify the old password and set a new one.

    Raises:
        400: Old password is incorrect
    """
    if not verify_password(body.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(body.new_password)
    await db.commit()
    logger.info(f"Password changed for user: {current_user.email}")
    return MessageResponse(message="Password updated successfully")



@router.get(
    "/me/permissions",
    summary="Get current user permissions profile",
)
async def get_my_permissions(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return get_permissions(current_user.id, role=current_user.role.value)


@router.get(
    "/landing",
    summary="Get recommended landing page for current user",
)
async def get_landing(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    permissions = get_permissions(current_user.id, role=current_user.role.value)
    return {
        "target": resolve_landing(current_user.id, role=current_user.role.value),
        "role": current_user.role.value,
        "permissions": permissions,
    }
