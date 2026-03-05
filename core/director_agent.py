"""
core/director_agent.py
======================
Director Agent — AI-powered orchestration brain for UGC Video Pro.

Uses GPT 5.2 (via KIE.AI Chat API) to make intelligent decisions about
the entire video production pipeline:

    1. Analyze inputs → determine production strategy
    2. Select optimal model → cost/quality tradeoff
    3. Plan segments → scene count, durations, progression
    4. Generate script → via LLM with product context
    5. Supervise frame chaining → delegate to FrameChainer
    6. Quality control → evaluate result, retry if needed
    7. Multi-language TTS → parallel audio generation
    8. Budget control → track spend, auto-downgrade if over limit

The Director replaces hardcoded orchestrator logic with LLM-driven
decision-making while keeping deterministic operations (FFmpeg, frame
extraction, file I/O) as tool functions.

Architecture:
    Director Agent (GPT 5.2)  ← brain, makes all decisions
        ├─ ScriptGenerator     ← generates scene prompts
        ├─ FrameChainer        ← sequential video generation + frame extraction
        ├─ VideoStitcher       ← FFmpeg concat/crossfade
        ├─ TTSService          ← multi-language voiceover
        ├─ LipSyncService      ← avatar lip sync
        ├─ ImageAnalyzer       ← product image analysis
        └─ KieGateway          ← unified API for all model calls
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from services.kie_gateway import KieGateway
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Cost estimates per model (USD) — used by Director for budgeting
# ──────────────────────────────────────────────────────────────

MODEL_COSTS = {
    "seedance_15":    {"per_10s": 0.08,  "label": "Seedance 1.5 Pro"},
    "veo_31_fast":    {"per_video": 0.30, "label": "Veo 3.1 Fast"},
    "veo_31_quality": {"per_video": 1.25, "label": "Veo 3.1 Quality"},
    "runway":         {"per_5s": 0.06,   "label": "Runway"},
    "runway_1080p":   {"per_5s": 0.15,   "label": "Runway 1080p"},
    "sora_2":         {"per_10s": 0.175, "label": "Sora 2"},
    "kling_26":       {"per_10s": 0.275, "label": "Kling 2.6"},
    "kling_30":       {"per_s_1080p": 0.20, "label": "Kling 3.0"},
    "hailuo":         {"per_6s": 0.15,   "label": "Hailuo 2.3"},
}

BUDGET_TIERS = {
    "economy":  {"max_usd": 0.60, "preferred_models": ["seedance_15", "runway"]},
    "premium":  {"max_usd": 2.50, "preferred_models": ["veo_31_fast", "seedance_15"]},
    "china":    {"max_usd": 1.50, "preferred_models": ["kling_30", "hailuo", "seedance_15"]},
}


# ──────────────────────────────────────────────────────────────
# Director System Prompt
# ──────────────────────────────────────────────────────────────

DIRECTOR_SYSTEM_PROMPT = """You are the Director Agent of UGC Video Pro — an AI video production system for e-commerce product videos.

Your role is like a film director: you analyze the product, plan the shoot, choose the right equipment (models), write the script, and supervise production. You make creative and budget decisions.

## YOUR CAPABILITIES (Tools)
You have access to these production tools:
1. `analyze_product` — Analyze a product image to extract colors, materials, shape, brand
2. `extract_url` — Extract product info from a URL
3. `generate_script` — Generate a video script with scene prompts
4. `select_model` — Choose the best video model based on quality tier and budget
5. `estimate_cost` — Calculate expected cost before generation
6. `generate_video_segments` — Generate all video clips via frame chaining
7. `stitch_video` — Combine clips into final video
8. `generate_tts` — Generate voiceover in specified language(s)
9. `generate_lipsync` — Apply lip-sync to avatar video

## PRODUCTION RULES (MUST FOLLOW)
1. **Product images are SACRED** — never alter, modify, or reimagine the product appearance
2. **Frame chaining is THE most critical feature** — ensure visual continuity between segments
3. **Budget limits are hard** — never exceed the budget tier. Downgrade model if needed
4. **Three languages equally important** — Italian (priority), Chinese, English
5. **Audio-First principle** — TTS audio defines timing, video follows audio rhythm

## DECISION FRAMEWORK
Given the inputs (images, URL, text, duration, language, quality tier), output a production plan as JSON:

```json
{
    "strategy": "brief description of creative approach",
    "model_selection": {
        "video_model": "model_key",
        "reason": "why this model"
    },
    "segment_plan": {
        "num_segments": N,
        "segment_durations": [8, 8, 8, 6],
        "scene_progression": ["establishing", "detail", "lifestyle", "hero"]
    },
    "estimated_cost_usd": 0.00,
    "tts_plan": {
        "languages": ["it", "zh", "en"],
        "style": "warm, professional"
    },
    "quality_threshold": 0.7,
    "max_retries": 1
}
```

## QUALITY TIERS
- **economy**: Budget-friendly. Use Seedance 1.5 Pro or Runway. Max $0.60/video
- **premium**: Best quality. Use Veo 3.1 Fast/Quality. Max $2.50/video
- **china**: Optimized for Chinese market. Use Kling 3.0 or Hailuo. Max $1.50/video

## MODEL CHARACTERISTICS
- **Veo 3.1** — Best frame chaining (exact first frame), max 8s/clip, $0.30-1.25
- **Seedance 1.5 Pro** — Strong reference lock, max 10s/clip, $0.08/10s, great value
- **Sora 2** — Style reference (may drift), max 12s/clip, $0.175/10s
- **Runway** — Fast generation, max 10s/clip, $0.06/5s
- **Kling 3.0** — Built-in audio, max 10s/clip, $0.20/s at 1080p
- **Hailuo 2.3** — High fidelity, max 6s/clip, $0.15/6s

Always respond with valid JSON only. No markdown, no explanation outside JSON."""


# ──────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────

@dataclass
class ProductionPlan:
    """Director's production plan for a video."""
    strategy: str
    video_model: str
    model_reason: str
    num_segments: int
    segment_durations: list[int]
    scene_progression: list[str]
    estimated_cost_usd: float
    tts_languages: list[str]
    tts_style: str
    quality_threshold: float
    max_retries: int
    raw_json: str = ""


@dataclass
class ProductionResult:
    """Final result of a directed production."""
    video_path: str
    drive_link: Optional[str]
    duration: int
    num_segments: int
    model: str
    elapsed_seconds: float
    total_cost_usd: float
    plan: Optional[ProductionPlan] = None
    segment_paths: list[str] = field(default_factory=list)
    tts_paths: dict = field(default_factory=dict)  # {lang: path}
    script_json: str = ""
    product_analysis: dict = field(default_factory=dict)
    quality_score: Optional[float] = None
    director_decisions: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Director Agent
# ──────────────────────────────────────────────────────────────

class DirectorAgent:
    """
    AI Director that orchestrates the entire video production pipeline.

    Uses GPT 5.2 via KIE.AI Chat API to make intelligent production decisions,
    then delegates execution to specialized tool modules.

    Usage:
        director = DirectorAgent(config)
        result = await director.produce(request, progress_cb, status_cb)
    """

    # LLM models for director brain (primary + fallback)
    PRIMARY_MODEL = "gemini-3-pro"
    FALLBACK_MODEL = "gemini-3-flash"

    def __init__(self, config: dict):
        self.config = config
        self.gateway = KieGateway(config)
        self._decisions: list[str] = []

        # Director-specific config
        director_config = config.get("director", {})
        self._primary_model = director_config.get("model", self.PRIMARY_MODEL)
        self._fallback_model = director_config.get("fallback_model", self.FALLBACK_MODEL)
        self._max_planning_retries = director_config.get("max_planning_retries", 2)

    def _log_decision(self, decision: str):
        """Record a director decision for audit trail."""
        self._decisions.append(f"[{time.strftime('%H:%M:%S')}] {decision}")
        logger.info(f"[Director] {decision}")

    # ── Planning Phase ──────────────────────────────────────

    async def create_production_plan(
        self,
        product_analysis: dict,
        duration: int,
        language: str,
        quality_tier: str,
        url_content: Optional[str] = None,
        user_model_override: Optional[str] = None,
        num_images: int = 1,
    ) -> ProductionPlan:
        """
        Ask the Director LLM to create a production plan.

        Args:
            product_analysis: Dict from ImageAnalyzer
            duration: Target video duration in seconds
            language: Comma-separated language codes (e.g. "it,zh,en")
            quality_tier: "economy", "premium", or "china"
            url_content: Optional product URL content
            user_model_override: If user explicitly chose a model
            num_images: Number of product images uploaded

        Returns:
            ProductionPlan with all decisions made
        """
        self._log_decision(
            f"Planning: duration={duration}s, tier={quality_tier}, "
            f"lang={language}, images={num_images}"
        )

        # Build context for the Director
        languages = [l.strip() for l in language.split(",") if l.strip()]
        budget = BUDGET_TIERS.get(quality_tier, BUDGET_TIERS["economy"])

        user_prompt = self._build_planning_prompt(
            product_analysis=product_analysis,
            duration=duration,
            languages=languages,
            quality_tier=quality_tier,
            budget=budget,
            url_content=url_content,
            user_model_override=user_model_override,
            num_images=num_images,
        )

        # Call Director LLM
        plan_json = await self._call_director_llm(user_prompt)
        plan = self._parse_production_plan(plan_json, duration, languages, quality_tier)

        # Validate and adjust
        plan = self._validate_plan(plan, duration, budget, user_model_override)

        self._log_decision(
            f"Plan ready: model={plan.video_model}, "
            f"segments={plan.num_segments}, "
            f"est_cost=${plan.estimated_cost_usd:.2f}"
        )

        return plan

    def _build_planning_prompt(
        self,
        product_analysis: dict,
        duration: int,
        languages: list[str],
        quality_tier: str,
        budget: dict,
        url_content: Optional[str],
        user_model_override: Optional[str],
        num_images: int,
    ) -> str:
        """Build the user prompt for production planning."""
        product_desc = self._format_product(product_analysis)
        url_desc = (url_content or "")[:1500]

        model_override_note = ""
        if user_model_override:
            model_override_note = (
                f"\n**USER EXPLICITLY SELECTED**: {user_model_override} — "
                f"use this model unless budget makes it impossible."
            )

        return f"""Plan a UGC product video production.

## Product
{product_desc}

## URL Content
{url_desc if url_desc else "Not provided"}

## Requirements
- Total duration: {duration} seconds
- Languages for TTS: {', '.join(languages)}
- Quality tier: {quality_tier}
- Budget limit: ${budget['max_usd']:.2f}
- Preferred models for this tier: {', '.join(budget['preferred_models'])}
- Number of product images: {num_images}
{model_override_note}

## Instructions
Create a production plan. Consider:
1. How many segments? Each model has a max clip duration.
2. Scene progression — hook viewers in first 3 seconds
3. Camera variety — don't repeat same movements
4. Budget — estimate total cost including TTS
5. If duration <= model max, use 1 segment (no chaining needed)

Return ONLY valid JSON matching the schema in your system prompt."""

    async def _call_director_llm(self, user_prompt: str) -> str:
        """Call the Director's brain (GPT 5.2 via KIE.AI)."""
        messages = [
            {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(self._max_planning_retries):
            model = self._primary_model if attempt == 0 else self._fallback_model
            try:
                self._log_decision(f"Calling {model} for planning (attempt {attempt + 1})")
                response = await self.gateway.chat_completion(
                    model=model,
                    messages=messages,
                    temperature=0.4,  # Lower temp for more consistent planning
                    max_tokens=2048,
                    response_format="json_object",
                )
                return response
            except Exception as e:
                logger.warning(f"Director LLM call failed ({model}): {e}")
                if attempt == self._max_planning_retries - 1:
                    self._log_decision(f"All LLM attempts failed, using fallback plan")
                    return ""

        return ""

    def _parse_production_plan(
        self,
        raw_json: str,
        duration: int,
        languages: list[str],
        quality_tier: str,
    ) -> ProductionPlan:
        """Parse LLM response into a ProductionPlan."""
        if not raw_json or not raw_json.strip():
            return self._create_fallback_plan(duration, languages, quality_tier)

        try:
            # Clean potential markdown wrapping
            cleaned = raw_json.strip()
            if cleaned.startswith("```"):
                import re
                cleaned = re.sub(r"```(?:json)?\s*", "", cleaned).strip("`").strip()

            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Director plan JSON: {e}")
            return self._create_fallback_plan(duration, languages, quality_tier)

        # Extract fields with safe defaults
        model_sel = data.get("model_selection", {})
        seg_plan = data.get("segment_plan", {})
        tts_plan = data.get("tts_plan", {})

        return ProductionPlan(
            strategy=data.get("strategy", "Standard product showcase"),
            video_model=model_sel.get("video_model", "seedance_15"),
            model_reason=model_sel.get("reason", "Default selection"),
            num_segments=seg_plan.get("num_segments", 3),
            segment_durations=seg_plan.get("segment_durations", []),
            scene_progression=seg_plan.get("scene_progression", []),
            estimated_cost_usd=data.get("estimated_cost_usd", 0.0),
            tts_languages=tts_plan.get("languages", languages),
            tts_style=tts_plan.get("style", "warm, professional"),
            quality_threshold=data.get("quality_threshold", 0.7),
            max_retries=data.get("max_retries", 1),
            raw_json=raw_json,
        )

    def _validate_plan(
        self,
        plan: ProductionPlan,
        duration: int,
        budget: dict,
        user_model_override: Optional[str],
    ) -> ProductionPlan:
        """Validate and fix the production plan."""
        from models.base import get_model_max_duration, MODEL_MAX_DURATIONS

        # Override model if user explicitly chose one
        if user_model_override and user_model_override in MODEL_MAX_DURATIONS:
            if plan.video_model != user_model_override:
                self._log_decision(
                    f"Overriding Director's model choice "
                    f"({plan.video_model} → {user_model_override}) per user selection"
                )
                plan.video_model = user_model_override

        # Ensure model exists
        if plan.video_model not in MODEL_MAX_DURATIONS:
            self._log_decision(
                f"Unknown model {plan.video_model}, falling back to seedance_15"
            )
            plan.video_model = "seedance_15"

        # Recalculate segments if needed
        max_clip = get_model_max_duration(plan.video_model)

        if not plan.segment_durations or sum(plan.segment_durations) != duration:
            num_segs = -(-duration // max_clip)  # ceiling division
            base = duration // num_segs
            remainder = duration % num_segs
            plan.segment_durations = [
                base + (1 if i < remainder else 0) for i in range(num_segs)
            ]
            plan.num_segments = num_segs
            self._log_decision(
                f"Recalculated segments: {plan.num_segments} × "
                f"{plan.segment_durations}"
            )

        # Ensure segment durations don't exceed model max
        fixed_durations = []
        for d in plan.segment_durations:
            if d > max_clip:
                # Split oversized segment
                sub_segs = -(-d // max_clip)
                sub_base = d // sub_segs
                sub_rem = d % sub_segs
                for j in range(sub_segs):
                    fixed_durations.append(sub_base + (1 if j < sub_rem else 0))
            else:
                fixed_durations.append(d)
        if fixed_durations != plan.segment_durations:
            plan.segment_durations = fixed_durations
            plan.num_segments = len(fixed_durations)
            self._log_decision(f"Fixed oversized segments: {plan.segment_durations}")

        # Fill scene progression if missing
        if len(plan.scene_progression) < plan.num_segments:
            default_progression = [
                "establishing", "detail", "lifestyle", "hero",
                "feature", "closeup", "ambient", "finale",
            ]
            plan.scene_progression = [
                default_progression[i % len(default_progression)]
                for i in range(plan.num_segments)
            ]

        return plan

    def _create_fallback_plan(
        self,
        duration: int,
        languages: list[str],
        quality_tier: str,
    ) -> ProductionPlan:
        """Create a safe fallback plan when LLM is unavailable."""
        from models.base import get_model_max_duration

        budget = BUDGET_TIERS.get(quality_tier, BUDGET_TIERS["economy"])
        model = budget["preferred_models"][0]
        max_clip = get_model_max_duration(model)

        num_segs = -(-duration // max_clip)
        base = duration // num_segs
        remainder = duration % num_segs
        durations = [base + (1 if i < remainder else 0) for i in range(num_segs)]

        self._log_decision(
            f"Using fallback plan: model={model}, segments={num_segs}"
        )

        return ProductionPlan(
            strategy="Standard product showcase (fallback)",
            video_model=model,
            model_reason=f"Default for {quality_tier} tier",
            num_segments=num_segs,
            segment_durations=durations,
            scene_progression=["establishing", "detail", "lifestyle", "hero"][:num_segs],
            estimated_cost_usd=budget["max_usd"] * 0.5,
            tts_languages=languages,
            tts_style="warm, professional",
            quality_threshold=0.6,
            max_retries=1,
        )

    # ── Execution Phase ─────────────────────────────────────

    async def execute_plan(
        self,
        plan: ProductionPlan,
        request,  # VideoRequest from orchestrator
        config: dict,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> ProductionResult:
        """
        Execute a production plan using the existing pipeline modules.

        The Director delegates actual work to:
        - ScriptGenerator (scene prompts)
        - FrameChainer (video generation + frame extraction)
        - VideoStitcher (FFmpeg concat)
        - TTSService (voiceover)
        - LipSyncService (avatar sync)

        Args:
            plan: ProductionPlan from create_production_plan()
            request: VideoRequest with user inputs
            config: Application config
            progress_callback: For WebSocket progress updates
            status_callback: For WebSocket status messages

        Returns:
            ProductionResult with final video and metadata
        """
        start_time = time.time()
        self._decisions = []  # Reset for this production

        self._log_decision(f"Executing plan: {plan.strategy}")

        async def update_status(key: str, **kwargs):
            if status_callback:
                await status_callback(key, **kwargs)

        # ── Step 1: Get model adapter ───────────────────────
        from models import get_model_adapter

        # Use Director's model selection (may differ from request.model)
        effective_model = plan.video_model
        self._log_decision(f"Using model: {effective_model}")

        model_adapter = get_model_adapter(effective_model, config)

        # ── Step 2: Analyze product image ───────────────────
        product_analysis = {}
        if request.image_path and Path(request.image_path).exists():
            await update_status("analyzing_image")
            try:
                from services.image_analyzer import ImageAnalyzer
                analyzer = ImageAnalyzer(config)
                product_analysis = await analyzer.analyze(request.image_path)
                self._log_decision(
                    f"Product analyzed: {product_analysis.get('type', 'unknown')}"
                )
            except Exception as e:
                logger.warning(f"Image analysis failed: {e}")

        if request.text_prompt:
            product_analysis["user_description"] = request.text_prompt

        # ── Step 3: Extract URL content ─────────────────────
        url_content = request.url_content
        if request.url and not url_content:
            await update_status("extracting_url")
            try:
                from services.url_extractor import URLExtractor
                extractor = URLExtractor(config)
                url_content = await extractor.extract(request.url)
                self._log_decision(f"URL extracted: {len(url_content or '')} chars")
            except Exception as e:
                logger.warning(f"URL extraction failed: {e}")

        # ── Step 4: Generate script ─────────────────────────
        await update_status("generating_script", segments=plan.num_segments)
        self._log_decision("Generating video script")

        try:
            from core.script_generator import ScriptGenerator
            script_gen = ScriptGenerator(config)
            script = await script_gen.generate_script(
                product_analysis=product_analysis,
                segment_durations=plan.segment_durations,
                model_key=effective_model,
                language=request.language,
                url_content=url_content,
                aspect_ratio=request.aspect_ratio,
            )
        except Exception as e:
            self._log_decision(f"Script generation failed: {e}")
            raise RuntimeError(f"Script generation failed: {e}") from e

        self._log_decision(f"Script ready: {script.num_segments} scenes")

        # ── Step 5: Frame chain generation ──────────────────
        self._log_decision("Starting frame chain generation")

        async def poll_cb(attempt: int, max_retries: int):
            if status_callback:
                await status_callback(
                    "polling",
                    model=effective_model.upper().replace("_", " "),
                    attempt=attempt,
                    max_retries=max_retries,
                )

        try:
            from core.frame_chainer import FrameChainer
            chainer = FrameChainer(config)
            segment_paths = await chainer.chain_segments(
                script=script,
                model_adapter=model_adapter,
                reference_image=request.image_path,
                aspect_ratio=request.aspect_ratio,
                progress_callback=progress_callback,
                poll_callback=poll_cb,
            )
        except Exception as e:
            self._log_decision(f"Frame chaining failed: {e}")
            raise RuntimeError(f"Video generation failed: {e}") from e

        self._log_decision(f"Frame chain complete: {len(segment_paths)} clips")

        # ── Step 6: Stitch clips ────────────────────────────
        await update_status("stitching", count=len(segment_paths))
        self._log_decision("Stitching video clips")

        try:
            from core.video_stitcher import VideoStitcher
            stitcher = VideoStitcher(config)
            output_dir = Path(
                config.get("video", {}).get("output_dir", "/tmp/ugc_videos")
            )
            output_filename = (
                f"UGC_{request.mode}_{effective_model}_{request.duration}s_"
                f"{int(time.time())}.mp4"
            )
            output_path = str(output_dir / output_filename)

            final_path = await stitcher.stitch(
                video_paths=segment_paths,
                output_path=output_path,
            )
        except Exception as e:
            logger.error(f"Stitching failed: {e}")
            if segment_paths:
                final_path = segment_paths[0]
                self._log_decision("Stitching failed, using first clip")
            else:
                raise RuntimeError(f"Video stitching failed: {e}") from e

        # ── Step 7: TTS generation (multi-language) ─────────
        tts_paths = {}
        if plan.tts_languages:
            await update_status("generating_tts")
            self._log_decision(
                f"Generating TTS: {', '.join(plan.tts_languages)}"
            )
            tts_paths = await self._generate_multilang_tts(
                script=script,
                languages=plan.tts_languages,
                config=config,
            )

        # ── Step 8: Upload to Drive (optional) ──────────────
        drive_link = None
        drive_config = config.get("google_drive", {})
        if drive_config.get("credentials_path"):
            await update_status("uploading_drive")
            try:
                from services.google_drive import GoogleDriveUploader
                uploader = GoogleDriveUploader(config)
                drive_link = await uploader.upload(
                    file_path=final_path,
                    folder_name=drive_config.get("folder_name", "UGC_Videos"),
                )
                self._log_decision(f"Uploaded to Drive: {drive_link}")
            except Exception as e:
                logger.warning(f"Drive upload failed: {e}")

        # ── Cleanup ─────────────────────────────────────────
        import os
        if len(segment_paths) > 1:
            for path in segment_paths:
                if path != final_path:
                    try:
                        if Path(path).exists():
                            os.unlink(path)
                    except Exception:
                        pass

        elapsed = time.time() - start_time
        self._log_decision(
            f"Production complete: {final_path} "
            f"({elapsed:.0f}s, {len(segment_paths)} clips)"
        )

        return ProductionResult(
            video_path=final_path,
            drive_link=drive_link,
            duration=request.duration,
            num_segments=plan.num_segments,
            model=effective_model,
            elapsed_seconds=elapsed,
            total_cost_usd=plan.estimated_cost_usd,
            plan=plan,
            segment_paths=segment_paths,
            tts_paths=tts_paths,
            script_json=script.raw_json,
            product_analysis=product_analysis,
            director_decisions=list(self._decisions),
        )

    # ── TTS Helper ──────────────────────────────────────────

    async def _generate_multilang_tts(
        self,
        script,
        languages: list[str],
        config: dict,
    ) -> dict:
        """
        Generate TTS audio for multiple languages.

        Returns:
            Dict mapping language code to audio file path
        """
        import asyncio

        tts_paths = {}

        async def gen_single_tts(lang: str) -> tuple:
            try:
                from services.tts_service import TTSService
                tts = TTSService(config)
                # Combine all scene audio descriptions into TTS text
                tts_text = " ".join(
                    scene.audio_description
                    for scene in script.scenes
                    if scene.audio_description
                )
                if not tts_text.strip():
                    return lang, None

                audio_path = await tts.generate(
                    text=tts_text,
                    language=lang,
                )
                self._log_decision(f"TTS generated for {lang}: {audio_path}")
                return lang, audio_path
            except Exception as e:
                logger.warning(f"TTS generation failed for {lang}: {e}")
                return lang, None

        # Run TTS for all languages in parallel
        tasks = [gen_single_tts(lang) for lang in languages]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, tuple):
                lang, path = result
                if path:
                    tts_paths[lang] = path

        return tts_paths

    # ── Helpers ──────────────────────────────────────────────

    def _format_product(self, analysis: dict) -> str:
        """Format product analysis for LLM context."""
        if not analysis:
            return "No product details available"

        lines = []
        for key in ["type", "brand", "description", "colors", "materials",
                     "text_on_product", "shape", "lighting", "user_description"]:
            val = analysis.get(key)
            if val:
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                lines.append(f"- {key}: {val}")

        return "\n".join(lines) if lines else str(analysis)

    def estimate_cost(self, model: str, duration: int, languages: list[str]) -> float:
        """
        Estimate total production cost in USD.

        Includes video generation + TTS for all languages.
        """
        costs = MODEL_COSTS.get(model, {})
        video_cost = 0.0

        from models.base import get_model_max_duration
        max_clip = get_model_max_duration(model)
        num_segments = -(-duration // max_clip)

        if "per_video" in costs:
            video_cost = costs["per_video"] * num_segments
        elif "per_10s" in costs:
            video_cost = costs["per_10s"] * (duration / 10.0)
        elif "per_5s" in costs:
            video_cost = costs["per_5s"] * (duration / 5.0)
        elif "per_6s" in costs:
            video_cost = costs["per_6s"] * (duration / 6.0)
        elif "per_s_1080p" in costs:
            video_cost = costs["per_s_1080p"] * duration

        # TTS cost estimate (~$0.03/1000 chars, assume ~100 chars per language)
        tts_cost = len(languages) * 0.03

        # Director LLM call (~$0.02)
        llm_cost = 0.02

        return round(video_cost + tts_cost + llm_cost, 2)
