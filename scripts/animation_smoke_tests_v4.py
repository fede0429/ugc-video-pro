
from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from projects.animation.story_bible import build_story_bible
from projects.animation.character_bible import build_character_bible
from projects.animation.episode_writer import EpisodeWriter
from projects.animation.relationship_graph import RelationshipGraphBuilder
from projects.animation.story_memory_bank import StoryMemoryBank
from projects.animation.season_conflict_tree import SeasonConflictTree
from projects.animation.scene_pacing_controller import ScenePacingController
from projects.animation.climax_orchestrator import ClimaxOrchestrator

def main():
    bible = build_story_bible(
        title="测试动画",
        genre="都市情感",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高张力",
        core_premise="失控合作关系引发公开冲突",
    )
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静", ["你最好想清楚再说。"]),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然", ["这戏我还真接了。"]),
    ]
    episode_obj = EpisodeWriter().create_episode_outline(bible, chars, "公开亮相却被旧情人打断", 4)
    episode = episode_obj.to_dict()
    graph = RelationshipGraphBuilder().build(bible, chars, episode_obj)
    memory = StoryMemoryBank().build(bible, chars, episode_obj, graph, previous_memory=None, episode_index=1)
    conflict = SeasonConflictTree().build(bible.to_dict(), graph, memory, previous_memory=None)
    pacing = ScenePacingController().build(episode)
    climax = ClimaxOrchestrator().build(episode, graph, conflict)
    assert pacing["scene_pacing"]
    assert climax["primary_climax_scene_id"]
    print(json.dumps({"scene_count": len(pacing["scene_pacing"]), "primary_climax": climax["primary_climax_scene_id"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
