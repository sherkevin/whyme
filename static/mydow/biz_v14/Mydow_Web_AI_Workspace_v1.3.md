# Mydow AI 工作台优化说明 v1.3

更新时间：2026-05-06

## 本次优化范围

本次只优化 `mydow.html` 中的 Mydow AI 工作台，不改变其他一级页面的信息架构。

## 已完成设计点

- 进入 Mydow AI 时默认不展开对话记录侧栏，点击历史按钮后再弹出。
- 每一条历史对话均提供三点菜单，可触发重命名和删除。
- 移除输入框里多余的独立 `@` 小按钮。
- 已产生对话后的页面改为 GPT 式聊天线程，不再用大白色结果卡片承载回答。
- 聊天详情采用轻量 Header、消息列表、底部固定轻量输入框。
- AI 页面改为工作台结构：左侧全局导航栏、对话记录侧栏、右侧主工作画布。
- 点击历史按钮后展开对话记录侧栏；关闭后主画布自动在剩余区域重新居中。
- 初始化状态展示 Mydow Logo 图形、标题“超级个体，超级输出”和核心 AI 输入框。
- 历史对话点击后进入详情状态，保留左侧对话记录高亮，右侧展示面包屑、对话内容和底部固定输入框。
- 顶部模型选择器改为定制模型菜单：Opus 4.6、Gemini 2.5 Flash、GPT-5.2、Mydow Auto。
- 增加“个性化”入口，V1 打开设置弹窗。
- 输入框支持背景信息 chip、`@` 添加上下文、`+` 外部材料菜单、高效/全能模式、语音输入和发送。
- 对话更多菜单改为：重命名、删除、上次更新时间。

## 主要 HTML 钩子

| 钩子 | 用途 |
|---|---|
| `data-ai-history-toggle` | 展开/收起对话记录侧栏 |
| `data-ai-history-pin` | 固定对话记录侧栏 |
| `data-ai-history-close` | 关闭对话记录侧栏 |
| `data-ai-chat-open` | 打开历史对话详情 |
| `data-ai-chat-back` | 从对话详情返回 AI 初始化首页 |
| `data-ai-chat-more` | 打开当前对话更多菜单 |
| `data-inline-menu="aiModel"` | 打开模型选择菜单 |
| `data-inline-menu="aiAdd"` | 打开外部材料添加菜单 |
| `data-ai-mode` | 切换高效 / 全能模式 |
| `data-ai-input` | AI 输入框，支持 `@` 与 Ctrl/Command + Enter |
| `data-remove-context` | 移除上下文 chip |
| `data-open-modal="aiPersonalize"` | 打开个性化设置 |

## 后端接口保持

本次 UI 优化不改变原 v1.1 接口建议。AI 工作台对应接口仍为：

- `GET /api/ai/chats`
- `GET /api/ai/chats/:chatId`
- `POST /api/ai/messages`
- `PATCH /api/ai/chats/:chatId`
- `DELETE /api/ai/chats/:chatId`
- `GET /api/ai/models`
- `PATCH /api/ai/settings/model`
