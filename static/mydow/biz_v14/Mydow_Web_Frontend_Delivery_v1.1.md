# Mydow Web 前端开发交付说明 v1.1

更新时间：2026-05-05

## 交付物

- `mydow.html`：最新单文件静态前端原型，内含 HTML、CSS、SVG 图标和交互脚本。
- `Mydow_Web_前后端交互与按钮接口定义_v1.1.md`：前后端接口、页面按钮和 HTML `data-*` 钩子对应关系。
- `Mydow_Web_Frontend_Handoff.md`：简版交接摘要。

## 当前完成范围

`mydow.html` 已完成以下 V1 页面与可点击流程：

- 灵感采集首页：文本记录、上传文件、网页剪藏、语音输入、深度研究、记录/最近捕捉切换。
- 我的记录：列表视图、卡片视图、记录详情抽屉、收藏、删除确认、移动到知识库、AI 方案生成。
- 知识库：分类筛选、网格/列表视图、文件夹详情、文档列表、文档详情/编辑页、新建文件夹、新建文档。
- 数字花园：图谱节点、时间/类型筛选、节点详情抽屉、布局和缩放反馈。
- Mydow AI：模型选择、模式选择、添加上下文、历史侧栏、对话详情、发送消息、保存 AI 结果。
- Skills 广场：分类筛选、Skill 详情、收藏、运行弹窗。
- 洞察中心：完整洞察页、洞察详情、历史洞察、自定义洞察规则。
- 通知中心：通知列表、通知设置、标记已读、跳转相关内容。
- 个人中心与设置：个人资料、账户安全、偏好设置、会员与用量、通知偏好。
- 全局能力：全局搜索、命令中心、Toast、弹窗、抽屉、二次删除确认。

## 最新补齐内容

- 补全 Mydow AI 页面未完成的历史侧栏、对话详情、模型菜单、AI 模式菜单和添加内容菜单。
- AI 对话历史现在支持打开、固定、关闭、进入指定对话、返回工作台。
- `data-inline-menu="aiModel" / "aiMode" / "aiAdd" / "aiConversation"` 已和前端菜单逻辑连通。
- 更新前后端按钮接口定义，明确每个主要按钮触发的接口、请求字段、返回结构和前端落点。

## 前端运行方式

这是单文件静态页面，不依赖构建工具。

直接打开：

```text
file:///C:/Users/ZZZzzz818/Documents/New%20project/mydow.html
```

也可以由任意静态服务托管 `mydow.html`。后端联调时，将文档中的 `simulateAction(...)` 和各类 `data-*` 事件替换为真实 API 调用即可。

## 代码结构说明

- `<style>`：所有视觉样式、响应式规则、页面状态类。
- `<body>`：完整页面结构、图标 symbol、弹窗、抽屉。
- `<script>`：页面切换、弹窗抽屉、筛选菜单、Toast 和模拟请求。

主要状态类：

- `.knowledge-open`：知识库首页。
- `.folder-open`：知识库文件夹详情。
- `.doc-open`：文档详情/编辑页。
- `.garden-open`：数字花园。
- `.ai-open`：Mydow AI 工作台。
- `.ai-history-open`：AI 历史侧栏展开。
- `.ai-history-pinned`：AI 历史侧栏固定。
- `.ai-chat-open`：AI 对话详情。
- `.skills-open`：Skills 广场。
- `.notifications-open`：通知中心。
- `.profile-open`：个人中心与设置。
- `.insights-full-open`：完整洞察中心。

## 后端联调建议

前端当前是静态原型，所有模拟提交都集中在 `simulateAction(...)`。联调时建议：

- 保留现有 `data-*` 钩子，不要依赖按钮文本做事件绑定。
- 优先按 `Mydow_Web_前后端交互与按钮接口定义_v1.1.md` 的模块接入接口。
- API 返回统一 JSON envelope，文件上传使用 `multipart/form-data`。
- 首轮联调可先接入：登录态 `/me`、灵感保存、上传、知识库列表、AI 对话、通知列表。

