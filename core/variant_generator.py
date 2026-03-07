"""
core/variant_generator.py
=========================
Creative variant generation for UGC hooks and angles.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.hook_score_engine import HookScoreEngine


@dataclass
class CreativeVariant:
    variant_id: str
    angle_name: str
    hook_style: str
    hook_line: str
    framework: str
    score_hint: float = 0.0
    notes: list[str] = field(default_factory=list)
    hook_score: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "angle_name": self.angle_name,
            "hook_style": self.hook_style,
            "hook_line": self.hook_line,
            "framework": self.framework,
            "score_hint": self.score_hint,
            "notes": self.notes,
            "hook_score": self.hook_score,
        }


class VariantGenerator:
    def __init__(self):
        self.scorer = HookScoreEngine()

    def build_variants(
        self,
        language: str,
        hook_styles: list[str],
        product_name: str,
        selling_points: list[str],
        max_variants: int = 3,
    ) -> list[CreativeVariant]:
        styles = [s for s in hook_styles if s] or ["result_first", "pain_point", "curiosity_gap"]
        points = [p for p in (selling_points or []) if p]
        first_point = points[0] if points else "it made the difference quickly"
        variants: list[CreativeVariant] = []
        unique_styles = list(dict.fromkeys(styles))
        for idx, style in enumerate(unique_styles[:max_variants], start=1):
            hook_line = localized_hook(style, language, product_name, first_point)
            hook_score = self.scorer.score(hook_line=hook_line, hook_style=style, language=language, product_name=product_name)
            variants.append(CreativeVariant(
                variant_id=f"variant_{idx:02d}",
                angle_name=style.replace("_", " "),
                hook_style=style,
                hook_line=hook_line,
                framework="",
                score_hint=hook_score.total_score / 100,
                notes=[f"Primary selling point: {first_point}"] + hook_score.notes,
                hook_score=hook_score.to_dict(),
            ))
        variants.sort(key=lambda v: (v.hook_score.get("total_score", 0), v.score_hint), reverse=True)
        return variants

    def build_batch_variants(
        self,
        language: str,
        product_name: str,
        selling_points: list[str],
        preferred_styles: list[str] | None = None,
        max_variants: int = 8,
    ) -> list[CreativeVariant]:
        styles = list(dict.fromkeys((preferred_styles or []) + [
            "pain_point",
            "result_first",
            "confession_hook",
            "anti_ad",
            "curiosity_gap",
            "comparison_challenge",
            "social_proof",
            "transformation_story",
            "authority_claim",
            "listicle_number",
        ]))
        return self.build_variants(
            language=language,
            hook_styles=styles,
            product_name=product_name,
            selling_points=selling_points,
            max_variants=max_variants,
        )


def localized_hook(style: str, language: str, product_name: str, first_point: str) -> str:
    lang = (language or "en").split(",")[0].lower()
    product_name = product_name or "this product"
    style = (style or "result_first").lower()

    zh = {
        "pain_point": f"我之前一直被这个问题困扰，直到用了{product_name}。",
        "result_first": f"说真的，{product_name} 的效果比我预想的还明显。",
        "authority_claim": f"我试过很多类似产品，但{product_name}让我记住了。",
        "curiosity_gap": f"你知道我为什么最近一直在用{product_name}吗？",
        "listicle_number": f"关于{product_name}，我只说三个重点。",
        "social_proof": f"最近真的很多人问我为什么在用{product_name}。",
        "comparison_challenge": f"我对比了几款之后，最后留下了{product_name}。",
        "transformation_story": f"如果早点遇到{product_name}，我可能就不会走那么多弯路。",
        "anti_ad": f"这不是硬广，但{product_name}确实让我改观了。",
        "confession_hook": f"老实说，一开始我还挺怀疑{product_name}的。",
    }
    it = {
        "pain_point": f"Avevo sempre lo stesso problema, poi ho provato {product_name}.",
        "result_first": f"Onestamente, {product_name} mi ha sorpresa più del previsto.",
        "authority_claim": f"Ne ho provati tanti, ma {product_name} mi è rimasto in testa.",
        "curiosity_gap": f"Sai perché ultimamente non esco senza {product_name}?",
        "listicle_number": f"Ti dico tre cose su {product_name}.",
        "social_proof": f"Tutti mi stanno chiedendo cosa sto usando: è {product_name}.",
        "comparison_challenge": f"Ho confrontato diverse opzioni, e alla fine è rimasto {product_name}.",
        "transformation_story": f"Se avessi scoperto prima {product_name}, mi sarei evitata tanti tentativi.",
        "anti_ad": f"Non è la solita pubblicità: {product_name} mi ha davvero fatto cambiare idea.",
        "confession_hook": f"Lo ammetto: all'inizio ero scettica su {product_name}.",
    }
    en = {
        "pain_point": f"I kept dealing with the same issue until I tried {product_name}.",
        "result_first": f"Honestly, {product_name} worked better than I expected.",
        "authority_claim": f"I have tested a lot of these, and {product_name} stood out.",
        "curiosity_gap": f"Want to know why I keep reaching for {product_name}?",
        "listicle_number": f"Here are three reasons {product_name} got my attention.",
        "social_proof": f"People keep asking what I'm using, and it's {product_name}.",
        "comparison_challenge": f"I compared a bunch of options, and {product_name} was the one I kept.",
        "transformation_story": f"If I had found {product_name} sooner, I would have saved a lot of trial and error.",
        "anti_ad": f"This is not one of those fake ads, but {product_name} really changed my mind.",
        "confession_hook": f"Confession: I did not trust {product_name} at first.",
    }
    table = {"zh": zh, "it": it, "en": en}.get(lang, en)
    return table.get(style, table["result_first"])
