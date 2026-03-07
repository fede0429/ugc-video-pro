
# V10 UPGRADE NOTES

## 项目1
- 新增平台发布适配器 `core/platform_publish_adapter.py`
- 新增发布队列 `core/publish_queue.py`
- UGC 任务完成后自动生成 `platform_publish_payload`
- UGC 任务完成后自动写入本地 publish queue
- 新增接口：
  - `GET /api/video/publish-queue`
  - `GET /api/video/tasks/{task_id}/publish-package`
  - `POST /api/video/tasks/{task_id}/publish-queue`

## 项目2
- 新增角色对白风格器 `projects/animation/dialogue_style_engine.py`
- 新增季级剧情冲突树 `projects/animation/season_conflict_tree.py`
- 渲染规划新增：
  - `dialogue_styles`
  - `season_conflict_tree`
- 新增接口：
  - `GET /api/animation/dialogue-styles`
  - `GET /api/animation/season-conflict/{season_id}`

## 前端
- 修复 animation-dashboard.js 中的 async 语法错误
- 修复 artifact 下载 key 不匹配
- 动画工作台新增对白风格器 / 季级冲突树预览面板

## 验证
- compileall 通过
- `python scripts/ugc_smoke_tests_v5.py` 通过
- `python scripts/animation_smoke_tests_v3.py` 通过
