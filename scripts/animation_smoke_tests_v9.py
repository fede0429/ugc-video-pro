
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from projects.animation.story_bible import build_story_bible
from projects.animation.character_bible import build_character_bible
from projects.animation.episode_writer import EpisodeWriter
from projects.animation.relationship_graph import RelationshipGraphBuilder
from projects.animation.story_memory_bank import StoryMemoryBank
from projects.animation.season_memory_bank import SeasonMemoryBank
from projects.animation.season_conflict_tree import SeasonConflictTree
from projects.animation.scene_twist_detector import SceneTwistDetector
from projects.animation.climax_orchestrator import ClimaxOrchestrator
from projects.animation.foreshadow_planter import ForeshadowPlanter
from projects.animation.payoff_tracker import PayoffTracker
from projects.animation.suspense_keeper import SuspenseKeeper
from projects.animation.payoff_strength_scorer import PayoffStrengthScorer
from projects.animation.season_suspense_chain import SeasonSuspenseChain
from projects.animation.finale_payoff_planner import FinalePayoffPlanner

def main() -> None:
    story = build_story_bible(
        title="季终前夜",
        genre="都市情感",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高张力、强反转",
        core_premise="隐藏多集的证据在季终夜逐层兑现。",
    )
    chars = [
        build_character_bible(name="沈晚", role="女主", age_range="23-28", appearance=["黑长发"], wardrobe=["黑色礼服"], personality=["理智"], voice_style="冷静", catchphrases=["你终于说出来了。"]),
        build_character_bible(name="周叙", role="男主", age_range="25-30", appearance=["短黑发"], wardrobe=["深色西装"], personality=["克制"], voice_style="低沉", catchphrases=["现在轮到我了。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(story_bible=story, characters=chars, episode_goal="在季终夜完成多线悬念与关系回收", scene_count=4)
    graph = RelationshipGraphBuilder().build(story, chars, episode)
    story_memory = StoryMemoryBank().build(story, chars, episode, graph, previous_memory=None, episode_index=4)
    season_memory = SeasonMemoryBank().build(story.to_dict(), graph, episode.to_dict(), None)
    conflict = SeasonConflictTree().build(story.to_dict(), graph, story_memory, None)
    twists = SceneTwistDetector().build(episode.to_dict())
    climax = ClimaxOrchestrator().build(episode.to_dict(), graph, conflict)
    foreshadow = ForeshadowPlanter().build(episode.to_dict(), twists, graph)
    tracker = PayoffTracker().build(foreshadow, twists, climax)
    suspense = SuspenseKeeper().build(episode.to_dict(), twists, foreshadow, climax)
    strength = PayoffStrengthScorer().build(foreshadow, tracker, climax, graph)
    chain = SeasonSuspenseChain().build(season_memory, story_memory, suspense, twists, climax, "batch_demo")
    finale = FinalePayoffPlanner().build(chain, tracker, strength, conflict, season_memory)
    assert chain["retention_target"] > 0
    assert finale["finale_intensity_target"] >= 70
    print("animation_smoke_tests_v9: ok", chain["retention_target"], finale["finale_intensity_target"])

if __name__ == "__main__":
    main()
