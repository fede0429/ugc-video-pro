# PROJECT 2 — Animation Studio Starter

这版已经不再只是规划页，而是可生产骨架。

## 已完成能力
- 世界观 / 角色 / 分场 / 分镜规划
- KIE.AI 路由的 Seedance adapter（优先 seedance_2，fallback seedance_15）
- 镜头级后台任务
- 任务状态查询
- WebSocket 进度推送
- 前端生产工作台 `/animation-studio.html`
- 镜头渲染后自动拼接、生成字幕、可选 TTS 对白

## 当前调用链
`/api/animation/projects/render`
→ AnimationRenderPipeline
→ KieSeedanceAnimationAdapter
→ KIE.AI video generation
→ ffmpeg concat
→ optional TTS
→ subtitle burn
→ final video

## 说明
- 为避免改动现有数据库枚举，这版 animation task 采用文件任务存储：
  `web.video_dir/animation_tasks/<task_id>/task.json`
- 这样不会影响现有项目 1。
- 当 seedance_2 在 KIE 开通后，可直接切换使用。
- 当前默认仍可 fallback 到 seedance_15。

## 重点文件
- `web/routes_animation.py`
- `web/schemas_animation.py`
- `projects/animation/render_pipeline.py`
- `projects/animation/kie_seedance_adapter.py`
- `projects/animation/task_store.py`
- `static/animation-studio.html`
- `static/js/animation-dashboard.js`
