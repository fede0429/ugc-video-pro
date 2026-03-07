# V24 Test Report

## Verified
- `python -m compileall -q core projects services web scripts`: returncode 0
- `python scripts/studio_e2e_audit.py`: returncode 0
- `python scripts/studio_test_hub.py --mode smoke --project all`: returncode 0
- `python scripts/run_studio_regression.py`: returncode 0
- `python scripts/generate_test_dashboard_data.py`: returncode 0
- `node --check tests/e2e/studio-e2e-matrix.spec.js`: returncode 0
- `node --check tests/e2e/ugc-dashboard.spec.js`: returncode 0
- `node --check tests/e2e/animation-workbench.spec.js`: returncode 0

## Notes
- The regression runner completed in smoke-first mode and wrote `STUDIO_REGRESSION_REPORT_V24.json`.
- The dashboard data file was generated at `static/data/studio_test_dashboard.json`.
- Optional backend dependency gaps may still cause some smoke targets to be marked as skipped inside `UNIFIED_TEST_RUN_REPORT.json`.
