# V20 Test Report

## Added
- Unified smoke / E2E entrypoint: `scripts/studio_test_hub.py`
- Project 1 Playwright mock spec: `tests/e2e/ugc-dashboard.spec.js`
- npm shortcuts: `package.json`

## Validation performed in this environment
- `python -m py_compile scripts/studio_test_hub.py` ✅
- `python -m compileall -q scripts projects/animation web core` ✅
- `node --check tests/e2e/ugc-dashboard.spec.js` ✅
- `node --check playwright.config.js` ✅
- `python scripts/studio_test_hub.py --mode smoke --project all` ✅

## Unified smoke result
- Project 1 UGC smoke: passed
- Project 2 animation planning smoke: passed
- Project 2 animation API smoke: skipped as optional in this container because `sqlalchemy` is not installed

## Notes
- The unified runner auto-discovers the latest versioned smoke script for UGC and animation.
- E2E execution still depends on Node + Playwright browsers being available in the target environment.
- Use `--strict-smoke` if you want missing optional dependencies to fail the suite.
