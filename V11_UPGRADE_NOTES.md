# V11_UPGRADE_NOTES.md

## Project 1
Added `core/direct_publish_skeleton.py` and `core/review_state_machine.py`.

### New routes
- `GET /api/video/tasks/{task_id}/review-state`
- `POST /api/video/tasks/{task_id}/review-state`
- `POST /api/video/tasks/{task_id}/publish-direct`

### Behavior
- UGC completion now stores a default `review_state` in `qa_report_json`.
- Direct publish is still a skeleton/dry-run layer; it normalizes provider payload and records an attempt object.

## Project 2
Added:
- `projects/animation/scene_pacing_controller.py`
- `projects/animation/climax_orchestrator.py`

### Planning additions
`AnimationRenderPipeline._build_plan()` now emits:
- `scene_pacing`
- `climax_plan`

Artifacts written by animation tasks:
- `planning/scene_pacing.json`
- `planning/climax_plan.json`

### Frontend
`animation-studio.html` and `animation-dashboard.js` now expose:
- scene pacing preview
- climax plan preview
