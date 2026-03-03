"""
services/image_analyzer.py
==========================
Product image analysis using Google Gemini Vision.

Analyzes product images with extreme precision to extract exact colors,
materials, text/logos, shape, and surface lighting. This analysis is
injected into every video generation prompt to preserve product appearance.

Falls back to basic PIL-based color extraction if Gemini is unavailable.
"""

import base64
import json
import re
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

ANALYSIS_PROMPT = """Analyze this product image with EXTREME precision for video production.

CRITICAL: Do NOT interpret, reimagine, or editorialize. Describe EXACTLY what you see.
This description will be used to preserve the product's exact appearance in AI-generated videos.

Return ONLY a valid JSON object with this exact schema:
{
    "type": "product" | "character" | "both" | "scene",
    "brand": "<exact brand name if visible, or null>",
    "colors": [
        {"hex": "#RRGGBB", "description": "<color name>", "location": "<where on product>"}
    ],
    "materials": ["<exact material names, e.g. brushed aluminum, matte plastic, glass>"],
    "text_on_product": "<exact text visible on product, or null>",
    "shape": "<precise shape description>",
    "size_reference": "<relative size cues from image context>",
    "lighting": "<how light currently interacts with the product surfaces>",
    "background": "<current background description>",
    "orientation": "<how the product is oriented/positioned>",
    "key_features": ["<list of distinctive visual features>"],
    "description": "<precise 2-3 sentence description capturing all essential visual details>"
}

Return ONLY the JSON, no markdown, no explanation."""


class ImageAnalyzer:
    """Analyzes product images using Gemini Vision API for fidelity preservation."""

    def __init__(self, config: dict):
        self.config = config
        gemini_config = config.get("gemini", {})
        api_key = gemini_config.get("api_key", "")
        self.model_name = gemini_config.get("model", "gemini-2.0-flash-exp")
        self._client = None

        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._client = genai.GenerativeModel(self.model_name)
                logger.info(f"ImageAnalyzer initialized with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini for image analysis: {e}")

    async def analyze(self, image_path: str) -> dict:
        """Analyze a product image and return structured description."""
        if not Path(image_path).exists():
            logger.error(f"Image not found: {image_path}")
            return {}

        if self._client:
            try:
                return await self._analyze_with_gemini(image_path)
            except Exception as e:
                logger.warning(f"Gemini image analysis failed: {e} — using basic fallback")

        return await self._analyze_basic(image_path)

    async def _analyze_with_gemini(self, image_path: str) -> dict:
        """Use Gemini Vision to analyze the product image."""
        import google.generativeai as genai

        with open(image_path, "rb") as f:
            image_data = f.read()

        suffix = Path(image_path).suffix.lower()
        mime_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

        image_part = {"mime_type": mime_type, "data": image_data}

        logger.info(f"Analyzing image with Gemini: {image_path}")

        generation_config = genai.types.GenerationConfig(
            temperature=0.1,
            top_p=0.9,
            response_mime_type="application/json",
            max_output_tokens=2048,
        )

        response = await self._client.generate_content_async(
            [ANALYSIS_PROMPT, image_part],
            generation_config=generation_config,
        )

        raw = response.text.strip()

        if raw.startswith("```"):
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip("`").strip()

        result = json.loads(raw)
        logger.info(
            f"Image analysis complete: type={result.get('type')}, "
            f"brand={result.get('brand')}"
        )
        return result

    async def _analyze_basic(self, image_path: str) -> dict:
        """Basic fallback analysis using PIL — extracts dominant colors."""
        try:
            from PIL import Image
            import colorsys

            with Image.open(image_path) as img:
                img_rgb = img.convert("RGB")
                img_small = img_rgb.resize((100, 100))
                pixels = list(img_small.getdata())

            from collections import Counter
            quantized = [
                (r // 32 * 32, g // 32 * 32, b // 32 * 32)
                for r, g, b in pixels
            ]
            color_counts = Counter(quantized).most_common(5)

            colors = []
            for (r, g, b), count in color_counts:
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                if v < 0.2:
                    name = "black"
                elif v > 0.9 and s < 0.1:
                    name = "white"
                elif s < 0.1:
                    name = "gray"
                else:
                    hue_names = [
                        (0.08, "red"), (0.17, "orange"), (0.25, "yellow"),
                        (0.45, "green"), (0.55, "cyan"), (0.7, "blue"),
                        (0.8, "purple"), (0.95, "pink"), (1.0, "red"),
                    ]
                    name = next((n for th, n in hue_names if h <= th), "colored")
                colors.append({"hex": hex_color, "description": name, "location": "product"})

            return {
                "type": "product",
                "brand": None,
                "colors": colors[:3],
                "materials": ["unknown"],
                "text_on_product": None,
                "shape": "object",
                "description": "Product image — detailed analysis unavailable",
                "key_features": [],
            }

        except Exception as e:
            logger.error(f"Basic image analysis failed: {e}")
            return {"type": "product", "description": "Product image", "colors": [], "materials": []}

    def format_for_prompt(self, analysis: dict) -> str:
        """Format analysis result into a string for injection into video generation prompts."""
        if not analysis:
            return ""

        parts = []

        if analysis.get("description"):
            parts.append(f"Product: {analysis['description']}")
        if analysis.get("brand"):
            parts.append(f"Brand: {analysis['brand']}")
        if analysis.get("colors"):
            color_strs = []
            for c in analysis["colors"]:
                if isinstance(c, dict):
                    desc = c.get("description", "")
                    hex_c = c.get("hex", "")
                    loc = c.get("location", "")
                    s = f"{desc} ({hex_c})"
                    if loc:
                        s += f" on {loc}"
                    color_strs.append(s)
                else:
                    color_strs.append(str(c))
            if color_strs:
                parts.append(f"Colors: {', '.join(color_strs)}")
        if analysis.get("materials"):
            parts.append(f"Materials: {', '.join(str(m) for m in analysis['materials'])}")
        if analysis.get("text_on_product"):
            parts.append(f"Text/Logo: \"{analysis['text_on_product']}\"")
        if analysis.get("shape"):
            parts.append(f"Shape: {analysis['shape']}")
        if analysis.get("key_features"):
            parts.append(f"Features: {', '.join(str(f) for f in analysis['key_features'][:5])}")

        return " | ".join(parts)
