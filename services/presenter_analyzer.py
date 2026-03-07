"""
services/presenter_analyzer.py
================================
Presenter (A-roll talent) understanding layer.

Responsibilities:
  - Accept presenter image, video, persona_template
  - Return a PresenterProfile used by every downstream module
  - Recommend shot types, hook styles, tone styles per persona
  - Infer speaking style from persona and voice_preset
  - Describe the presenter visually (via optional vision_client)

This module does NOT do lip-sync, NOT do generation.
It only does structured understanding.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Optional

from core.timeline_types import PresenterProfile
from core.persona_engine import get_persona_definition
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Persona knowledge ─────────────────────────────────────────────────────────

_PERSONA_SHOT_MAP: dict[str, list[str]] = {
    "bao_ma_recommendation":    ["selfie_closeup", "bathroom_demo", "kitchen_counter_talk"],
    "girlfriend_recommendation":["selfie_closeup", "mirror_demo", "handheld_reaction"],
    "review_blogger":           ["desktop_review", "side_by_side_compare", "unbox_closeup"],
    "professional_explainer":   ["desk_review", "half_body_talk", "product_detail_hold"],
    "contrast_complainer":      ["handheld_reaction", "selfie_closeup", "mirror_selfie"],
    "boyfriend_pov":            ["handheld_reaction", "selfie_closeup"],
    "energetic_female":         ["selfie_closeup", "handheld_reaction", "mirror_demo"],
    "luxury_female":            ["selfie_closeup", "texture_macro", "desktop_review"],
    "english_influencer":       ["selfie_closeup", "handheld_reaction", "over_sink_demo"],
    "chinese_kol":              ["selfie_closeup", "mirror_demo", "handheld_reaction"],
    "calm_male":                ["desktop_review", "half_body_talk", "product_detail_hold"],
}

_PERSONA_HOOK_MAP: dict[str, list[str]] = {
    "review_blogger":       ["result_first", "comparison_challenge", "authority_claim"],
    "professional_explainer":["authority_claim", "listicle_number", "result_first"],
    "contrast_complainer":  ["pain_point", "transformation_story", "result_first"],
    "bao_ma_recommendation":["pain_point", "social_proof", "transformation_story"],
    "luxury_female":        ["curiosity_gap", "authority_claim", "result_first"],
}
_DEFAULT_HOOKS = ["pain_point", "result_first", "curiosity_gap"]

_PERSONA_TONE_MAP: dict[str, list[str]] = {
    "bao_ma_recommendation":    ["warm_reassuring", "practical", "trustworthy"],
    "review_blogger":           ["confident", "clear", "educational"],
    "professional_explainer":   ["confident", "clear", "educational"],
    "luxury_female":            ["poised", "aspirational", "deliberate"],
    "contrast_complainer":      ["sarcastic_then_delighted", "authentic", "comedic"],
    "energetic_female":         ["energetic", "punchy", "authentic"],
}
_DEFAULT_TONES = ["authentic", "casual", "platform_native"]

_PERSONA_SPEAKING_STYLE: dict[str, str] = {
    "bao_ma_recommendation":    "warm_reassuring",
    "girlfriend_recommendation":"conversational_soft_sell",
    "review_blogger":           "clear_confident",
    "professional_explainer":   "clear_confident",
    "contrast_complainer":      "casual_expressive",
    "boyfriend_pov":            "casual_expressive",
    "energetic_female":         "casual_conversational",
    "luxury_female":            "poised_deliberate",
    "english_influencer":       "casual_conversational",
    "chinese_kol":              "conversational_soft_sell",
    "calm_male":                "warm_reassuring",
}

_PERSONA_LIPSYNC_MODEL: dict[str, str] = {
    "luxury_female":  "kling_avatar_1080p",
}
_DEFAULT_LIPSYNC_MODEL = "kling_avatar_720p"

_PERSONA_VOICE_PRESET: dict[str, str] = {
    "energetic_female":  "it",
    "luxury_female":     "it",
    "calm_male":         "it",
    "chinese_kol":       "zh",
    "bao_ma_recommendation":    "zh",
    "girlfriend_recommendation":"zh",
    "review_blogger":           "zh",
    "professional_explainer":   "zh",
    "contrast_complainer":      "zh",
    "boyfriend_pov":            "zh",
    "english_influencer":       "en",
}

_PERSONA_DEFAULT_VOICE: dict[str, str] = {
    "it": "pNInz6obpgDQGcFmaJgB",
    "zh": "ThT5KcBeYPX3keUQqHPh",
    "en": "21m00Tcm4TlvDq8ikWAM",
}


class PresenterAnalyzer:
    """
    Builds a PresenterProfile from presenter assets + persona template.

    Can be constructed two ways:
        PresenterAnalyzer(config)                       # standard
        PresenterAnalyzer(vision_client, logger)        # PDF blueprint DI style
    """

    def __init__(self, config_or_vision=None, _logger=None):
        if isinstance(config_or_vision, dict):
            self.config = config_or_vision
            self._vision_client = None   # Gemini vision — future
            self._log = logger
        else:
            self.config = {}
            self._vision_client = config_or_vision   # injected vision client
            self._log = _logger or logger

    # ════════════════════════════════════════════════════════════════════════
    # NEW: PDF blueprint API
    # ════════════════════════════════════════════════════════════════════════

    async def build_presenter_profile(
        self,
        presenter_image: Optional[str] = None,
        presenter_video: Optional[str] = None,
        persona_template: str = "energetic_female",
        voice_preset: Optional[str] = None,
        # Legacy keyword args (backward compat)
        face_image_path: Optional[str] = None,
        voice_id_override: Optional[str] = None,
        lipsync_model_override: Optional[str] = None,
    ) -> PresenterProfile:
        """
        Build a PresenterProfile from presenter assets and persona.

        Args:
            presenter_image:   path to face photo
            presenter_video:   path to reference video (optional)
            persona_template:  one of the PERSONA_ keys
            voice_preset:      language override (it/zh/en)
        """
        # Normalize: accept both arg styles
        face_path = presenter_image or face_image_path
        validated_face = self._validate_image(face_path)

        source_summary = {
            "presenter_image": face_path,
            "presenter_video": presenter_video,
            "voice_preset": voice_preset,
        }

        # Optional vision analysis
        visual_analysis = await self._analyze_visuals(
            presenter_image=face_path,
            presenter_video=presenter_video,
        )

        persona_def = get_persona_definition(persona_template, voice_preset or "")
        resolved_preset = voice_preset or _PERSONA_VOICE_PRESET.get(persona_template, persona_def.language or "it")
        resolved_voice_id = (
            voice_id_override
            or _PERSONA_DEFAULT_VOICE.get(resolved_preset, _PERSONA_DEFAULT_VOICE["it"])
        )

        resolved_lipsync = (
            lipsync_model_override
            or (
                _PERSONA_LIPSYNC_MODEL.get(persona_template, _DEFAULT_LIPSYNC_MODEL)
                if validated_face else "none"
            )
        )

        style_notes = self._build_style_notes(persona_template, visual_analysis)
        if persona_def.realism_notes:
            style_notes = f"{style_notes}; realism: {', '.join(persona_def.realism_notes)}"

        profile = PresenterProfile(
            presenter_id=self._build_id(face_path, presenter_video, persona_template),
            face_image_path=validated_face,
            persona_template=persona_template,
            voice_preset=resolved_preset,
            voice_id=resolved_voice_id,
            lipsync_model=resolved_lipsync,
            style_notes=style_notes,
            role_label=persona_def.role_label,
            speaking_style=persona_def.speaking_style,
            emotional_tone=persona_def.emotional_tone,
            trust_mode=persona_def.trust_mode,
            camera_behavior=persona_def.camera_behavior,
            vocabulary_style=persona_def.vocabulary_style,
            cta_style=persona_def.cta_style,
            recommended_shot_types=list(persona_def.recommended_shot_types),
            preferred_hook_styles=list(persona_def.preferred_hook_styles),
            realism_notes=list(persona_def.realism_notes),
        )

        self._log.info(
            "presenter profile built",
            extra={
                "presenter_id": profile.presenter_id,
                "persona_template": persona_template,
                "has_face": bool(validated_face),
                "lipsync_model": resolved_lipsync,
                "voice_preset": resolved_preset,
            },
        )
        return profile

    # ── Visual analysis ───────────────────────────────────────────────────────

    async def _analyze_visuals(
        self,
        presenter_image: Optional[str],
        presenter_video: Optional[str],
    ) -> dict:
        """
        Optionally call vision_client to describe presenter appearance.
        Falls back to empty dict if no client or image available.
        """
        if self._vision_client is None or (not presenter_image and not presenter_video):
            return {
                "display_name": "ugc_presenter",
                "gender_hint": "",
                "age_hint": "",
                "framing_hint": "selfie_closeup",
            }
        try:
            return await self._vision_client.describe_presenter(
                presenter_image=presenter_image,
                presenter_video=presenter_video,
            )
        except Exception as e:
            logger.warning(f"Vision analysis failed: {e}")
            return {}

    # ── Derivation helpers ────────────────────────────────────────────────────

    def _build_id(
        self,
        image_path: Optional[str],
        video_path: Optional[str],
        persona_template: str,
    ) -> str:
        base = video_path or image_path or persona_template
        h = hashlib.md5(base.encode()).hexdigest()[:12]
        return f"presenter_{h}"

    def _validate_image(self, path: Optional[str]) -> Optional[str]:
        """Return path if it exists and is a valid image, else None."""
        if not path:
            return None
        p = Path(path)
        if p.exists() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            return str(p)
        return None

    def _build_style_notes(self, persona_template: str, visual_analysis: dict) -> str:
        base = _PERSONA_SPEAKING_STYLE.get(persona_template, "natural")
        visual = visual_analysis.get("framing_hint", "")
        notes = f"Speaking style: {base}"
        if visual:
            notes += f". Recommended framing: {visual}"
        return notes

    # ── Public recommendation helpers ─────────────────────────────────────────

    def recommend_shots(self, persona_template: str) -> list[str]:
        return _PERSONA_SHOT_MAP.get(persona_template, ["selfie_closeup", "half_body_talk", "product_holdup"])

    def recommend_hooks(self, persona_template: str) -> list[str]:
        return _PERSONA_HOOK_MAP.get(persona_template, _DEFAULT_HOOKS)

    def recommend_tones(self, persona_template: str) -> list[str]:
        return _PERSONA_TONE_MAP.get(persona_template, _DEFAULT_TONES)

    def infer_speaking_style(self, persona_template: str, voice_preset: str = "it") -> str:
        if persona_template in _PERSONA_SPEAKING_STYLE:
            return _PERSONA_SPEAKING_STYLE[persona_template]
        if "female" in voice_preset.lower():
            return "casual_conversational"
        return "natural"
