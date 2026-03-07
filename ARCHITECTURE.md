# UGC Video Pro — Architecture & Callchain

## Pipeline Overview
```
POST /api/video/generate/ugc
        │
        ▼
routes_video.py
  → FileStore.save_upload(task_id, asset_group)   [saves multi-image + presenter]
  → VideoTask + TaskAsset[] persisted to DB
  → asyncio.create_task(run_ugc_generation_task())
        │
        ▼
web/tasks.py  ─  17 stages
        │
        ├─ 1.  FileStore(config)  →  create_task_dirs(task_id)
        │        Directory: <data_root>/tasks/<task_id>/
        │        inputs/{product_primary,product_gallery,product_usage,presenter_image,presenter_video}/
        │        audio/  video/a_roll/  video/b_roll/  subtitles/  reports/  final/
        │
        ├─ 2.  ExtendedUGCVideoRequest.from_task_and_paths(task, primary, gallery[], usage[], presenter)
        │        Fields: product_primary_image, product_gallery_images[], product_usage_images[]
        │        presenter_image_path, presenter_video_path, hook_style, tone_style, platform, …
        │
        ├─ 3.  ImageAnalyzer.analyze_images(image_paths[], description)
        │        → ProductProfile
        │          .product_type, .brand, .description, .key_features[], .selling_points[]
        │          .demo_actions[], .consistency_anchors[], .before_after_opportunity
        │
        ├─ 4.  PresenterAnalyzer.build_presenter_profile(
        │            presenter_image, presenter_video, persona_template, voice_preset)
        │        → PresenterProfile
        │          .presenter_id, .face_image_path, .persona_template
        │          .voice_preset, .voice_id, .lipsync_model, .style_notes
        │          Recommends: shots[], hooks[], tones[] per persona
        │
        ├─ 5.  UGCProducer.build_plan(product_summary, request, presenter_profile)
        │        → ProductionPlan
        │          .strategy, .video_model, .platform, .persona, .hook_style
        │          .a_roll_ratio, .b_roll_ratio, .segments_json[], .cta_segment
        │
        ├─ 6.  ScriptGenerator.generate_timeline(request, product_profile, presenter_profile, plan)
        │        → TimelineScript
        │          .segments[]  ← TimelineSegment(track_type=a_roll|b_roll, spoken_line, emotion,
        │                                          shot_type, visual_prompt, product_focus,
        │                                          overlay_text, duration_seconds)
        │          .a_roll_segments, .b_roll_segments, .total_duration
        │
        ├─ 7.  DB: TaskSegment[] persisted per timeline segment
        │
        ├─ 8.  TTSService.synthesize_segments(task_id, timeline, voice_preset, language, file_store)
        │        For each a_roll segment with spoken_line:
        │          file_store.segment_audio_path(task_id, segment_id)
        │          KieGateway.tts(text, voice_id, model)
        │          _map_emotion_to_style(segment.emotion) → energetic|conversational|confident|soft
        │        → AudioSegmentAsset[](segment_id, audio_path, duration_seconds, language)
        │
        ├─ 9.  LipSyncService.render_a_roll_segments(task_id, timeline, presenter_profile, audio_assets, file_store)
        │        Matches audio_assets to a_roll segments
        │        file_store.segment_video_path(task_id, segment_id, "a_roll")
        │        KieGateway.lipsync(face_image, audio_path, model)
        │        → RenderedAsset[](segment_id, video_path, duration_seconds, track_type="a_roll")
        │
        ├─ 10. BRollSequenceBuilder.render_b_roll_segments(task_id, timeline, product_profile, request)
        │        VideoModelRouter.select_b_roll_model(payload)  ← quality_tier → model key
        │        _build_source_pool(request)  → [{path, kind: primary|gallery|usage}]
        │        _choose_best_source(segment, pool, product_profile):
        │          apply/demo shots    → prefer usage_images
        │          detail/macro shots  → prefer gallery_images
        │          default             → primary → gallery → usage
        │        file_store.segment_video_path(task_id, segment_id, "b_roll")
        │        model.generate_b_roll(prompt, source_image, duration, shot_type, output_path)
        │        → RenderedAsset[](segment_id, video_path, duration_seconds, track_type="b_roll")
        │
        ├─ 11. SubtitleService.generate_srt(task_id, timeline, audio_assets)
        │        → captions.srt (timecoded from audio_asset durations)
        │
        ├─ 12. OverlayService.build_plan(timeline, a_roll_assets, b_roll_assets)
        │        → [{text, start, end, fontsize, x, y}]  ← from segment.overlay_text
        │
        ├─ 13. TimelineComposer.compose(task_id, timeline, a_roll_assets, b_roll_assets,
        │                               subtitle_path, bgm_path, overlay_plan, file_store)
        │        Ordered clip list from timeline.segments
        │        FFmpegTools.assemble_timeline():
        │          concat_clips → burn_subtitles → overlay_text → mix_bgm → final.mp4
        │        → final_video_path
        │
        ├─ 14. QAService.run(timeline, final_video_path, subtitle_path, a_roll[], b_roll[], audio[])
        │        6 checks: a_roll_presence, b_roll_presence, audio_coverage,
        │                  subtitle_presence, final_video_exists, black_frames
        │        → QAReport(passed, issues[], checks{})
        │
        └─ 15. Persist → DB update + copy to video_dir + WebSocket broadcast
```

## Module Responsibility Table

| Layer           | Module                        | Does                              | Does NOT        |
|-----------------|-------------------------------|-----------------------------------|-----------------|
| API             | routes_video.py               | Receive inputs, save files, queue | Any AI calls    |
| Intelligence    | image_analyzer.py             | Multi-image → ProductProfile      | Generate video  |
| Intelligence    | presenter_analyzer.py         | Persona → PresenterProfile        | Generate video  |
| Creative Brain  | director_agent.py (UGCProducer)| Strategy, plan, timeline JSON     | Low-level ops   |
| Audio Engine    | tts_service.py                | Per-segment TTS + emotion style   | Video, lipsync  |
| A-roll Engine   | lipsync_service.py            | Talking-head per segment          | B-roll, TTS     |
| B-roll Engine   | frame_chainer.py (BRollSeqBuilder)| Product demo clips, img selection| A-roll, audio  |
| Post-Production | video_stitcher.py (TimelineComposer)| Multi-track compose, subtitle, overlay | Analysis |
| QA              | qa_service.py                 | 6-point quality checks            | Fix issues      |
| File System     | utils/file_store.py           | All path resolution               | Content ops     |

## FileStore Directory Tree
```
<data_root>/tasks/<task_id>/
    inputs/
        product_primary/      ← primary product image
        product_gallery/      ← detail / angle shots (from gallery_images)
        product_usage/        ← in-use / context images (from usage_images)
        presenter_image/      ← face photo
        presenter_video/      ← reference talking-head video
    audio/
        seg_01.wav            ← per A-roll TTS segment
        seg_03.wav
    video/
        a_roll/
            seg_01.mp4        ← lipsync rendered
            seg_03.mp4
        b_roll/
            seg_02.mp4        ← AI product demo
            seg_04.mp4
    subtitles/
        captions.srt
    reports/
        timeline.json
        product_profile.json
        presenter_profile.json
        qa_report.json
    final/
        final_video.mp4
        final_voice.wav
        cover.jpg
```
