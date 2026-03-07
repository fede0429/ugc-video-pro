
from __future__ import annotations

from typing import Any


class SeasonTrailerGenerator:
    def build(
        self,
        season_suspense_chain: dict[str, Any],
        finale_payoff_plan: dict[str, Any],
        suspense_keeper: dict[str, Any] | None = None,
        payoff_strength: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        suspense_keeper = suspense_keeper or {}
        payoff_strength = payoff_strength or {}
        strongest_hold = season_suspense_chain.get("strongest_hold_arc") or {}
        finale_focus = finale_payoff_plan.get("hero_payoff") or {}
        trailer_beats = []
        if strongest_hold:
            trailer_beats.append({
                "beat": "mystery_hook",
                "line": f"一切从{strongest_hold.get('scene_id', '关键场') }开始失控。",
                "editorial_hint": "前3秒只露情绪，不露完整真相",
            })
        for node in season_suspense_chain.get("suspense_nodes", [])[:3]:
            trailer_beats.append({
                "beat": "season_tease",
                "line": f"{node.get('scene_id')} 埋下的悬念将在更大的代价中兑现。",
                "editorial_hint": "快速切3帧角色反应+1帧道具特写",
            })
        if finale_focus:
            trailer_beats.append({
                "beat": "finale_reward",
                "line": f"终局回收到{finale_focus.get('scene_id', '终局场')}，所有关系都会被改写。",
                "editorial_hint": "只给 payoff 的前半句，不给完整结果",
            })
        cliffhanger = suspense_keeper.get("cliffhanger_candidates", [])
        if cliffhanger:
            trailer_beats.append({
                "beat": "cliffhanger_tag",
                "line": f"真正的答案，还藏在{cliffhanger[0].get('scene_id', '下一场')}之后。",
                "editorial_hint": "片尾 0.6 秒黑场后再打一条文字钩子",
            })
        strength = float(payoff_strength.get("overall_strength", 0.0) or 0.0)
        return {
            "trailer_title": "季终预告建议版",
            "trailer_angle": "高悬念终局预告",
            "trailer_duration_seconds": 18 if strength >= 70 else 22,
            "voiceover_style": "压迫感递进 + 留白",
            "trailer_beats": trailer_beats,
            "text_hooks": [
                "下一集，所有埋下的真相都会反咬回来",
                "你以为结束了，其实真正的局刚开始",
                "别眨眼，最狠的一刀永远在最后",
            ],
            "cover_copy": "终局来临，谁才是最后的赢家？",
            "editorial_notes": [
                "前半段多用 reaction shot，不提前泄露 payoff 本体",
                "BGM 在 70% 处断一下，再进终局回收镜头",
                "结尾必须留 1 个没解释完的关系裂缝，方便带出下季",
            ],
        }
