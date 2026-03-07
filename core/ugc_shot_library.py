
from __future__ import annotations

from dataclasses import dataclass, asdict, field


@dataclass
class UGCBRollTemplate:
    template_id: str
    purpose: str
    shot_type: str
    camera_movement: str
    framing: str
    prompt_keywords: list[str] = field(default_factory=list)
    overlay_patterns: list[str] = field(default_factory=list)
    use_for_categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class UGCShotLibrary:
    def __init__(self):
        self.templates = [
            UGCBRollTemplate(
                template_id="hook_macro_reveal",
                purpose="hook",
                shot_type="macro_reveal",
                camera_movement="push_in",
                framing="extreme close-up",
                prompt_keywords=["dramatic reveal", "premium detail", "high contrast", "phone-native realism"],
                overlay_patterns=["先看这个", "重点看细节", "第一眼就懂"],
                use_for_categories=["beauty", "skincare", "home", "electronics"],
            ),
            UGCBRollTemplate(
                template_id="problem_demo",
                purpose="problem",
                shot_type="problem_demo",
                camera_movement="handheld",
                framing="medium close-up",
                prompt_keywords=["real usage", "before fix", "pain point", "natural hand movement"],
                overlay_patterns=["以前真的很麻烦", "这个问题我天天遇到", "痛点太真实"],
                use_for_categories=["home", "electronics", "daily", "kitchen"],
            ),
            UGCBRollTemplate(
                template_id="texture_closeup",
                purpose="proof",
                shot_type="texture_closeup",
                camera_movement="slow_pan",
                framing="close-up",
                prompt_keywords=["texture detail", "clean lighting", "consistency anchor", "material fidelity"],
                overlay_patterns=["细节真的能打", "质感很重要", "给你看清楚"],
                use_for_categories=["beauty", "skincare", "fashion"],
            ),
            UGCBRollTemplate(
                template_id="hands_on_demo",
                purpose="demo",
                shot_type="hands_on_demo",
                camera_movement="overhead_follow",
                framing="medium shot",
                prompt_keywords=["hands using product", "clear action", "functional demonstration", "creator desk setup"],
                overlay_patterns=["这样用最直观", "实际操作给你看", "上手很简单"],
                use_for_categories=["electronics", "home", "daily", "kitchen"],
            ),
            UGCBRollTemplate(
                template_id="before_after_split",
                purpose="transformation",
                shot_type="before_after",
                camera_movement="static",
                framing="split comparison",
                prompt_keywords=["before after", "clear difference", "same lighting", "same angle"],
                overlay_patterns=["前后差别很明显", "对比一眼看懂", "变化真的大"],
                use_for_categories=["beauty", "skincare", "fitness", "cleaning"],
            ),
            UGCBRollTemplate(
                template_id="cta_packshot",
                purpose="cta",
                shot_type="packshot",
                camera_movement="push_in",
                framing="hero product shot",
                prompt_keywords=["hero shot", "clean product lockup", "logo visible", "creator recommendation"],
                overlay_patterns=["最后总结一下", "我会继续回购", "真的值得试试"],
                use_for_categories=["beauty", "electronics", "home", "daily"],
            ),
        ]

    def infer_category(self, product_type: str, description: str = "") -> str:
        text = f"{product_type} {description}".lower()
        if any(x in text for x in ["serum", "cream", "skincare", "mask", "cosmetic", "makeup", "护肤", "美妆"]):
            return "beauty"
        if any(x in text for x in ["kitchen", "clean", "organizer", "vacuum", "home", "家居", "厨房"]):
            return "home"
        if any(x in text for x in ["phone", "camera", "earbud", "charger", "tech", "电子", "数码"]):
            return "electronics"
        if any(x in text for x in ["sport", "fitness", "健身"]):
            return "fitness"
        return "daily"

    def choose_template(self, purpose: str, product_type: str = "", description: str = "") -> UGCBRollTemplate:
        category = self.infer_category(product_type, description)
        purpose_norm = (purpose or "").lower()
        if any(x in purpose_norm for x in ["hook", "开场", "opening"]):
            candidates = [t for t in self.templates if t.purpose == "hook"]
        elif any(x in purpose_norm for x in ["problem", "痛点"]):
            candidates = [t for t in self.templates if t.purpose == "problem"]
        elif any(x in purpose_norm for x in ["proof", "detail", "细节"]):
            candidates = [t for t in self.templates if t.purpose == "proof"]
        elif any(x in purpose_norm for x in ["before", "after", "transform", "变化"]):
            candidates = [t for t in self.templates if t.purpose == "transformation"]
        elif any(x in purpose_norm for x in ["cta", "收口", "call to action"]):
            candidates = [t for t in self.templates if t.purpose == "cta"]
        else:
            candidates = [t for t in self.templates if t.purpose == "demo"]
        ranked = sorted(candidates, key=lambda t: 0 if category in t.use_for_categories else 1)
        return ranked[0]

    def list_templates(self) -> list[dict]:
        return [t.to_dict() for t in self.templates]
