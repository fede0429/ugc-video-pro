
from __future__ import annotations

import json
import time
from pathlib import Path

from projects.animation.story_bible import build_story_bible
from projects.animation.character_bible import build_character_bible
from projects.animation.episode_writer import EpisodeWriter
from projects.animation.storyboard_generator import StoryboardGenerator
from projects.animation.continuity_engine import ContinuityEngine
from projects.animation.shot_template_library import ShotTemplateLibrary
from projects.animation.character_consistency import CharacterConsistencyEngine
from projects.animation.character_state_machine import CharacterStateMachine
from projects.animation.scene_asset_library import SceneAssetLibrary
from projects.animation.scene_state_flow import SceneStateFlowEngine
from projects.animation.episode_asset_reuse import EpisodeAssetReusePlanner
from projects.animation.relationship_graph import RelationshipGraphBuilder
from projects.animation.story_memory_bank import StoryMemoryBank
from projects.animation.outline_editor import OutlineEditor
from projects.animation.season_memory_bank import SeasonMemoryBank
from projects.animation.dialogue_style_engine import DialogueStyleEngine
from projects.animation.season_conflict_tree import SeasonConflictTree
from projects.animation.scene_pacing_controller import ScenePacingController
from projects.animation.climax_orchestrator import ClimaxOrchestrator
from projects.animation.character_emotion_arc_engine import CharacterEmotionArcEngine
from projects.animation.punchline_dialogue_generator import PunchlineDialogueGenerator
from projects.animation.scene_twist_detector import SceneTwistDetector
from projects.animation.highlight_shot_orchestrator import HighlightShotOrchestrator
from projects.animation.shot_emotion_filter import ShotEmotionFilter
from projects.animation.foreshadow_planter import ForeshadowPlanter
from projects.animation.payoff_tracker import PayoffTracker
from projects.animation.suspense_keeper import SuspenseKeeper
from projects.animation.payoff_strength_scorer import PayoffStrengthScorer
from projects.animation.season_suspense_chain import SeasonSuspenseChain
from projects.animation.finale_payoff_planner import FinalePayoffPlanner
from projects.animation.season_trailer_generator import SeasonTrailerGenerator
from projects.animation.next_season_hook_planner import NextSeasonHookPlanner
from projects.animation.trailer_editor import TrailerEditor
from projects.animation.next_episode_cold_open_planner import NextEpisodeColdOpenPlanner
from projects.animation.kie_seedance_adapter import KieSeedanceAnimationAdapter
from projects.animation.task_store import AnimationTaskStore
from services.tts_service import TTSService
from utils.ffmpeg_tools import FFmpegTools
try:
    from web.websocket import broadcast_progress
except Exception:  # pragma: no cover
    async def broadcast_progress(task_id: str, data: dict):
        return None


class AnimationRenderPipeline:
    def __init__(self, config: dict):
        self.config = config
        self.store = AnimationTaskStore(config)
        self.ffmpeg = FFmpegTools(config)
        self.tts = TTSService(config)

    async def run(self, task_id: str, request: dict) -> dict:
        task_dir = Path(self.store.path(task_id))
        plan_dir = task_dir / "planning"
        shots_dir = task_dir / "shots"
        audio_dir = task_dir / "audio"
        final_dir = task_dir / "final"
        for d in (plan_dir, shots_dir, audio_dir, final_dir):
            d.mkdir(parents=True, exist_ok=True)

        try:
            await self._update(task_id, "processing", "planning", "正在生成世界观、角色与分镜规划…", 10)
            plan = self._build_plan(request)
            plan_path = plan_dir / "animation_plan.json"
            template_path = plan_dir / "shot_templates.json"
            consistency_path = plan_dir / "character_consistency.json"
            state_path = plan_dir / "character_states.json"
            assets_path = plan_dir / "scene_assets.json"
            scene_flow_path = plan_dir / "scene_state_flow.json"
            reuse_path = plan_dir / "episode_asset_reuse.json"
            relationship_path = plan_dir / "relationship_graph.json"
            memory_path = plan_dir / "story_memory_bank.json"
            outline_path = plan_dir / "outline_editor.json"
            season_path = plan_dir / "season_memory_bank.json"
            dialogue_styles_path = plan_dir / "dialogue_styles.json"
            conflict_tree_path = plan_dir / "season_conflict_tree.json"
            scene_pacing_path = plan_dir / "scene_pacing.json"
            climax_plan_path = plan_dir / "climax_plan.json"
            emotion_arcs_path = plan_dir / "emotion_arcs.json"
            punchline_path = plan_dir / "punchline_dialogue.json"
            scene_twists_path = plan_dir / "scene_twists.json"
            highlight_shots_path = plan_dir / "highlight_shots.json"
            shot_emotion_filters_path = plan_dir / "shot_emotion_filters.json"
            foreshadow_plan_path = plan_dir / "foreshadow_plan.json"
            payoff_tracker_path = plan_dir / "payoff_tracker.json"
            suspense_keeper_path = plan_dir / "suspense_keeper.json"
            payoff_strength_path = plan_dir / "payoff_strength.json"
            season_suspense_chain_path = plan_dir / "season_suspense_chain.json"
            finale_payoff_plan_path = plan_dir / "finale_payoff_plan.json"
            season_trailer_path = plan_dir / "season_trailer_generator.json"
            next_season_hook_path = plan_dir / "next_season_hook_planner.json"
            trailer_editor_path = plan_dir / "trailer_editor.json"
            next_episode_cold_open_path = plan_dir / "next_episode_cold_open.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            template_path.write_text(json.dumps(plan["shot_templates"], ensure_ascii=False, indent=2), encoding="utf-8")
            consistency_path.write_text(json.dumps(plan["consistency_report"], ensure_ascii=False, indent=2), encoding="utf-8")
            state_path.write_text(json.dumps(plan.get("character_states", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            assets_path.write_text(json.dumps(plan.get("scene_assets", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            scene_flow_path.write_text(json.dumps(plan.get("scene_state_flow", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            reuse_path.write_text(json.dumps(plan.get("episode_asset_reuse", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            relationship_path.write_text(json.dumps(plan.get("relationship_graph", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            memory_path.write_text(json.dumps(plan.get("story_memory_bank", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            outline_path.write_text(json.dumps(plan.get("outline_editor", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            season_path.write_text(json.dumps(plan.get("season_memory_bank", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            dialogue_styles_path.write_text(json.dumps(plan.get("dialogue_styles", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            conflict_tree_path.write_text(json.dumps(plan.get("season_conflict_tree", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            scene_pacing_path.write_text(json.dumps(plan.get("scene_pacing", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            climax_plan_path.write_text(json.dumps(plan.get("climax_plan", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            emotion_arcs_path.write_text(json.dumps(plan.get("emotion_arcs", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            punchline_path.write_text(json.dumps(plan.get("punchline_dialogue", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            scene_twists_path.write_text(json.dumps(plan.get("scene_twists", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            highlight_shots_path.write_text(json.dumps(plan.get("highlight_shots", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            shot_emotion_filters_path.write_text(json.dumps(plan.get("shot_emotion_filters", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            foreshadow_plan_path.write_text(json.dumps(plan.get("foreshadow_plan", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            payoff_tracker_path.write_text(json.dumps(plan.get("payoff_tracker", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            suspense_keeper_path.write_text(json.dumps(plan.get("suspense_keeper", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            payoff_strength_path.write_text(json.dumps(plan.get("payoff_strength", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            season_suspense_chain_path.write_text(json.dumps(plan.get("season_suspense_chain", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            finale_payoff_plan_path.write_text(json.dumps(plan.get("finale_payoff_plan", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            season_trailer_path.write_text(json.dumps(plan.get("season_trailer_generator", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            next_season_hook_path.write_text(json.dumps(plan.get("next_season_hook_planner", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            trailer_editor_path.write_text(json.dumps(plan.get("trailer_editor", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            next_episode_cold_open_path.write_text(json.dumps(plan.get("next_episode_cold_open", {}), ensure_ascii=False, indent=2), encoding="utf-8")
            self.store.update(task_id, plan=plan, artifacts={
                "plan": str(plan_path),
                "templates": str(template_path),
                "consistency_report": str(consistency_path),
                "character_states": str(state_path),
                "scene_assets": str(assets_path),
                "scene_state_flow": str(scene_flow_path),
                "episode_asset_reuse": str(reuse_path),
                "relationship_graph": str(relationship_path),
                "story_memory_bank": str(memory_path),
                "outline_editor": str(outline_path),
                "season_memory_bank": str(season_path),
                "dialogue_styles": str(dialogue_styles_path),
                "season_conflict_tree": str(conflict_tree_path),
                "scene_pacing": str(scene_pacing_path),
                "climax_plan": str(climax_plan_path),
                    "emotion_arcs": str(emotion_arcs_path),
                    "punchline_dialogue": str(punchline_path),
                "emotion_arcs": str(emotion_arcs_path),
                "punchline_dialogue": str(punchline_path),
                "scene_twists": str(scene_twists_path),
                "highlight_shots": str(highlight_shots_path),
                "shot_emotion_filters": str(shot_emotion_filters_path),
                "foreshadow_plan": str(foreshadow_plan_path),
                "payoff_tracker": str(payoff_tracker_path),
                "suspense_keeper": str(suspense_keeper_path),
                "payoff_strength": str(payoff_strength_path),
                "season_suspense_chain": str(season_suspense_chain_path),
                "finale_payoff_plan": str(finale_payoff_plan_path),
                "season_trailer_generator": str(season_trailer_path),
                "next_season_hook_planner": str(next_season_hook_path),
            })

            if request.get("dry_run", False):
                await self._update(task_id, "completed", "dry_run", "规划完成（dry run）", 100)
                state = self.store.update(task_id, output_video=None, subtitle_path=None, storyboard_path=str(plan_path.relative_to(task_dir)))
                EpisodeAssetReusePlanner(self.store).update_batch_cache(
                    request.get("batch_parent_id") or None,
                    plan["episode"].get("episode_title", request.get("title", "")),
                    plan.get("episode_asset_reuse", {}),
                )
                season_memory = plan.get("season_memory_bank", {})
                if season_memory.get("season_id"):
                    season_payload = dict(season_memory)
                    season_payload["season_conflict_tree"] = plan.get("season_conflict_tree", {})
                    self.store.save_season_memory(season_memory.get("season_id"), season_payload)
                return state

            await self._update(task_id, "processing", "rendering", "正在按 shot 逐镜头生成…", 30)
            adapter = KieSeedanceAnimationAdapter(
                self.config,
                model_variant=request.get("model_variant", "seedance_2"),
                fallback_model=request.get("fallback_model", "seedance_15"),
            )
            shot_results = []
            clips = []
            total_shots = sum(len(scene["shots"]) for scene in plan["episode"]["scenes"]) or 1
            completed = 0

            for scene in plan["episode"]["scenes"]:
                for shot in scene["shots"]:
                    shot_id = shot["shot_id"]
                    prompt = shot.get("render_prompt") or shot.get("visual_prompt") or scene["title"]
                    ref_image = shot.get("reference_image_url") or ""
                    duration = shot.get("render_duration_seconds") or shot.get("duration_seconds") or 4
                    clip_path = str(shots_dir / f"{shot_id}.mp4")
                    try:
                        job_id = await adapter.generate_shot_job(
                            prompt=prompt,
                            duration_seconds=duration,
                            aspect_ratio=plan["render_meta"].get("aspect_ratio", "9:16"),
                            reference_image=ref_image or None,
                        )
                        job = await adapter.wait_for_completion(job_id)
                        if job.status != "succeeded":
                            raise RuntimeError(job.error or f"{shot_id} render failed")
                        downloaded = await adapter.download_result(job, str(shots_dir))
                        if downloaded != clip_path:
                            Path(downloaded).rename(clip_path)
                        clips.append(clip_path)
                        result = {
                            "shot_id": shot_id,
                            "scene_id": scene["scene_id"],
                            "status": "succeeded",
                            "job_id": job_id,
                            "output_path": clip_path,
                            "retry_count": shot.get("retry_count", 0),
                        }
                    except Exception as exc:
                        result = {
                            "shot_id": shot_id,
                            "scene_id": scene["scene_id"],
                            "status": "failed",
                            "error": str(exc),
                            "retry_count": shot.get("retry_count", 0),
                        }
                    shot_results.append(result)
                    completed += 1
                    await self._update(task_id, "processing", "rendering", f"已完成 {completed}/{total_shots} 个 shot", min(85, 30 + int(completed / total_shots * 55)))
                    self.store.update(task_id, shot_results=shot_results)

            if not clips:
                raise RuntimeError("No shot clips were rendered successfully")

            subtitle_path = str(final_dir / "episode.srt")
            self._write_subtitles(plan, subtitle_path)

            final_video = str(final_dir / "episode.mp4")
            if len(clips) == 1:
                Path(clips[0]).rename(final_video)
            else:
                await self._concat_videos(clips, final_video)

            if request.get("enable_tts", True):
                await self._update(task_id, "processing", "audio", "正在生成旁白与对白音轨…", 90)
                tts_path = await self._synthesize_episode_audio(plan, audio_dir)
                muxed_video = str(final_dir / "episode_muxed.mp4")
                await self._mux_audio(final_video, tts_path, muxed_video)
                final_video = muxed_video

            await self._update(task_id, "completed", "done", "动画任务完成", 100)
            state = self.store.update(
                task_id,
                output_video=str(Path(final_video).relative_to(task_dir)),
                subtitle_path=str(Path(subtitle_path).relative_to(task_dir)),
                storyboard_path=str(plan_path.relative_to(task_dir)),
                shot_results=shot_results,
                artifacts={
                    "final_video": str(final_video),
                    "subtitle": str(subtitle_path),
                    "plan": str(plan_path),
                    "templates": str(template_path),
                    "consistency_report": str(consistency_path),
                    "character_states": str(state_path),
                    "scene_assets": str(assets_path),
                    "scene_state_flow": str(scene_flow_path),
                    "episode_asset_reuse": str(reuse_path),
                    "dialogue_styles": str(dialogue_styles_path),
                    "season_conflict_tree": str(conflict_tree_path),
                "scene_pacing": str(scene_pacing_path),
                "climax_plan": str(climax_plan_path),
                "emotion_arcs": str(emotion_arcs_path),
                "punchline_dialogue": str(punchline_path),
                "scene_twists": str(scene_twists_path),
                "highlight_shots": str(highlight_shots_path),
                },
            )
            EpisodeAssetReusePlanner(self.store).update_batch_cache(
                request.get("batch_parent_id") or None,
                plan["episode"].get("episode_title", request.get("title", "")),
                plan.get("episode_asset_reuse", {}),
            )
            season_memory = plan.get("season_memory_bank", {})
            if season_memory.get("season_id"):
                season_payload = dict(season_memory)
                season_payload["season_conflict_tree"] = plan.get("season_conflict_tree", {})
                self.store.save_season_memory(season_memory.get("season_id"), season_payload)
            return state
        except Exception as exc:
            await self._update(task_id, "failed", "error", f"动画任务失败：{exc}", 100)
            return self.store.update(task_id, error=str(exc))

    async def retry_shot(self, task_id: str, shot_id: str) -> dict:
        task = self.store.load(task_id)
        if not task:
            raise FileNotFoundError(f"Task {task_id} not found")
        plan = task.get("plan")
        if not plan:
            raise ValueError("Task has no stored plan")

        task_dir = Path(self.store.path(task_id))
        shots_dir = task_dir / "shots"
        shots_dir.mkdir(parents=True, exist_ok=True)

        target_shot = None
        target_scene = None
        for scene in plan["episode"]["scenes"]:
            for shot in scene["shots"]:
                if shot["shot_id"] == shot_id:
                    target_shot = shot
                    target_scene = scene
                    break
            if target_shot:
                break
        if not target_shot:
            raise ValueError(f"Shot {shot_id} not found in task {task_id}")

        retry_limit = int(target_shot.get("shot_retry_limit", 2))
        retry_count = int(target_shot.get("retry_count", 0))
        if retry_count >= retry_limit:
            raise ValueError(f"Shot {shot_id} retry limit reached ({retry_limit})")

        target_shot["retry_count"] = retry_count + 1
        adapter = KieSeedanceAnimationAdapter(
            self.config,
            model_variant=plan["render_meta"].get("requested_model", "seedance_2"),
            fallback_model=plan["render_meta"].get("fallback_model", "seedance_15"),
        )
        prompt = target_shot.get("render_prompt") or target_shot.get("visual_prompt") or target_scene["title"]
        ref_image = target_shot.get("reference_image_url") or None
        clip_path = str(shots_dir / f"{shot_id}_retry_{target_shot['retry_count']}.mp4")
        job_id = await adapter.generate_shot_job(
            prompt=prompt,
            duration_seconds=target_shot.get("render_duration_seconds") or target_shot.get("duration_seconds") or 4,
            aspect_ratio=plan["render_meta"].get("aspect_ratio", "9:16"),
            reference_image=ref_image,
        )
        job = await adapter.wait_for_completion(job_id)
        if job.status != "succeeded":
            raise RuntimeError(job.error or "retry render failed")
        downloaded = await adapter.download_result(job, str(shots_dir))
        if downloaded != clip_path:
            Path(downloaded).rename(clip_path)

        results = task.get("shot_results", [])
        results.append({
            "shot_id": shot_id,
            "scene_id": target_scene["scene_id"],
            "status": "succeeded",
            "job_id": job_id,
            "output_path": clip_path,
            "retry_count": target_shot["retry_count"],
            "retry": True,
        })
        self.store.update(task_id, plan=plan, shot_results=results, updated_at=time.time())
        return {"task_id": task_id, "shot_id": shot_id, "output_path": clip_path, "retry_count": target_shot["retry_count"]}

    async def _synthesize_episode_audio(self, plan: dict, audio_dir: Path) -> str:
        from core.timeline_types import UGCVideoRequest
        voice_lines = []
        for scene in plan["episode"]["scenes"]:
            for shot in scene["shots"]:
                text = (shot.get("dialogue") or "").strip()
                if text and text != "无对白":
                    voice_lines.append(text)
        if not voice_lines:
            silent = audio_dir / "silent.aac"
            await self.ffmpeg._run([self.ffmpeg.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1", str(silent)])
            return str(silent)

        req = UGCVideoRequest(task_id="animation-tts", user_id="animation", mode="text_to_video", model="seedance_2", duration=10, language=plan["render_meta"].get("language", "zh"))
        output = audio_dir / "episode_tts.mp3"
        line = " ".join(voice_lines)
        await self.tts.synthesize_full(line, req.language, str(output))
        return str(output)

    def _build_plan(self, request: dict) -> dict:
        story_bible = build_story_bible(
            title=request["title"],
            genre=request.get("genre", "都市情感"),
            format_type=request.get("format_type", "竖屏短剧"),
            target_platform=request.get("target_platform", "douyin"),
            visual_style=request.get("visual_style", "high consistency anime cinematic"),
            tone=request.get("tone", "高张力、强反转"),
            core_premise=request["core_premise"],
        )
        characters = [
            build_character_bible(
                name=char["name"],
                role=char["role"],
                age_range=char.get("age_range", "18-25"),
                appearance=char.get("appearance", []),
                wardrobe=char.get("wardrobe", []),
                personality=char.get("personality", []),
                voice_style=char.get("voice_style", "清晰、年轻、有辨识度"),
                catchphrases=char.get("catchphrases", []),
                reference_image_url=char.get("reference_image_url", ""),
            )
            for char in request.get("characters", [])
        ]
        episode = EpisodeWriter().create_episode_outline(
            story_bible=story_bible,
            characters=characters,
            episode_goal=request["episode_goal"],
            scene_count=int(request.get("scene_count", 4)),
        )
        template_library = ShotTemplateLibrary()
        episode = StoryboardGenerator(template_library=template_library).build_shots(
            episode=episode,
            characters=characters,
            visual_style=story_bible.visual_style,
        )

        state_machine = CharacterStateMachine()
        character_states = state_machine.build_for_characters(characters)
        state_assignments = state_machine.apply_to_episode(episode, character_states)

        scene_asset_library = SceneAssetLibrary()
        scene_assets = scene_asset_library.build_for_story(story_bible)
        scene_asset_map = scene_asset_library.assign_to_episode(episode, scene_assets)
        scene_state_flow = SceneStateFlowEngine().build(episode)
        relationship_graph = RelationshipGraphBuilder().build(story_bible, characters, episode)
        previous_memory = self.store.load_batch_memory(request.get("batch_parent_id", "")) if request.get("reuse_assets_across_episodes", True) else None
        outline_editor = OutlineEditor().build(request.get("title", ""), request.get("core_premise", ""), request.get("episode_goal", ""), int(request.get("scene_count", 4) or 4), previous_memory=previous_memory)
        story_memory_bank = StoryMemoryBank().build(
            story_bible=story_bible,
            characters=characters,
            episode=episode,
            relationship_graph=relationship_graph,
            previous_memory=previous_memory,
            episode_index=int(request.get("episode_index", 1)),
        )
        season_memory_bank = SeasonMemoryBank().build(story_bible.to_dict(), relationship_graph, episode.to_dict(), previous_memory)
        dialogue_styles = DialogueStyleEngine().build(story_bible.to_dict(), [c.to_dict() for c in characters], relationship_graph)
        DialogueStyleEngine().apply_to_episode(episode, dialogue_styles)
        season_conflict_tree = SeasonConflictTree().build(story_bible.to_dict(), relationship_graph, story_memory_bank, previous_memory)
        scene_pacing = ScenePacingController().build(episode.to_dict())
        climax_plan = ClimaxOrchestrator().build(episode.to_dict(), relationship_graph, season_conflict_tree)
        emotion_arcs = CharacterEmotionArcEngine().build(episode.to_dict(), [c.to_dict() for c in characters])
        CharacterEmotionArcEngine().apply_to_episode(episode, emotion_arcs)
        punchline_dialogue = PunchlineDialogueGenerator().build(episode.to_dict(), relationship_graph, dialogue_styles)
        PunchlineDialogueGenerator().apply_to_episode(episode, punchline_dialogue)
        scene_twists = SceneTwistDetector().build(episode.to_dict())
        highlight_shots = HighlightShotOrchestrator().build(episode.to_dict(), scene_twists, climax_plan)
        shot_emotion_filters = ShotEmotionFilter().build(episode.to_dict(), emotion_arcs)
        ShotEmotionFilter().apply_to_episode(episode, shot_emotion_filters)
        foreshadow_plan = ForeshadowPlanter().build(episode.to_dict(), scene_twists, relationship_graph)
        ForeshadowPlanter().apply_to_episode(episode, foreshadow_plan)
        payoff_tracker = PayoffTracker().build(foreshadow_plan, scene_twists, climax_plan)
        suspense_keeper = SuspenseKeeper().build(episode.to_dict(), scene_twists, foreshadow_plan, climax_plan)
        SuspenseKeeper().apply_to_episode(episode, suspense_keeper)
        payoff_strength = PayoffStrengthScorer().build(foreshadow_plan, payoff_tracker, climax_plan, relationship_graph)
        PayoffStrengthScorer().apply_to_episode(episode, payoff_strength)
        season_suspense_chain = SeasonSuspenseChain().build(season_memory_bank, story_memory_bank, suspense_keeper, scene_twists, climax_plan, request.get("batch_parent_id"))
        SeasonSuspenseChain().apply_to_episode(episode, season_suspense_chain)
        finale_payoff_plan = FinalePayoffPlanner().build(season_suspense_chain, payoff_tracker, payoff_strength, season_conflict_tree, season_memory_bank)
        FinalePayoffPlanner().apply_to_episode(episode, finale_payoff_plan)
        season_trailer_generator = SeasonTrailerGenerator().build(
            season_suspense_chain,
            finale_payoff_plan,
            suspense_keeper=suspense_keeper,
            payoff_strength=payoff_strength,
        )
        next_season_hook_planner = NextSeasonHookPlanner().build(
            season_suspense_chain,
            finale_payoff_plan,
            relationship_graph=relationship_graph,
            season_memory_bank=season_memory_bank,
        )
        trailer_editor = TrailerEditor().build(
            season_trailer_generator,
            highlight_shots,
            suspense_keeper=suspense_keeper,
            climax_plan=climax_plan,
        )
        next_episode_cold_open = NextEpisodeColdOpenPlanner().build(
            next_season_hook_planner,
            finale_payoff_plan,
            season_memory_bank=season_memory_bank,
            relationship_graph=relationship_graph,
        )
        if request.get("batch_parent_id"):
            self.store.save_batch_memory(request.get("batch_parent_id"), story_memory_bank)
        for scene in episode.scenes:
            for shot in scene.shots:
                shot.state_assignments = list(state_assignments.get(shot.shot_id, []))
                shot.scene_assets = list(scene_asset_map.get(scene.scene_id, []))
                related = [edge for edge in relationship_graph.get("edges", []) if any(name in shot.action or name in shot.dialogue for name in [edge["source"], edge["target"]])]
                if related:
                    shot.continuity_notes.append(related[0]["dynamic_summary"])
                open_loops = story_memory_bank.get("open_loops", [])
                if open_loops:
                    shot.continuity_notes.append(f"长线记忆锚点：{open_loops[0]}")
                twist_scene_ids = {item.get("scene_id") for item in scene_twists.get("twist_scenes", [])}
                if scene.scene_id in twist_scene_ids:
                    shot.continuity_notes.append("反转提示：这一场承担信息翻转或立场翻转，镜头反应优先。")
                hero_highlight = (highlight_shots.get("hero_highlight") or {})
                if hero_highlight.get("shot_id") == shot.shot_id:
                    shot.continuity_notes.append("爆点镜头：保留停顿、字幕强调与人物特写。")
                payoff_items = [item for item in payoff_tracker.get("payoffs", []) if item.get("seed_scene_id") == scene.scene_id]
                if payoff_items:
                    shot.continuity_notes.append(f"高潮回收路径：{payoff_items[0].get('seed_scene_id')} -> {payoff_items[0].get('payoff_scene_id')}")

        consistency_engine = CharacterConsistencyEngine()
        consistency_profiles = consistency_engine.apply_to_episode(episode, characters)
        consistency_report = consistency_engine.evaluate(episode, characters)
        retry_limit = int(request.get("shot_retry_limit", 2))
        for scene in episode.scenes:
            for shot in scene.shots:
                shot.reference_image_url = shot.reference_image_url or next((c.reference_image_url for c in characters if c.reference_image_url), "")
                shot.render_duration_seconds = int(max(4, round(float(shot.duration_seconds))))
                shot.shot_retry_limit = retry_limit

        reuse_planner = EpisodeAssetReusePlanner(self.store)
        episode_asset_reuse = reuse_planner.build(
            story_bible=story_bible,
            characters=characters,
            episode=episode,
            scene_assets={"library": scene_assets, "scene_asset_map": scene_asset_map},
            batch_parent_id=request.get("batch_parent_id") if request.get("reuse_assets_across_episodes", True) else None,
        )
        adapter = KieSeedanceAnimationAdapter(
            self.config,
            model_variant=request.get("model_variant", "seedance_2"),
            fallback_model=request.get("fallback_model", "seedance_15"),
        )
        for scene in episode.scenes:
            for shot in scene.shots:
                shot.render_prompt = adapter.build_render_prompt(story_bible, characters, shot, scene.title)
                shot.render_duration_seconds = adapter.normalize_duration(shot.duration_seconds)
        continuity = ContinuityEngine().validate(episode, characters, consistency_report=consistency_report)
        return {
            "story_bible": story_bible.to_dict(),
            "characters": [c.to_dict() for c in characters],
            "episode": episode.to_dict(),
            "consistency_report": consistency_report,
            "continuity_report": continuity,
            "shot_templates": template_library.list_templates(),
            "consistency_profiles": consistency_profiles,
            "character_states": character_states,
            "scene_assets": {
                "library": scene_assets,
                "scene_asset_map": scene_asset_map,
            },
            "scene_state_flow": scene_state_flow,
            "episode_asset_reuse": episode_asset_reuse,
            "relationship_graph": relationship_graph,
            "story_memory_bank": story_memory_bank,
            "outline_editor": outline_editor,
            "season_memory_bank": season_memory_bank,
            "dialogue_styles": dialogue_styles,
            "season_conflict_tree": season_conflict_tree,
            "scene_pacing": scene_pacing,
            "climax_plan": climax_plan,
            "emotion_arcs": emotion_arcs,
            "punchline_dialogue": punchline_dialogue,
            "scene_twists": scene_twists,
            "highlight_shots": highlight_shots,
            "shot_emotion_filters": shot_emotion_filters,
            "foreshadow_plan": foreshadow_plan,
            "payoff_tracker": payoff_tracker,
            "suspense_keeper": suspense_keeper,
            "payoff_strength": payoff_strength,
            "season_suspense_chain": season_suspense_chain,
            "finale_payoff_plan": finale_payoff_plan,
            "season_trailer_generator": season_trailer_generator,
            "next_season_hook_planner": next_season_hook_planner,
            "trailer_editor": trailer_editor,
            "next_episode_cold_open": next_episode_cold_open,
            "render_meta": {
                "requested_model": request.get("model_variant", "seedance_2"),
                "fallback_model": request.get("fallback_model", "seedance_15"),
                "language": request.get("language", "zh"),
                "aspect_ratio": request.get("aspect_ratio", "9:16"),
                "enable_tts": bool(request.get("enable_tts", True)),
                "dry_run": bool(request.get("dry_run", False)),
                "shot_retry_limit": retry_limit,
            },
        }

    async def _update(self, task_id: str, status: str, stage: str, message: str, progress: int) -> None:
        self.store.update(
            task_id,
            status=status,
            stage=stage,
            stage_message=message,
            progress=progress,
            updated_at=time.time(),
        )
        await broadcast_progress(task_id, {
            "task_id": task_id,
            "event": "progress",
            "status": status,
            "stage": stage,
            "stage_message": message,
            "progress": progress,
        })

    async def _concat_videos(self, clips: list[str], output_path: str) -> str:
        concat_file = Path(output_path).with_suffix(".concat.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for clip in clips:
                f.write(f"file '{Path(clip).as_posix()}'\n")
        await self.ffmpeg._run([self.ffmpeg.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", output_path])
        return output_path

    async def _mux_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        cmd = [
            self.ffmpeg.ffmpeg_bin, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", "[1:a]apad[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path,
        ]
        await self.ffmpeg._run(cmd)
        return output_path

    def _write_subtitles(self, plan: dict, subtitle_path: str) -> str:
        lines = []
        cursor = 0.0
        idx = 1
        for scene in plan["episode"]["scenes"]:
            for shot in scene["shots"]:
                duration = float(shot.get("render_duration_seconds") or shot.get("duration_seconds") or 4)
                text = (shot.get("subtitle_text") or "").strip()
                if text:
                    lines.extend([
                        str(idx),
                        f"{self._ts(cursor)} --> {self._ts(cursor + duration)}",
                        text,
                        "",
                    ])
                    idx += 1
                cursor += duration
        Path(subtitle_path).write_text("\n".join(lines), encoding="utf-8")
        return subtitle_path

    @staticmethod
    def _ts(seconds: float) -> str:
        total_ms = int(seconds * 1000)
        h = total_ms // 3600000
        m = (total_ms % 3600000) // 60000
        s = (total_ms % 60000) // 1000
        ms = total_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
