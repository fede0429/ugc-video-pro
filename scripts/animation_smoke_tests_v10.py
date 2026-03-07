
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
from projects.animation.scene_twist_detector import SceneTwistDetector
from projects.animation.climax_orchestrator import ClimaxOrchestrator
from projects.animation.foreshadow_planter import ForeshadowPlanter
from projects.animation.payoff_tracker import PayoffTracker
from projects.animation.suspense_keeper import SuspenseKeeper
from projects.animation.payoff_strength_scorer import PayoffStrengthScorer
from projects.animation.season_suspense_chain import SeasonSuspenseChain
from projects.animation.finale_payoff_planner import FinalePayoffPlanner
from projects.animation.season_trailer_generator import SeasonTrailerGenerator
from projects.animation.next_season_hook_planner import NextSeasonHookPlanner


def main() -> None:
    bible = build_story_bible(
        title="烟雾后的真相",
        genre="都市悬疑",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高压悬疑",
        core_premise="终局揭开真相但还必须引出下一季",
    )
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, "真相揭露但代价刚开始", 5)
    graph = RelationshipGraphBuilder().build(bible, chars, episode)
    memory = StoryMemoryBank().build(bible, chars, episode, graph, None)
    season_memory = SeasonMemoryBank().build(bible.to_dict(), graph, episode.to_dict(), None)
    twists = SceneTwistDetector().build(episode.to_dict())
    climax = ClimaxOrchestrator().build(episode.to_dict(), graph, {})
    foreshadow = ForeshadowPlanter().build(episode.to_dict(), twists, graph)
    payoff_tracker = PayoffTracker().build(foreshadow, twists, climax)
    suspense = SuspenseKeeper().build(episode.to_dict(), twists, foreshadow, climax)
    strength = PayoffStrengthScorer().build(foreshadow, payoff_tracker, climax, graph)
    chain = SeasonSuspenseChain().build(season_memory, memory, suspense, twists, climax)
    finale = FinalePayoffPlanner().build(chain, payoff_tracker, strength, {}, season_memory)
    trailer = SeasonTrailerGenerator().build(chain, finale, suspense, strength)
    hooks = NextSeasonHookPlanner().build(chain, finale, graph, season_memory)
    assert trailer["trailer_beats"], "trailer beats should not be empty"
    assert hooks["carry_over_hooks"], "carry over hooks should not be empty"
    print(f"animation_smoke_tests_v10: ok {len(trailer['trailer_beats'])} {len(hooks['carry_over_hooks'])}")


if __name__ == "__main__":
    main()
