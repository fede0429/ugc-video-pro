
from __future__ import annotations

from typing import List
from .models import StoryBible, CharacterBible, EpisodePlan, ScenePlan


class EpisodeWriter:
    def create_episode_outline(
        self,
        story_bible: StoryBible,
        characters: List[CharacterBible],
        episode_goal: str,
        scene_count: int = 4,
    ) -> EpisodePlan:
        leads = "、".join(c.name for c in characters[:3]) or "主角团"
        synopsis = f"{story_bible.title}本集围绕“{episode_goal}”展开，{leads}在极短时间内面对升级的冲突与抉择。"
        hook = f"开场 3 秒抛出异常事件：{episode_goal}"
        cliffhanger = "结尾留下更大的误会、威胁或秘密曝光，为下一集续接。"

        scene_templates = [
            ("异常事件爆发", "建立冲突"),
            ("冲突升级", "角色对抗"),
            ("秘密被揭开", "信息反转"),
            ("代价落下", "反转/悬念"),
            ("短暂喘息", "关系递进"),
            ("最终对抗", "高潮推进"),
        ]
        scenes: List[ScenePlan] = []
        for idx in range(scene_count):
            scene_id = f"S{idx + 1}"
            title, purpose = scene_templates[min(idx, len(scene_templates) - 1)]
            scenes.append(
                ScenePlan(
                    scene_id=scene_id,
                    title=title,
                    location="常驻主场景" if idx in (0, 1) else "转折场景",
                    dramatic_purpose=purpose,
                    beats=[
                        f"{leads}围绕本集目标产生新的张力变化",
                        "抛出一个更具体的问题或威胁",
                        "让角色做一个会影响下一场戏的选择",
                    ],
                    dialogue_summary=[
                        "对白短句化、强情绪、适合镜头级拆分。",
                        "每场戏只保留一个核心信息点，降低渲染成本。",
                    ],
                )
            )

        return EpisodePlan(
            episode_title=f"{story_bible.title} - Episode 01",
            synopsis=synopsis,
            hook=hook,
            cliffhanger=cliffhanger,
            scenes=scenes,
        )
