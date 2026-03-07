
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
from projects.animation.foreshadow_planter import ForeshadowPlanter
from projects.animation.payoff_tracker import PayoffTracker
from projects.animation.suspense_keeper import SuspenseKeeper
from projects.animation.payoff_strength_scorer import PayoffStrengthScorer

def main() -> None:
    story = build_story_bible(
        title="终局前夜",
        genre="都市情感",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高张力、强反转",
        core_premise="旧案证据在订婚夜被逐层揭开。",
    )
    chars = [
        build_character_bible(name="沈晚", role="女主", age_range="23-28", appearance=["黑长发"], wardrobe=["黑色礼服"], personality=["理智"], voice_style="冷静", catchphrases=["你终于说出来了。"]),
        build_character_bible(name="周叙", role="男主", age_range="25-30", appearance=["短黑发"], wardrobe=["深色西装"], personality=["克制"], voice_style="低沉", catchphrases=["现在轮到我了。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(story_bible=story, characters=chars, episode_goal="在订婚夜完成身份反转和情感回收", scene_count=4)
    episode = StoryboardGenerator(template_library=ShotTemplateLibrary()).build_shots(episode=episode, characters=chars, visual_style=story.visual_style)
    ep = episode.to_dict()
    graph = RelationshipGraphBuilder().build(story, chars, episode)
    twists = SceneTwistDetector().build(ep)
    climax = ClimaxOrchestrator().build(ep, graph, {"core_conflict": "真相与关系双冲突"})
    foreshadow = ForeshadowPlanter().build(ep, twists, graph)
    payoff = PayoffTracker().build(foreshadow, twists, climax)
    suspense = SuspenseKeeper().build(ep, twists, foreshadow, climax)
    strength = PayoffStrengthScorer().build(foreshadow, payoff, climax, graph)
    assert suspense["suspense_index"] > 0
    assert strength["overall_strength"] >= 0
    print("animation_smoke_tests_v8: ok", suspense["suspense_index"], strength["overall_strength"])

if __name__ == "__main__":
    main()
