# Animation Workbench Testing

## API smoke
Runs the animation routes in-process through FastAPI `TestClient`:

```bash
python scripts/animation_api_smoke_v19.py
```

## Frontend E2E
Uses Playwright against `/animation-studio.html`.

### Mock mode (default)
No backend required:

```bash
ANIMATION_E2E_MOCK=1 npx playwright test tests/e2e/animation-workbench.spec.js
```

### Real backend mode
Start the app first, then run:

```bash
ANIMATION_E2E_MOCK=0 ANIMATION_E2E_BASE_URL=http://127.0.0.1:8000 npx playwright test tests/e2e/animation-workbench.spec.js
```


## Unified entry (Project 1 + Project 2)

### Smoke only
```bash
python scripts/studio_test_hub.py --mode smoke --project all
```

### E2E only (mock mode)
```bash
python scripts/studio_test_hub.py --mode e2e --project all --e2e-mock 1
```

### All tests
```bash
python scripts/studio_test_hub.py --mode all --project all --e2e-mock 1
```

### npm shortcuts
```bash
npm run test:studio:smoke
npm run test:studio:e2e:mock
npm run test:studio:all
```



## v22 新增
- `animation-workbench.spec.js` 现在覆盖 animation 工作台所有主要按钮
- `ANIMATION_REAL_BROWSER_CHECKLIST_V22.md` 提供真实浏览器逐按钮联调清单

### 运行 animation 全量按钮 E2E（mock）
```bash
ANIMATION_E2E_MOCK=1 npx playwright test tests/e2e/animation-workbench.spec.js
```

### 运行 animation 全量按钮 E2E（真实后端）
```bash
ANIMATION_E2E_MOCK=0 ANIMATION_E2E_BASE_URL=http://127.0.0.1:8000 npx playwright test tests/e2e/animation-workbench.spec.js
```


## Unified matrix (v23)
- `tests/e2e/studio-e2e-matrix.spec.js`
- Covers project 1 UGC dashboard + project 2 animation workbench in one suite.


## v24 unified regression
Run the full regression bundle:

```bash
python scripts/run_studio_regression.py --with-e2e --e2e-mock 1
```

Generate the dashboard data used by `/static/test-dashboard.html`:

```bash
python scripts/generate_test_dashboard_data.py
```
