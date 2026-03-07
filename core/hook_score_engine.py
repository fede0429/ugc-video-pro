from __future__ import annotations

from dataclasses import dataclass, asdict


POWER_WORDS = {
    "zh": ["后悔", "真的", "别再", "立刻", "为什么", "秘密", "救星", "崩溃", "翻车", "反转"],
    "en": ["actually", "honestly", "secret", "stop", "need", "why", "mistake", "better", "confession", "warning"],
    "it": ["davvero", "errore", "segreto", "smetti", "perché", "attenzione", "ammetto"],
}


@dataclass
class HookScore:
    total_score: int
    curiosity_score: int
    clarity_score: int
    platform_fit_score: int
    product_signal_score: int
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class HookScoreEngine:
    def score(self, hook_line: str, hook_style: str, language: str, product_name: str = "") -> HookScore:
        text = (hook_line or "").strip()
        lang = (language or "en").split(",")[0].lower()
        notes: list[str] = []

        curiosity = 58
        if "?" in text or "？" in text:
            curiosity += 12
            notes.append("question_open_loop")
        if any(w in text.lower() for w in POWER_WORDS.get(lang, POWER_WORDS["en"])):
            curiosity += 10
            notes.append("power_words")
        if hook_style in {"curiosity_gap", "confession_hook", "comparison_challenge", "anti_ad"}:
            curiosity += 8
            notes.append("native_hook_style")

        clarity = 62
        if 8 <= len(text) <= 38:
            clarity += 12
            notes.append("concise_length")
        if product_name and product_name.lower()[:12] in text.lower():
            clarity += 8
            notes.append("mentions_product")
        if any(mark in text for mark in ["。", ".", "，", ","]):
            clarity += 4

        platform_fit = 60
        if hook_style in {"pain_point", "result_first", "confession_hook", "anti_ad"}:
            platform_fit += 12
        if len(text) <= 30:
            platform_fit += 8
        if any(w in text.lower() for w in ["真的", "honestly", "ammetto"]):
            platform_fit += 5

        product_signal = 58
        if product_name and any(tok for tok in product_name.split()[:2] if tok and tok.lower() in text.lower()):
            product_signal += 14
            notes.append("product_signal")
        if any(k in text.lower() for k in ["skin", "精华", "护肤", "shampoo", "serum", "mask", "cream", "机", "刷"]):
            product_signal += 8

        total = round((curiosity + clarity + platform_fit + product_signal) / 4)
        return HookScore(
            total_score=max(0, min(100, total)),
            curiosity_score=max(0, min(100, curiosity)),
            clarity_score=max(0, min(100, clarity)),
            platform_fit_score=max(0, min(100, platform_fit)),
            product_signal_score=max(0, min(100, product_signal)),
            notes=notes,
        )
