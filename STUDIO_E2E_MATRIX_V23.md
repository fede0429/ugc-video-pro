
# Studio Unified E2E Matrix v23

This file is the single matrix for project 1 (UGC) and project 2 (Animation).

## Coverage

### UGC dashboard
- btn-generate
- btn-logout

### Animation workbench
- btn-emotion-arcs
- btn-punchlines
- btn-scene-twists
- btn-highlight-shots
- btn-suspense-keeper
- btn-payoff-strength
- btn-load-state-machine
- btn-load-scene-assets
- btn-load-scene-flow
- btn-load-relationship-graph
- btn-scene-pacing
- btn-climax-plan
- btn-shot-emotion-filters
- btn-foreshadow-plan
- btn-payoff-tracker
- check-consistency-btn
- load-templates-btn
- plan-btn
- btn-outline-editor
- btn-season-memory
- btn-dialogue-styles
- btn-season-conflict
- btn-season-suspense-chain
- btn-finale-payoff-plan
- btn-season-trailer-generator
- btn-next-season-hook-planner
- btn-trailer-editor
- btn-next-episode-cold-open
- render-btn
- batch-render-btn
- refresh-tasks-btn
- retry-shot-btn

## Run

Mock mode:
```bash
ANIMATION_E2E_MOCK=1 npx playwright test tests/e2e/studio-e2e-matrix.spec.js
```

Real backend mode:
```bash
ANIMATION_E2E_MOCK=0 ANIMATION_E2E_BASE_URL=http://127.0.0.1:8000 npx playwright test tests/e2e/studio-e2e-matrix.spec.js
```
