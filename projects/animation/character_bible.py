
from __future__ import annotations

from typing import Iterable, List
from .models import CharacterBible


def build_character_bible(
    name: str,
    role: str,
    age_range: str,
    appearance: Iterable[str],
    wardrobe: Iterable[str],
    personality: Iterable[str],
    voice_style: str,
    catchphrases: Iterable[str] = (),
    reference_image_url: str = "",
) -> CharacterBible:
    appearance_list = [x for x in appearance if x]
    wardrobe_list = [x for x in wardrobe if x]
    personality_list = [x for x in personality if x]
    continuity_rules: List[str] = [
        f"{name} 的主色调、发型、脸型锚点保持一致。",
        f"{name} 的语言节奏和气质要持续贴合角色身份：{role}。",
        "关键道具和主服装在同一集内保持命名与外观一致。",
    ]
    return CharacterBible(
        name=name,
        role=role,
        age_range=age_range,
        appearance=appearance_list,
        wardrobe=wardrobe_list,
        personality=personality_list,
        voice_style=voice_style,
        catchphrases=list(catchphrases),
        continuity_rules=continuity_rules,
        reference_image_url=reference_image_url,
    )
