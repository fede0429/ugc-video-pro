# V14 UPGRADE NOTES

## Project 1
Added:
- `core/publish_task_executor.py`
- `core/platform_receipt_recorder.py`

Routes:
- `POST /api/video/publish-queue/{queue_id}/execute`
- `GET /api/video/publish-receipts`
- `GET /api/video/tasks/{task_id}/publish-receipts`

Behavior:
- Executes publish queue entries in dry-run/provider-envelope mode
- Validates review state + credential presence
- Writes receipt records and updates queue entry status

## Project 2
Added:
- `projects/animation/shot_emotion_filter.py`
- `projects/animation/foreshadow_planter.py`
- `projects/animation/payoff_tracker.py`

Routes:
- `GET /api/animation/shot-emotion-filters`
- `GET /api/animation/foreshadow-plan`
- `GET /api/animation/payoff-tracker`

Planning artifacts:
- `planning/shot_emotion_filters.json`
- `planning/foreshadow_plan.json`
- `planning/payoff_tracker.json`

Front-end:
- Added preview buttons and panels for the new planning layers
- Fixed goal-field fallback to use `episode-goal` when `goal` does not exist
