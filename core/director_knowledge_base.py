"""
core/director_knowledge_base.py
================================
UGC Production Knowledge Base.

Three template layers (from PDF Architecture doc):
  1. PERSONA_TEMPLATES  — presenter personality types
  2. HOOK_TEMPLATES     — proven opening patterns
  3. UGC_SHOT_LIBRARY   — shot types by function
  4. PLATFORM_PRESETS   — platform-specific rules
  5. SCENE_PROGRESSIONS — pre-built editing templates
"""
from __future__ import annotations
from typing import Optional

# ════════════════════════════════════════════════════════════════════════════════
# 1. PERSONA TEMPLATES
# ════════════════════════════════════════════════════════════════════════════════

PERSONA_TEMPLATES = {
    "bao_ma_recommendation": {
        "name": "宝妈推荐",
        "description": "Mother-of-children, trustworthy, practical, price-conscious",
        "hook_affinity": ["pain_point", "social_proof"],
        "tone": "warm, reassuring, practical",
        "speaking_rate": "medium",
        "voice_preset": "zh",
        "shot_types": ["selfie_closeup", "over_sink_demo", "desktop_review"],
        "openings": ["作为一个妈妈，我真的太理解这个困扰了…", "买了这么多，只有这个我会反复回购。"],
    },
    "girlfriend_recommendation": {
        "name": "闺蜜种草",
        "description": "Best-friend energy, enthusiastic, relatable, fun",
        "hook_affinity": ["result_first", "curiosity_gap"],
        "tone": "enthusiastic, casual, exclamatory",
        "speaking_rate": "fast",
        "voice_preset": "zh",
        "shot_types": ["selfie_closeup", "mirror_demo", "handheld_reaction"],
        "openings": ["姐妹们！这个东西我真的后悔没早买！", "天呐这个也太好用了吧！"],
    },
    "review_blogger": {
        "name": "测评博主",
        "description": "Professional reviewer, analytical, data-driven, authoritative",
        "hook_affinity": ["comparison_challenge", "authority_claim", "listicle_number"],
        "tone": "measured, analytical, credible",
        "speaking_rate": "medium",
        "voice_preset": "zh",
        "shot_types": ["desktop_review", "side_by_side_compare", "unbox_closeup"],
        "openings": ["我买了市面上五款，只有这一款值得推荐。", "测评结果出来了，只有一款满分。"],
    },
    "professional_explainer": {
        "name": "专业讲解",
        "description": "Subject-matter expert, educational, technical, trust-building",
        "hook_affinity": ["authority_claim", "listicle_number"],
        "tone": "expert, structured, informative",
        "speaking_rate": "measured",
        "voice_preset": "zh",
        "shot_types": ["desktop_review", "texture_macro", "side_by_side_compare"],
        "openings": ["作为从业十年的……", "今天给大家科普一下……"],
    },
    "contrast_complainer": {
        "name": "反差吐槽",
        "description": "Relatable frustration turned delight, comedic, authentic",
        "hook_affinity": ["pain_point", "transformation_story"],
        "tone": "sarcastic-then-delighted, authentic, comedic",
        "speaking_rate": "fast",
        "voice_preset": "zh",
        "shot_types": ["selfie_closeup", "handheld_reaction", "mirror_demo"],
        "openings": ["我以为这又是个智商税……结果我错了。", "买这个纯属被迫，结果香爆了。"],
    },
    "boyfriend_pov": {
        "name": "男友视角",
        "description": "Male perspective, genuine, clueless-turned-impressed",
        "hook_affinity": ["social_proof", "result_first"],
        "tone": "genuine, slightly confused, impressed",
        "speaking_rate": "medium",
        "voice_preset": "zh",
        "shot_types": ["selfie_closeup", "handheld_reaction"],
        "openings": ["我老婆让我拍这个……但说实话，效果确实不错。"],
    },
    "energetic_female": {
        "name": "Energetic Female (IT/EN)",
        "description": "High-energy Italian/English female presenter",
        "hook_affinity": ["result_first", "curiosity_gap"],
        "tone": "energetic, authentic, punchy",
        "speaking_rate": "fast",
        "voice_preset": "it",
        "shot_types": ["selfie_closeup", "handheld_reaction", "mirror_demo"],
        "openings": ["Guardate che risultati incredibili!", "Questo prodotto ha cambiato tutto!"],
    },
    "luxury_female": {
        "name": "Luxury Aspirational",
        "description": "Elegant, aspirational, slow-burn reveal",
        "hook_affinity": ["authority_claim", "curiosity_gap"],
        "tone": "poised, deliberate, aspirational",
        "speaking_rate": "slow",
        "voice_preset": "it",
        "shot_types": ["selfie_closeup", "texture_macro", "desktop_review"],
        "openings": ["C'è un segreto che uso da anni…", "Non tutti sanno che questo cambia tutto."],
    },
    "english_influencer": {
        "name": "English Influencer",
        "description": "US/UK influencer style, trend-aware, community-first",
        "hook_affinity": ["result_first", "social_proof"],
        "tone": "trendy, relatable, community-focused",
        "speaking_rate": "fast",
        "voice_preset": "en",
        "shot_types": ["selfie_closeup", "handheld_reaction", "over_sink_demo"],
        "openings": ["Okay I HAVE to share this with you guys…", "This product is genuinely changing my life."],
    },
}

# ════════════════════════════════════════════════════════════════════════════════
# 2. HOOK TEMPLATES
# ════════════════════════════════════════════════════════════════════════════════

HOOK_TEMPLATES = {
    "pain_point": {
        "name": "问题打断",
        "description": "Start with the viewer's frustration, then introduce product as savior",
        "structure": "PROBLEM → DISCOVERY → SOLUTION",
        "duration_range": [3, 6],
        "energy": "medium→high",
        "examples": {
            "zh": "我一直有{problem}的烦恼……直到我发现了这个。",
            "it": "Ho sempre sofferto di {problem}… finché non ho trovato questo.",
            "en": "I always struggled with {problem}… until I found this.",
        },
    },
    "result_first": {
        "name": "结果先行",
        "description": "Show the amazing result immediately, build curiosity around how",
        "structure": "RESULT → HOW → PRODUCT",
        "duration_range": [3, 5],
        "energy": "high",
        "examples": {
            "zh": "看看这个效果！我真的没想到会这么好。",
            "it": "Guardate questi risultati! Non me lo aspettavo proprio.",
            "en": "Look at these results! I genuinely cannot believe it.",
        },
    },
    "authority_claim": {
        "name": "权威背书",
        "description": "Establish expertise first, then give recommendation weight",
        "structure": "CREDENTIALS → CLAIM → EVIDENCE",
        "duration_range": [4, 6],
        "energy": "medium",
        "examples": {
            "zh": "用了三年护肤品，这一款是我唯一的回购。",
            "it": "Tre anni di skincare — questo è l'unico che ricompro sempre.",
            "en": "After three years of trying everything, this is the only one I reorder.",
        },
    },
    "curiosity_gap": {
        "name": "好奇缺口",
        "description": "Tease a secret/trick, gradually reveal over the video",
        "structure": "TEASE → BUILD → REVEAL",
        "duration_range": [3, 5],
        "energy": "medium→high",
        "examples": {
            "zh": "你知道为什么我每天出门必带这个吗？",
            "it": "Sapete perché porto sempre questo con me? Ve lo spiego.",
            "en": "Do you know why I never leave home without this?",
        },
    },
    "listicle_number": {
        "name": "数字列表",
        "description": "\"N reasons why\" structure — clear, scannable, credible",
        "structure": "NUMBER → REASONS → CTA",
        "duration_range": [3, 5],
        "energy": "medium",
        "examples": {
            "zh": "三个理由让你必须试试这个。",
            "it": "Tre motivi per cui devi provare questo.",
            "en": "Three reasons you absolutely need to try this.",
        },
    },
    "social_proof": {
        "name": "社会认证",
        "description": "Show that others love it before personal endorsement",
        "structure": "CROWD EVIDENCE → PERSONAL → PRODUCT",
        "duration_range": [3, 6],
        "energy": "medium",
        "examples": {
            "zh": "全公司都在问我用了什么，我今天来揭秘。",
            "it": "Tutti in ufficio mi chiedono cosa uso — oggi ve lo dico.",
            "en": "Everyone at work keeps asking what I use — here's the answer.",
        },
    },
    "comparison_challenge": {
        "name": "对比挑战",
        "description": "Put against competitors or old solution — clear winner emerges",
        "structure": "ALTERNATIVES → TEST → CLEAR WINNER",
        "duration_range": [4, 7],
        "energy": "high",
        "examples": {
            "zh": "我买了市面上五款，只有这一款用完整瓶。",
            "it": "Ne ho provati cinque sul mercato — solo questo l'ho finito.",
            "en": "I tested five brands — only this one made it to the bottom.",
        },
    },
    "transformation_story": {
        "name": "蜕变叙事",
        "description": "Personal before/after story — emotional, high relatability",
        "structure": "BEFORE STATE → JOURNEY → AFTER STATE",
        "duration_range": [4, 6],
        "energy": "medium",
        "examples": {
            "zh": "三个月前我还在为这个问题烦恼……现在完全不一样了。",
            "it": "Tre mesi fa avevo ancora questo problema… ora è tutto diverso.",
            "en": "Three months ago I was still struggling with this… now everything's different.",
        },
    },
}

# ════════════════════════════════════════════════════════════════════════════════
# 3. UGC SHOT LIBRARY
# ════════════════════════════════════════════════════════════════════════════════

UGC_SHOT_LIBRARY = {
    # ── Selfie / A-roll shots ─────────────────────────────────────────────────
    "selfie_closeup": {
        "name": "Selfie Close-up",
        "track": "a_roll",
        "description": "Tight selfie framing, face fills most of frame, direct eye contact",
        "prompt_template": "Vertical selfie-style close-up of a {persona} holding {product}, direct eye contact with camera, natural home lighting, authentic UGC feel, 9:16 portrait",
        "duration_range": [3, 8], "energy": "medium",
    },
    "mirror_demo": {
        "name": "Mirror Demo",
        "track": "a_roll",
        "description": "Person demonstrating product in front of bathroom/bedroom mirror",
        "prompt_template": "Person demonstrating {product} in front of bathroom mirror, warm backlighting, casual home setting, genuine reaction, 9:16 vertical",
        "duration_range": [4, 8], "energy": "medium",
    },
    "handheld_reaction": {
        "name": "Handheld Reaction",
        "track": "a_roll",
        "description": "Slightly shaky handheld camera, authentic reaction shot",
        "prompt_template": "Handheld POV style, person holding {product} with genuine surprised/delighted expression, slight camera movement, authentic creator content feel, 9:16 vertical",
        "duration_range": [3, 6], "energy": "high",
    },
    "over_sink_demo": {
        "name": "Over-sink Demo",
        "track": "a_roll",
        "description": "Classic bathroom/kitchen sink demo shot, overhead or eye-level",
        "prompt_template": "Clean overhead or eye-level shot of hands demonstrating {product} over bathroom sink, well-lit, clean white tiles, authentic tutorial feel, 9:16 vertical",
        "duration_range": [4, 8], "energy": "low",
    },
    "desktop_review": {
        "name": "Desktop Review",
        "track": "a_roll",
        "description": "Product displayed on desk/vanity with reviewer in background",
        "prompt_template": "Product {product} displayed neatly on a desk or vanity, reviewer visible in background reviewing, organized flat lay elements, clean lighting, 9:16 vertical",
        "duration_range": [5, 10], "energy": "low",
    },
    # ── B-roll product shots ──────────────────────────────────────────────────
    "side_by_side_compare": {
        "name": "Side-by-side Compare",
        "track": "b_roll",
        "description": "Two products or before/after side by side",
        "prompt_template": "Split frame or side-by-side comparison showing {product} next to {comparison}, clean minimal background, sharp focus on both, 9:16 vertical",
        "duration_range": [4, 8], "energy": "medium",
    },
    "unbox_closeup": {
        "name": "Unboxing Close-up",
        "track": "b_roll",
        "description": "Hands opening packaging, first reveal of product",
        "prompt_template": "Close-up of hands carefully opening premium packaging to reveal {product}, white tissue paper, warm soft light, anticipation and satisfaction, 9:16 vertical",
        "duration_range": [4, 7], "energy": "medium",
    },
    "texture_macro": {
        "name": "Texture Macro",
        "track": "b_roll",
        "description": "Extreme close-up showing product texture, material quality",
        "prompt_template": "Extreme macro close-up of {product} surface texture, shallow depth of field, dramatic raking side light revealing material quality and detail, 9:16 vertical",
        "duration_range": [3, 6], "energy": "low",
    },
    "apply_closeup": {
        "name": "Application Close-up",
        "track": "b_roll",
        "description": "Close-up of product being applied or used",
        "prompt_template": "Close-up of hands applying {product}, soft lighting, smooth motion, result visible on skin/surface, beauty editorial quality, 9:16 vertical",
        "duration_range": [4, 8], "energy": "medium",
    },
    "product_360": {
        "name": "360° Product Orbit",
        "track": "b_roll",
        "description": "Camera orbits around product on clean surface",
        "prompt_template": "Camera slowly orbiting {product} on clean white marble surface, studio lighting, shadows rotating, premium product photography motion, 9:16 vertical",
        "duration_range": [5, 10], "energy": "low",
    },
    "lifestyle_context": {
        "name": "Lifestyle Context",
        "track": "b_roll",
        "description": "Product in natural lifestyle environment",
        "prompt_template": "{product} placed in a beautiful {lifestyle_setting}, natural window light, lifestyle editorial feel, aspirational but achievable, 9:16 vertical",
        "duration_range": [5, 8], "energy": "low",
    },
    "result_reveal": {
        "name": "Result Reveal",
        "track": "b_roll",
        "description": "The before→after transformation moment",
        "prompt_template": "Reveal shot showing the result of using {product}, dramatic lighting improvement or visual transformation, before/after feel without split screen, 9:16 vertical",
        "duration_range": [4, 7], "energy": "high",
    },
}

# ════════════════════════════════════════════════════════════════════════════════
# 4. PLATFORM PRESETS
# ════════════════════════════════════════════════════════════════════════════════

PLATFORM_PRESETS = {
    "douyin": {
        "name": "抖音 Douyin",
        "aspect_ratio": "9:16",
        "max_duration": 60,
        "optimal_duration": 20,
        "hook_window_seconds": 3,
        "subtitle_style": "large_center",
        "preferred_hook_styles": ["result_first", "pain_point", "curiosity_gap"],
        "cta_style": "comment_below",
    },
    "tiktok": {
        "name": "TikTok",
        "aspect_ratio": "9:16",
        "max_duration": 60,
        "optimal_duration": 25,
        "hook_window_seconds": 3,
        "subtitle_style": "large_center",
        "preferred_hook_styles": ["result_first", "transformation_story", "social_proof"],
        "cta_style": "link_in_bio",
    },
    "instagram": {
        "name": "Instagram Reels",
        "aspect_ratio": "9:16",
        "max_duration": 90,
        "optimal_duration": 30,
        "hook_window_seconds": 4,
        "subtitle_style": "bottom_bar",
        "preferred_hook_styles": ["authority_claim", "curiosity_gap", "listicle_number"],
        "cta_style": "link_in_bio",
    },
    "youtube_shorts": {
        "name": "YouTube Shorts",
        "aspect_ratio": "9:16",
        "max_duration": 60,
        "optimal_duration": 40,
        "hook_window_seconds": 5,
        "subtitle_style": "bottom_bar",
        "preferred_hook_styles": ["listicle_number", "comparison_challenge", "authority_claim"],
        "cta_style": "subscribe",
    },
    "kuaishou": {
        "name": "快手 Kuaishou",
        "aspect_ratio": "9:16",
        "max_duration": 60,
        "optimal_duration": 20,
        "hook_window_seconds": 2,
        "subtitle_style": "large_center",
        "preferred_hook_styles": ["pain_point", "social_proof", "transformation_story"],
        "cta_style": "buy_now",
    },
}

# ════════════════════════════════════════════════════════════════════════════════
# 5. SCENE PROGRESSIONS (pre-built editing templates)
# ════════════════════════════════════════════════════════════════════════════════

SCENE_PROGRESSIONS = {
    "15s_testimonial": [
        {"track": "a_roll", "shot": "selfie_closeup",   "duration": 4, "role": "hook"},
        {"track": "b_roll", "shot": "apply_closeup",    "duration": 5, "role": "demo"},
        {"track": "a_roll", "shot": "handheld_reaction","duration": 3, "role": "reaction"},
        {"track": "a_roll", "shot": "selfie_closeup",   "duration": 3, "role": "cta"},
    ],
    "30s_hybrid": [
        {"track": "a_roll", "shot": "selfie_closeup",   "duration": 4, "role": "hook"},
        {"track": "b_roll", "shot": "unbox_closeup",    "duration": 5, "role": "reveal"},
        {"track": "a_roll", "shot": "mirror_demo",      "duration": 5, "role": "demo_narration"},
        {"track": "b_roll", "shot": "texture_macro",    "duration": 4, "role": "detail"},
        {"track": "a_roll", "shot": "handheld_reaction","duration": 4, "role": "reaction"},
        {"track": "b_roll", "shot": "lifestyle_context","duration": 5, "role": "lifestyle"},
        {"track": "a_roll", "shot": "selfie_closeup",   "duration": 3, "role": "cta"},
    ],
    "60s_deep_dive": [
        {"track": "a_roll", "shot": "selfie_closeup",   "duration": 5, "role": "hook"},
        {"track": "b_roll", "shot": "unbox_closeup",    "duration": 6, "role": "unbox"},
        {"track": "a_roll", "shot": "desktop_review",   "duration": 6, "role": "intro"},
        {"track": "b_roll", "shot": "texture_macro",    "duration": 5, "role": "detail"},
        {"track": "a_roll", "shot": "over_sink_demo",   "duration": 6, "role": "demo"},
        {"track": "b_roll", "shot": "apply_closeup",    "duration": 6, "role": "application"},
        {"track": "a_roll", "shot": "mirror_demo",      "duration": 5, "role": "mid_reaction"},
        {"track": "b_roll", "shot": "result_reveal",    "duration": 6, "role": "result"},
        {"track": "a_roll", "shot": "handheld_reaction","duration": 5, "role": "final_reaction"},
        {"track": "b_roll", "shot": "lifestyle_context","duration": 5, "role": "lifestyle"},
        {"track": "a_roll", "shot": "selfie_closeup",   "duration": 5, "role": "cta"},
    ],
    "pure_broll_20s": [
        {"track": "b_roll", "shot": "unbox_closeup",    "duration": 5, "role": "reveal"},
        {"track": "b_roll", "shot": "texture_macro",    "duration": 4, "role": "detail"},
        {"track": "b_roll", "shot": "apply_closeup",    "duration": 5, "role": "demo"},
        {"track": "b_roll", "shot": "result_reveal",    "duration": 4, "role": "result"},
        {"track": "b_roll", "shot": "lifestyle_context","duration": 4, "role": "lifestyle"},
    ],
}

CAMERA_MOVEMENT_RULES = {
    "variety_required": True,
    "no_consecutive_same": True,
    "movements": [
        "static_closeup", "slow_dolly_in", "slow_dolly_out",
        "orbit_left", "orbit_right", "tilt_up", "tilt_down",
        "pan_left", "pan_right", "handheld_shake", "top_down",
        "low_angle", "rack_focus",
    ],
    "energy_mapping": {
        "high": ["handheld_shake", "slow_dolly_in", "rack_focus"],
        "medium": ["orbit_left", "orbit_right", "tilt_up", "pan_left"],
        "low": ["static_closeup", "slow_dolly_out", "top_down"],
    },
}

HOOK_PATTERNS = HOOK_TEMPLATES   # alias for backward compat

PROMPT_TEMPLATES = {
    "seedance_15": "Strong reference lock. Camera: {camera}. {scene}. Reference image is exact first frame.",
    "veo_31_fast": "Veo: reference = LITERAL first frame. Motion only for continuation. {scene}. (no subtitles)",
    "veo_31_quality": "Veo Pro: cinematic precision. {scene}. Rack focus, motivated lighting. (no subtitles)",
    "runway": "Fast clip. Self-contained scene. {scene}. {camera} movement.",
    "kling_30": "{scene}. {camera}. Native audio supported.",
    "sora_2": "Style reference (may drift). {scene}. {camera}.",
    "hailuo": "High-fidelity. {scene}. {camera}.",
}


def get_production_context(
    product_category: str = "unknown",
    duration: int = 30,
    platform: str = "douyin",
    persona_key: str = "girlfriend_recommendation",
    hook_style: str = "result_first",
) -> dict:
    """Return a tailored knowledge package for the UGCProducer."""
    platform_info = PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS["douyin"])
    persona_info = PERSONA_TEMPLATES.get(persona_key, PERSONA_TEMPLATES["energetic_female"])
    hook_info = HOOK_TEMPLATES.get(hook_style, HOOK_TEMPLATES["result_first"])

    # Pick progression template
    if duration <= 18:
        progression_key = "15s_testimonial"
    elif duration <= 40:
        progression_key = "30s_hybrid"
    else:
        progression_key = "60s_deep_dive"

    return {
        "platform": platform_info,
        "persona": persona_info,
        "hook": hook_info,
        "scene_progression": SCENE_PROGRESSIONS.get(progression_key, []),
        "shot_library": UGC_SHOT_LIBRARY,
        "camera_rules": CAMERA_MOVEMENT_RULES,
        "prompt_templates": PROMPT_TEMPLATES,
    }


def get_shot_prompt(shot_key: str, product_desc: str, **kwargs) -> str:
    shot = UGC_SHOT_LIBRARY.get(shot_key)
    if not shot:
        return f"Product showcase: {product_desc}, cinematic, 9:16 vertical"
    template = shot["prompt_template"]
    return template.format(product=product_desc, **{k: v for k, v in kwargs.items() if f"{{{k}}}" in template})
