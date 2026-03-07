# ANIMATION_V4_TEST_REPORT

## 已执行
- Python compileall：通过
- `scripts/animation_smoke_tests.py`：通过
- `AnimationRenderPipeline._build_plan()`：通过
- `AnimationRenderPipeline.run(..., dry_run=True)`：通过
- 本地参考图资产保存：通过

## smoke test 输出
```json
{
  "ok": true,
  "task_id": "974fc02d3d7b41dea9f9e897cc4ad1bf",
  "shot_count": 9,
  "asset_id": "087c5eb0c4074af084ee600972b407ec",
  "temp_root": "/tmp/animation_smoke_trscdwyt"
}
```

## 本版新增
- 角色参考图上传：`POST /api/animation/reference/upload`
- 角色参考图访问：`GET /api/animation/assets/{asset_id}`
- 单镜头重试：`POST /api/animation/shots/retry`
- 批量集数生成：`POST /api/animation/projects/render-batch`
- 前端角色编辑器 + 文件上传 + 批量按钮 + 镜头重试面板

## 未在当前环境完成
- 真实 KIE.AI 远端调用
- 浏览器端到端点击联调
- 真实 FFmpeg 长链合成
- 真实 shot retry 在线重渲染

## 风险提醒
- `seedance_2` 在当前 `models/kie_video.py` 中仍被标记为 `coming_soon`，实际可用性取决于 KIE.AI 账户侧。
- 参考图目前保存为本地文件路径，并传给后端 KIE adapter；这依赖 `models/kie_video.py` 对本地路径引用的处理。
- 批量任务当前是“一集一个子任务”，不是单任务内多集拼大合集。
- shot retry 依赖原任务已有 plan 和 clip 顺序完整。
