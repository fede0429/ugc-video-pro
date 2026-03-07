# Animation V5 Upgrade Notes

This version adds two project-2 production upgrades:

## 1. Character consistency
- Added `projects/animation/character_consistency.py`
- Builds reusable character profiles
- Injects appearance / wardrobe anchors into shot continuity notes
- Produces `consistency_report` with a score, warnings, and suggestions
- Stores report as `planning/character_consistency.json`

## 2. Shot template library
- Added `projects/animation/shot_template_library.py`
- Storyboard generation now chooses templates by dramatic purpose
- Each shot now keeps:
  - `template_id`
  - `shot_category`
  - `negative_prompt`
- Stores template catalog as `planning/shot_templates.json`

## Frontend
- Added template library preview
- Added consistency-check button
- Character reference uploads now prefer the public asset URL over a local path

## Known limits
- No real browser E2E test was performed in this environment
- No live KIE remote render call was executed in this environment
