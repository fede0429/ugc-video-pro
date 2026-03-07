# UGC Studio Upgrade Notes

This patched build adds studio-focused improvements to the UGC pipeline:

## What changed
- Added persona-aware director planning
- Added sales framework selection (PAS / AIDA / comparison / testimonial)
- Added creative variant generation for hooks
- Enriched `PresenterProfile` and `ProductProfile`
- Made `ScriptGenerator.generate_timeline()` compatible with `production_plan=...`
- Allowed timeline generation directly from director segments, reducing fragile LLM hops
- Fixed service constructor compatibility for:
  - `SubtitleService(config)`
  - `QAService(config)`
  - `TimelineComposer.compose(..., overlay_plan=...)`
- Simplified `core/__init__.py` to avoid heavy eager imports

## New files
- `core/persona_engine.py`
- `core/sales_framework_engine.py`
- `core/variant_generator.py`

## Patched files
- `core/director_agent.py`
- `core/script_generator.py`
- `core/timeline_types.py`
- `services/presenter_analyzer.py`
- `services/subtitle_service.py`
- `services/qa_service.py`
- `core/video_stitcher.py`
- `core/__init__.py`

## Why this matters
The old pipeline had several interface mismatches that could break the new UGC route.
This patched build makes the studio UGC route much more coherent without rewriting the whole app.

## Recommended next steps
1. Add a UI selector for persona / framework / variant count
2. Persist chosen framework + variants in the DB
3. Add a scoring layer for hook strength / authenticity / conversion intent
4. Add batch render mode for 3-10 variants per product
