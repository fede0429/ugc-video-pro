# V19 Testing Additions

## Added
- `scripts/animation_api_smoke_v19.py`
- `playwright.config.js`
- `tests/e2e/animation-workbench.spec.js`
- `tests/e2e/README.md`

## Coverage
### API smoke
- `/api/animation/health`
- multiple preview endpoints
- `POST /api/animation/projects/plan`
- `POST /api/animation/projects/consistency-check`
- `POST /api/animation/projects/scene-pacing`
- `POST /api/animation/projects/climax-plan`
- `POST /api/animation/projects/render` with `dry_run=true`
- `POST /api/animation/projects/render-batch` with `dry_run=true`
- `GET /api/animation/tasks`

### Frontend E2E
- load `/animation-studio.html`
- generate plan preview
- consistency preview
- season suspense chain preview
- finale payoff preview
- render dry-run flow and artifact preview

## Notes
- Playwright spec supports fully mocked mode and real-backend mode.
- Mock mode is intended for stable UI regression checks even without running KIE / Seedance.
