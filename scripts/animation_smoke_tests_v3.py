
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
from projects.animation.story_bible import build_story_bible
from projects.animation.character_bible import build_character_bible
from projects.animation.episode_writer import EpisodeWriter
from projects.animation.relationship_graph import RelationshipGraphBuilder
from projects.animation.story_memory_bank import StoryMemoryBank
from projects.animation.dialogue_style_engine import DialogueStyleEngine
from projects.animation.season_conflict_tree import SeasonConflictTree

def main():
    bible = build_story_bible(
        title="测试动画",
        genre="都市情感",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高张力",
        core_premise="两人被迫合作后关系失控",
    )
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静", ["你最好想清楚再说。"]),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然", ["这戏我还真接了。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, "合作关系第一次公开却被打断", 4)
    graph = RelationshipGraphBuilder().build(bible, chars, episode)
    memory = StoryMemoryBank().build(bible, chars, episode, graph, previous_memory=None, episode_index=1)
    dialogue = DialogueStyleEngine().build(bible.to_dict(), [c.to_dict() for c in chars], graph)
    conflict = SeasonConflictTree().build(bible.to_dict(), graph, memory, previous_memory=None)
    assert dialogue["styles"]["沈晚"]["tone"]
    assert conflict["conflict_nodes"]
    print(json.dumps({"dialogue_roles": list(dialogue["styles"].keys()), "conflicts": len(conflict["conflict_nodes"])}, ensure_ascii=False))

if __name__ == "__main__":
    main()
