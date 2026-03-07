# V7 Upgrade Notes

## 项目1
- 新增 hook 评分引擎 `core/hook_score_engine.py`
- `core/variant_generator.py` 支持批量变体生成与按 hook_score 排序
- `core/director_agent.py` 默认生成 6 个变体并把 hook_score 写入 plan
- `web/tasks.py` 在时间线生成后写入 `creative_score`，完成后把 `video_score` 写入 `qa_report_json`

## 项目2
- 新增 `projects/animation/scene_state_flow.py`
- 新增 `projects/animation/episode_asset_reuse.py`
- `_build_plan()` 新增 `scene_state_flow` 与 `episode_asset_reuse`
- 批量渲染时会透传 `batch_parent_id`、`episode_index` 与 `reuse_assets_across_episodes`
- 规划与成片任务都会生成并缓存 episode 资产复用信息
- 新增接口：
  - `GET /api/animation/scene-flow`
  - `GET /api/animation/batch-assets/{batch_task_id}`

## 修复
- 动画 artifact 路由支持绝对/相对路径
