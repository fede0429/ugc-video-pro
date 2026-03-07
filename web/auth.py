"""
web/auth.py
===========
Authentication utilities for UGC Video Pro web application.

Provides:
    - hash_password() / verify_password() — bcrypt wrappers
    - create_access_token() / create_refresh_token() — JWT creation
    - decode_token() — JWT verification
    - get_current_user() — FastAPI dependency (Bearer token → User)
    - require_admin() — FastAPI dependency (ensures admin role)

Environment variables:
    JWT_SECRET             — signing key (required in production)
    ACCESS_TOKEN_EXPIRE    — minutes (default: 30)
    REFRESH_TOKEN_EXPIRE   — days (default: 7)
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.database import get_db

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────────────

JWT_SECRET: str = os.environ.get("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION_super_secret_key_32chars")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.environ.get("REFRESH_TOKEN_EXPIRE", "7"))

# ── Password hashing ─────────────────────────────────────────────────────────────────────


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ── JWT token creation ──────────────────────────────────────────────────────────────────

def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: The user's UUID (stored in 'sub' claim)
        extra_claims: Optional dict of additional claims to embed

    Returns:
        Signed JWT string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """
    Create a signed JWT refresh token (long-lived).

    Args:
        subject: The user's UUID

    Returns:
        Signed JWT string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict:
    """
    Decode and validate a JWT token.

    Args:
        token: The encoded JWT string
        expected_type: Either 'access' or 'refresh'

    Returns:
        Decoded payload dict

    Raises:
        HTTPException 401: If the token is invalid, expired, or of wrong type
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        logger.debug(f"JWT decode error: {exc}")
        raise credentials_exception

    if payload.get("type") != expected_type:
        raise credentials_exception

    sub = payload.get("sub")
    if not sub:
        raise credentials_exception

    return payload


# ── HTTP Bearer scheme ──────────────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=True)


# ── FastAPI dependencies ───────────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    FastAPI dependency: extract the current user from a Bearer access token.

    Returns:
        web.models_db.User ORM object

    Raises:
        HTTPException 401: If token invalid / user not found / account inactive
    """
    from web.models_db import User

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id: str = payload["sub"]

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return user


async def require_admin(
    current_user: Annotated["any", Depends(get_current_user)],
):
    """
    FastAPI dependency: ensure the current user has the admin role.

    Returns:
        The same User object if the check passes.

    Raises:
        HTTPException 403: If the user is not an admin
    """
    from web.models_db import UserRole

    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user
