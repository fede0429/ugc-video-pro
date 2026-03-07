
# V22 Animation 工作台真实浏览器联调清单

## 目标
用真实浏览器逐个检查 animation 工作台所有按钮和主要交互，确认：
- 前端按钮存在
- 点击后不会报错
- 能命中正确 API
- 能把结果写进正确预览区
- 任务类动作能更新任务状态区

## 运行前准备
1. 启动后端服务。
2. 打开浏览器开发者工具，保留 Network / Console。
3. 登录后确认本地已有 token。
4. 打开 `/animation-studio.html`。
5. 先填基础数据：
   - 标题
   - premise
   - episode-goal
   - batch-goals

## A. 基础规划与一致性
1. 先生成规划
   - 按钮：`#plan-btn`
   - 预期：`#plan-preview` 有 JSON，`#form-status` 显示成功

2. 一致性检查
   - 按钮：`#check-consistency-btn`
   - 预期：`#consistency-preview` 有 score 和 continuity_report

3. 查看分镜模板库
   - 按钮：`#load-templates-btn`
   - 预期：`#template-preview` 有 templates

## B. 角色 / 场景 / 关系层
4. 角色情绪弧线器
   - 按钮：`#btn-emotion-arcs`
   - 预期：`#emotion-arcs-preview` 非空

5. 爆点台词生成器
   - 按钮：`#btn-punchlines`
   - 预期：`#punchline-preview` 非空

6. 角色状态机
   - 按钮：`#btn-load-state-machine`
   - 预期：`#state-box` 非空

7. 场景资产库
   - 按钮：`#btn-load-scene-assets`
   - 预期：`#asset-box` 非空

8. 场景流
   - 按钮：`#btn-load-scene-flow`
   - 预期：`#scene-flow-output` 非空

9. 关系图
   - 按钮：`#btn-load-relationship-graph`
   - 预期：`#relationship-preview` 非空

10. 角色对白风格器
   - 按钮：`#btn-dialogue-style`
   - 预期：`#dialogue-style-preview` 非空

11. 季级剧情冲突树
   - 按钮：`#btn-season-conflict`
   - 预期：`#season-conflict-preview` 非空

12. 剧情大纲编辑器
   - 按钮：`#btn-outline`
   - 预期：`#outline-preview` 非空

13. 查看季度级记忆库
   - 按钮：`#btn-season-memory`
   - 预期：`#season-memory-preview` 非空

## C. 节奏 / 高潮 / 爆点 / 悬念
14. 场景反转检测器
   - 按钮：`#btn-scene-twists`
   - 预期：`#scene-twists-preview` 非空

15. 爆点镜头编排器
   - 按钮：`#btn-highlight-shots`
   - 预期：`#highlight-shots-preview` 非空

16. 分场节奏控制
   - 按钮：`#btn-scene-pacing`
   - 预期：`#pacing-preview` 非空

17. 高潮点编排
   - 按钮：`#btn-climax-plan`
   - 预期：`#climax-preview` 非空

18. 镜头情绪滤镜器
   - 按钮：`#btn-shot-emotion-filters`
   - 预期：`#shot-emotion-filters-preview` 非空

19. 反转前埋点器
   - 按钮：`#btn-foreshadow-plan`
   - 预期：`#foreshadow-preview` 非空

20. 线索回收追踪器
   - 按钮：`#btn-payoff-tracker`
   - 预期：`#payoff-tracker-preview` 非空

21. 悬念保持器
   - 按钮：`#btn-suspense-keeper`
   - 预期：`#suspense-keeper-preview` 非空

22. 回收强度评分器
   - 按钮：`#btn-payoff-strength`
   - 预期：`#payoff-strength-preview` 非空

23. 季级悬念链
   - 按钮：`#season-suspense-chain-btn`
   - 预期：`#season-suspense-chain-preview` 非空

24. 终局回收规划器
   - 按钮：`#finale-payoff-plan-btn`
   - 预期：`#finale-payoff-plan-preview` 非空

25. 季终预告生成器
   - 按钮：`#season-trailer-generator-btn`
   - 预期：`#season-trailer-generator-preview` 非空

26. 下季钩子规划器
   - 按钮：`#next-season-hook-planner-btn`
   - 预期：`#next-season-hook-planner-preview` 非空

27. 预告片剪辑器
   - 按钮：`#trailer-editor-btn`
   - 预期：`#trailer-editor-preview` 非空

28. 下季首集冷开场
   - 按钮：`#next-episode-cold-open-btn`
   - 预期：`#next-episode-cold-open-preview` 非空

## D. 任务动作
29. 直接开始生产
   - 按钮：`#render-btn`
   - 预期：
     - `#task-status` 更新
     - `#task-id` 写入 task id
     - `#task-links` 有 artifact 链接

30. 批量生产多集
   - 按钮：`#batch-render-btn`
   - 预期：
     - `#task-status` 出现 batch id 或多个 task id
     - `#batch-assets-output` 后续可配合 batch 资产接口查看

31. 刷新最近任务
   - 按钮：`#refresh-btn`
   - 预期：`#task-list` 更新

32. 重试单镜头
   - 输入：
     - `#retry-task-id`
     - `#retry-shot-id`
   - 按钮：`#retry-shot-btn`
   - 预期：`#task-status` 更新，Network 中命中 `/api/animation/shots/retry`

## E. Console / Network 通过标准
- Console 中不应有未捕获异常
- 所有按钮点击后不应出现 `null.textContent`、`undefined` 相关错误
- Network 返回码应为 2xx
- 如果接口失败，页面也应有失败文案，不应整页卡死

## 推荐执行顺序
1. A 类
2. B 类
3. C 类
4. D 类
5. 最后导出 Network HAR 和 Console 日志
