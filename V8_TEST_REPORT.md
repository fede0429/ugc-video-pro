
# V8 Test Report

## Scope
- Project 1: 多脚本批量生产 + 自动选优
- Project 2: 角色关系图 + 长线剧情记忆库

## Validation completed
- Python `compileall`: passed
- `python scripts/ugc_smoke_tests_v3.py`: passed
- `python scripts/animation_smoke_tests.py`: passed

## Smoke outputs
### UGC
- top_hook_score: 80
- transition_count: 3
- reuse_asset_count: 6

### Animation
- shot_count: 9
- consistency_score: 91
- template_count: 6
- character_state_count: 2
- scene_asset_count: 6
- transition_count: 2
- reuse_asset_count: 5

## Known limits
- Browser E2E click testing not executed in this environment
- Real KIE.AI remote rendering not executed in this environment
- `seedance_2` warning still depends on your KIE account/model status
