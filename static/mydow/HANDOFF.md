# Mydow Web Frontend Handoff

## Deliverables

- `mydow.html`: single-file static frontend prototype.
- `Mydow_Web_前端实现PRD_v1.0.md`: frontend implementation PRD.
- `Mydow_Web_前后端交互与按钮接口绑定PRD_v1.0.md`: API and button binding PRD.

## Current Scope

The HTML implements a complete clickable V1 prototype for:

- 灵感采集首页
- 我的记录列表
- 最近捕捉卡片
- 内容详情抽屉
- 知识库首页
- 知识库文件夹详情
- 文档详情 / 编辑页
- 数字花园
- 节点详情抽屉
- Mydow AI 工作台
- AI 上下文选择弹窗
- AI 结果保存弹窗
- Skills 广场
- Skill 详情抽屉
- Skill 运行弹窗
- 洞察中心
- 洞察详情抽屉
- 通知中心
- 通知设置弹窗
- 个人中心与设置
- 账户安全 / 偏好设置 / 会员与用量切换
- 全局搜索 / 命令中心
- 上传文件、网页剪藏、语音输入、深度研究、新建文件夹、新建文档、删除确认、Toast

## Frontend Interaction Binding

The prototype uses data attributes as backend integration hooks:

- `data-nav-target`: route-like page switching.
- `data-open-modal`: opens a modal.
- `data-open-drawer`: opens a drawer.
- `data-toast`: simulates an API success response.
- `data-create-doc`: simulates `POST /kb/docs`, then opens the editor.
- `data-settings-panel`: switches settings subpages.
- `data-account-action`: account menu actions.

## Suggested Backend Replacement Points

Replace `simulateAction(...)` with real API calls:

- `POST /capture/items`
- `POST /capture/upload`
- `POST /capture/link`
- `GET /capture/items/:id`
- `PATCH /capture/items/:id/favorite`
- `GET /kb/folders`
- `POST /kb/folders`
- `GET /kb/folders/:id/docs`
- `POST /kb/docs`
- `PATCH /kb/docs/:id`
- `GET /garden/graph`
- `GET /garden/nodes/:id`
- `GET /ai/chats`
- `POST /ai/chats`
- `POST /ai/messages`
- `POST /ai/context/search`
- `POST /kb/docs/from-ai`
- `GET /skills`
- `GET /skills/:id`
- `POST /skills/:id/run`
- `GET /insights`
- `GET /insights/:id`
- `GET /notifications`
- `PATCH /notifications/:id/read`
- `POST /notifications/read-all`
- `PATCH /settings/preferences`
- `PATCH /me`

## Notes

- Default page is still 灵感采集.
- Other pages are not removed or hidden from the codebase; they are switched by page state classes.
- The current prototype is intentionally static and API-free, but all major user-facing buttons now have visible feedback or open the expected page, modal, or drawer.
