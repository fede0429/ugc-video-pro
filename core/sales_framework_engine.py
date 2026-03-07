"""
core/sales_framework_engine.py
==============================
Sales narrative frameworks for UGC conversion-oriented scripts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SalesFrameworkPlan:
    framework: str
    hook_focus: str
    problem: str
    solution: str
    proof_points: list[str] = field(default_factory=list)
    objection_handling: list[str] = field(default_factory=list)
    cta_line: str = ""


class SalesFrameworkEngine:
    def choose_framework(
        self,
        product_category: str,
        platform: str,
        has_presenter: bool,
        explicit_hook_style: str = "",
    ) -> str:
        category = (product_category or "").lower()
        platform = (platform or "").lower()
        hook = (explicit_hook_style or "").lower()

        if "comparison" in hook:
            return "comparison"
        if category in {"skincare", "beauty", "supplement"}:
            return "pas"
        if category in {"electronics", "home"}:
            return "problem_solution_proof"
        if platform in {"instagram", "tiktok", "douyin"} and has_presenter:
            return "testimonial"
        return "aida"

    def build(
        self,
        framework: str,
        product_name: str,
        selling_points: list[str],
        target_audience: str,
        use_case: str,
        language: str,
    ) -> SalesFrameworkPlan:
        points = [p for p in (selling_points or []) if p]
        product_label = product_name or "this product"
        audience = target_audience or "people with this need"
        use_case = use_case or "daily use"
        proof = points[:3] or ["easy to use", "visibly useful", "fits into daily routine"]

        if framework == "pas":
            return SalesFrameworkPlan(
                framework="pas",
                hook_focus="pain_to_relief",
                problem=f"{audience} often struggle with an annoying daily problem.",
                solution=f"{product_label} helps simplify {use_case}.",
                proof_points=proof,
                objection_handling=["Does it really work?", "Is it easy to fit into a routine?"],
                cta_line=_localized_cta(language, product_label),
            )
        if framework == "comparison":
            return SalesFrameworkPlan(
                framework="comparison",
                hook_focus="why_this_one_wins",
                problem=f"There are too many options for {use_case}.",
                solution=f"{product_label} stands out because of {proof[0]}.",
                proof_points=proof,
                objection_handling=["What makes this different?", "Is it worth switching?"],
                cta_line=_localized_cta(language, product_label),
            )
        if framework == "testimonial":
            return SalesFrameworkPlan(
                framework="testimonial",
                hook_focus="personal_experience",
                problem=f"I did not expect much from {product_label} at first.",
                solution=f"After trying it in a real {use_case} context, it felt genuinely useful.",
                proof_points=proof,
                objection_handling=["Is this just hype?", "Would a normal person actually use it?"],
                cta_line=_localized_cta(language, product_label),
            )
        if framework == "problem_solution_proof":
            return SalesFrameworkPlan(
                framework="problem_solution_proof",
                hook_focus="clear_use_case",
                problem=f"{audience} want a simpler way to handle {use_case}.",
                solution=f"{product_label} is built to solve that with {proof[0]}.",
                proof_points=proof,
                objection_handling=["Will it be complicated?", "Does it look reliable?"],
                cta_line=_localized_cta(language, product_label),
            )
        return SalesFrameworkPlan(
            framework="aida",
            hook_focus="attention_interest_desire_action",
            problem=f"Most people overlook what makes {product_label} useful.",
            solution=f"{product_label} makes {use_case} easier and more enjoyable.",
            proof_points=proof,
            objection_handling=["Is this worth trying?"],
            cta_line=_localized_cta(language, product_label),
        )


def _localized_cta(language: str, product_name: str) -> str:
    lang = (language or "en").split(",")[0].lower()
    if lang == "it":
        return f"Se ti incuriosisce, prova {product_name} adesso."
    if lang == "zh":
        return f"如果你也有这个需求，现在就去看看 {product_name}。"
    return f"If this feels right for you, check out {product_name} now."
