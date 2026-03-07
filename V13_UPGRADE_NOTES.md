# V13_UPGRADE_NOTES

## 项目1
- 新增平台凭证中心 `core/platform_credential_center.py`
- 发布队列支持 `scheduled_at`
- 新增平台凭证 API
- 新增到期队列查询与重排发布时间 API

## 项目2
- 新增场景反转检测器 `projects/animation/scene_twist_detector.py`
- 新增爆点镜头编排器 `projects/animation/highlight_shot_orchestrator.py`
- planning 产物新增：
  - scene_twists.json
  - highlight_shots.json
- 动画工作台新增两块预览：
  - 场景反转检测
  - 爆点镜头编排
