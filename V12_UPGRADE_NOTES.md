# V12 Upgrade Notes

## 项目1
- 新增平台资源中心 `core/platform_resource_center.py`
- 新增发布失败重试器 `core/publish_retry_engine.py`
- 新增接口：
  - `GET /api/video/platform-resources`
  - `POST /api/video/platform-resources`
  - `GET /api/video/publish-queue/{queue_id}`
  - `POST /api/video/publish-queue/{queue_id}/retry`
- `publish-queue` 入队时会写入 `platform_resource_bundle`

## 项目2
- 新增角色情绪弧线器 `projects/animation/character_emotion_arc_engine.py`
- 新增爆点台词生成器 `projects/animation/punchline_dialogue_generator.py`
- 新增接口：
  - `GET /api/animation/emotion-arcs`
  - `GET /api/animation/punchline-dialogue`
- 动画规划产物新增：
  - `planning/emotion_arcs.json`
  - `planning/punchline_dialogue.json`
