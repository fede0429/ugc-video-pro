"""
services/overlay_service.py
============================
Builds the overlay (drawtext) plan from a TimelineScript.

Overlays include:
  - Product callout captions (from segment.overlay_text)
  - Price badges
  - CTA cards at the end

Returns a list of dicts consumed by FFmpegTools.overlay_text_blocks().
"""
from __future__ import annotations
from core.timeline_types import RenderedAsset, TimelineScript
from utils.logger import get_logger
logger = get_logger(__name__)


OVERLAY_STYLES = {
    "callout": {"fontsize": 44, "y": "h*0.82", "x": "(w-text_w)/2"},
    "top_bar": {"fontsize": 38, "y": "h*0.06", "x": "(w-text_w)/2"},
    "cta":     {"fontsize": 52, "y": "h*0.75", "x": "(w-text_w)/2"},
}


class OverlayService:
    def __init__(self, config: dict):
        self.config = config

    def build_plan(
        self,
        timeline: TimelineScript,
        a_roll_assets: list[RenderedAsset],
        b_roll_assets: list[RenderedAsset],
    ) -> list[dict]:
        """
        Build the drawtext overlay plan from timeline overlay_text values.
        Returns list of {text, start, end, x, y, fontsize} dicts.
        """
        a_map = {a.segment_id: a for a in a_roll_assets}
        b_map = {b.segment_id: b for b in b_roll_assets}

        plan: list[dict] = []
        cursor = 0.0
        total_segments = len(timeline.segments)

        for i, segment in enumerate(sorted(timeline.segments, key=lambda s: s.segment_index)):
            asset = a_map.get(segment.segment_id) or b_map.get(segment.segment_id)
            dur = asset.duration_seconds if asset else float(segment.duration_seconds)

            overlay = segment.overlay_text.strip() if segment.overlay_text else ""
            if overlay:
                # CTA style for last segment
                is_last = (i == total_segments - 1)
                style_key = "cta" if is_last else "callout"
                style = OVERLAY_STYLES[style_key]

                plan.append({
                    "text": overlay,
                    "start": cursor + 0.3,
                    "end": cursor + dur - 0.3,
                    **style,
                })
            cursor += dur

        logger.info(f"Overlay plan: {len(plan)} text blocks")
        return plan
