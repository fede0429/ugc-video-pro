"""
core/director_knowledge_base.py
================================
Professional Knowledge Base for the Director Agent.

This module transforms the Director Agent from a generic "film director" persona
into a specialized UGC product video production expert. It contains:

    1. UGC_SHOT_LIBRARY      — 30+ professional shot types with video-gen prompts
    2. HOOK_PATTERNS          — 8 proven opening hook strategies for first 3 seconds
    3. SCENE_PROGRESSIONS     — Pre-built editing templates by video duration
    4. PRODUCT_DEMO_ACTIONS   — Category-specific product demonstration actions
    5. CTA_TEMPLATES          — Multi-language call-to-action endings (IT/ZH/EN)
    6. CAMERA_MOVEMENT_RULES  — Movement variety & transition rules
    7. PROMPT_TEMPLATES       — Per-model optimized prompt engineering rules
    8. A_B_ROLL_SYSTEM        — A-Roll / B-Roll / C-Roll layering definitions

The Director Agent calls `get_production_context()` to receive a tailored
knowledge package for each video generation job.

Architecture:
    DirectorAgent.create_production_plan()
        └─ knowledge_base.get_production_context(
               product_category, duration, languages, model_key
           )
        └─ Returns: dict with shot_sequence, hook, cta, prompt_rules, etc.

IMPORTANT: Product images are SACRED — never alter product appearance.
All shots describe SCENE/CAMERA around the product, not product modification.
"""

from typing import Optional


# ════════════════════════════════════════════════════════════
# 1. UGC SHOT LIBRARY — Professional shot types for product videos
# ════════════════════════════════════════════════════════════

UGC_SHOT_LIBRARY = {
    # ── Opening / Hook Shots ────────────────────────────────────
    "hook_product_drop": {
        "name": "Product Drop Reveal",
        "description": "Product enters frame from above, lands on surface with impact",
        "prompt_template": "A {product} drops from above into frame, landing on a {surface}, slight bounce, dramatic lighting from the side, shallow depth of field, slow motion impact, commercial style, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "high",
        "position": "opening",
    },
    "hook_hand_reveal": {
        "name": "Hand Reveal",
        "description": "Human hand reaches into frame and reveals/presents the product",
        "prompt_template": "A woman's hand elegantly reaches into frame from the right side, presenting a {product} to the camera, clean {background} background, soft studio lighting, close-up, commercial photography style, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "medium",
        "position": "opening",
    },
    "hook_unboxing_pov": {
        "name": "Unboxing POV",
        "description": "First-person view opening a package to reveal the product",
        "prompt_template": "First person POV of hands opening a premium package box, tissue paper being pulled aside to reveal a {product} inside, warm ambient lighting, anticipation, unboxing experience, 9:16 vertical",
        "duration_range": [4, 6],
        "energy": "medium",
        "position": "opening",
    },
    "hook_before_after": {
        "name": "Before/After Split",
        "description": "Quick visual comparison showing the problem then the product solution",
        "prompt_template": "Split screen showing a {problem_scene} transitioning to a {solution_scene} with {product}, clean modern aesthetic, bright lighting, transformation reveal, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "high",
        "position": "opening",
    },
    "hook_lifestyle_interrupt": {
        "name": "Lifestyle Pattern Interrupt",
        "description": "Person in everyday situation suddenly notices/discovers the product",
        "prompt_template": "A person in a {lifestyle_setting} pauses and picks up a {product} from the table, genuine curiosity and delight on their face, natural ambient lighting, candid lifestyle shot, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "medium",
        "position": "opening",
    },

    # ── Product Detail Shots ────────────────────────────────────
    "detail_360_orbit": {
        "name": "360° Product Orbit",
        "description": "Camera orbits around the product showing all angles",
        "prompt_template": "Smooth 360-degree orbital camera movement around a {product} floating on a {background} background, 3-point studio lighting, product rotating slowly, showing all angles and details, commercial quality, 9:16 vertical",
        "duration_range": [4, 8],
        "energy": "low",
        "position": "middle",
    },
    "detail_macro_texture": {
        "name": "Macro Texture Close-up",
        "description": "Extreme close-up showing material quality, stitching, or surface detail",
        "prompt_template": "Extreme close-up macro shot of {product_detail} on the {product}, sharp focus on texture and craftsmanship, soft bokeh background, studio lighting revealing surface details, 100mm lens feel, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "low",
        "position": "middle",
    },
    "detail_feature_highlight": {
        "name": "Feature Callout",
        "description": "Camera pushes in to highlight a specific feature or detail",
        "prompt_template": "Camera slowly pushes in toward the {feature} of the {product}, cinematic focus pull from background to sharp detail, clean studio environment, dramatic side lighting, product hero shot, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "low",
        "position": "middle",
    },
    "detail_color_showcase": {
        "name": "Color/Variant Display",
        "description": "Multiple color variants or related products arranged aesthetically",
        "prompt_template": "Flat lay arrangement of {product} in multiple colors on a {surface}, camera slowly pulling up and back, organized aesthetic display, soft overhead lighting, product catalog style, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "low",
        "position": "middle",
    },

    # ── Demonstration Shots ───────────────────────────────────
    "demo_hand_use": {
        "name": "Hands-On Demo",
        "description": "Hands actively using/interacting with the product",
        "prompt_template": "Close-up of hands {action_verb} the {product}, natural and confident movements, clean workspace, warm lighting, demonstrating ease of use, UGC authentic feel, 9:16 vertical",
        "duration_range": [4, 8],
        "energy": "medium",
        "position": "middle",
    },
    "demo_application": {
        "name": "Product Application",
        "description": "Showing the product being applied or used on skin/surface",
        "prompt_template": "Close-up of {product} being applied to {surface_or_skin}, smooth and satisfying application motion, natural lighting, focus on the product in use, clean aesthetic, 9:16 vertical",
        "duration_range": [4, 6],
        "energy": "medium",
        "position": "middle",
    },
    "demo_comparison": {
        "name": "Side-by-Side Comparison",
        "description": "Product next to competitor or older version for visual comparison",
        "prompt_template": "Side-by-side comparison on a clean surface, {product} prominently positioned on the right, {comparison_item} on the left, overhead camera angle, even lighting, product advantage clearly visible, 9:16 vertical",
        "duration_range": [4, 6],
        "energy": "medium",
        "position": "middle",
    },
    "demo_result_reveal": {
        "name": "Result Reveal",
        "description": "Showing the result or effect after using the product",
        "prompt_template": "Dramatic reveal of the result after using {product}, camera pulling back to show the {result}, clean environment, wow moment, satisfying transformation, bright lighting, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "high",
        "position": "middle",
    },
    "demo_pour_squeeze": {
        "name": "Pour/Squeeze/Dispense",
        "description": "Product dispensing its contents (cream, liquid, powder)",
        "prompt_template": "Satisfying close-up of {product} being {dispense_action}, the {content_type} flowing out smoothly, clean background, ASMR-like detail, studio lighting catching the texture, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "medium",
        "position": "middle",
    },

    # ── Lifestyle / Context Shots ─────────────────────────────
    "lifestyle_in_use": {
        "name": "Lifestyle In-Use",
        "description": "Product being used naturally in a real-life setting",
        "prompt_template": "A person casually using {product} in a {setting}, natural body language, warm ambient lighting, lifestyle photography feel, genuine and relatable moment, 9:16 vertical",
        "duration_range": [4, 8],
        "energy": "medium",
        "position": "middle",
    },
    "lifestyle_environment": {
        "name": "Environment Context",
        "description": "Product placed naturally in its intended environment",
        "prompt_template": "{product} placed naturally on a {surface} in a {environment}, environmental context showing where the product belongs, soft natural lighting from a window, editorial style, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "low",
        "position": "middle",
    },
    "lifestyle_morning_routine": {
        "name": "Morning Routine Integration",
        "description": "Product as part of a daily routine sequence",
        "prompt_template": "A person incorporating {product} into their morning routine, reaching for it on the bathroom counter, warm golden hour light through window, authentic daily life moment, 9:16 vertical",
        "duration_range": [4, 6],
        "energy": "low",
        "position": "middle",
    },
    "lifestyle_social_proof": {
        "name": "Social Sharing Moment",
        "description": "Person excitedly showing the product to someone/camera",
        "prompt_template": "A person excitedly holding up {product} toward the camera, genuine smile and enthusiasm, bright and clean background, UGC selfie-style framing, natural front-facing lighting, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "high",
        "position": "middle",
    },

    # ── Hero / Cinematic Shots ──────────────────────────────
    "hero_pedestal": {
        "name": "Product Pedestal Hero",
        "description": "Product on a pedestal or elevated surface, dramatic lighting",
        "prompt_template": "Cinematic hero shot of {product} on a marble pedestal, dramatic volumetric lighting from behind, slight camera dolly forward, premium feel, dark gradient background, commercial ad quality, 9:16 vertical",
        "duration_range": [4, 6],
        "energy": "medium",
        "position": "ending",
    },
    "hero_golden_hour": {
        "name": "Golden Hour Beauty Shot",
        "description": "Product bathed in warm golden light, dreamy atmosphere",
        "prompt_template": "{product} bathed in warm golden hour sunlight, lens flare, dreamy bokeh background, warm color grading, the product glowing beautifully, aspirational mood, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "low",
        "position": "ending",
    },
    "hero_splash_dynamic": {
        "name": "Dynamic Splash/Impact",
        "description": "Product with dynamic elements (water splash, powder burst, etc.)",
        "prompt_template": "{product} surrounded by a dramatic {dynamic_element}, frozen motion capture, black background, high-speed photography style, striking visual impact, premium commercial quality, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "high",
        "position": "ending",
    },

    # ── Closing / CTA Shots ───────────────────────────────
    "cta_product_array": {
        "name": "Product Line Display",
        "description": "Multiple products from the line arranged together for final shot",
        "prompt_template": "Elegant arrangement of {product} and related items from the product line, clean minimal background, perfectly organized, overhead camera slowly pulling away, commercial catalog quality, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "low",
        "position": "ending",
    },
    "cta_satisfied_user": {
        "name": "Satisfied User Close",
        "description": "Person looking satisfied/happy after using the product",
        "prompt_template": "Close-up of a person's satisfied expression after using {product}, genuine contentment, warm soft lighting, gentle camera push-in, emotional connection, authentic UGC feel, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "medium",
        "position": "ending",
    },
    "cta_logo_reveal": {
        "name": "Brand Logo Reveal",
        "description": "Product with brand visible, clean ending frame",
        "prompt_template": "{product} centered in frame with brand label clearly visible, clean background fading to white, subtle light rays, final commercial shot, professional product photography, 9:16 vertical",
        "duration_range": [2, 4],
        "energy": "low",
        "position": "ending",
    },
    "cta_hand_gesture": {
        "name": "Gesture to Action",
        "description": "Hand pointing at or gesturing toward the product as a visual CTA",
        "prompt_template": "A hand elegantly gesturing toward {product} in center frame, 'look at this' invitation gesture, clean background, ring light reflection, direct to camera style, 9:16 vertical",
        "duration_range": [2, 4],
        "energy": "medium",
        "position": "ending",
    },

    # ── Transition / B-Roll Shots ───────────────────────────
    "broll_ambient_pour": {
        "name": "Ambient Pour/Flow",
        "description": "Satisfying liquid or material flow as visual texture",
        "prompt_template": "Satisfying slow-motion {material} flowing smoothly, warm tones, clean background, ASMR-like visual texture, abstract beauty shot, closeup, 9:16 vertical",
        "duration_range": [2, 4],
        "energy": "low",
        "position": "transition",
    },
    "broll_hands_prep": {
        "name": "Preparation Hands",
        "description": "Hands preparing or organizing before using the product",
        "prompt_template": "Close-up of hands carefully arranging items on a clean surface, preparing to use {product}, deliberate and satisfying movements, top-down angle, warm lighting, 9:16 vertical",
        "duration_range": [3, 5],
        "energy": "low",
        "position": "transition",
    },
    "broll_environment_detail": {
        "name": "Environment Detail",
        "description": "Close-up of the surrounding environment to set mood",
        "prompt_template": "Atmospheric close-up of {environment_detail} in a {setting}, shallow depth of field, setting the mood, warm ambient lighting, cinematic feel, 9:16 vertical",
        "duration_range": [2, 4],
        "energy": "low",
        "position": "transition",
    },
}


# ════════════════════════════════════════════════════════════
# 2. HOOK PATTERNS — First 3 seconds that stop the scroll
# ════════════════════════════════════════════════════════════

HOOK_PATTERNS = {
    "pain_point": {
        "name": "Pain Point Call-Out",
        "description": "Start by naming a common frustration the viewer relates to",
        "structure": "Name problem → Show frustration → Introduce product as solution",
        "visual_hook": "Close-up of messy/frustrating situation, then quick cut to product",
        "audio_templates": {
            "it": "Sei stanca di {problem}? Ho trovato la soluzione perfetta.",
            "zh": "还在为{problem}烦恼吗？我找到了完美的解决方案。",
            "en": "Tired of {problem}? I found the perfect solution.",
        },
        "best_for": ["skincare", "cleaning", "tech", "health"],
    },
    "result_first": {
        "name": "Result-First Reveal",
        "description": "Show the amazing end result immediately, then explain how",
        "structure": "Show stunning result → Build curiosity → Reveal the product",
        "visual_hook": "Beautiful result shot (glowing skin, clean space, etc.) holds 2 seconds",
        "audio_templates": {
            "it": "Guarda questo risultato incredibile... tutto grazie a un solo prodotto.",
            "zh": "看看这个惊人的效果……全靠一个产品。",
            "en": "Look at this incredible result... all thanks to one product.",
        },
        "best_for": ["beauty", "skincare", "fitness", "home"],
    },
    "authority_claim": {
        "name": "Authority/Expertise Claim",
        "description": "Establish credibility immediately with a bold claim",
        "structure": "Authority statement → Specific credential → Product recommendation",
        "visual_hook": "Person confidently looking at camera, holding or near the product",
        "audio_templates": {
            "it": "Come esperta di {field} con {years} anni di esperienza, questo è il prodotto che raccomando di più.",
            "zh": "作为拥有{years}年经验的{field}专家，这是我最推荐的产品。",
            "en": "As a {field} expert with {years} years of experience, this is my top recommendation.",
        },
        "best_for": ["professional_tools", "health", "tech", "luxury"],
    },
    "curiosity_gap": {
        "name": "Curiosity Gap / Secret",
        "description": "Hint at hidden knowledge or a secret the viewer needs to know",
        "structure": "Tease secret → Create urgency → Reveal product",
        "visual_hook": "Product partially hidden or covered, gradually revealed",
        "audio_templates": {
            "it": "Il segreto che le {group} italiane non condividono...",
            "zh": "很多人不知道的秘密……",
            "en": "The secret that nobody is talking about...",
        },
        "best_for": ["beauty", "fashion", "food", "wellness"],
    },
    "listicle_number": {
        "name": "Number/Listicle Hook",
        "description": "Start with a specific number to promise structured value",
        "structure": "State number → Preview value → Deliver each point",
        "visual_hook": "Text overlay with number, product in background",
        "audio_templates": {
            "it": "3 motivi per cui questo {product_type} sta spopolando in Italia.",
            "zh": "这款{product_type}火遍全网的3个原因。",
            "en": "3 reasons why this {product_type} is going viral.",
        },
        "best_for": ["any"],
    },
    "social_proof": {
        "name": "Social Proof Trigger",
        "description": "Start with evidence that others love/use the product",
        "structure": "Social proof statement → Show evidence → Present product",
        "visual_hook": "Quick montage of reactions or usage clips, then product hero shot",
        "audio_templates": {
            "it": "Questo prodotto ha già conquistato {number} persone... ecco perché.",
            "zh": "已经有{number}人入手了这款产品……原因是这样的。",
            "en": "Over {number} people already love this product... here's why.",
        },
        "best_for": ["trending", "beauty", "tech", "fashion"],
    },
    "comparison_challenge": {
        "name": "Comparison Challenge",
        "description": "Put the product against alternatives to show superiority",
        "structure": "Show alternatives → Introduce product → Demonstrate superiority",
        "visual_hook": "Two items side by side, one clearly winning",
        "audio_templates": {
            "it": "Ho provato {number} {product_type} diversi... questo ha vinto su tutti.",
            "zh": "我测试了{number}款不同的{product_type}……这款完胜。",
            "en": "I tested {number} different {product_type}s... this one won.",
        },
        "best_for": ["tech", "kitchen", "beauty", "fitness"],
    },
    "transformation_story": {
        "name": "Personal Transformation",
        "description": "Start with a personal before/after transformation story",
        "structure": "Before state → Discovery moment → After state with product",
        "visual_hook": "Split frame or quick cut: before (dull) → after (vibrant)",
        "audio_templates": {
            "it": "Un mese fa avevo {before_state}... guarda adesso.",
            "zh": "一个月前我还是{before_state}……你看看现在。",
            "en": "A month ago I had {before_state}... look at me now.",
        },
        "best_for": ["skincare", "fitness", "health", "lifestyle"],
    },
}


# ════════════════════════════════════════════════════════════
# 3. SCENE PROGRESSIONS — Pre-built editing templates by duration
# ════════════════════════════════════════════════════════════

SCENE_PROGRESSIONS = {
    "15s_quick_demo": {
        "name": "15s Quick Product Demo",
        "total_duration": 15,
        "segments": [
            {"role": "A-Roll", "shot": "hook_hand_reveal",     "seconds": 4, "purpose": "Hook — grab attention, reveal product"},
            {"role": "A-Roll", "shot": "demo_hand_use",         "seconds": 5, "purpose": "Core — demonstrate product in use"},
            {"role": "B-Roll", "shot": "detail_macro_texture",  "seconds": 3, "purpose": "Detail — show quality/craftsmanship"},
            {"role": "A-Roll", "shot": "cta_logo_reveal",       "seconds": 3, "purpose": "Close — brand shot + CTA"},
        ],
        "tts_script_structure": "Hook line (2s) → Key benefit (4s) → Feature callout (4s) → CTA (3s)",
        "notes": "Fast pace. No more than 4 cuts. Each shot must convey one clear message.",
    },
    "30s_standard_showcase": {
        "name": "30s Standard Product Showcase",
        "total_duration": 30,
        "segments": [
            {"role": "A-Roll", "shot": "hook_product_drop",      "seconds": 4, "purpose": "Hook — dramatic product entrance"},
            {"role": "A-Roll", "shot": "detail_360_orbit",        "seconds": 6, "purpose": "Beauty — full product view"},
            {"role": "A-Roll", "shot": "demo_hand_use",           "seconds": 6, "purpose": "Demo — product in action"},
            {"role": "B-Roll", "shot": "detail_feature_highlight", "seconds": 4, "purpose": "Detail — key feature close-up"},
            {"role": "A-Roll", "shot": "lifestyle_in_use",        "seconds": 5, "purpose": "Context — real-life usage scene"},
            {"role": "A-Roll", "shot": "hero_pedestal",           "seconds": 5, "purpose": "Hero + CTA — final premium shot"},
        ],
        "tts_script_structure": "Hook (3s) → Product intro (5s) → Benefit 1 demo (6s) → Feature highlight (4s) → Lifestyle context (5s) → CTA (4s)",
        "notes": "Standard e-commerce flow. Balance between detail and lifestyle. Peak energy at hook and CTA.",
    },
    "60s_full_story": {
        "name": "60s Full Product Story",
        "total_duration": 60,
        "segments": [
            {"role": "A-Roll", "shot": "hook_before_after",        "seconds": 5, "purpose": "Hook — problem/solution tease"},
            {"role": "B-Roll", "shot": "broll_environment_detail",  "seconds": 4, "purpose": "Set the scene — mood establishment"},
            {"role": "A-Roll", "shot": "hook_unboxing_pov",         "seconds": 5, "purpose": "Unboxing — build anticipation"},
            {"role": "A-Roll", "shot": "detail_360_orbit",          "seconds": 6, "purpose": "Full product reveal — all angles"},
            {"role": "A-Roll", "shot": "demo_hand_use",             "seconds": 6, "purpose": "Primary demo — main function"},
            {"role": "B-Roll", "shot": "detail_macro_texture",      "seconds": 4, "purpose": "Quality evidence — material detail"},
            {"role": "A-Roll", "shot": "demo_result_reveal",        "seconds": 5, "purpose": "Result — show the outcome"},
            {"role": "A-Roll", "shot": "lifestyle_in_use",          "seconds": 6, "purpose": "Lifestyle — daily use context"},
            {"role": "B-Roll", "shot": "lifestyle_social_proof",    "seconds": 4, "purpose": "Social proof — genuine excitement"},
            {"role": "A-Roll", "shot": "demo_comparison",           "seconds": 5, "purpose": "Comparison — vs alternatives"},
            {"role": "A-Roll", "shot": "hero_pedestal",             "seconds": 5, "purpose": "Hero — final beauty shot"},
            {"role": "A-Roll", "shot": "cta_hand_gesture",          "seconds": 5, "purpose": "CTA — direct call to action"},
        ],
        "tts_script_structure": "Hook/Problem (5s) → Scene set (4s) → Unboxing narration (5s) → Product description (6s) → Demo narration (6s) → Quality callout (4s) → Result excitement (5s) → Lifestyle context (6s) → Social proof (4s) → Why this wins (5s) → Hero statement (5s) → CTA (5s)",
        "notes": "Full storytelling arc. Alternating energy: high-low-high-low. B-Roll every 2-3 A-Roll shots for rhythm. Use music shifts to mark sections.",
    },
    "90s_deep_review": {
        "name": "90s In-Depth Product Review",
        "total_duration": 90,
        "segments": [
            {"role": "A-Roll", "shot": "hook_lifestyle_interrupt",  "seconds": 5, "purpose": "Hook — everyday discovery moment"},
            {"role": "B-Roll", "shot": "broll_environment_detail",   "seconds": 4, "purpose": "Scene — establish environment"},
            {"role": "A-Roll", "shot": "hook_unboxing_pov",          "seconds": 6, "purpose": "Unboxing — first impression"},
            {"role": "A-Roll", "shot": "detail_360_orbit",           "seconds": 8, "purpose": "Overview — complete product view"},
            {"role": "B-Roll", "shot": "detail_macro_texture",       "seconds": 4, "purpose": "Texture detail — quality evidence"},
            {"role": "A-Roll", "shot": "detail_feature_highlight",   "seconds": 5, "purpose": "Feature 1 — primary selling point"},
            {"role": "A-Roll", "shot": "demo_hand_use",              "seconds": 8, "purpose": "Demo 1 — main function showcase"},
            {"role": "B-Roll", "shot": "broll_hands_prep",           "seconds": 4, "purpose": "Transition — preparation moment"},
            {"role": "A-Roll", "shot": "demo_application",           "seconds": 6, "purpose": "Demo 2 — application technique"},
            {"role": "A-Roll", "shot": "demo_result_reveal",         "seconds": 5, "purpose": "Result — transformation moment"},
            {"role": "A-Roll", "shot": "demo_comparison",            "seconds": 6, "purpose": "Comparison — vs alternatives"},
            {"role": "B-Roll", "shot": "detail_color_showcase",      "seconds": 4, "purpose": "Variants — show options"},
            {"role": "A-Roll", "shot": "lifestyle_in_use",           "seconds": 6, "purpose": "Lifestyle — daily integration"},
            {"role": "A-Roll", "shot": "lifestyle_social_proof",     "seconds": 4, "purpose": "Social proof — authentic reaction"},
            {"role": "A-Roll", "shot": "hero_golden_hour",           "seconds": 5, "purpose": "Beauty — aspirational shot"},
            {"role": "A-Roll", "shot": "cta_product_array",          "seconds": 5, "purpose": "Product line display"},
            {"role": "A-Roll", "shot": "cta_satisfied_user",         "seconds": 5, "purpose": "CTA — emotional close + call to action"},
        ],
        "tts_script_structure": "Hook (5s) → Scene (4s) → Unboxing (6s) → Overview (8s) → Detail (4s) → Feature 1 (5s) → Demo 1 (8s) → Transition (4s) → Demo 2 (6s) → Result (5s) → Comparison (6s) → Variants (4s) → Lifestyle (6s) → Social proof (4s) → Beauty (5s) → Product line (5s) → CTA (5s)",
        "notes": "Full review format. Three energy peaks: hook, result reveal, CTA. Use B-Roll as breathing room. Music tempo shifts at each act.",
    },
}


# ════════════════════════════════════════════════════════════
# 4. PRODUCT DEMO ACTIONS — Category-specific interaction verbs
# ════════════════════════════════════════════════════════════

PRODUCT_DEMO_ACTIONS = {
    "skincare": {
        "actions": ["applying gently to skin", "pumping out from bottle", "spreading cream in circular motion",
                     "patting serum onto face", "showing texture on back of hand"],
        "key_features": ["texture close-up", "absorption speed", "skin glow after application"],
        "environment": ["bathroom vanity", "bedroom mirror", "spa-like setting"],
    },
    "cosmetics": {
        "actions": ["swiping lipstick on lips", "blending foundation with fingers", "applying mascara",
                     "brushing on eyeshadow", "showing color swatch on arm"],
        "key_features": ["color payoff", "blendability", "lasting power", "packaging design"],
        "environment": ["vanity desk", "ring light setup", "natural window light"],
    },
    "tech_gadget": {
        "actions": ["unboxing from packaging", "pressing power button", "connecting with phone",
                     "demonstrating screen", "plugging in to charge"],
        "key_features": ["screen clarity", "build quality", "interface demo", "size comparison"],
        "environment": ["modern desk", "coffee shop", "travel setting"],
    },
    "fashion": {
        "actions": ["trying on garment", "spinning to show fit", "folding to show fabric",
                     "styling with accessories", "walking confidently"],
        "key_features": ["fabric texture", "fit on body", "label/tag detail", "multiple styling options"],
        "environment": ["bedroom mirror", "street outdoor", "studio white background"],
    },
    "food_supplement": {
        "actions": ["opening container lid", "scooping powder", "mixing into water/shake",
                     "pouring capsules into hand", "stirring drink"],
        "key_features": ["ingredient label", "dissolving speed", "color and texture", "portion size"],
        "environment": ["kitchen counter", "gym setting", "morning breakfast table"],
    },
    "home_appliance": {
        "actions": ["plugging in and turning on", "adjusting settings", "demonstrating suction/power",
                     "cleaning a surface", "showing before and after"],
        "key_features": ["power demonstration", "noise level", "size comparison", "storage"],
        "environment": ["living room", "kitchen", "bathroom"],
    },
    "kitchen": {
        "actions": ["chopping ingredients", "cooking with the tool", "plating finished dish",
                     "cleaning the tool", "showing food result"],
        "key_features": ["cutting precision", "heat distribution", "easy cleaning", "durability"],
        "environment": ["kitchen countertop", "dining table", "outdoor grill area"],
    },
    "jewelry_accessories": {
        "actions": ["clasping necklace", "sliding on bracelet", "adjusting earring",
                     "showing sparkle in light", "pairing with outfit"],
        "key_features": ["light reflection", "clasp mechanism", "size on wrist/neck", "material quality"],
        "environment": ["vanity mirror", "natural sunlight", "elegant dark background"],
    },
    "generic": {
        "actions": ["holding and examining", "turning over in hands", "placing on surface",
                     "using as intended", "showing size against common object"],
        "key_features": ["build quality", "size and weight", "packaging", "key differentiator"],
        "environment": ["clean desk", "white background", "lifestyle setting"],
    },
}


# ════════════════════════════════════════════════════════════
# 5. CTA TEMPLATES — Multi-language call-to-action closings
# ════════════════════════════════════════════════════════════

CTA_TEMPLATES = {
    "shop_now": {
        "it": "Clicca il link in bio per acquistarlo subito!",
        "zh": "点击主页链接，立即购买！",
        "en": "Click the link in bio to shop now!",
    },
    "limited_offer": {
        "it": "Offerta limitata — non fartela scappare!",
        "zh": "限时优惠，不要错过！",
        "en": "Limited time offer — don't miss out!",
    },
    "try_it": {
        "it": "Provalo tu stesso e vedrai la differenza!",
        "zh": "亲自试试，你会看到不同！",
        "en": "Try it yourself and see the difference!",
    },
    "follow_more": {
        "it": "Seguimi per altre recensioni sincere!",
        "zh": "关注我，获取更多真实测评！",
        "en": "Follow me for more honest reviews!",
    },
    "comment_question": {
        "it": "Hai domande? Scrivile nei commenti!",
        "zh": "有问题吗？评论区见！",
        "en": "Got questions? Drop them in the comments!",
    },
    "save_later": {
        "it": "Salva questo video per dopo! Lo ringrazierai.",
        "zh": "收藏这个视频，以后会用到的！",
        "en": "Save this video for later! You'll thank me.",
    },
}


# ════════════════════════════════════════════════════════════
# 6. CAMERA MOVEMENT RULES — Variety & continuity constraints
# ════════════════════════════════════════════════════════════

CAMERA_MOVEMENT_RULES = {
    "variety_constraint": "NEVER use the same camera movement for consecutive segments. "
                          "Alternate between: orbit, push-in, pull-back, static, pan, tilt, dolly.",

    "movement_vocabulary": [
        "static (tripod, locked frame)",
        "slow push-in (dolly forward, building intimacy)",
        "pull-back reveal (dolly backward, showing context)",
        "orbit (circular movement around subject)",
        "pan left/right (horizontal sweep)",
        "tilt up/down (vertical sweep)",
        "handheld slight shake (UGC authentic feel)",
        "top-down overhead (bird's eye, flat lay)",
        "low angle upward (product dominance, power)",
        "rack focus (foreground to background shift)",
    ],

    "transition_rules": [
        "When cutting between segments, prefer matching movement direction",
        "Slow shot → Slow shot: OK (contemplative rhythm)",
        "Fast shot → Slow shot: Use as energy brake after climax",
        "Slow shot → Fast shot: Build anticipation, then burst",
        "Never cut from orbit to orbit (disorienting)",
        "After 2 slow shots, insert 1 dynamic shot to maintain energy",
        "Hook shot should always have movement (not static)",
        "CTA/closing shot can be static with slow push-in",
    ],

    "frame_chaining_notes": [
        "Extract last frame of segment N as first-frame reference for segment N+1",
        "Maintain color temperature continuity across segments",
        "If model supports exact first-frame (Veo, Seedance), use extracted frame literally",
        "If model uses style reference (Sora), describe the scene to match ending of previous segment",
        "Crossfade 0.3-0.5s at segment boundaries hides minor inconsistencies",
    ],
}


# ════════════════════════════════════════════════════════════
# 7. PROMPT TEMPLATES — Per-model optimized prompt rules
# ════════════════════════════════════════════════════════════

PROMPT_TEMPLATES = {
    "veo_31": {
        "strengths": "Best frame-to-frame consistency, exact first frame, cinematic quality",
        "prompt_style": "Descriptive, cinematic language. Include camera direction and lighting.",
        "must_include": ["camera movement description", "lighting type", "9:16 vertical"],
        "avoid": ["multiple scene changes in one prompt", "text/UI overlays"],
        "example_prefix": "Cinematic product shot, ",
        "max_clip": 8,
    },
    "seedance_15": {
        "strengths": "Strong reference lock, good value, reliable consistency",
        "prompt_style": "Direct and clear. Reference image anchors the product appearance.",
        "must_include": ["clear subject description", "one camera movement", "background description"],
        "avoid": ["complex multi-element scenes", "rapid movement changes"],
        "example_prefix": "Product showcase, ",
        "max_clip": 12,
        "valid_durations": [4, 8, 12],
    },
    "sora_2": {
        "strengths": "Creative interpretation, good style transfer, longer clips",
        "prompt_style": "More creative/artistic prompts work well. Style descriptions help.",
        "must_include": ["art direction/style notes", "mood description", "product placement"],
        "avoid": ["expecting exact reference reproduction", "very technical camera terms"],
        "example_prefix": "Stylish commercial, ",
        "max_clip": 10,
    },
    "runway": {
        "strengths": "Fast generation, good for B-roll and transitions",
        "prompt_style": "Simple, focused prompts. One action per clip.",
        "must_include": ["single clear action", "background description"],
        "avoid": ["complex scenes", "multiple moving elements", "expecting long clips"],
        "example_prefix": "Clean product shot, ",
        "max_clip": 5,
    },
    "kling_30": {
        "strengths": "Built-in audio generation, longer clips possible, good for lifestyle",
        "prompt_style": "Natural language, include ambient sound descriptions.",
        "must_include": ["environment sounds", "natural movement", "lifestyle context"],
        "avoid": ["pure abstract/artistic shots", "overly technical camera terms"],
        "example_prefix": "Natural lifestyle moment, ",
        "max_clip": 15,
    },
    "hailuo": {
        "strengths": "High visual fidelity, strong on detail and texture",
        "prompt_style": "Detail-oriented prompts, emphasize textures and materials.",
        "must_include": ["material/texture description", "lighting quality", "close-up details"],
        "avoid": ["wide establishing shots", "rapid camera movements"],
        "example_prefix": "High-fidelity product detail, ",
        "max_clip": 6,
    },
}


# ════════════════════════════════════════════════════════════
# 8. A/B/C-ROLL LAYERING SYSTEM
# ════════════════════════════════════════════════════════════

ROLL_SYSTEM = {
    "A-Roll": {
        "definition": "Primary narrative footage — the main story of the product video",
        "characteristics": [
            "Features the product as the star",
            "Carries the main message/story",
            "Uses high-quality model (Veo, Seedance)",
            "Typically 4-8 seconds per clip",
        ],
        "examples": ["Product demo", "Unboxing", "Lifestyle usage", "Hero shot"],
        "model_priority": ["veo_31_quality", "veo_31_fast", "seedance_15"],
    },
    "B-Roll": {
        "definition": "Supporting footage — adds visual variety and breathing room",
        "characteristics": [
            "Does not need to feature the product directly",
            "Provides context, mood, or visual rest",
            "Can use lower-cost models",
            "Typically 2-4 seconds per clip",
        ],
        "examples": ["Environment detail", "Texture close-up", "Ambient pour", "Preparation hands"],
        "model_priority": ["runway", "seedance_15", "hailuo"],
    },
    "C-Roll": {
        "definition": "Post-production overlays — text, UI elements, effects (NOT AI-generated)",
        "characteristics": [
            "Added in FFmpeg post-production, not generated by video models",
            "Text overlays, lower thirds, brand logos",
            "Transition effects, color grading",
            "Music and sound effects",
        ],
        "examples": ["Brand logo overlay", "Feature text callout", "Price/offer text", "Subscribe button"],
        "model_priority": [],  # Handled by FFmpeg/post-production
    },
    "mixing_rules": [
        "Never exceed 3 consecutive A-Roll clips without a B-Roll break",
        "B-Roll should be 20-30% of total video duration",
        "Start with A-Roll (hook), end with A-Roll (CTA)",
        "B-Roll after demo segments provides visual breathing room",
        "C-Roll elements are added in post by VideoStitcher, not planned as segments",
    ],
}


# ════════════════════════════════════════════════════════════
# MAIN API — Called by DirectorAgent
# ════════════════════════════════════════════════════════════

def get_production_context(
    product_category: str = "generic",
    duration: int = 30,
    languages: Optional[list[str]] = None,
    model_key: str = "seedance_15",
    hook_style: Optional[str] = None,
) -> dict:
    """
    Build a complete production context package for the Director Agent.

    Args:
        product_category: One of PRODUCT_DEMO_ACTIONS keys (e.g., "skincare", "tech_gadget")
        duration: Target video duration in seconds
        languages: List of language codes (default: ["it", "zh", "en"])
        model_key: Selected video model key
        hook_style: Override hook pattern (default: auto-select based on category)

    Returns:
        Dict with all production knowledge needed for planning:
        {
            "scene_template": {...},      # Matched SCENE_PROGRESSIONS entry
            "hook": {...},                # Selected HOOK_PATTERNS entry
            "demo_actions": {...},        # Category-specific PRODUCT_DEMO_ACTIONS
            "cta": {...},                 # Selected CTA_TEMPLATES entry
            "prompt_rules": {...},        # Model-specific PROMPT_TEMPLATES
            "camera_rules": {...},        # CAMERA_MOVEMENT_RULES
            "roll_system": {...},         # A/B/C-ROLL definitions
            "shot_library_keys": [...],   # Recommended shot keys from UGC_SHOT_LIBRARY
        }
    """
    if languages is None:
        languages = ["it", "zh", "en"]

    # ── Select scene template based on duration ────────────────────────
    scene_template = _select_scene_template(duration)

    # ── Select hook pattern ─────────────────────────────────────────
    if hook_style and hook_style in HOOK_PATTERNS:
        hook = HOOK_PATTERNS[hook_style]
    else:
        hook = _auto_select_hook(product_category)

    # ── Get demo actions for product category ───────────────────────
    demo_actions = PRODUCT_DEMO_ACTIONS.get(
        product_category,
        PRODUCT_DEMO_ACTIONS["generic"]
    )

    # ── Select CTA ────────────────────────────────────────────
    cta = CTA_TEMPLATES["shop_now"]  # Default; Director can override

    # ── Get model-specific prompt rules ───────────────────────────
    prompt_rules = _get_prompt_rules(model_key)

    # ── Collect recommended shots ────────────────────────────────
    shot_keys = [seg["shot"] for seg in scene_template.get("segments", [])]

    return {
        "scene_template": scene_template,
        "hook": hook,
        "demo_actions": demo_actions,
        "cta": cta,
        "prompt_rules": prompt_rules,
        "camera_rules": CAMERA_MOVEMENT_RULES,
        "roll_system": ROLL_SYSTEM,
        "shot_library_keys": shot_keys,
        "all_cta_options": CTA_TEMPLATES,
        "all_hook_options": list(HOOK_PATTERNS.keys()),
    }


def get_shot_prompt(shot_key: str, **kwargs) -> str:
    """
    Get the prompt template for a specific shot, with variable substitution.

    Args:
        shot_key: Key from UGC_SHOT_LIBRARY
        **kwargs: Variables to substitute in the template (e.g., product="red lipstick")

    Returns:
        Formatted prompt string ready for video generation API
    """
    shot = UGC_SHOT_LIBRARY.get(shot_key)
    if not shot:
        return f"Product showcase shot, clean studio lighting, 9:16 vertical"

    template = shot["prompt_template"]
    # Substitute any provided kwargs
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))

    return template


# ── Private helpers ───────────────────────────────────────────────

def _select_scene_template(duration: int) -> dict:
    """Select the closest matching scene template for the target duration."""
    if duration <= 20:
        return SCENE_PROGRESSIONS["15s_quick_demo"]
    elif duration <= 45:
        return SCENE_PROGRESSIONS["30s_standard_showcase"]
    elif duration <= 75:
        return SCENE_PROGRESSIONS["60s_full_story"]
    else:
        return SCENE_PROGRESSIONS["90s_deep_review"]


def _auto_select_hook(product_category: str) -> dict:
    """Auto-select the best hook pattern for a product category."""
    # Map categories to preferred hook styles
    category_hook_map = {
        "skincare":       "result_first",
        "cosmetics":      "result_first",
        "tech_gadget":    "comparison_challenge",
        "fashion":        "transformation_story",
        "food_supplement": "authority_claim",
        "home_appliance": "pain_point",
        "kitchen":        "pain_point",
        "jewelry_accessories": "curiosity_gap",
        "generic":        "listicle_number",
    }
    hook_key = category_hook_map.get(product_category, "listicle_number")
    return HOOK_PATTERNS.get(hook_key, HOOK_PATTERNS["listicle_number"])


def _get_prompt_rules(model_key: str) -> dict:
    """Get prompt engineering rules for the specified model."""
    # Map model keys to prompt template categories
    model_map = {
        "veo_31_fast":    "veo_31",
        "veo_31_quality": "veo_31",
        "seedance_15":    "seedance_15",
        "seedance_2":     "seedance_15",
        "sora_2":         "sora_2",
        "sora_2_pro":     "sora_2",
        "runway":         "runway",
        "runway_1080p":   "runway",
        "kling_30":       "kling_30",
        "kling_26":       "kling_30",
        "hailuo":         "hailuo",
    }
    template_key = model_map.get(model_key, "seedance_15")
    return PROMPT_TEMPLATES.get(template_key, PROMPT_TEMPLATES["seedance_15"])
