"""
web/models_db.py
================
SQLAlchemy ORM models for UGC Video Pro web application.

Tables:
    users        — application users with role-based access
    invite_codes — one-time invite codes for registration
    video_tasks  — video generation jobs with status tracking
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from web.database import Base


# ── Helpers ──────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# ── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    """Application user account."""

    __tablename__ = "users"

    # Public UUID (used in API responses)
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid, index=True
    )

    # Internal auto-increment int (used by VideoRequest.user_id which expects int)
    numeric_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False, start=1, increment=1),
        unique=True,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.user
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    # Relationships
    invite_codes_created: Mapped[list["InviteCode"]] = relationship(
        "InviteCode",
        foreign_keys="InviteCode.created_by",
        back_populates="creator",
        lazy="select",
    )
    invite_codes_used: Mapped[list["InviteCode"]] = relationship(
        "InviteCode",
        foreign_keys="InviteCode.used_by",
        back_populates="user",
        lazy="select",
    )
    video_tasks: Mapped[list["VideoTask"]] = relationship(
        "VideoTask",
        back_populates="user",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"


# ── InviteCode ────────────────────────────────────────────────────────────────

class InviteCode(Base):
    """One-time registration invite code."""

    __tablename__ = "invite_codes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid, index=True
    )
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)

    # Who created this code
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Who consumed this code
    used_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    # Relationships
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], back_populates="invite_codes_created"
    )
    user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[used_by], back_populates="invite_codes_used"
    )

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_by is not None

    def __repr__(self) -> str:
        return f"<InviteCode code={self.code} used={self.is_used}>"


# ── VideoTask ─────────────────────────────────────────────────────────────────

class VideoTask(Base):
    """A video generation job submitted by a user."""

    __tablename__ = "video_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Generation parameters
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.pending
    )
    mode: Mapped[str] = mapped_column(String(50), nullable=False)         # text_to_video | image_to_video | url_to_video
    model: Mapped[str] = mapped_column(String(50), nullable=False)        # sora_2 | veo_31_pro | …
    duration: Mapped[int] = mapped_column(Integer, nullable=False)        # seconds
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    aspect_ratio: Mapped[str] = mapped_column(String(10), nullable=False, default="9:16")

    # Input content
    text_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)  # text_to_video
    image_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)  # relative path
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)  # url_to_video

    # Output
    result_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)  # relative path
    result_drive_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Failure
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Progress tracking (updated by progress_callback)
    progress_segment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Soft-delete flag
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="video_tasks")

    def __repr__(self) -> str:
        return f"<VideoTask id={self.id} status={self.status} user={self.user_id}>"
