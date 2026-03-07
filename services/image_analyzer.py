"""
services/image_analyzer.py
==========================
Multi-image product analysis using Google Gemini Vision.

Two APIs:
    analyze(image_path)                        → dict  (legacy, single image)
    analyze_images(image_paths, description)   → ProductProfile (new multi-image)

Outputs a ProductProfile capturing everything needed to:
  - Keep the product appearance 100% consistent across AI clips
  - Extract selling points, demo actions, before/after opportunities
  - Flag risky claims and forbidden words
"""
from __future__ import annotations
import base64, json, re
from pathlib import Path
from typing import Optional

from utils.logger import get_logger
logger = get_logger(__name__)

SINGLE_IMAGE_PROMPT = """Analyze this product image with EXTREME precision for video production.
CRITICAL: Describe EXACTLY what you see — no interpretation.
Return ONLY valid JSON:
{
  "type": "product",
  "brand": "<brand name or null>",
  "colors": [{"hex":"#RRGGBB","description":"<name>","location":"<where>"}],
  "materials": ["<exact material>"],
  "text_on_product": "<exact visible text or null>",
  "shape": "<shape description>",
  "size_reference": "<size cues>",
  "lighting": "<light interaction>",
  "background": "<background>",
  "orientation": "<orientation>",
  "key_features": ["<feature>"],
  "description": "<2-3 sentence visual description>"
}"""

MULTI_IMAGE_PROMPT = """You are analyzing {n} product images to build a complete ProductProfile for UGC video production.
{description_hint}

Return ONLY valid JSON:
{{
  "product_type": "<category: skincare|supplement|electronics|food|fashion|home|other>",
  "brand": "<brand name>",
  "description": "<2-3 sentence product description>",
  "colors": ["<color>"],
  "materials": ["<material>"],
  "text_on_product": "<exact visible text>",
  "shape": "<shape>",
  "key_features": ["<feature>"],
  "selling_points": ["<point>"],
  "demo_actions": ["<action viewers want to see: apply, pour, squeeze, twist, compare, etc.>"],
  "visual_consistency_anchors": ["<must-preserve visual detail>"],
  "before_after_opportunity": "<describe the problem→solution visual if applicable>",
  "target_audience": "<primary audience>",
  "use_case": "<primary use scenario>",
  "risk_words": ["<any claims that may be regulatory risk>"]
}}"""


class ImageAnalyzer:
    def __init__(self, config: dict):
        self.config = config
        gc = config.get("gemini", {})
        api_key = gc.get("api_key", "")
        self.model_name = gc.get("model", "gemini-2.5-flash")
        self.fallback_model = gc.get("fallback_model", "gemini-2.0-flash")
        self._client = None

        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._client = genai.GenerativeModel(self.model_name)
                logger.info(f"ImageAnalyzer: {self.model_name}")
            except Exception as e:
                logger.warning(f"ImageAnalyzer init failed: {e}")

    # ── NEW: multi-image analysis → ProductProfile ───────────────────────────
    async def analyze_images(
        self,
        image_paths: list[str],
        description: Optional[str] = None,
    ):
        """
        Analyze 1-N product images and return a ProductProfile.
        Usage images, gallery shots, and packaging images all contribute.
        """
        from core.timeline_types import ProductProfile

        valid = [p for p in image_paths if Path(p).exists()]
        if not valid:
            logger.warning("analyze_images: no valid image paths")
            return ProductProfile(description=description or "")

        if self._client:
            try:
                raw = await self._gemini_multi(valid, description)
                return ProductProfile(
                    product_type=raw.get("product_type", ""),
                    brand=raw.get("brand", ""),
                    description=raw.get("description", "") or description or "",
                    colors=raw.get("colors", []),
                    materials=raw.get("materials", []),
                    text_on_product=raw.get("text_on_product", ""),
                    shape=raw.get("shape", ""),
                    key_features=raw.get("key_features", []),
                    target_audience=raw.get("target_audience", ""),
                    use_case=raw.get("use_case", ""),
                    raw_analysis={
                        **raw,
                        "selling_points": raw.get("selling_points", []),
                        "demo_actions": raw.get("demo_actions", []),
                        "visual_consistency_anchors": raw.get("visual_consistency_anchors", []),
                        "before_after_opportunity": raw.get("before_after_opportunity", ""),
                        "risk_words": raw.get("risk_words", []),
                    },
                )
            except Exception as e:
                logger.warning(f"Gemini multi-image failed: {e}")

        # Fallback: analyze first image only
        raw = await self.analyze(valid[0])
        return ProductProfile(
            product_type=raw.get("type", ""),
            brand=raw.get("brand", "") or "",
            description=raw.get("description", "") or description or "",
            colors=raw.get("colors", []),
            materials=raw.get("materials", []),
            text_on_product=raw.get("text_on_product", "") or "",
            key_features=raw.get("key_features", []),
            raw_analysis=raw,
        )

    async def _gemini_multi(self, image_paths: list[str], description: Optional[str]) -> dict:
        import google.generativeai as genai
        parts = []
        hint = f"Additional product description: {description}" if description else ""
        parts.append(MULTI_IMAGE_PROMPT.format(n=len(image_paths), description_hint=hint))
        for path in image_paths[:5]:   # Gemini limit
            data = Path(path).read_bytes()
            suffix = Path(path).suffix.lower()
            mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
            parts.append({"mime_type": mime, "data": data})

        cfg = genai.types.GenerationConfig(
            temperature=0.1, response_mime_type="application/json", max_output_tokens=2048
        )
        resp = await self._client.generate_content_async(parts, generation_config=cfg)
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip("`").strip()
        return json.loads(raw)

    # ── LEGACY: single image → dict ──────────────────────────────────────────
    async def analyze(self, image_path: str) -> dict:
        if not Path(image_path).exists():
            return {}
        if self._client:
            try:
                return await self._analyze_with_gemini(image_path)
            except Exception as e:
                logger.warning(f"Gemini single-image failed: {e}")
        return await self._analyze_basic(image_path)

    async def _analyze_with_gemini(self, image_path: str) -> dict:
        import google.generativeai as genai
        data = Path(image_path).read_bytes()
        suffix = Path(image_path).suffix.lower()
        mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        cfg = genai.types.GenerationConfig(
            temperature=0.1, response_mime_type="application/json", max_output_tokens=2048
        )
        resp = await self._client.generate_content_async(
            [SINGLE_IMAGE_PROMPT, {"mime_type": mime, "data": data}], generation_config=cfg
        )
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip("`").strip()
        result = json.loads(raw)
        logger.info(f"Image analyzed: type={result.get('type')}, brand={result.get('brand')}")
        return result

    async def _analyze_basic(self, image_path: str) -> dict:
        try:
            from PIL import Image
            import colorsys
            with Image.open(image_path) as img:
                pixels = list(img.convert("RGB").resize((100, 100)).getdata())
            from collections import Counter
            quantized = [(r // 32 * 32, g // 32 * 32, b // 32 * 32) for r, g, b in pixels]
            colors = []
            for (r, g, b), _ in Counter(quantized).most_common(3):
                hex_c = f"#{r:02x}{g:02x}{b:02x}"
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                if v < 0.2: name = "black"
                elif v > 0.9 and s < 0.1: name = "white"
                elif s < 0.1: name = "gray"
                else: name = ["red","orange","yellow","green","cyan","blue","purple","pink","red"][int(h*8)]
                colors.append({"hex": hex_c, "description": name, "location": "product"})
            return {"type":"product","brand":None,"colors":colors,"materials":["unknown"],"text_on_product":None,"shape":"object","description":"Product image","key_features":[]}
        except Exception as e:
            logger.error(f"Basic analysis failed: {e}")
            return {"type":"product","description":"Product image","colors":[],"materials":[]}

    def format_for_prompt(self, analysis: dict) -> str:
        if not analysis: return ""
        parts = []
        for key, label in [("description","Product"),("brand","Brand"),("text_on_product","Logo"),("shape","Shape")]:
            if analysis.get(key):
                parts.append(f"{label}: {analysis[key]}")
        if analysis.get("colors"):
            parts.append("Colors: " + ", ".join(
                f"{c['description']}({c.get('hex','')})" if isinstance(c, dict) else str(c)
                for c in analysis["colors"]
            ))
        if analysis.get("materials"):
            parts.append(f"Materials: {', '.join(str(m) for m in analysis['materials'])}")
        if analysis.get("key_features"):
            parts.append(f"Features: {', '.join(str(f) for f in analysis['key_features'][:4])}")
        return " | ".join(parts)
