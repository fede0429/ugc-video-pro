"""
web/schemas.py
==============
Pydantic v2 request/response schemas for UGC Video Pro API.

All schemas use model_config = ConfigDict(from_attributes=True) where
appropriate so they can be built from SQLAlchemy ORM objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Auth schemas
# ─────────────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """POST /api/auth/login"""
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    """POST /api/auth/register"""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=1, max_length=32)
    display_name: str = Field(default="", max_length=100)


class TokenResponse(BaseModel):
    """Returned on successful login / register / token refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """POST /api/auth/refresh"""
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """PUT /api/auth/password"""
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


# ─────────────────────────────────────────────────────────────────────────────
# User schemas
# ─────────────────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    """Public representation of a user."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """PUT /api/admin/users/{user_id} — fields are all optional."""
    display_name: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    is_active: Optional[bool] = None


class UserCreateDirect(BaseModel):
    """POST /api/admin/users — admin creates user directly."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=100)
    role: str = Field(default="user", pattern="^(admin|user)$")


# ─────────────────────────────────────────────────────────────────────────────
# Video generation schemas
# ─────────────────────────────────────────────────────────────────────────────

class VideoGenerateRequest(BaseModel):
    """
    Parameters for POST /api/video/generate.

    NOTE: This schema is used when parsing Form fields (each field is a
    separate form value).  The image is uploaded as a separate UploadFile.
    """
    mode: str = Field(
        pattern="^(text_to_video|image_to_video|url_to_video)$",
        description="Generation mode",
    )
    model: str = Field(
        pattern="^(sora_2|sora_2_pro|seedance_2|veo_3|veo_3_pro|veo_31_pro)$",
        description="AI model key",
    )
    duration: int = Field(ge=4, le=600, description="Total video duration in seconds")
    language: str = Field(
        default="en",
        pattern="^(zh|en|it)$",
        description="Narration language",
    )
    aspect_ratio: str = Field(
        default="9:16",
        pattern="^(9:16|16:9)$",
        description="Video aspect ratio",
    )
    text_prompt: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="Text description (text_to_video or supplemental description)",
    )
    url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Product URL (url_to_video mode)",
    )


# ─────────────────────────────────────────────────────────────────────────────
# VideoTask schemas
# ─────────────────────────────────────────────────────────────────────────────

class VideoTaskResponse(BaseModel):
    """Full representation of a VideoTask."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    status: str
    mode: str
    model: str
    duration: int
    language: str
    aspect_ratio: str
    text_prompt: Optional[str]
    image_filename: Optional[str]
    url: Optional[str]
    result_filename: Optional[str]
    result_drive_link: Optional[str]
    error_message: Optional[str]
    progress_segment: int
    progress_total: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


class VideoTaskList(BaseModel):
    """Paginated list of video tasks."""
    items: list[VideoTaskResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ─────────────────────────────────────────────────────────────────────────────
# Invite code schemas
# ─────────────────────────────────────────────────────────────────────────────

class InviteCodeCreate(BaseModel):
    """POST /api/admin/invite-codes"""
    count: int = Field(default=1, ge=1, le=100, description="Number of codes to generate")
    expires_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Days until expiry (None = no expiry)",
    )


class InviteCodeResponse(BaseModel):
    """Representation of an invite code."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    created_by: Optional[str]
    used_by: Optional[str]
    used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    is_used: bool
    is_expired: bool


# ─────────────────────────────────────────────────────────────────────────────
# Generic response schemas
# ─────────────────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    """Generic message envelope used for errors and simple confirmations."""
    message: str
    detail: Optional[str] = None


class TaskCreatedResponse(BaseModel):
    """Returned immediately after POST /api/video/generate."""
    task_id: str
    message: str = "Video generation started"


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket / Progress schemas
# ─────────────────────────────────────────────────────────────────────────────

class ProgressUpdate(BaseModel):
    """
    JSON message broadcast over WebSocket at /api/ws/progress/{task_id}.

    event values:
        status   — task status changed (pending/processing/completed/failed)
        progress — segment progress update
        message  — human-readable status message (localised)
        error    — error details when failed
    """
    task_id: str
    event: str                           # status | progress | message | error
    status: Optional[str] = None         # TaskStatus value
    segment: Optional[int] = None        # current segment number
    total: Optional[int] = None          # total segments
    message: Optional[str] = None        # human-readable text
    result_filename: Optional[str] = None
    drive_link: Optional[str] = None
    error: Optional[str] = None
