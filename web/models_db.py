"""
web/models_db.py
================
SQLAlchemy ORM models for UGC Video Pro.

Tables:
    users           — application users
    invite_codes    — one-time registration codes
    video_tasks     — video generation jobs (legacy + ugc)
    task_assets     — per-task file assets (NEW)
    task_segments   — per-task timeline segments (NEW)
"""
from __future__ import annotations
import enum, uuid
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float, ForeignKey,
    Identity, Integer, JSON, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from web.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def new_uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"

class TaskStatus(str, enum.Enum):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"

class TaskType(str, enum.Enum):
    legacy = "legacy"
    ugc    = "ugc"

class SegmentStatus(str, enum.Enum):
    pending    = "pending"
    generating = "generating"
    done       = "done"
    failed     = "failed"

class AssetType(str, enum.Enum):
    product_primary  = "product_primary"
    product_gallery  = "product_gallery"
    product_usage    = "product_usage"
    presenter_image  = "presenter_image"
    presenter_video  = "presenter_video"
    tts_audio        = "tts_audio"
    a_roll_clip      = "a_roll_clip"
    b_roll_clip      = "b_roll_clip"
    subtitle         = "subtitle"
    overlay          = "overlay"
    cover            = "cover"
    final_video      = "final_video"


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid, index=True)
    numeric_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=False, start=1, increment=1), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.user)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    invite_codes_created: Mapped[list["InviteCode"]] = relationship("InviteCode", foreign_keys="InviteCode.created_by", back_populates="creator", lazy="select")
    invite_codes_used: Mapped[list["InviteCode"]] = relationship("InviteCode", foreign_keys="InviteCode.used_by", back_populates="user", lazy="select")
    video_tasks: Mapped[list["VideoTask"]] = relationship("VideoTask", back_populates="user", lazy="select")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


# ── InviteCode ────────────────────────────────────────────────────────────────

class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid, index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    used_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by], back_populates="invite_codes_created")
    user: Mapped["User | None"] = relationship("User", foreign_keys=[used_by], back_populates="invite_codes_used")

    @property
    def is_expired(self) -> bool:
        return False if self.expires_at is None else datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_by is not None


# ── VideoTask ─────────────────────────────────────────────────────────────────

class VideoTask(Base):
    """Video generation job — supports both legacy and UGC pipeline."""
    __tablename__ = "video_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Pipeline type
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType, name="task_type_enum"), nullable=False, default=TaskType.ugc)

    # Core parameters
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.pending)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="it")
    aspect_ratio: Mapped[str] = mapped_column(String(10), nullable=False, default="9:16")
    quality_tier: Mapped[str] = mapped_column(String(20), nullable=True, default="economy")

    # ── Product inputs ────────────────────────────────────────────────────────
    text_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)  # legacy primary image
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    selling_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Presenter inputs ──────────────────────────────────────────────────────
    presenter_image_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    presenter_video_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    persona_template: Mapped[str | None] = mapped_column(String(64), nullable=True, default="energetic_female")
    voice_preset: Mapped[str | None] = mapped_column(String(10), nullable=True)
    voice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lipsync_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    use_lipsync: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Creative inputs ───────────────────────────────────────────────────────
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True, default="douyin")
    hook_style: Mapped[str | None] = mapped_column(String(64), nullable=True, default="result_first")
    tone_style: Mapped[str | None] = mapped_column(String(64), nullable=True, default="authentic_friend")
    cta_style: Mapped[str | None] = mapped_column(String(64), nullable=True, default="link_in_bio")
    video_goal: Mapped[str | None] = mapped_column(String(64), nullable=True, default="brand_awareness")
    use_bgm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Outputs ───────────────────────────────────────────────────────────────
    result_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_drive_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    subtitle_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    final_audio_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Metadata JSON blobs ───────────────────────────────────────────────────
    timeline_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    product_profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    presenter_profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    qa_report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Error / progress ──────────────────────────────────────────────────────
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_segment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="video_tasks")
    assets: Mapped[list["TaskAsset"]] = relationship("TaskAsset", back_populates="task", lazy="select", cascade="all, delete-orphan")
    segments: Mapped[list["TaskSegment"]] = relationship("TaskSegment", back_populates="task", lazy="select", cascade="all, delete-orphan", order_by="TaskSegment.segment_index")

    def __repr__(self) -> str:
        return f"<VideoTask id={self.id} type={self.task_type} status={self.status}>"


# ── TaskAsset ─────────────────────────────────────────────────────────────────

class TaskAsset(Base):
    """
    Every file asset associated with a task — inputs and outputs.
    Replaces the old single image_filename + result_filename approach.
    """
    __tablename__ = "task_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid, index=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("video_tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType, name="asset_type_enum"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)   # relative to DATA_ROOT
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    task: Mapped["VideoTask"] = relationship("VideoTask", back_populates="assets")

    def __repr__(self) -> str:
        return f"<TaskAsset type={self.asset_type} file={self.filename}>"


# ── TaskSegment ───────────────────────────────────────────────────────────────

class TaskSegment(Base):
    """
    One segment in the production timeline.
    Created after TimelineScript is generated; updated as assets are rendered.
    """
    __tablename__ = "task_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid, index=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("video_tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_ref_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # TimelineSegment.segment_id
    track_type: Mapped[str] = mapped_column(String(20), nullable=False)   # a_roll | b_roll | overlay
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    spoken_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    overlay_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    b_roll_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotion: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shot_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[SegmentStatus] = mapped_column(Enum(SegmentStatus, name="segment_status"), nullable=False, default=SegmentStatus.pending)
    source_asset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("task_assets.id", ondelete="SET NULL"), nullable=True)
    output_asset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("task_assets.id", ondelete="SET NULL"), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    task: Mapped["VideoTask"] = relationship("VideoTask", back_populates="segments")

    def __repr__(self) -> str:
        return f"<TaskSegment idx={self.segment_index} track={self.track_type} status={self.status}>"
