from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PublishPackage:
    title: str
    short_title: str
    description: str
    hashtags: list[str] = field(default_factory=list)
    caption_options: list[str] = field(default_factory=list)
    hook_line: str = ""
    cta_line: str = ""
    platform_notes: dict[str, Any] = field(default_factory=dict)
    reusable_assets: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PublishPrepService:
    def _hashtags(self, product_profile, request) -> list[str]:
        seeds = []
        lang = getattr(request, "language", "zh")
        if lang == "zh":
            seeds += ["#好物推荐", "#真实测评", "#种草", "#开箱"]
        elif lang == "en":
            seeds += ["#ugccreator", "#productreview", "#musthave", "#adcreative"]
        else:
            seeds += ["#recensione", "#ugcvideo", "#consigli", "#prodotto"]
        desc = getattr(product_profile, "description", "") or ""
        brand = getattr(product_profile, "brand", "") or ""
        for item in [brand, desc, *list(getattr(product_profile, "selling_points", []) or [])[:3]]:
            if not item:
                continue
            tag = "#" + "".join(ch for ch in str(item) if ch.isalnum())[:20]
            if len(tag) > 1:
                seeds.append(tag)
        return list(dict.fromkeys(seeds))[:10]

    def build(self, *, request, product_profile, presenter_profile, production_plan, timeline, final_video_path: str | None = None) -> PublishPackage:
        first_line = ""
        cta_line = ""
        for seg in getattr(timeline, "segments", []) or []:
            if not first_line and (getattr(seg, "spoken_line", "") or "").strip():
                first_line = seg.spoken_line.strip()
            if "cta" in ((getattr(seg, "scene_purpose", "") or "") + " " + (getattr(seg, "overlay_text", "") or "")).lower():
                cta_line = (getattr(seg, "spoken_line", "") or getattr(seg, "overlay_text", "") or "").strip() or cta_line
        brand = getattr(product_profile, "brand", "") or ""
        desc = getattr(product_profile, "description", "") or "产品"
        short_title = f"{brand} {desc}".strip()
        title = f"{short_title}｜{first_line[:28] if first_line else 'UGC短视频'}"
        features = "、".join((getattr(product_profile, "selling_points", []) or getattr(product_profile, "key_features", []) or [])[:4])
        persona = getattr(production_plan, "persona", "") or getattr(presenter_profile, "persona_template", "")
        description = f"{first_line or short_title}。重点卖点：{features}。人设：{persona or '真实测评'}。"
        caption_options = [
            first_line or f"{short_title} 真的有点超预期",
            f"{short_title} 我会回购的点：{features}" if features else short_title,
            cta_line or "想看同款测评可以继续往下看",
        ]
        reusable_assets = []
        if final_video_path:
            reusable_assets.append({"asset_type": "final_video", "path": str(final_video_path), "label": "final_video"})
        for seg in getattr(timeline, "segments", []) or []:
            if getattr(seg, "track_type", "") == "b_roll":
                reusable_assets.append({
                    "asset_type": "b_roll_prompt",
                    "label": getattr(seg, "overlay_text", "") or getattr(seg, "scene_purpose", "") or "b_roll",
                    "prompt": getattr(seg, "b_roll_prompt", "") or getattr(seg, "visual_prompt", ""),
                })
        platform = getattr(request, "platform", "douyin")
        platform_notes = {
            "platform": platform,
            "recommended_cover_text": (getattr(timeline.segments[0], "overlay_text", "") if getattr(timeline, "segments", None) else "") or first_line[:12],
            "recommended_title_length": 20 if platform in ("douyin", "xiaohongshu") else 50,
            "post_timing_hint": "19:00-22:00",
        }
        return PublishPackage(
            title=title[:80],
            short_title=short_title[:40] or "UGC视频",
            description=description[:240],
            hashtags=self._hashtags(product_profile, request),
            caption_options=caption_options,
            hook_line=first_line,
            cta_line=cta_line,
            platform_notes=platform_notes,
            reusable_assets=reusable_assets[:12],
        )
