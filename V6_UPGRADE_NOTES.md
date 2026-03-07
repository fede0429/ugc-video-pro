
# V6 Upgrade Notes

## Project 1 — UGC second enhancement
- Added `core/ugc_shot_library.py`
- Added `services/video_scoring_service.py`
- `core/script_generator.py`
  - fixed async signature for `await sg.generate_timeline(...)`
  - enriches B-roll prompt generation via shot library
- `web/tasks.py`
  - writes creative score report to `reports/video_score.json`
  - stores score report in `task.metadata_json`

## Project 2 — character state machine + scene asset library
- Added `projects/animation/character_state_machine.py`
- Added `projects/animation/scene_asset_library.py`
- `projects/animation/render_pipeline.py`
  - emits `character_states` and `scene_assets`
  - saves planning files:
    - `planning/character_states.json`
    - `planning/scene_assets.json`
- `projects/animation/kie_seedance_adapter.py`
  - injects state + scene asset anchors into render prompt
- `web/routes_animation.py`
  - new endpoints:
    - `GET /api/animation/states`
    - `GET /api/animation/scene-assets`
- `static/animation-studio.html`
  - added buttons / panels for state machine and scene asset preview
