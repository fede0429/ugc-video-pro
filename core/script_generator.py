"""
core/script_generator.py
========================
Timeline and legacy script generation for the UGC pipeline.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


from core.timeline_types import (
    PresenterProfile,
    ProductProfile,
    TimelineScript,
    TimelineSegment,
    UGCVideoRequest,
    make_segment_id,
)
from utils.logger import get_logger
from core.ugc_shot_library import UGCShotLibrary

logger = get_logger(__name__)


@dataclass
class VideoScene:
    segment_index: int
    duration_seconds: int
    scene_prompt: str
    continuation_hint: str
    camera_movement: str
    product_focus: bool
    audio_description: str


@dataclass
class VideoScript:
    scenes: list[VideoScene]
    total_duration: int
    num_segments: int
    model_used: str
    language: str
    product_description: str
    raw_json: str = field(default="", repr=False)

    @property
    def segment_durations(self) -> list[int]:
        return [s.duration_seconds for s in self.scenes]


TIMELINE_SYSTEM_PROMPT = """You are a top UGC video director creating a short-form product video.

## INPUTS
Product: {product_summary}
Presenter persona: {persona_style}
Total duration: {total_duration}s
Language: {language}, Platform: {platform}
Hook: {hook_pattern}

## RULES
- A-roll = presenter to camera. spoken_line must be natural.
- B-roll = product demonstration. b_roll_prompt must preserve the exact product.
- overlay_text = short, 1-6 words.
- First segment should be the hook.
- End with a CTA.

Return ONLY valid JSON array with:
[
  {{
    "segment_index": 0,
    "track_type": "a_roll" | "b_roll",
    "duration_seconds": 5,
    "spoken_line": "",
    "b_roll_prompt": "",
    "scene_description": "",
    "overlay_text": "",
    "camera_movement": "static",
    "continuation_hint": "",
    "emotion": "",
    "shot_type": "",
    "visual_prompt": "",
    "product_focus": ""
  }}
]
"""

SYSTEM_PROMPT_TEMPLATE = """You are an expert UGC product video scriptwriter for e-commerce.

## INPUT CONTEXT
- Product analysis: {product_analysis}
- URL content: {url_content}
- Total duration: {total_duration}s, Segments: {num_segments}
- Segment durations: {segment_durations}
- Model: {model_name}, Language: {language}, Aspect: {aspect_ratio}

## RULES
1. NEVER alter the product appearance. Preserve exact colors, materials, brand text.
2. Return ONLY a valid JSON array.

Each element:
{{
    "segment_index": <int>, "duration_seconds": <int>,
    "scene_prompt": "<prompt>", "continuation_hint": "<end-frame state>",
    "camera_movement": "<movement>", "product_focus": <bool>,
    "audio_description": "<audio>"
}}
"""


MODEL_SPECIFIC_INSTRUCTIONS = {
    "veo_3": "- Reference image = literal first frame",
    "veo_3_pro": "- Cinematic precision",
    "veo_31_pro": "- Most capable Veo model",
    "sora_2": "- Self-contained descriptions",
    "sora_2_pro": "- Self-contained descriptions",
    "seedance_2": "- Strong camera control",
}


class ScriptGenerator:
    def __init__(self, config: dict):
        self.config = config
        self.shot_library = UGCShotLibrary()
        gemini_config = config.get("gemini", {})
        api_key = gemini_config.get("api_key", "")
        self.model_name = gemini_config.get("model", "gemini-2.0-flash-exp")
        self.fallback_model = gemini_config.get("fallback_model", "gemini-1.5-flash")

        if not api_key:
            logger.warning("Gemini API key not configured")
            self._client = None
            self._fallback_client = None
        else:
            try:
                import google.generativeai as genai
                self._genai = genai
                genai.configure(api_key=api_key)
                self._client = genai.GenerativeModel(self.model_name)
                self._fallback_client = genai.GenerativeModel(self.fallback_model)
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")
                self._client = None
                self._fallback_client = None
                self._genai = None

    async def generate_timeline(
        self,
        request: UGCVideoRequest,
        product_profile: ProductProfile,
        presenter_profile: PresenterProfile,
        plan=None,
        production_plan=None,
    ) -> TimelineScript:
        plan = production_plan or plan
        if plan is None:
            raise ValueError("generate_timeline requires plan or production_plan")

        if getattr(plan, "segments_json", None):
            segments = self._segments_from_plan(plan.segments_json, request.task_id, product_profile)
            return TimelineScript(
                task_id=request.task_id,
                language=request.language,
                segments=segments,
                raw_json=json.dumps(plan.to_dict() if hasattr(plan, "to_dict") else {"segments": plan.segments_json}, ensure_ascii=False),
            )

        product_summary = self._format_product_profile(product_profile)
        total_duration = getattr(plan, "total_duration", None) or sum(getattr(plan, "segment_durations", []) or [request.duration])
        prompt = TIMELINE_SYSTEM_PROMPT.format(
            product_summary=product_summary,
            persona_style=presenter_profile.style_notes or presenter_profile.persona_template,
            total_duration=total_duration,
            language=request.language,
            platform=request.platform,
            hook_pattern=getattr(plan, "hook_style", "") or getattr(plan, "hook_pattern", "result_first"),
        )
        raw_json = await self._call_gemini(prompt)
        segments = self._parse_timeline_segments(raw_json, request.task_id, product_profile)
        return TimelineScript(
            task_id=request.task_id,
            language=request.language,
            segments=segments,
            raw_json=raw_json,
        )

    def _segments_from_plan(self, segments_json: list[dict], task_id: str, product_profile: ProductProfile) -> list[TimelineSegment]:
        segments: list[TimelineSegment] = []
        for i, item in enumerate(segments_json):
            track = item.get("track") or item.get("track_type") or "b_roll"
            duration = item.get("duration") or item.get("duration_seconds") or 5
            scene_purpose = item.get("scene_purpose", "")
            point = item.get("overlay_text") or item.get("visual_goal") or item.get("product_action") or ""
            b_roll_prompt = ""
            visual_prompt = ""
            shot_type = str(item.get("shot_type", ""))
            camera_movement = str(item.get("camera_movement", ""))
            if track == "b_roll":
                b_roll_prompt, shot_type, camera_movement = self._build_broll_prompt(
                    product_profile=product_profile,
                    scene_purpose=scene_purpose or item.get("visual_goal", ""),
                    product_action=item.get("product_action", ""),
                    point=point,
                    shot_type_hint=shot_type,
                )
                visual_prompt = b_roll_prompt
            segments.append(TimelineSegment(
                segment_id=make_segment_id(),
                segment_index=i,
                track_type=track,
                duration_seconds=Decimal(str(duration)),
                spoken_line=str(item.get("spoken_line", "")),
                emotion=str(item.get("emotion", "")),
                shot_type=shot_type or str(item.get("shot_type", "")),
                visual_prompt=visual_prompt,
                product_focus=str(item.get("product_focus", "")),
                b_roll_prompt=b_roll_prompt,
                scene_description=str(item.get("scene_description", scene_purpose)),
                overlay_text=str(item.get("overlay_text", "")),
                camera_movement=camera_movement or str(item.get("camera_movement", self._default_camera(scene_purpose or item.get("product_action", "")))),
                continuation_hint=str(item.get("continuation_hint", "")),
            ))
        return segments

    def _parse_timeline_segments(self, raw_json: str, task_id: str, product_profile: ProductProfile) -> list[TimelineSegment]:
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"```(?:json)?\s*", "", cleaned).strip("`").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"[task={task_id}] Timeline JSON parse error: {e}")
            data = self._fallback_timeline_data()

        segments = []
        for i, item in enumerate(data):
            dur = item.get("duration_seconds", 8)
            b_roll_prompt = str(item.get("b_roll_prompt", ""))
            visual_prompt = str(item.get("visual_prompt", "")) or b_roll_prompt
            if item.get("track_type", "b_roll") == "b_roll" and not b_roll_prompt:
                b_roll_prompt, suggested_shot_type, suggested_camera = self._build_broll_prompt(
                    product_profile,
                    item.get("scene_description", ""),
                    item.get("shot_type", ""),
                    item.get("overlay_text", ""),
                    shot_type_hint=str(item.get("shot_type", "")),
                )
                visual_prompt = visual_prompt or b_roll_prompt
                if not item.get("shot_type"):
                    item["shot_type"] = suggested_shot_type
                if not item.get("camera_movement"):
                    item["camera_movement"] = suggested_camera
            seg = TimelineSegment(
                segment_id=make_segment_id(),
                segment_index=i,
                track_type=item.get("track_type", "b_roll"),
                duration_seconds=Decimal(str(dur)),
                spoken_line=str(item.get("spoken_line", "")),
                b_roll_prompt=b_roll_prompt,
                scene_description=str(item.get("scene_description", "")),
                overlay_text=str(item.get("overlay_text", "")),
                camera_movement=str(item.get("camera_movement", "static")),
                continuation_hint=str(item.get("continuation_hint", "")),
                emotion=str(item.get("emotion", "")),
                shot_type=str(item.get("shot_type", "")),
                visual_prompt=visual_prompt,
                product_focus=str(item.get("product_focus", "")),
            )
            segments.append(seg)
        return segments

    def _build_broll_prompt(self, product_profile: ProductProfile, scene_purpose: str, product_action: str, point: str, shot_type_hint: str = "") -> tuple[str, str, str]:
        brand = product_profile.brand or "generic product"
        desc = product_profile.description or "premium product"
        colors = ", ".join(str(c) for c in product_profile.colors[:3]) if product_profile.colors else ""
        anchors = ", ".join(product_profile.consistency_anchors[:4]) if product_profile.consistency_anchors else ""
        features = ", ".join(product_profile.key_features[:3] or product_profile.selling_points[:3])
        purpose = scene_purpose or product_action or "product demo"
        template = self.shot_library.choose_template(
            purpose=purpose,
            product_type=product_profile.product_type or product_profile.category,
            description=product_profile.description,
        )
        shot_type = shot_type_hint or template.shot_type
        camera = template.camera_movement or self._default_camera(scene_purpose or product_action)
        keyword_blob = ", ".join(template.prompt_keywords)
        overlay = point or (template.overlay_patterns[0] if template.overlay_patterns else "")
        prompt = (
            f"UGC {template.shot_type} shot, {template.framing}, {camera}. "
            f"Show {brand} {desc}. Scene purpose: {purpose}. "
            f"Action: {product_action or 'natural creator demonstration'}. "
            f"Highlight: {overlay}. Features: {features}. "
            f"Consistency anchors: {anchors}. Colors/materials: {colors}. "
            f"Style keywords: {keyword_blob}. Keep product exact, creator-friendly, phone-native realism, commercial clarity."
        )
        return " ".join(prompt.split()), shot_type, camera

    def _default_camera(self, scene_purpose: str) -> str:
        purpose = (scene_purpose or "").lower()
        if "hook" in purpose:
            return "push_in"
        if "proof" in purpose:
            return "macro_dolly"
        if "solution" in purpose:
            return "handheld_pan"
        return "static"

    def _fallback_timeline_data(self) -> list[dict]:
        return [
            {"segment_index": 0, "track_type": "a_roll", "duration_seconds": 5,
             "spoken_line": "Honestly, this worked better than I expected.", "b_roll_prompt": "",
             "scene_description": "Hook: presenter introduces product", "overlay_text": "Worth trying",
             "camera_movement": "static", "continuation_hint": "Presenter camera-facing", "emotion": "surprised_authentic", "shot_type": "selfie_closeup"},
            {"segment_index": 1, "track_type": "b_roll", "duration_seconds": 8,
             "spoken_line": "", "b_roll_prompt": "Close-up product demo, creator style, natural light, handheld macro, 9:16 portrait",
             "scene_description": "Product detail reveal", "overlay_text": "Easy to use",
             "camera_movement": "dolly_in", "continuation_hint": "Product centered, macro close-up", "shot_type": "usage_demo"},
            {"segment_index": 2, "track_type": "a_roll", "duration_seconds": 6,
             "spoken_line": "What I like most is how easy it fits into my routine.", "b_roll_prompt": "",
             "scene_description": "Presenter demonstrates product", "overlay_text": "",
             "camera_movement": "static", "continuation_hint": "Presenter with product in hand", "emotion": "warm_casual", "shot_type": "handheld_reaction"},
            {"segment_index": 3, "track_type": "b_roll", "duration_seconds": 7,
             "spoken_line": "", "b_roll_prompt": "Lifestyle shot in a real home, warm light, product in use, 9:16 portrait",
             "scene_description": "Lifestyle context", "overlay_text": "Real results",
             "camera_movement": "orbit", "continuation_hint": "Product in lifestyle setting", "shot_type": "result_reveal"},
            {"segment_index": 4, "track_type": "a_roll", "duration_seconds": 5,
             "spoken_line": "If you're curious, check it out now.", "b_roll_prompt": "",
             "scene_description": "CTA close", "overlay_text": "Check it out",
             "camera_movement": "static", "continuation_hint": "Presenter smiling", "emotion": "clear_confident", "shot_type": "selfie_closeup"},
        ]

    async def generate_script(
        self,
        product_analysis: dict,
        segment_durations: list[int],
        model_key: str,
        language: str = "zh",
        url_content: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> VideoScript:
        total_duration = sum(segment_durations)
        num_segments = len(segment_durations)
        logger.info(f"Generating legacy script: {num_segments}x{total_duration}s model={model_key}")

        model_instructions = MODEL_SPECIFIC_INSTRUCTIONS.get(model_key, MODEL_SPECIFIC_INSTRUCTIONS["veo_31_pro"])
        product_desc = self._format_product_analysis(product_analysis)
        url_desc = url_content[:2000] if url_content else "Not provided"

        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            product_analysis=product_desc, url_content=url_desc,
            total_duration=total_duration, num_segments=num_segments,
            segment_durations=segment_durations,
            model_name=model_key.upper().replace("_", " "),
            language=language, aspect_ratio=aspect_ratio,
            model_specific_instructions=model_instructions,
        )
        scenes_json = await self._call_gemini(prompt)
        scenes = self._parse_scenes(scenes_json, segment_durations)
        return VideoScript(
            scenes=scenes, total_duration=total_duration,
            num_segments=num_segments, model_used=model_key,
            language=language, product_description=product_desc,
            raw_json=scenes_json,
        )

    def _format_product_profile(self, profile: ProductProfile) -> str:
        lines = []
        for attr, label in [
            ("product_type", "Type"),
            ("brand", "Brand"),
            ("description", "Desc"),
            ("text_on_product", "Logo"),
            ("key_features", "Features"),
            ("target_audience", "Audience"),
            ("selling_points", "Selling Points"),
            ("demo_actions", "Demo Actions"),
        ]:
            val = getattr(profile, attr, None)
            if val:
                lines.append(f"{label}: {', '.join(val) if isinstance(val, list) else val}")
        if profile.colors:
            lines.append(f"Colors: {', '.join(str(c) for c in profile.colors)}")
        if profile.materials:
            lines.append(f"Materials: {', '.join(profile.materials)}")
        return "\n".join(lines) or "Product details not available"

    def _format_product_analysis(self, analysis: dict) -> str:
        if not analysis:
            return "Product details not available"
        lines = []
        for key in ("type", "brand", "description", "colors", "materials", "text_on_product", "shape"):
            val = analysis.get(key)
            if val:
                lines.append(f"{key.title()}: {', '.join(str(v) for v in val) if isinstance(val, list) else val}")
        return "\n".join(lines) or str(analysis)

    async def _call_gemini(self, prompt: str) -> str:
        if not self._client:
            return json.dumps(self._fallback_timeline_data(), ensure_ascii=False)
        gen_cfg = self._genai.types.GenerationConfig(
            temperature=0.7, top_p=0.9, response_mime_type="application/json", max_output_tokens=4096
        )
        try:
            resp = await self._client.generate_content_async(prompt, generation_config=gen_cfg)
            return resp.text
        except Exception as e:
            logger.warning(f"Primary Gemini failed: {e}")
            try:
                resp = await self._fallback_client.generate_content_async(
                    prompt, generation_config=self._genai.types.GenerationConfig(temperature=0.7, max_output_tokens=4096)
                )
                return resp.text
            except Exception as e2:
                logger.error(f"Fallback Gemini failed: {e2}")
                return json.dumps(self._fallback_timeline_data(), ensure_ascii=False)

    def _parse_scenes(self, raw_json: str, segment_durations: list[int]) -> list[VideoScene]:
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"```(?:json)?\s*", "", cleaned).strip("`").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = [{"scene_prompt": f"Product shot {i}", "continuation_hint": "",
                     "camera_movement": "static", "product_focus": True, "audio_description": "music"} for i in range(len(segment_durations))]

        scenes = []
        for i, item in enumerate(data):
            duration = segment_durations[i] if i < len(segment_durations) else 8
            scenes.append(VideoScene(
                segment_index=i, duration_seconds=duration,
                scene_prompt=str(item.get("scene_prompt", f"Product shot {i+1}")),
                continuation_hint=str(item.get("continuation_hint", "")),
                camera_movement=str(item.get("camera_movement", "static")),
                product_focus=bool(item.get("product_focus", True)),
                audio_description=str(item.get("audio_description", "ambient")),
            ))
        while len(scenes) < len(segment_durations):
            idx = len(scenes)
            scenes.append(VideoScene(idx, segment_durations[idx], "Product hero shot", "", "static", True, "ambient"))
        return scenes[:len(segment_durations)]
