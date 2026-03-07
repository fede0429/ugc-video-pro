
# V22 Upgrade Notes

## 本次目标
- 做 animation 工作台真实浏览器 E2E 修复包
- 把 animation 工作台所有按钮逐个形成可执行联调清单

## 主要改动
- 为 6 个内联 onclick 按钮补充稳定 id，便于 Playwright 选择器定位
- 重写 `tests/e2e/animation-workbench.spec.js`
  - 覆盖规划、预览、任务动作
  - 覆盖 animation 工作台主要按钮
- 新增 `ANIMATION_REAL_BROWSER_CHECKLIST_V22.md`
  - 提供真实浏览器逐按钮联调步骤
- 更新 `tests/e2e/README.md`
