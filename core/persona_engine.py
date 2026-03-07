"""
core/persona_engine.py
======================
Presenter persona selection and normalization for UGC video generation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PersonaDefinition:
    persona_id: str
    role_label: str
    language: str
    speaking_style: str
    emotional_tone: str
    trust_mode: str
    camera_behavior: str
    vocabulary_style: str
    cta_style: str
    recommended_shot_types: list[str] = field(default_factory=list)
    preferred_hook_styles: list[str] = field(default_factory=list)
    realism_notes: list[str] = field(default_factory=list)


PERSONA_LIBRARY: dict[str, PersonaDefinition] = {
    "energetic_female": PersonaDefinition(
        persona_id="energetic_female",
        role_label="energetic creator friend",
        language="it",
        speaking_style="casual_conversational",
        emotional_tone="energetic",
        trust_mode="friend_recommendation",
        camera_behavior="handheld_selfie",
        vocabulary_style="short punchy sentences",
        cta_style="soft_urgent",
        recommended_shot_types=["selfie_closeup", "handheld_reaction", "mirror_demo"],
        preferred_hook_styles=["result_first", "pain_point", "curiosity_gap"],
        realism_notes=["slight handheld motion", "quick sentence cadence", "small reaction pauses"],
    ),
    "luxury_female": PersonaDefinition(
        persona_id="luxury_female",
        role_label="premium beauty tastemaker",
        language="it",
        speaking_style="poised_deliberate",
        emotional_tone="calm_confident",
        trust_mode="aspirational_authority",
        camera_behavior="steady_phone_camera",
        vocabulary_style="clean premium phrasing",
        cta_style="elegant_soft_sell",
        recommended_shot_types=["selfie_closeup", "texture_macro", "desktop_review"],
        preferred_hook_styles=["curiosity_gap", "authority_claim", "result_first"],
        realism_notes=["controlled movement", "clean framing", "slightly slower pacing"],
    ),
    "bao_ma_recommendation": PersonaDefinition(
        persona_id="bao_ma_recommendation",
        role_label="practical mom reviewer",
        language="zh",
        speaking_style="warm_reassuring",
        emotional_tone="trustworthy",
        trust_mode="family_recommendation",
        camera_behavior="home_handheld",
        vocabulary_style="daily-life examples",
        cta_style="warm_reassurance",
        recommended_shot_types=["selfie_closeup", "bathroom_demo", "kitchen_counter_talk"],
        preferred_hook_styles=["pain_point", "social_proof", "transformation_story"],
        realism_notes=["home environment", "natural pauses", "less polished framing"],
    ),
    "review_blogger": PersonaDefinition(
        persona_id="review_blogger",
        role_label="review style creator",
        language="zh",
        speaking_style="clear_confident",
        emotional_tone="confident",
        trust_mode="testing_and_proof",
        camera_behavior="desk_plus_handheld",
        vocabulary_style="specific comparison points",
        cta_style="proof_then_cta",
        recommended_shot_types=["desktop_review", "side_by_side_compare", "unbox_closeup"],
        preferred_hook_styles=["result_first", "comparison_challenge", "authority_claim"],
        realism_notes=["quick cuts", "comparison language", "hands-on framing"],
    ),
    "professional_explainer": PersonaDefinition(
        persona_id="professional_explainer",
        role_label="expert explainer",
        language="zh",
        speaking_style="clear_confident",
        emotional_tone="educational",
        trust_mode="authority",
        camera_behavior="half_body_static",
        vocabulary_style="simple but structured",
        cta_style="reasoned_recommendation",
        recommended_shot_types=["desk_review", "half_body_talk", "product_detail_hold"],
        preferred_hook_styles=["authority_claim", "listicle_number", "result_first"],
        realism_notes=["stable framing", "measured cadence", "proof oriented"],
    ),
    "english_influencer": PersonaDefinition(
        persona_id="english_influencer",
        role_label="US style TikTok creator",
        language="en",
        speaking_style="casual_conversational",
        emotional_tone="authentic",
        trust_mode="friend_recommendation",
        camera_behavior="selfie_phone_camera",
        vocabulary_style="natural creator slang",
        cta_style="link_in_bio",
        recommended_shot_types=["selfie_closeup", "handheld_reaction", "over_sink_demo"],
        preferred_hook_styles=["pain_point", "anti_ad", "confession_hook"],
        realism_notes=["filler words", "micro pauses", "slight framing imperfections"],
    ),
    "calm_male": PersonaDefinition(
        persona_id="calm_male",
        role_label="calm male reviewer",
        language="it",
        speaking_style="warm_reassuring",
        emotional_tone="steady",
        trust_mode="reasoned_recommendation",
        camera_behavior="desk_static",
        vocabulary_style="simple direct wording",
        cta_style="clear_soft_sell",
        recommended_shot_types=["desktop_review", "half_body_talk", "product_detail_hold"],
        preferred_hook_styles=["pain_point", "comparison_challenge", "result_first"],
        realism_notes=["stable posture", "measured delivery"],
    ),
}


def get_persona_definition(
    persona_template: Optional[str],
    language: str = "it",
) -> PersonaDefinition:
    key = (persona_template or "").strip() or ""
    if key in PERSONA_LIBRARY:
        persona = PERSONA_LIBRARY[key]
        return persona
    # choose first matching language fallback
    lang = (language or "it").split(",")[0].strip().lower()
    for persona in PERSONA_LIBRARY.values():
        if persona.language == lang:
            return persona
    return PERSONA_LIBRARY["energetic_female"]


def list_persona_ids() -> list[str]:
    return sorted(PERSONA_LIBRARY.keys())
