# Animation Studio V3 Test Report

本次为代码级验证，不是浏览器真人点击验收。

## 已执行
1. `compileall` 通过
2. `create_animation_plan()` 直接调用通过
3. `AnimationRenderPipeline.run(..., dry_run=True)` 通过
   - 能生成 `task.json`
   - 能生成 `planning/animation_plan.json`
   - 任务状态能落盘为 completed / dry_run_complete

## 已验证点
- animation 路由能导入
- schema 能解析默认请求
- plan 结构与 render pipeline 一致
- 项目 2 已接入：
  - 任务创建
  - 任务查询
  - artifact 下载路由
  - KIE/Seedance adapter 骨架
  - 前端任务轮询 + WebSocket URL token 兼容

## 未完成的自动化验证
- 浏览器端真实点击
- KIE 真 API 调用（当前环境无 API key）
- FFmpeg 实际拼接渲染（dry_run 模式未执行）
- WebSocket 真连接验收

## 已知限制
- 如果 KIE 侧 `seedance_2` 仍未开放，系统会回退到 `seedance_15`
- 最终成片下载依赖任务完成后 artifact 路由
- 若要做完整 E2E，建议在目标服务器上再跑一轮 smoke test
