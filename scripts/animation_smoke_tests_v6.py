from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from projects.animation.story_bible import build_story_bible
from projects.animation.character_bible import build_character_bible
from projects.animation.episode_writer import EpisodeWriter
from projects.animation.storyboard_generator import StoryboardGenerator
from projects.animation.shot_template_library import ShotTemplateLibrary
from projects.animation.scene_twist_detector import SceneTwistDetector
from projects.animation.highlight_shot_orchestrator import HighlightShotOrchestrator
from projects.animation.climax_orchestrator import ClimaxOrchestrator
from projects.animation.relationship_graph import RelationshipGraphBuilder


def main() -> None:
    story = build_story_bible(
        title="身份局中局",
        genre="都市情感",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高张力、强反转",
        core_premise="一场订婚宴上公开揭穿双重身份。",
    )
    chars = [
        build_character_bible(name="沈晚", role="女主", age_range="23-28", appearance=["黑长发"], wardrobe=["黑色礼服"], personality=["理智"], voice_style="冷静", catchphrases=["你终于露面了。"]),
        build_character_bible(name="周叙", role="男主", age_range="25-30", appearance=["短黑发"], wardrobe=["深色西装"], personality=["克制"], voice_style="低沉", catchphrases=["今天谁都别想走。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(story_bible=story, characters=chars, episode_goal="宴会公开反转", scene_count=4)
    episode = StoryboardGenerator(template_library=ShotTemplateLibrary()).build_shots(episode=episode, characters=chars, visual_style=story.visual_style)
    twist = SceneTwistDetector().build(episode.to_dict())
    graph = RelationshipGraphBuilder().build(story, chars, episode)
    climax = ClimaxOrchestrator().build(episode.to_dict(), graph, {"core_conflict": "身份与情感的双重冲突"})
    highlights = HighlightShotOrchestrator().build(episode.to_dict(), twist, climax)
    assert twist["strongest_twist"] is not None
    assert isinstance(highlights["highlight_shots"], list)
    print("Animation v13 smoke test passed", twist["strongest_twist"]["scene_id"], len(highlights["highlight_shots"]))


if __name__ == "__main__":
    main()
