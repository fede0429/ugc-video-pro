"""
web/schemas.py
==============
Pydantic v2 request/response schemas for UGC Video Pro API.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ── Auth ──────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=1, max_length=32)
    display_name: str = Field(default="", max_length=100)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

# ── User ──────────────────────────────────────────────────────────────────────
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; email: str; display_name: str; role: str
    is_active: bool; created_at: datetime; updated_at: datetime

class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    is_active: Optional[bool] = None

class UserCreateDirect(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=100)
    role: str = Field(default="user", pattern="^(admin|user)$")

# ── Legacy video request (backward compat) ────────────────────────────────────
class VideoGenerateRequest(BaseModel):
    mode: str = Field(pattern="^(text_to_video|image_to_video|url_to_video)$")
    model: str = Field(pattern="^(auto|veo_31_fast|veo_31_quality|seedance_15|seedance_2|sora_2|sora_2_pro|runway|kling_30|hailuo|veo_3|veo_3_pro|veo_31_pro)$")
    duration: int = Field(ge=4, le=600)
    language: str = Field(default="it", pattern="^(zh|en|it)(,(zh|en|it))*$")
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9)$")
    text_prompt: Optional[str] = Field(default=None, max_length=4000)
    url: Optional[str] = Field(default=None, max_length=2048)
    quality_tier: str = Field(default="economy", pattern="^(economy|premium|china)$")

# ── NEW: UGC request schemas ──────────────────────────────────────────────────

class ProductAssetSchema(BaseModel):
    """Describes the product inputs for a UGC video."""
    product_description: Optional[str] = Field(default=None, max_length=2000)
    brand_name: Optional[str] = Field(default=None, max_length=200)
    product_url: Optional[str] = Field(default=None, max_length=2048)
    selling_points: Optional[str] = Field(
        default=None, max_length=1000,
        description="Comma-separated key selling points"
    )
    target_audience: Optional[str] = Field(default=None, max_length=500)

class PresenterInputSchema(BaseModel):
    """Presenter / digital-human configuration."""
    persona_template: str = Field(
        default="energetic_female",
        description="energetic_female|calm_male|luxury_female|chinese_kol|english_influencer"
    )
    voice_preset: Optional[str] = Field(
        default=None, pattern="^(it|zh|en)$",
        description="Language for TTS voice (defaults to request language)"
    )
    voice_id: Optional[str] = Field(default=None, max_length=64, description="ElevenLabs voice ID override")
    lipsync_model: Optional[str] = Field(
        default=None,
        description="kling_avatar_720p|kling_avatar_1080p|infinitetalk_720p|none"
    )

class CreativeInputSchema(BaseModel):
    """Creative strategy parameters."""
    platform: str = Field(
        default="douyin",
        description="douyin|tiktok|instagram|youtube_shorts|kuaishou"
    )
    hook_style: str = Field(
        default="result_first",
        description="pain_point|result_first|authority_claim|curiosity_gap|listicle_number|social_proof|comparison_challenge|transformation_story"
    )
    tone_style: str = Field(
        default="authentic_friend",
        description="authentic_friend|professional_expert|energetic_hype|luxury_aspirational|funny_relatable"
    )
    cta_style: str = Field(
        default="link_in_bio",
        description="link_in_bio|buy_now|limited_offer|follow_for_more|comment_below"
    )
    video_goal: str = Field(
        default="brand_awareness",
        description="brand_awareness|conversion|engagement|education|comparison"
    )

class UGCGenerateRequest(BaseModel):
    """
    POST /api/video/generate/ugc
    Full UGC production task specification.
    """
    mode: str = Field(default="ugc_video")
    model: str = Field(
        default="auto",
        description="Video model — auto lets UGCProducer decide"
    )
    duration: int = Field(ge=10, le=180, description="Target duration in seconds")
    language: str = Field(default="it", pattern="^(zh|en|it)(,(zh|en|it))*$")
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9)$")
    quality_tier: str = Field(default="economy", pattern="^(economy|premium|china)$")

    product: ProductAssetSchema = Field(default_factory=ProductAssetSchema)
    presenter: PresenterInputSchema = Field(default_factory=PresenterInputSchema)
    creative: CreativeInputSchema = Field(default_factory=CreativeInputSchema)

# ── Task response schemas ─────────────────────────────────────────────────────

class TaskAssetResponse(BaseModel):
    """One file asset attached to a task."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    asset_type: str
    filename: str
    sort_order: int
    metadata_json: Optional[Any] = None
    created_at: datetime

class TimelineSegmentResponse(BaseModel):
    """One segment in the task timeline."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    segment_index: int
    track_type: str              # a_roll | b_roll | overlay
    duration: float
    spoken_line: Optional[str]
    overlay_text: Optional[str]
    status: str                  # pending | generating | done | failed
    output_asset_id: Optional[str]

class TaskTimelineResponse(BaseModel):
    """Full timeline preview for a task."""
    task_id: str
    total_duration: float
    segments: list[TimelineSegmentResponse]
    strategy: Optional[str]
    platform: Optional[str]
    persona: Optional[str]

class VideoTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; user_id: str; status: str; mode: str; model: str
    duration: int; language: str; aspect_ratio: str
    text_prompt: Optional[str]; image_filename: Optional[str]; url: Optional[str]
    result_filename: Optional[str]; result_drive_link: Optional[str]
    error_message: Optional[str]; progress_segment: int; progress_total: int
    created_at: datetime; updated_at: datetime; completed_at: Optional[datetime]
    # UGC extensions
    task_type: Optional[str] = None
    platform: Optional[str] = None
    persona_template: Optional[str] = None
    subtitle_filename: Optional[str] = None
    cover_filename: Optional[str] = None

class VideoTaskList(BaseModel):
    items: list[VideoTaskResponse]
    total: int; page: int; page_size: int; pages: int

# ── Invite / Admin ────────────────────────────────────────────────────────────
class InviteCodeCreate(BaseModel):
    count: int = Field(default=1, ge=1, le=100)
    expires_days: Optional[int] = Field(default=None, ge=1, le=365)

class InviteCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; code: str; created_by: Optional[str]; used_by: Optional[str]
    used_at: Optional[datetime]; expires_at: Optional[datetime]
    is_active: bool; created_at: datetime; is_used: bool; is_expired: bool

# ── Generic ───────────────────────────────────────────────────────────────────
class MessageResponse(BaseModel):
    message: str; detail: Optional[str] = None

class TaskCreatedResponse(BaseModel):
    task_id: str; message: str = "Video generation started"

class ProgressUpdate(BaseModel):
    task_id: str; event: str
    status: Optional[str] = None; stage: Optional[str] = None
    stage_message: Optional[str] = None
    segment: Optional[int] = None; total: Optional[int] = None
    message: Optional[str] = None; result_filename: Optional[str] = None
    drive_link: Optional[str] = None; error: Optional[str] = None
    qa_passed: Optional[bool] = None

# ── Preset response schemas (for dropdowns) ───────────────────────────────────
class PersonaPreset(BaseModel):
    key: str; name: str; description: str
    voice_preset: str; style_notes: str

class PlatformPreset(BaseModel):
    key: str; name: str; aspect_ratio: str; max_duration: int
    description: str

class PresetListResponse(BaseModel):
    personas: list[PersonaPreset]
    platforms: list[PlatformPreset]
    hook_styles: list[dict]
    tone_styles: list[dict]
    cta_styles: list[dict]
