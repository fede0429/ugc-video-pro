
from __future__ import annotations

from .models import StoryBible


def build_story_bible(
    title: str,
    genre: str,
    format_type: str,
    target_platform: str,
    visual_style: str,
    tone: str,
    core_premise: str,
) -> StoryBible:
    world_rules = [
        "角色设计在整季中保持高一致性，避免发型、主服装、主色大幅变化。",
        "单镜头只表达一个核心动作或一个情绪转折，便于 shot 级生成与重试。",
        "每集开头 3 秒必须有异常事件或高风险信息差，结尾必须留下悬念。",
        "对白短句化，方便字幕与 TTS 对齐，避免一镜头说太长的话。",
    ]
    recurring_locations = [
        "主角常驻空间",
        "高冲突对峙空间",
        "低成本可复用过场空间",
    ]
    themes = ["身份与欲望", "关系冲突", "代价与反转"]
    camera_language = [
        "竖屏短剧优先 medium close-up / over-shoulder / insert close-up",
        "角色对峙多用 two-shot 和 over-shoulder，减少调度复杂度",
        "关键反转使用 detail insert 和 reaction close-up 加强传播点",
    ]
    rendering_constraints = [
        "优先控制在 4~8 秒镜头，减少模型长镜头崩坏概率。",
        "镜头说明要同时包含角色、动作、表情、场景、光线和构图。",
        "连续镜头必须重复角色外观锚点与场景锚点。",
    ]

    return StoryBible(
        title=title,
        genre=genre,
        format=format_type,
        target_platform=target_platform,
        visual_style=visual_style,
        tone=tone,
        logline=core_premise,
        world_rules=world_rules,
        recurring_locations=recurring_locations,
        themes=themes,
        camera_language=camera_language,
        rendering_constraints=rendering_constraints,
    )
