# V7 Test Report

## Completed checks
- `compileall`: passed
- `python scripts/ugc_smoke_tests_v3.py`: passed
- `python scripts/animation_smoke_tests.py`: passed

## Verified
### Project 1
- 批量变体生成可返回 6 个 hook 变体
- hook 评分已写入 variant payload
- 变体按 `hook_score.total_score` 降序排序

### Project 2
- 规划阶段新增 `scene_state_flow`
- 规划阶段新增 `episode_asset_reuse`
- dry-run 可成功写出：
  - `planning/animation_plan.json`
  - `planning/scene_state_flow.json`
  - `planning/episode_asset_reuse.json`

## Known limits
- 未做真实浏览器端 E2E 点击验收
- 未做真实 KIE.AI 远端渲染验收
- `seedance_2` 真实可用性仍取决于你的 KIE 账号和模型状态
