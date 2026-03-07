from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from projects.animation.story_bible import build_story_bible
from projects.animation.character_bible import build_character_bible
from projects.animation.episode_writer import EpisodeWriter
from projects.animation.storyboard_generator import StoryboardGenerator
from projects.animation.shot_template_library import ShotTemplateLibrary
from projects.animation.relationship_graph import RelationshipGraphBuilder
from projects.animation.scene_twist_detector import SceneTwistDetector
from projects.animation.climax_orchestrator import ClimaxOrchestrator
from projects.animation.character_emotion_arc_engine import CharacterEmotionArcEngine
from projects.animation.shot_emotion_filter import ShotEmotionFilter
from projects.animation.foreshadow_planter import ForeshadowPlanter
from projects.animation.payoff_tracker import PayoffTracker

def main() -> None:
    story = build_story_bible(
        title="真相错位",
        genre="都市情感",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高张力、强反转",
        core_premise="前任与现任在订婚直播现场同框，真相被分层揭开。",
    )
    chars = [
        build_character_bible(name="沈晚", role="女主", age_range="23-28", appearance=["黑长发"], wardrobe=["黑色礼服"], personality=["理智"], voice_style="冷静", catchphrases=["你终于露面了。"]),
        build_character_bible(name="周叙", role="男主", age_range="25-30", appearance=["短黑发"], wardrobe=["深色西装"], personality=["克制"], voice_style="低沉", catchphrases=["今天谁都别想走。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(story_bible=story, characters=chars, episode_goal="在直播事故里完成情感和身份双反转", scene_count=4)
    episode = StoryboardGenerator(template_library=ShotTemplateLibrary()).build_shots(episode=episode, characters=chars, visual_style=story.visual_style)
    episode_dict = episode.to_dict()
    graph = RelationshipGraphBuilder().build(story, chars, episode)
    twists = SceneTwistDetector().build(episode_dict)
    climax = ClimaxOrchestrator().build(episode_dict, graph, {"core_conflict": "身份与情感双冲突"})
    arcs = CharacterEmotionArcEngine().build(episode_dict, [c.to_dict() for c in chars])
    filters = ShotEmotionFilter().build(episode_dict, arcs)
    foreshadow = ForeshadowPlanter().build(episode_dict, twists, graph)
    payoff = PayoffTracker().build(foreshadow, twists, climax)
    assert filters["shot_emotion_filters"]
    assert foreshadow["foreshadow_seeds"] or foreshadow["target_twist_scene"] is not None
    assert payoff["main_payoff_scene"] is not None
    print("Animation v14 smoke test passed", payoff["main_payoff_scene"], len(filters["shot_emotion_filters"]))

if __name__ == "__main__":
    main()
