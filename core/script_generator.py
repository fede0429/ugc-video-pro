"""
core/script_generator.py
========================
AI-powered video script generator using Google Gemini.

Generates a structured JSON array of video scenes with:
    - Detailed generation prompts per segment
    - Frame transition hints
    - Camera movement instructions
    - Audio descriptions

CRITICAL PRINCIPLE:
    Product images are SACRED.
    All prompts must PRESERVE the exact appearance of the product.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VideoScene:
    """A single video segment / scene in the generated script."""
    segment_index: int
    duration_seconds: int
    scene_prompt: str
    continuation_hint: str
    camera_movement: str
    product_focus: bool
    audio_description: str


@dataclass
class VideoScript:
    """Complete script for a video with all segments."""
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


SYSTEM_PROMPT_TEMPLATE = """You are an expert UGC product video scriptwriter for e-commerce.

Your task is to create a detailed, segmented video script for AI video generation.

## INPUT CONTEXT
- Product analysis: {product_analysis}
- URL content (if provided): {url_content}
- Total video duration: {total_duration} seconds
- Number of segments: {num_segments}
- Each segment duration: {segment_durations} (list of seconds per segment)
- Video model: {model_name}
- Output language for narration: {language}
- Aspect ratio: {aspect_ratio} (portrait/vertical)

## CRITICAL PRODUCT FIDELITY RULES
1. NEVER alter, modify, or reimagine the product's appearance
2. Use EXACT colors, materials, brand text as described in the product analysis
3. Describe product details with EXTREME precision to preserve identity
4. If the product has text/logo, include exact text in every prompt where visible

## OUTPUT FORMAT
Return ONLY a valid JSON array. No markdown, no explanation.

Each element:
{{
    "segment_index": <integer, 0-based>,
    "duration_seconds": <integer, from segment_durations list>,
    "scene_prompt": "<Complete video generation prompt>",
    "continuation_hint": "<EXACT VISUAL STATE at the END of this segment>",
    "camera_movement": "<Single camera movement>",
    "product_focus": <true/false>,
    "audio_description": "<ambient sounds in {language}>"
}}

## SCENE PROGRESSION
1. Segment 0: Establishing shot — product approaching
2. Middle: Close-up details, feature highlights, lifestyle context
3. Final: Hero shot or call-to-action
4. Camera movements should vary

## PROMPT ENGINEERING FOR {model_name}
{model_specific_instructions}

Generate exactly {num_segments} scenes. Return ONLY the JSON array."""


MODEL_SPECIFIC_INSTRUCTIONS = {
    "veo_3": """- Veo uses reference image as LITERAL first frame
- For continuation prompts: describe only MOTION and CHANGES
- Add "(no subtitles)" to any dialogue prompts
- Use [brackets] for sound effects""",

    "veo_3_pro": """- Veo Pro: reference image = LITERAL first frame
- Describe motion with cinematic precision
- "(no subtitles)" for any spoken word
- Focus on tactile/material descriptions for luxury feel""",

    "veo_31_pro": """- Veo 3.1 Pro is the most capable model
- Reference image = exact first frame
- Use professional cinematography language: "rack focus", "motivated lighting"
- Handles complex multi-element scenes very well""",

    "sora_2": """- Sora treats reference as STYLE REFERENCE (not exact frame)
- Write self-contained prompts (slight visual drift expected)
- Focus on product and environment, not human models""",

    "sora_2_pro": """- Sora Pro: longer clips (up to 25s)
- Self-contained scene descriptions
- Pro quality handles fine details better""",

    "seedance_2": """- Seedance: strong camera control
- Camera: zoom_in, zoom_out, pan_left, pan_right, tilt_up, tilt_down, static
- Reference locking is strong""",
}


class ScriptGenerator:
    """Generates segmented video scripts using Google Gemini."""

    def __init__(self, config: dict):
        self.config = config
        gemini_config = config.get("gemini", {})
        api_key = gemini_config.get("api_key", "")
        self.model_name = gemini_config.get("model", "gemini-2.0-flash-exp")
        self.fallback_model = gemini_config.get("fallback_model", "gemini-1.5-flash")

        if not api_key:
            logger.warning("Gemini API key not configured — script generation will use fallback")
            self._client = None
        else:
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(self.model_name)
            self._fallback_client = genai.GenerativeModel(self.fallback_model)

    async def generate_script(
        self,
        product_analysis: dict,
        segment_durations: list[int],
        model_key: str,
        language: str = "zh",
        url_content: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> VideoScript:
        """Generate a complete video script."""
        total_duration = sum(segment_durations)
        num_segments = len(segment_durations)

        logger.info(
            f"Generating script: {num_segments} segments, "
            f"{total_duration}s total, model={model_key}, lang={language}"
        )

        model_instructions = MODEL_SPECIFIC_INSTRUCTIONS.get(
            model_key, MODEL_SPECIFIC_INSTRUCTIONS["veo_31_pro"],
        )

        product_desc = self._format_product_analysis(product_analysis)
        url_desc = url_content[:2000] if url_content else "Not provided"

        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            product_analysis=product_desc,
            url_content=url_desc,
            total_duration=total_duration,
            num_segments=num_segments,
            segment_durations=segment_durations,
            model_name=model_key.upper().replace("_", " "),
            language=language,
            aspect_ratio=aspect_ratio,
            model_specific_instructions=model_instructions,
        )

        scenes_json = await self._call_gemini(prompt)
        scenes = self._parse_scenes(scenes_json, segment_durations)

        script = VideoScript(
            scenes=scenes,
            total_duration=total_duration,
            num_segments=num_segments,
            model_used=model_key,
            language=language,
            product_description=product_desc,
            raw_json=scenes_json,
        )

        logger.info(f"Script generated: {len(scenes)} scenes, total {total_duration}s")
        return script

    def _format_product_analysis(self, analysis: dict) -> str:
        """Format product analysis dict into a readable description."""
        if not analysis:
            return "Product details not available"

        lines = []
        if analysis.get("type"):
            lines.append(f"Type: {analysis['type']}")
        if analysis.get("brand"):
            lines.append(f"Brand: {analysis['brand']}")
        if analysis.get("description"):
            lines.append(f"Description: {analysis['description']}")
        if analysis.get("colors"):
            colors = analysis["colors"]
            if isinstance(colors, list):
                color_strs = [
                    f"{c.get('description', '')} ({c.get('hex', '')})" if isinstance(c, dict) else str(c)
                    for c in colors
                ]
                lines.append(f"Colors: {', '.join(color_strs)}")
        if analysis.get("materials"):
            materials = analysis["materials"]
            if isinstance(materials, list):
                lines.append(f"Materials: {', '.join(str(m) for m in materials)}")
        if analysis.get("text_on_product"):
            lines.append(f"Text/Logo: {analysis['text_on_product']}")
        if analysis.get("shape"):
            lines.append(f"Shape: {analysis['shape']}")
        if analysis.get("lighting"):
            lines.append(f"Surface lighting: {analysis['lighting']}")

        return "\n".join(lines) if lines else str(analysis)

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API and return raw response text."""
        if not self._client:
            logger.warning("Gemini client not initialized — using fallback script")
            return self._generate_fallback_script_json()

        generation_config = genai.types.GenerationConfig(
            temperature=0.7, top_p=0.9,
            response_mime_type="application/json",
            max_output_tokens=4096,
        )

        try:
            response = await self._client.generate_content_async(
                prompt, generation_config=generation_config,
            )
            return response.text
        except Exception as e:
            logger.warning(f"Primary Gemini model failed: {e}, trying fallback")
            try:
                response = await self._fallback_client.generate_content_async(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7, max_output_tokens=4096,
                    ),
                )
                return response.text
            except Exception as e2:
                logger.error(f"Fallback Gemini also failed: {e2}")
                return self._generate_fallback_script_json()

    def _parse_scenes(self, raw_json: str, segment_durations: list[int]) -> list[VideoScene]:
        """Parse raw JSON response into VideoScene objects."""
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"```(?:json)?\s*", "", cleaned).strip("`").strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse script JSON: {e} — using fallback")
            data = json.loads(self._generate_fallback_script_json())

        scenes = []
        for i, item in enumerate(data):
            duration = segment_durations[i] if i < len(segment_durations) else 8
            scene = VideoScene(
                segment_index=i,
                duration_seconds=duration,
                scene_prompt=str(item.get("scene_prompt", f"Product showcase shot {i + 1}")),
                continuation_hint=str(item.get("continuation_hint", "")),
                camera_movement=str(item.get("camera_movement", "static")),
                product_focus=bool(item.get("product_focus", True)),
                audio_description=str(item.get("audio_description", "ambient background music")),
            )
            scenes.append(scene)

        while len(scenes) < len(segment_durations):
            idx = len(scenes)
            scenes.append(VideoScene(
                segment_index=idx,
                duration_seconds=segment_durations[idx],
                scene_prompt="Product hero shot, warm studio lighting, sharp focus on product details",
                continuation_hint="Product centered on clean background, static camera",
                camera_movement="slow dolly in",
                product_focus=True,
                audio_description="Subtle ambient music",
            ))

        return scenes[:len(segment_durations)]

    def _generate_fallback_script_json(self) -> str:
        """Generate a generic fallback script when Gemini is unavailable."""
        return json.dumps([
            {
                "segment_index": 0, "duration_seconds": 8,
                "scene_prompt": "Product showcase: elegant product on clean white marble surface, soft diffused studio lighting. Camera slowly approaches from medium distance to close-up. Shallow depth of field, bokeh background. Photorealistic, 9:16 portrait.",
                "continuation_hint": "Product in close-up, centered, warm studio light from upper right, marble surface visible.",
                "camera_movement": "slow dolly in", "product_focus": True,
                "audio_description": "Soft ambient music, clean studio atmosphere",
            },
            {
                "segment_index": 1, "duration_seconds": 8,
                "scene_prompt": "Product detail showcase: extreme close-up revealing textures. Camera slowly orbits around the product. Dramatic side lighting emphasizes surface quality.",
                "continuation_hint": "Product orbiting complete, angled at 45 degrees, dramatic side lighting.",
                "camera_movement": "slow orbit", "product_focus": True,
                "audio_description": "Subtle whoosh of camera movement, ambient tone",
            },
            {
                "segment_index": 2, "duration_seconds": 8,
                "scene_prompt": "Product lifestyle shot: product in beautiful lifestyle context, natural window light. Camera pulls back slightly to reveal elegant surroundings.",
                "continuation_hint": "Product in lifestyle environment, natural window light, camera slightly pulled back.",
                "camera_movement": "slow pull back", "product_focus": True,
                "audio_description": "Warm ambient interior sounds, light music",
            },
            {
                "segment_index": 3, "duration_seconds": 6,
                "scene_prompt": "Final hero shot: product floating against deep gradient background, multiple light beams highlighting product. Camera slowly tilts up. Premium commercial photography feel.",
                "continuation_hint": "Product centered, full-frame hero shot, gradient background, premium lighting.",
                "camera_movement": "slow tilt up", "product_focus": True,
                "audio_description": "Triumphant ambient music swell, clean ending",
            },
        ])
