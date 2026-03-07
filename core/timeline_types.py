"""
core/timeline_types.py
======================
Protocol layer — single source of truth for all data contracts in the
UGC video production pipeline.

Every inter-module handoff is typed here:
    UGCVideoRequest   → what the user submitted
    ProductProfile    → structured product understanding (ImageAnalyzer output)
    PresenterProfile  → structured presenter understanding
    ProductionPlan    → high-level director decisions
    TimelineScript    → executable, segment-by-segment production plan
    AudioSegmentAsset → TTS output for one A-roll segment
    RenderedAsset     → rendered video clip (A-roll or B-roll)
    QAIssue           → a single quality-check finding
    QAReport          → complete QA result for one job
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────
# Request
# ─────────────────────────────────────────────────────────────────

@dataclass
class UGCVideoRequest:
    """
    Full specification for one UGC video generation job.
    Created by routes_video.py and consumed by tasks.py.
    """
    task_id: str
    user_id: str

    # Generation parameters
    mode: str                          # text_to_video | image_to_video | url_to_video
    model: str                         # auto | veo_31_fast | seedance_15 | ...
    duration: int                      # target seconds
    language: str = "it"               # it | zh | en  (or comma-separated)
    aspect_ratio: str = "9:16"
    quality_tier: str = "economy"      # economy | premium | china
    platform: str = "tiktok"           # tiktok | instagram | youtube

    # Inputs
    text_prompt: str = ""
    url: Optional[str] = None

    # Uploaded file paths (relative to DATA_ROOT)
    product_image_paths: list[str] = field(default_factory=list)
    presenter_image_path: Optional[str] = None   # for A-roll lipsync

    # Feature flags
    use_lipsync: bool = True
    use_bgm: bool = False
    bgm_path: Optional[str] = None

    # Pre-extracted URL content (filled in by orchestrator if needed)
    url_content: Optional[str] = None


# ─────────────────────────────────────────────────────────────────
# Profiles (analysis outputs)
# ─────────────────────────────────────────────────────────────────

@dataclass
class ProductProfile:
    """Structured result of ImageAnalyzer.build_product_profile()."""
    product_type: str = ""
    brand: str = ""
    description: str = ""
    colors: list[Any] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    text_on_product: str = ""
    shape: str = ""
    key_features: list[str] = field(default_factory=list)
    target_audience: str = ""
    use_case: str = ""

    # Raw Gemini/analysis output, serialised for persistence
    # Extended fields from multi-image analysis
    selling_points: list[str] = field(default_factory=list)
    demo_actions: list[str] = field(default_factory=list)
    consistency_anchors: list[str] = field(default_factory=list)
    before_after_opportunity: str = ""
    category: str = ""                  # alias for product_type

    raw_analysis: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "product_type": self.product_type,
            "brand": self.brand,
            "description": self.description,
            "colors": self.colors,
            "materials": self.materials,
            "text_on_product": self.text_on_product,
            "shape": self.shape,
            "key_features": self.key_features,
            "target_audience": self.target_audience,
            "use_case": self.use_case,
            "selling_points": self.selling_points,
            "demo_actions": self.demo_actions,
            "consistency_anchors": self.consistency_anchors,
            "before_after_opportunity": self.before_after_opportunity,
            "category": self.category,
            "raw_analysis": self.raw_analysis,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProductProfile":
        return cls(
            product_type=d.get("product_type", ""),
            brand=d.get("brand", ""),
            description=d.get("description", ""),
            colors=d.get("colors", []),
            materials=d.get("materials", []),
            text_on_product=d.get("text_on_product", ""),
            shape=d.get("shape", ""),
            key_features=d.get("key_features", []),
            target_audience=d.get("target_audience", ""),
            use_case=d.get("use_case", ""),
            selling_points=d.get("selling_points", []) or [],
            demo_actions=d.get("demo_actions", []) or [],
            consistency_anchors=d.get("consistency_anchors", []) or [],
            before_after_opportunity=d.get("before_after_opportunity", ""),
            category=d.get("category", ""),
            raw_analysis=d.get("raw_analysis", {}),
        )


@dataclass
class PresenterProfile:
    """Structured result of PresenterAnalyzer.build_presenter_profile()."""
    presenter_id: str = ""
    face_image_path: Optional[str] = None     # local path
    persona_template: str = "energetic_female"
    voice_preset: str = "it"
    voice_id: Optional[str] = None            # ElevenLabs voice_id override
    lipsync_model: str = "kling_avatar_720p"  # model key for LipSyncService
    style_notes: str = ""
    role_label: str = ""
    speaking_style: str = ""
    emotional_tone: str = ""
    trust_mode: str = ""
    camera_behavior: str = ""
    vocabulary_style: str = ""
    cta_style: str = ""
    recommended_shot_types: list[str] = field(default_factory=list)
    preferred_hook_styles: list[str] = field(default_factory=list)
    realism_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "presenter_id": self.presenter_id,
            "face_image_path": self.face_image_path,
            "persona_template": self.persona_template,
            "voice_preset": self.voice_preset,
            "voice_id": self.voice_id,
            "lipsync_model": self.lipsync_model,
            "style_notes": self.style_notes,
            "role_label": self.role_label,
            "speaking_style": self.speaking_style,
            "emotional_tone": self.emotional_tone,
            "trust_mode": self.trust_mode,
            "camera_behavior": self.camera_behavior,
            "vocabulary_style": self.vocabulary_style,
            "cta_style": self.cta_style,
            "recommended_shot_types": self.recommended_shot_types,
            "preferred_hook_styles": self.preferred_hook_styles,
            "realism_notes": self.realism_notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PresenterProfile":
        return cls(
            presenter_id=d.get("presenter_id", ""),
            face_image_path=d.get("face_image_path"),
            persona_template=d.get("persona_template", "energetic_female"),
            voice_preset=d.get("voice_preset", "it"),
            voice_id=d.get("voice_id"),
            lipsync_model=d.get("lipsync_model", "kling_avatar_720p"),
            style_notes=d.get("style_notes", ""),
            role_label=d.get("role_label", ""),
            speaking_style=d.get("speaking_style", ""),
            emotional_tone=d.get("emotional_tone", ""),
            trust_mode=d.get("trust_mode", ""),
            camera_behavior=d.get("camera_behavior", ""),
            vocabulary_style=d.get("vocabulary_style", ""),
            cta_style=d.get("cta_style", ""),
            recommended_shot_types=d.get("recommended_shot_types", []) or [],
            preferred_hook_styles=d.get("preferred_hook_styles", []) or [],
            realism_notes=d.get("realism_notes", []) or [],
        )


# ─────────────────────────────────────────────────────────────────
# Production Plan
# ─────────────────────────────────────────────────────────────────

@dataclass
class ProductionPlan:
    """High-level decisions made by DirectorAgent / UGCProducer."""
    video_model: str = "seedance_15"
    num_segments: int = 3
    segment_durations: list[int] = field(default_factory=lambda: [8, 8, 8])
    tts_languages: list[str] = field(default_factory=list)
    a_roll_ratio: float = 0.4          # fraction of timeline that is A-roll
    b_roll_ratio: float = 0.6
    estimated_cost_usd: float = 0.0
    hook_pattern: str = "question_hook"
    scene_progression: str = "problem_solution"
    raw_json: str = ""

    def to_dict(self) -> dict:
        return {
            "video_model": self.video_model,
            "num_segments": self.num_segments,
            "segment_durations": self.segment_durations,
            "tts_languages": self.tts_languages,
            "a_roll_ratio": self.a_roll_ratio,
            "b_roll_ratio": self.b_roll_ratio,
            "estimated_cost_usd": self.estimated_cost_usd,
            "hook_pattern": self.hook_pattern,
            "scene_progression": self.scene_progression,
        }


# ─────────────────────────────────────────────────────────────────
# Timeline Script (the execution plan)
# ─────────────────────────────────────────────────────────────────

@dataclass
class TimelineSegment:
    """One segment/clip in the production timeline."""
    segment_id: str
    segment_index: int
    track_type: str                     # "a_roll" | "b_roll" | "overlay"
    duration_seconds: Decimal           # exact duration, use Decimal for arithmetic safety

    # A-roll fields
    spoken_line: str = ""               # what the presenter says
    emotion: str = ""                   # emotional delivery: surprised_authentic, warm_casual, ...
    shot_type: str = ""                 # selfie_closeup, mirror_demo, handheld_reaction, ...
    visual_prompt: str = ""             # full AI prompt for b_roll generation
    product_focus: str = ""             # what product aspect to show
    # B-roll fields
    b_roll_prompt: str = ""             # prompt for AI video generation
    scene_description: str = ""         # human-readable scene intent
    # Shared
    overlay_text: str = ""              # on-screen caption / product callout
    camera_movement: str = "static"
    continuation_hint: str = ""         # EXACT end-frame state for frame-chaining

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "segment_index": self.segment_index,
            "track_type": self.track_type,
            "duration_seconds": float(self.duration_seconds),
            "spoken_line": self.spoken_line,
            "b_roll_prompt": self.b_roll_prompt,
            "scene_description": self.scene_description,
            "overlay_text": self.overlay_text,
            "camera_movement": self.camera_movement,
            "continuation_hint": self.continuation_hint,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TimelineSegment":
        return cls(
            segment_id=d["segment_id"],
            segment_index=d["segment_index"],
            track_type=d["track_type"],
            duration_seconds=Decimal(str(d["duration_seconds"])),
            spoken_line=d.get("spoken_line", ""),
            b_roll_prompt=d.get("b_roll_prompt", ""),
            scene_description=d.get("scene_description", ""),
            overlay_text=d.get("overlay_text", ""),
            camera_movement=d.get("camera_movement", "static"),
            continuation_hint=d.get("continuation_hint", ""),
        )


@dataclass
class TimelineScript:
    """
    Full, executable production timeline.
    Output of TimelineScriptGenerator / ScriptGenerator.
    """
    task_id: str
    segments: list[TimelineSegment]
    language: str = "it"
    raw_json: str = ""

    @property
    def total_duration(self) -> float:
        return float(sum(seg.duration_seconds for seg in self.segments))

    @property
    def a_roll_segments(self) -> list[TimelineSegment]:
        return [s for s in self.segments if s.track_type == "a_roll"]

    @property
    def b_roll_segments(self) -> list[TimelineSegment]:
        return [s for s in self.segments if s.track_type == "b_roll"]

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "language": self.language,
            "total_duration": self.total_duration,
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TimelineScript":
        return cls(
            task_id=d.get("task_id", ""),
            language=d.get("language", "it"),
            segments=[TimelineSegment.from_dict(s) for s in d.get("segments", [])],
        )


def make_segment_id() -> str:
    """Generate a short unique segment ID."""
    return uuid.uuid4().hex[:12]


# ─────────────────────────────────────────────────────────────────
# Asset types (pipeline outputs)
# ─────────────────────────────────────────────────────────────────

@dataclass
class AudioSegmentAsset:
    """
    TTS audio for one A-roll segment.
    Output of TTSService.synthesize_segments().
    """
    segment_id: str
    audio_path: str
    duration_seconds: float
    language: str = "it"

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "audio_path": self.audio_path,
            "duration_seconds": self.duration_seconds,
            "language": self.language,
        }


@dataclass
class RenderedAsset:
    """
    A rendered video clip — A-roll (lipsync) or B-roll (AI generated).
    Output of LipSyncService / BRollSequenceBuilder.
    """
    segment_id: str
    video_path: str
    duration_seconds: float
    track_type: str   # "a_roll" | "b_roll"

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "video_path": self.video_path,
            "duration_seconds": self.duration_seconds,
            "track_type": self.track_type,
        }


# ─────────────────────────────────────────────────────────────────
# QA types
# ─────────────────────────────────────────────────────────────────

@dataclass
class QAIssue:
    """One quality-check finding."""
    code: str
    severity: str          # "error" | "warning" | "info"
    message: str
    segment_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "segment_id": self.segment_id,
        }


@dataclass
class QAReport:
    """Complete quality-assurance result for one production job."""
    passed: bool
    issues: list[QAIssue] = field(default_factory=list)
    checks: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "checks": self.checks,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "QAReport":
        return cls(
            passed=d.get("passed", False),
            issues=[
                QAIssue(**i) for i in d.get("issues", [])
            ],
            checks=d.get("checks", {}),
        )

# ─────────────────────────────────────────────────────────────────
# Extended UGCVideoRequest — multi-image + presenter fields
# (additive — UGCVideoRequest above is the base; use ExtendedUGCVideoRequest
#  for the new pipeline that fully matches the PDF blueprint)
# ─────────────────────────────────────────────────────────────────

@dataclass
class ExtendedUGCVideoRequest(UGCVideoRequest):
    """
    Full UGCVideoRequest with separate product image pools + presenter assets.
    Matches the PDF blueprint field names used by BRollSequenceBuilder.
    """
    # Product image pools (mapped from TaskAsset records)
    product_primary_image: str = ""             # single primary path
    product_gallery_images: list[str] = field(default_factory=list)
    product_usage_images: list[str] = field(default_factory=list)

    # Presenter assets
    presenter_video_path: Optional[str] = None  # reference talking-head video

    # Creative overrides
    hook_style: str = "result_first"
    tone_style: str = "authentic_friend"
    cta_style: str = "link_in_bio"
    video_goal: str = "brand_awareness"
    persona_template: str = "energetic_female"

    @classmethod
    def from_task_and_paths(
        cls,
        task,
        primary_image: Optional[str],
        gallery_images: list[str],
        usage_images: list[str],
        presenter_image: Optional[str],
        presenter_video: Optional[str],
    ) -> "ExtendedUGCVideoRequest":
        """Build from a VideoTask ORM object + pre-resolved file paths."""
        return cls(
            task_id=task.id,
            user_id=str(task.user_id),
            mode=task.mode,
            model=task.model,
            duration=task.duration,
            language=task.language,
            aspect_ratio=task.aspect_ratio,
            quality_tier=task.quality_tier or "economy",
            platform=task.platform or "douyin",
            url=task.url,
            text_prompt=task.text_prompt or "",
            use_lipsync=task.use_lipsync,
            use_bgm=task.use_bgm,
            # Multi-image pools
            product_image_paths=[p for p in [primary_image] + gallery_images + usage_images if p],
            product_primary_image=primary_image or "",
            product_gallery_images=gallery_images,
            product_usage_images=usage_images,
            # Presenter
            presenter_image_path=presenter_image,
            presenter_video_path=presenter_video,
            # Creative
            hook_style=task.hook_style or "result_first",
            tone_style=task.tone_style or "authentic_friend",
            cta_style=task.cta_style or "link_in_bio",
            video_goal=task.video_goal or "brand_awareness",
            persona_template=task.persona_template or "energetic_female",
        )
