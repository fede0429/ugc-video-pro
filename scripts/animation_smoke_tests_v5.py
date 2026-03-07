from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from projects.animation.story_bible import build_story_bible
from projects.animation.character_bible import build_character_bible
from projects.animation.episode_writer import EpisodeWriter
from projects.animation.relationship_graph import RelationshipGraphBuilder
from projects.animation.character_emotion_arc_engine import CharacterEmotionArcEngine
from projects.animation.punchline_dialogue_generator import PunchlineDialogueGenerator

def main():
    bible = build_story_bible(
        title="测试动画",
        genre="都市情感",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高张力",
        core_premise="公开冲突后关系彻底失控",
    )
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, "发布会翻车后强行同框", 4)
    graph = RelationshipGraphBuilder().build(bible, chars, episode)
    arcs = CharacterEmotionArcEngine().build(episode.to_dict(), [c.to_dict() for c in chars])
    punches = PunchlineDialogueGenerator().build(episode.to_dict(), graph, {})
    assert arcs["emotion_arcs"]["沈晚"]["scene_beats"]
    assert punches["lines"][0]["punchline"]
    print(json.dumps({"emotion_characters": list(arcs["emotion_arcs"].keys()), "first_punchline": punches["lines"][0]["punchline"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
