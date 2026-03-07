from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List


@dataclass
class ShotTemplate:
    template_id: str
    category: str
    dramatic_purpose: str
    camera: str
    framing: str
    action_pattern: str
    dialogue_pattern: str
    continuity_hints: List[str]
    prompt_keywords: List[str]
    default_duration_seconds: float = 4.0

    def to_dict(self) -> dict:
        return asdict(self)


class ShotTemplateLibrary:
    def __init__(self) -> None:
        self.templates: List[ShotTemplate] = [
            ShotTemplate(
                template_id="hook_reaction_pushin",
                category="hook",
                dramatic_purpose="建立冲突",
                camera="handheld push-in",
                framing="medium close-up",
                action_pattern="{hero}在{location}察觉异常，瞬间绷紧神经并看向镜头外",
                dialogue_pattern="{hero}：等一下，这和你刚才说的不一样。",
                continuity_hints=["延续上一镜头主服装", "保留角色面部主锚点", "保持冲突开始前的环境光方向"],
                prompt_keywords=["urgent reaction", "dramatic reveal", "high tension", "vertical short drama"],
                default_duration_seconds=4.0,
            ),
            ShotTemplate(
                template_id="faceoff_twoshot",
                category="conflict",
                dramatic_purpose="角色对抗",
                camera="over-shoulder",
                framing="two-shot",
                action_pattern="{hero}与{rival}在{location}正面对峙，压迫感不断上升",
                dialogue_pattern="{rival}：你现在才发现，已经太晚了。",
                continuity_hints=["人物站位保持前后连续", "对视方向不能跳轴", "主要道具保持同一只手持有"],
                prompt_keywords=["face off", "dialogue tension", "anime drama", "cinematic blocking"],
                default_duration_seconds=5.0,
            ),
            ShotTemplate(
                template_id="detail_clue_insert",
                category="twist",
                dramatic_purpose="信息反转",
                camera="static insert",
                framing="detail close-up",
                action_pattern="镜头切到关键线索，在{location}中暴露出足以改变局势的细节",
                dialogue_pattern="无对白",
                continuity_hints=["道具细节与前文设定一致", "环境色温保持一致", "线索文字/纹理不要跳变"],
                prompt_keywords=["insert close-up", "clue reveal", "high detail", "dramatic insert"],
                default_duration_seconds=4.0,
            ),
            ShotTemplate(
                template_id="silence_aftermath",
                category="aftermath",
                dramatic_purpose="反转/悬念",
                camera="slow dolly out",
                framing="wide medium",
                action_pattern="{hero}在{location}短暂失语，只剩下危险信息在空气里扩散",
                dialogue_pattern="{hero}：原来你们一直都知道。",
                continuity_hints=["保留角色受冲击后的表情残留", "场景破坏状态连续", "光线与上一镜头连贯"],
                prompt_keywords=["aftermath", "suspense", "silent shock", "dramatic fallout"],
                default_duration_seconds=5.0,
            ),
            ShotTemplate(
                template_id="emotion_bridge",
                category="relationship",
                dramatic_purpose="关系递进",
                camera="gentle lateral move",
                framing="medium two-shot",
                action_pattern="{hero}与{rival}在{location}关系短暂缓和，却埋下新的误会",
                dialogue_pattern="{hero}：我不是不相信你，我是不敢信。",
                continuity_hints=["人物距离与情绪温度渐变", "背景环境避免跳变", "角色主色保持稳定"],
                prompt_keywords=["emotional bridge", "relationship beat", "gentle motion", "character acting"],
                default_duration_seconds=5.0,
            ),
            ShotTemplate(
                template_id="cliffhanger_lockoff",
                category="cliffhanger",
                dramatic_purpose="高潮推进",
                camera="locked-off dramatic reveal",
                framing="medium wide",
                action_pattern="在{location}出现新的威胁或人物，让{hero}的计划被彻底打断",
                dialogue_pattern="画外音：下一秒，真正的麻烦才刚刚开始。",
                continuity_hints=["最后一镜为下一集预留清晰钩子", "新角色或新威胁必须有单独视觉锚点", "保持服装和场景一致"],
                prompt_keywords=["cliffhanger", "episode ending", "dramatic reveal", "viral suspense"],
                default_duration_seconds=4.0,
            ),
        ]

    def list_templates(self) -> List[dict]:
        return [t.to_dict() for t in self.templates]

    def choose_template(self, dramatic_purpose: str, shot_index: int = 0) -> ShotTemplate:
        dramatic_purpose = (dramatic_purpose or "").strip()
        priority = [t for t in self.templates if t.dramatic_purpose == dramatic_purpose]
        if not priority:
            priority = self.templates
        return priority[shot_index % len(priority)]
