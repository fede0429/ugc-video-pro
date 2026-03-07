# V25 UI + Admin Upgrade Notes

## 主要变更
- 优化项目1前端 UI，增加顶部项目切换导航，布局更接近项目2工作台。
- 为项目2补上明显的“返回项目1”按钮和统一导航。
- 新增 `static/admin.html` 管理后台页面。
- 管理后台支持：
  - admin 密码登录后进入
  - 创建子账户（邮箱 + 密码）
  - 停用 / 删除其他子账户
  - 编辑用户角色与启停状态
  - 生成邀请码
- `dashboard.js` 新增当前用户读取与管理员入口显示逻辑。
- 重写 `static/js/admin.js` 以适配新的后台页面。

## 说明
后端原本已有 admin / user 角色、JWT 登录和管理员接口，本次重点是把它前端产品化，让部署后的网页直接可用。

## 访问页面
- `/index.html` 项目1 UGC
- `/animation-studio.html` 项目2 动画剧
- `/admin.html` 管理后台
