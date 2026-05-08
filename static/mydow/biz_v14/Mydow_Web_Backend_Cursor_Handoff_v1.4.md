# Mydow Web 后端 / Cursor 开发交接说明 v1.4

更新时间：2026-05-06  
交付目标：让后端开发者在 Cursor 中直接打开前端原型、理解页面结构、按稳定 `data-*` 钩子接入真实 API。

## 1. 包内容

| 文件 | 用途 |
|---|---|
| `mydow.html` | 最新单文件前端原型，包含 HTML、CSS、SVG 图标和交互脚本 |
| `Mydow_Web_API_Contract_v1.4.md` | 后端接口契约、数据模型、按钮钩子和联调优先级 |
| `Mydow_Web_Backend_Cursor_Handoff_v1.4.md` | 当前文档，说明 Cursor 接手方式和开发注意事项 |
| `Mydow_Web_Frontend_Handoff.md` | 历史简版交接摘要 |
| `Mydow_Web_前后端交互与按钮接口定义_v1.1.md` | 历史接口定义，保留用于追溯 |
| `Mydow_Web_前端开发交付说明_v1.1.md` | 历史前端交付说明 |
| `Mydow_Web_AI工作台优化说明_v1.3.md` | AI 工作台优化说明 |
| `package-manifest.json` | 文件清单、版本和建议入口 |

## 2. 运行方式

这是静态单文件原型，不依赖构建步骤。

```text
file:///C:/Users/ZZZzzz818/Documents/New%20project/Mydow_Web_Frontend_Complete_Package_v1.4/mydow.html
```

也可以在 Cursor 中用任意静态服务打开：

```bash
npx serve .
```

## 3. 后端接入原则

1. 保留 HTML 中已有的 `data-*` 钩子，不要用中文按钮文案作为唯一事件绑定依据。
2. 原型里的 `simulateAction(...)`、`showToast(...)` 和静态数组是后端接入时替换的主要位置。
3. 后端建议统一返回 JSON envelope：`{ code, message, data, requestId }`。
4. 分页列表统一使用 `{ items, page, pageSize, total, hasMore }`。
5. 详情抽屉和弹窗打开时再请求详情，避免首屏一次性拉取过多数据。
6. AI 对话、深度研究、上传解析建议后端提供任务状态接口；V1 可先轮询，后续升级 SSE/WebSocket。

## 4. 最新 UX / 交互状态

本轮已合入的最新需求：

- 首页默认打开 `灵感采集`，并默认激活 `我的记录`。
- 数字花园右侧 `AI 生成洞察` 模块已收敛到卡片内部，避免内容横向溢出。
- `新建洞察` 和 `洞察历史` 已中文化。
- 全局搜索弹窗中的 `排序 / 搜索范围 / 创建者 / 搜索位置 / 日期` 均已接入下拉菜单。
- 通知中心的分类 Tab、筛选下拉、通知行按钮、右侧快捷操作均有明确交互。
- 通知中心右侧卡片已压缩，适配 16:9 页面范围，减少下滑溢出。
- Skills 首个卡片详情和运行弹窗已同步加载，不再等待异步空白。
- 二级页面左上角已保留返回上一页入口。

## 5. 页面状态类

后端或框架迁移时，可以把这些 class 视为路由状态：

| 状态类 | 页面 |
|---|---|
| 无额外 open class | 灵感采集首页 |
| `.knowledge-open` | 知识库 |
| `.folder-open` | 知识库文件夹详情 |
| `.doc-open` | 文档详情 / 编辑页 |
| `.garden-open` | 数字花园 |
| `.ai-open` | Mydow AI 工作台 |
| `.ai-chat-open` | AI 对话详情 |
| `.skills-open` | Skills 广场 |
| `.notifications-open` | 通知中心 |
| `.profile-open` | 个人中心与设置 |
| `.insights-full-open` | 完整洞察中心 |

## 6. 关键后端接入钩子

| 钩子 | 接入用途 |
|---|---|
| `data-nav-target` | 主导航路由切换 |
| `data-view-target` | 灵感采集：我的记录 / 最近捕捉 |
| `data-view-icon` | 灵感采集：列表 / 网格 |
| `data-inline-menu` | 所有下拉：筛选、模型、日期、搜索范围等 |
| `data-open-modal` | 打开弹窗，确认按钮再请求 API |
| `data-open-drawer` | 打开详情抽屉，按当前对象 id 请求详情 |
| `data-open-folder` | 打开知识库文件夹 |
| `data-create-doc` | 创建文档并进入编辑页 |
| `data-note-option` | 新建洞察弹窗中选择关联笔记 |
| `data-generate-insight` | 生成自定义洞察 |
| `data-notice-filter` | 通知中心分类筛选 |
| `data-notice-action` | 通知行按钮跳转目标 |
| `data-notice-quick` | 通知中心右侧快捷操作 |
| `data-search-trigger` | 全局搜索入口 |

## 7. 建议 Cursor 改造路线

第一阶段：保留静态页面结构，替换数据层。

- 建立 `apiClient.ts`，封装 `get/post/patch/delete/upload`。
- 建立 `types.ts`，按 `Mydow_Web_API_Contract_v1.4.md` 定义类型。
- 将 `simulateAction(...)` 替换为真实请求。
- 先接入 `/me`、`/capture/items`、`/kb/folders`、`/ai/chats`、`/notifications`。

第二阶段：组件化。

- 将 `mydow.html` 拆为 Layout、Sidebar、Topbar、HomeCapture、KnowledgeBase、DigitalGarden、MydowAI、Skills、Notifications、Settings。
- 保留原 `data-*` 作为测试选择器和埋点选择器。
- 将弹窗、抽屉、Toast、下拉菜单抽为共享组件。

第三阶段：实时能力。

- AI 回复流式输出：`POST /ai/messages` + SSE `/ai/messages/:id/stream`。
- 文件上传解析：`POST /capture/upload` + `GET /tasks/:id`。
- 通知中心：WebSocket 或 SSE 推送未读数和任务完成状态。

## 8. 验收清单

后端联调时建议逐项验证：

- 首页首次打开是否是 `灵感采集 / 我的记录`。
- 保存灵感后是否刷新我的记录和最近捕捉。
- 搜索弹窗点击外部和 Esc 是否关闭，5 个筛选项是否能展开。
- 知识库文件夹能否打开、筛选、进入文档。
- 数字花园图谱能否请求节点和边，AI 洞察能否请求当前洞察和历史洞察。
- 新建洞察能否选择 notes、提交 topic、生成后插入当前列表和历史。
- AI 对话能否创建、发送、拉取历史、保存结果到知识库。
- Skills 第一个卡片点击后详情是否立即展示。
- 通知中心分类、筛选、行按钮和快捷操作能否触发真实 API。
- 设置、个人资料、通知偏好能否读写。

## 9. 注意事项

- 当前前端是高保真静态原型，不包含真实鉴权和后端错误处理。
- 所有文案和交互状态已经尽量中文化，英文内容只保留在产品名、模型名或历史示例中。
- 不建议后端直接修改视觉 CSS，除非为了接入真实数据长度做必要的布局保护。
- 新增 API 时请优先补充到 `Mydow_Web_API_Contract_v1.4.md`，避免前后端口径漂移。
