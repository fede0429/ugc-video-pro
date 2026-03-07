"""
web/routes_admin.py
===================
Admin-only API router for UGC Video Pro.

All endpoints require the requester to have role=admin (enforced via the
require_admin FastAPI dependency).

Endpoints:
    GET    /users               — list all users
    POST   /users               — create a user directly (no invite code needed)
    PUT    /users/{user_id}     — update a user's role / active status
    DELETE /users/{user_id}     — deactivate (soft-delete) a user
    POST   /invite-codes        — generate N invite codes
    GET    /invite-codes        — list all invite codes with usage status
"""

import logging
import os
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.auth import get_current_user, hash_password, require_admin
from web.database import get_db
from web.user_permissions_store import get_permissions, list_permissions, set_permissions
from web.models_db import InviteCode, User, UserRole
from web.schemas import (
    InviteCodeCreate,
    InviteCodeResponse,
    MessageResponse,
    UserCreateDirect,
    UserResponse,
    UserUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

# ── Helpers ───────────────────────────────────────────────────────────────────────────

def _generate_code(length: int = 8) -> str:
    """Generate a random uppercase alphanumeric invite code."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.SystemRandom().choices(alphabet, k=length))


# ── Users ───────────────────────────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List all users",
)
async def list_users(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[UserResponse]:
    """Return a paginated list of all registered users."""
    offset = (page - 1) * page_size
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
    )
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user directly (admin, no invite code required)",
)
async def create_user_direct(
    body: UserCreateDirect,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """
    Create a new user account without requiring an invite code.
    Useful for bootstrapping additional admins.

    Raises:
        409: Email already registered
    """
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address already registered",
        )

    role = UserRole.admin if body.role == "admin" else UserRole.user
    new_user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.email.split("@")[0],
        role=role,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"Admin {admin.email} created user: {new_user.email} role={role}")
    return UserResponse.model_validate(new_user)


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update a user's role or active status",
)
async def update_user(
    user_id: str,
    body: UserUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """
    Update role and/or active status for any user.

    Raises:
        404: User not found
        400: Cannot deactivate yourself
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.display_name is not None:
        user.display_name = body.display_name

    if body.role is not None:
        user.role = UserRole.admin if body.role == "admin" else UserRole.user

    if body.is_active is not None:
        if not body.is_active and user.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account",
            )
        user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)
    logger.info(f"Admin {admin.email} updated user {user.email}: role={user.role} active={user.is_active}")
    return UserResponse.model_validate(user)


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
    summary="Deactivate a user account",
)
async def deactivate_user(
    user_id: str,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """
    Deactivate (soft-delete) a user account.  The user record is kept for
    audit purposes; they simply cannot log in anymore.

    Raises:
        404: User not found
        400: Cannot deactivate yourself
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    user.is_active = False
    await db.commit()
    logger.info(f"Admin {admin.email} deactivated user: {user.email}")
    return MessageResponse(message=f"User {user.email} deactivated")


# ── Invite codes ────────────────────────────────────────────────────────────────

@router.post(
    "/invite-codes",
    response_model=list[InviteCodeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate one or more invite codes",
)
async def generate_invite_codes(
    body: InviteCodeCreate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[InviteCodeResponse]:
    """
    Generate N unique invite codes.

    Optionally set an expiry (in days from now).
    Returns the list of newly created InviteCodeResponse objects.
    """
    expires_at: datetime | None = None
    if body.expires_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)

    created: list[InviteCode] = []
    for _ in range(body.count):
        # Ensure uniqueness — retry up to 10 times if collision
        for attempt in range(10):
            candidate = _generate_code(length=8)
            exists = await db.execute(
                select(InviteCode).where(InviteCode.code == candidate)
            )
            if exists.scalar_one_or_none() is None:
                break
        else:
            logger.error("Failed to generate a unique invite code after 10 attempts")
            continue

        code = InviteCode(
            code=candidate,
            created_by=admin.id,
            expires_at=expires_at,
            is_active=True,
        )
        db.add(code)
        created.append(code)

    await db.commit()
    for code in created:
        await db.refresh(code)

    logger.info(f"Admin {admin.email} generated {len(created)} invite code(s)")
    return [InviteCodeResponse.model_validate(c) for c in created]


@router.get(
    "/invite-codes",
    response_model=list[InviteCodeResponse],
    summary="List all invite codes with usage status",
)
async def list_invite_codes(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
) -> list[InviteCodeResponse]:
    """Return all invite codes, newest first."""
    offset = (page - 1) * page_size
    result = await db.execute(
        select(InviteCode)
        .order_by(InviteCode.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    codes = result.scalars().all()
    return [InviteCodeResponse.model_validate(c) for c in codes]



@router.get(
    "/user-permissions",
    summary="List permission profiles for users",
)
async def list_user_permissions(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(select(User))
    users = result.scalars().all()
    rows = []
    stored = list_permissions()
    for user in users:
        rows.append({
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role.value,
            "permissions": get_permissions(user.id, role=user.role.value),
            "stored": stored.get(user.id, {}),
        })
    return {"items": rows}


@router.get(
    "/user-permissions/{user_id}",
    summary="Get one user's permission profile",
)
async def get_user_permissions(
    user_id: str,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "permissions": get_permissions(user.id, role=user.role.value),
    }


@router.put(
    "/user-permissions/{user_id}",
    summary="Update one user's permission profile",
)
async def update_user_permissions(
    user_id: str,
    body: dict,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    permissions = set_permissions(user.id, body, role=user.role.value)
    return {
        "message": "Permissions updated",
        "user_id": user.id,
        "permissions": permissions,
    }


@router.post(
    "/users/{user_id}/reset-password",
    response_model=MessageResponse,
    summary="Reset a user's password",
)
async def reset_user_password(
    user_id: str,
    body: dict,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    if admin.id == user_id and not body.get("allow_self_reset", False):
        raise HTTPException(status_code=400, detail="Use /auth/password to change your own password")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    new_password = str(body.get("new_password", "")).strip()
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user.password_hash = hash_password(new_password)
    await db.commit()
    return MessageResponse(message=f"Password reset for {user.email}")
