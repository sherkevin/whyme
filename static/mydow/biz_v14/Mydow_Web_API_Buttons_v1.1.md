# Mydow Web 前后端交互与按钮接口定义 v1.1

更新时间：2026-05-05

## 1. 通用约定

### 1.1 请求

- Base URL：由后端环境提供，例如 `/api/v1`。
- 鉴权：`Authorization: Bearer <accessToken>`。
- JSON 请求头：`Content-Type: application/json`。
- 文件上传：`multipart/form-data`。
- 时间字段：ISO 8601，例如 `2026-05-05T10:30:00+08:00`。

### 1.2 通用返回

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "requestId": "req_20260505_xxx"
}
```

分页列表：

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 120,
  "hasMore": true
}
```

### 1.3 前端 HTML 钩子

前端原型使用以下 `data-*` 作为后端接入点：

| 钩子 | 用途 | 后端接入说明 |
|---|---|---|
| `data-nav-target` | 主导航切页 | 切页前可按模块拉取首屏数据 |
| `data-view-target` | 我的记录/最近捕捉切换 | 调用记录列表接口，传 `view` |
| `data-inline-menu` | 下拉筛选/模型/模式选择 | 部分纯前端，筛选类需要重新拉取列表 |
| `data-open-modal` | 打开弹窗 | 弹窗确认按钮再触发 API |
| `data-open-drawer` | 打开详情抽屉 | 打开时按 `id` 请求详情 |
| `data-open-folder` | 打开知识库文件夹 | 请求文件夹详情和文档列表 |
| `data-create-doc` | 创建文档并进入编辑页 | `POST /kb/docs` |
| `data-toast` | 当前静态反馈 | 替换为真实 API 成功/失败反馈 |
| `data-settings-panel` | 设置子页切换 | 切换时拉取对应设置数据 |
| `data-account-action` | 账户菜单动作 | 个人资料、账单、偏好、退出登录 |

## 2. 灵感采集首页

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| 发送灵感 | `.capture .send-button` | `POST /capture/items` | `content`, `inputType`, `source`, `tags[]` | `item` | 清空输入框，刷新最近捕捉 |
| 识别方式 | `data-inline-menu="captureMode"` | 无或 `PATCH /settings/preferences` | `defaultCaptureMode` | `preferences` | 更新按钮文案 |
| 上传文件 | `data-open-modal="uploadFile"` | 弹窗打开无请求 | - | - | 打开上传弹窗 |
| 开始上传 | `data-toast="上传任务已创建"` | `POST /capture/upload` | `file`, `folderId?`, `autoExtract=true` | `uploadTask` | 关闭弹窗，展示任务进度 |
| 网页剪藏 | `data-open-modal="webLink"` | 弹窗打开无请求 | - | - | 打开链接输入弹窗 |
| 保存剪藏 | `data-toast="网页已保存到最近捕捉"` | `POST /capture/link` | `url`, `title?`, `folderId?` | `item` | 写入最近捕捉 |
| 语音输入 | `data-open-modal="voiceInput"` | `POST /capture/voice/sessions` | `language`, `device?` | `sessionId` | 打开录音弹窗 |
| 暂停录音 | `data-toast="录音已暂停"` | `PATCH /capture/voice/sessions/:id` | `status="paused"` | `session` | 更新录音状态 |
| 结束并保存 | `data-toast="语音记录已保存"` | `POST /capture/voice/sessions/:id/finish` | `autoTranscribe=true` | `item` | 生成语音记录 |
| 深度研究 | `data-open-modal="deepResearch"` | 弹窗打开无请求 | - | - | 打开研究任务弹窗 |
| 开始研究 | `data-toast="深度研究任务已创建"` | `POST /research/tasks` | `topic`, `scope`, `depth`, `sources[]` | `task` | 进入任务/通知流 |
| 我的记录 Tab | `data-view-target="records"` | `GET /capture/items?view=records` | `page`, `pageSize`, `filter?` | `items` | 切换列表 |
| 最近捕捉 Tab | `data-view-target="recent"` | `GET /capture/items?view=recent` | `page`, `pageSize` | `items` | 切换卡片 |
| 记录类型筛选 | `data-inline-menu="recordFilter"` | `GET /capture/items` | `type`, `view` | `items` | 刷新记录 |
| 打开记录/卡片 | `.record-card`, `.recent-doc-row`, `.idea-card` | `GET /capture/items/:id` | path `id` | `item` | 打开 `itemDetail` 抽屉 |

## 3. 记录详情抽屉

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| 收藏/取消收藏 | `.favorite`, `.save-icon`, `.star-action` | `PATCH /capture/items/:id/favorite` | `favorite` | `item` | 更新收藏状态 |
| 移动到知识库 | `data-toast="已移动到知识库"` | `POST /kb/docs/from-capture` | `itemId`, `folderId` | `doc` | 刷新知识库 |
| 让 AI 生成方案 | `data-open-modal="aiSave"` | `POST /ai/messages` | `itemId`, `prompt`, `contextIds[]` | `message` | 打开保存结果弹窗 |
| 删除 | `data-open-modal="confirmDelete"` | 弹窗打开无请求 | - | - | 二次确认 |
| 确认删除 | `data-toast="已删除，仍可在回收站恢复"` | `DELETE /capture/items/:id` | path `id` | `deleted=true` | 关闭抽屉并刷新列表 |

## 4. 知识库

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| 知识库导航 | `data-nav-target="knowledge"` | `GET /kb/folders` | `category`, `page`, `pageSize` | `folders` | 展示知识库首页 |
| 分类 Tab | `data-kb-tab` | `GET /kb/folders` | `category=all/mine/auto/favorite` | `folders` | 刷新文件夹 |
| 网格/列表视图 | `data-kb-view-target` | 无 | `viewMode` 本地保存 | - | 前端切换 |
| 展开知识库侧栏 | `data-knowledge-sidebar-toggle` | `GET /kb/stats` | - | `stats` | 展示统计侧栏 |
| 新建 | `data-open-modal="newFolder"` | 弹窗打开无请求 | - | - | 打开新建文件夹弹窗 |
| 创建文件夹 | `data-toast="知识库文件夹已创建"` | `POST /kb/folders` | `name`, `description?`, `visibility` | `folder` | 刷新文件夹列表 |
| 打开文件夹 | `data-open-folder` | `GET /kb/folders/:id` + `GET /kb/folders/:id/docs` | path `id`, `filters` | `folder`, `docs` | 进入文件夹页 |
| 文件夹筛选 | `folderType/folderSource/folderTag/folderSort` | `GET /kb/folders/:id/docs` | `type`, `source`, `tag`, `sort` | `docs` | 刷新文档列表 |
| 文件夹视图 | `data-folder-view` | 无 | - | - | 前端列表/网格切换 |
| 更多操作-重命名 | `data-folder-menu` -> 重命名 | `PATCH /kb/folders/:id` | `name` | `folder` | 更新列表 |
| 更多操作-复制 | `data-folder-menu` -> 复制 | `POST /kb/folders/:id/duplicate` | `targetFolderId?` | `folder` | 新增副本 |
| 更多操作-移动 | `data-folder-menu` -> 移动 | `PATCH /kb/folders/:id/move` | `parentId` | `folder` | 刷新树 |
| 更多操作-权限 | `data-folder-menu` -> 设置权限 | `PATCH /kb/folders/:id/permissions` | `visibility`, `members[]` | `permissions` | 更新权限 |
| 更多操作-删除 | `data-open-modal="confirmDelete"` | `DELETE /kb/folders/:id` | path `id` | `deleted=true` | 刷新知识库 |

## 5. 文档详情/编辑页

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| 打开文档 | `.doc-row` | `GET /kb/docs/:id` | path `id` | `doc` | 进入 `doc-open` |
| 返回文件夹 | `data-back-folder` | 无或 `GET /kb/folders/:id/docs` | `folderId` | `docs` | 返回文件夹页 |
| 复制分享链接 | `data-toast="已复制分享链接"` | `POST /kb/docs/:id/share-links` | `permission`, `expiresAt?` | `url` | 写入剪贴板 |
| AI 摘要 | `data-toast="AI 已开始生成摘要"` | `POST /ai/tasks/summarize` | `docId`, `model` | `task` | 通知任务开始 |
| 工具栏加粗/斜体/列表/链接 | toolbar button | `PATCH /kb/docs/:id` | `content`, `ops[]` | `doc` | 保存编辑结果 |
| 新建文档弹窗 | `data-open-modal="newDocument"` | 弹窗打开无请求 | - | - | 打开弹窗 |
| 创建并打开 | `data-create-doc` | `POST /kb/docs` | `folderId`, `title`, `content?`, `template?` | `doc` | 进入编辑页 |

## 6. 数字花园

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| 数字花园导航 | `data-nav-target="garden"` | `GET /garden/graph` | `range`, `type`, `depth` | `nodes`, `edges` | 展示图谱 |
| 时间范围 | `data-inline-menu="gardenTime"` | `GET /garden/graph` | `range` | `nodes`, `edges` | 刷新图谱 |
| 节点类型 | `data-inline-menu="gardenType"` | `GET /garden/graph` | `type` | `nodes`, `edges` | 刷新图谱 |
| 打开节点 | `data-open-drawer="nodeDetail"` / `.garden-node` | `GET /garden/nodes/:id` | path `id` | `node` | 打开节点抽屉 |
| 切换布局 | `data-toast="已切换图谱布局"` | 无或 `PATCH /settings/preferences` | `gardenLayout` | `preferences` | 前端布局切换 |
| 缩放 | `图谱已缩小/放大` | 无 | - | - | 前端缩放 |

## 7. Mydow AI

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| AI 导航 | `data-nav-target="ai"` | `GET /ai/chats?limit=20` | `limit` | `chats` | 展示 AI 工作台 |
| 模型选择 | `data-inline-menu="aiModel"` | `GET /ai/models` / `PATCH /ai/chats/:id` | `model` | `chat` | 更新当前模型 |
| 打开历史 | `data-ai-history-toggle` | `GET /ai/chats` | `page`, `pageSize`, `keyword?` | `chats` | 展开历史侧栏 |
| 固定历史侧栏 | `data-ai-history-pin` | 无或 `PATCH /settings/preferences` | `aiHistoryPinned` | `preferences` | 固定侧栏 |
| 关闭历史侧栏 | `data-ai-history-close` | 无 | - | - | 收起侧栏 |
| 搜索历史 | `.ai-history-search input` | `GET /ai/chats` | `keyword` | `chats` | 过滤历史 |
| 打开对话 | `data-ai-chat-open` | `GET /ai/chats/:id/messages` | path `id` | `chat`, `messages` | 进入对话详情 |
| 返回 AI 工作台 | `data-ai-chat-back` | 无 | - | - | 退出对话详情 |
| 对话更多操作 | `data-ai-thread-menu` / `data-folder-menu` | 见知识库更多操作模式 | `chatId` | - | 重命名/复制/移动/删除 |
| 添加背景信息 | `data-open-modal="aiContext"` | `POST /ai/context/search` | `query`, `types[]`, `limit` | `contextItems` | 打开上下文选择 |
| 添加上下文 | `data-toast="上下文已添加到 AI 对话"` | `POST /ai/chats/:id/context` | `contextIds[]` | `context` | 添加到当前对话 |
| 新页面 | `data-open-modal="newDocument"` | `POST /kb/docs` | `title`, `folderId?` | `doc` | 创建文档 |
| 添加内容菜单 | `data-inline-menu="aiAdd"` | 按选择触发上传/网页/知识库/语音接口 | `type` | - | 打开对应弹窗 |
| AI 模式菜单 | `data-inline-menu="aiMode"` | `PATCH /ai/chats/:id` | `mode` | `chat` | 更新模式；深度研究打开研究弹窗 |
| 语音输入 | `data-open-modal="voiceInput"` | 见灵感采集语音接口 | - | - | 打开录音 |
| 提交 AI 消息 | `.ai-composer .send-button` | `POST /ai/messages` | `chatId?`, `content`, `model`, `mode`, `contextIds[]` | `message`, `assistantMessage` | 渲染 AI 回复 |
| 新建对话 | `data-toast="已新建对话"` | `POST /ai/chats` | `title?`, `model`, `mode` | `chat` | 新建并打开 |
| 复制回答 | `data-toast="已复制回答"` | 无 | - | - | 复制到剪贴板 |
| 添加后续问题 | `data-toast="已添加后续问题"` | `POST /ai/messages` | `parentMessageId`, `content` | `message` | 添加追问 |
| 点赞/反馈 | `data-toast="感谢反馈"` / `data-toast="已记录反馈"` | `POST /ai/messages/:id/feedback` | `rating`, `comment?` | `feedback` | 更新反馈 |
| 保存 AI 结果 | `data-open-modal="aiSave"` / 保存按钮 | `POST /kb/docs/from-ai` | `messageId`, `folderId`, `title`, `tags[]` | `doc` | 保存到知识库 |

## 8. Skills 广场

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| Skills 导航 | `data-nav-target="skills"` | `GET /skills` | `category`, `keyword`, `page` | `skills` | 展示广场 |
| 分类 Chip | `.skill-chip` | `GET /skills` | `category` | `skills` | 刷新卡片 |
| Skill 卡片 | `.skill-card` | `GET /skills/:id` | path `id` | `skill` | 打开详情抽屉 |
| 试用/立即试用 | `data-open-modal="skillRun"` | 弹窗打开无请求 | - | - | 打开运行弹窗 |
| 运行 Skill | `data-toast="Skill 正在运行"` | `POST /skills/:id/run` | `inputs`, `contextIds[]` | `run` | 进入运行状态 |
| 收藏 Skill | `data-toast="已收藏 Skill"` | `PATCH /skills/:id/favorite` | `favorite` | `skill` | 更新收藏 |

## 9. 洞察中心

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| 展开完整洞察 | `data-insights-full` | `GET /insights/dashboard` | `range` | `metrics`, `reports` | 进入完整洞察页 |
| 洞察卡片 | `data-open-drawer="insightDetail"` / `.insight-card` | `GET /insights/:id` | path `id` | `insight` | 打开详情 |
| 重新生成摘要 | `data-toast="摘要已重新生成"` | `POST /insights/:id/regenerate` | `mode` | `task` | 刷新摘要 |
| 提取推荐标签 | `data-toast="已提取推荐标签"` | `POST /ai/tasks/extract-tags` | `sourceId`, `sourceType` | `tags[]` | 更新标签 |
| 生成知识卡片 | `data-toast="已生成知识卡片"` | `POST /kb/docs/from-insight` | `insightId`, `folderId` | `doc` | 写入知识库 |
| 关联数字花园 | `data-toast="已关联数字花园"` | `POST /garden/links` | `sourceId`, `targetIds[]` | `edges` | 更新图谱 |
| 历史洞察 | `data-open-modal="insightHistory"` | `GET /insights/history` | `page`, `pageSize` | `items` | 打开历史弹窗 |
| 新建洞察/保存规则 | `data-open-modal="customInsight"` / 保存规则 | `POST /insights/rules` | `name`, `query`, `frequency`, `targets[]` | `rule` | 创建规则 |
| 保存到知识库 | `data-toast="洞察已保存到知识库"` | `POST /kb/docs/from-insight` | `insightId`, `folderId` | `doc` | 保存成功 |
| 生成研究报告 | `data-open-modal="aiSave"` | `POST /research/tasks` | `insightId`, `reportType` | `task` | 生成报告 |

## 10. 通知中心

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| 顶部通知按钮 | `data-open-notifications` | `GET /notifications` | `page`, `pageSize`, `type?`, `unread?` | `notifications` | 进入通知中心 |
| 通知分类 Tab | 通知中心顶部按钮 | `GET /notifications` | `type`, `unread` | `notifications` | 刷新列表 |
| 标记全部已读 | `data-toast="已全部标记为已读"` | `POST /notifications/read-all` | `type?` | `updatedCount` | 更新未读数 |
| 通知设置 | `data-open-modal="notificationSettings"` | `GET /settings/notifications` | - | `settings` | 打开设置弹窗 |
| 保存通知设置 | `data-toast="通知设置已保存"` | `PATCH /settings/notifications` | `channels`, `types`, `quietHours` | `settings` | 保存设置 |
| 通知行点击 | `.notice-row` | `PATCH /notifications/:id/read` + 业务详情接口 | path `id` | `notification` | 打开相关详情 |
| 去整理/生成 | `notice-action` | 按通知 `targetType` 调用对应接口 | `targetId` | - | 跳转或打开弹窗 |

## 11. 个人中心与设置

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| 头像/账户入口 | `data-open-profile`, `data-top-profile` | `GET /me` | - | `user` | 打开菜单或设置页 |
| 个人资料 | `data-settings-panel="profile"` | `GET /me` | - | `user` | 展示资料 |
| 编辑资料 | `data-open-modal="editProfile"` | 弹窗打开无请求 | - | - | 打开编辑弹窗 |
| 保存资料 | `data-toast="个人资料已保存"` | `PATCH /me` | `name`, `avatarUrl?`, `bio?` | `user` | 更新资料 |
| 账户安全 | `data-settings-panel="security"` | `GET /settings/security` | - | `security` | 展示安全项 |
| 验证邮箱 | `data-toast="邮箱验证链接已发送"` | `POST /auth/email-verification` | `email` | `sent=true` | 提示发送 |
| 修改密码 | `data-toast="修改密码入口已打开"` | `POST /auth/password/reset-link` 或打开表单 | `email` | `sent=true` | 打开修改流程 |
| 二步验证 | `data-toast="二步验证状态已更新"` | `PATCH /settings/security/2fa` | `enabled` | `security` | 更新状态 |
| 偏好设置 | `data-settings-panel="preferences"` | `GET /settings/preferences` | - | `preferences` | 展示偏好 |
| 自动保存开关 | `data-toast="自动保存设置已更新"` | `PATCH /settings/preferences` | `autoSave` | `preferences` | 更新开关 |
| 会员与用量 | `data-settings-panel="billing"` | `GET /billing/summary` | - | `plan`, `usage`, `invoices` | 展示用量 |
| 管理订阅 | `data-toast="订阅管理已打开"` | `POST /billing/portal-session` | `returnUrl` | `url` | 跳转订阅后台 |
| 存储详情 | `data-toast="存储详情已刷新"` | `GET /billing/storage` | - | `storage` | 刷新用量 |
| 退出登录 | `data-account-action="logout"` | `POST /auth/logout` | `refreshToken?` | `success=true` | 清理本地登录态 |

## 12. 全局搜索/命令中心

| 按钮/区域 | HTML 钩子 | 接口 | 请求字段 | 成功返回 | 前端行为 |
|---|---|---|---|---|---|
| 搜索框 / `⌘K` | `data-search-trigger` | `GET /search` | `q`, `scope`, `limit` | `items` | 打开搜索弹窗并展示结果 |
| 搜索结果 | `.result-row` | 按 `result.type` 调用详情接口 | `id`, `type` | detail | 打开详情抽屉或页面 |
| 搜索筛选 | `.search-filters button` | `GET /search` | `q`, `scope` | `items` | 刷新结果 |

## 13. 后端优先级建议

第一批建议优先接入：

1. `GET /me`
2. `POST /capture/items`
3. `POST /capture/upload`
4. `GET /capture/items`
5. `GET /kb/folders`
6. `GET /kb/folders/:id/docs`
7. `POST /kb/docs`
8. `GET /ai/chats`
9. `POST /ai/messages`
10. `GET /notifications`

第二批接入：

1. 数字花园图谱和节点详情。
2. 洞察中心与自定义洞察规则。
3. Skills 广场、Skill 运行。
4. 账单、用量、账户安全。

