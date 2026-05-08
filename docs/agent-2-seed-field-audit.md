# Seed-vs-PRD10 §5 字段差距审计

> **作者**：Agent 4
> **目的**：让工程师 2 在写 SPA 渲染器时知道哪些字段在 demo 数据中**真有值**、哪些**永远空**——从而决定每个 panel 是渲染还是空态。
> **复现**：`scripts/seed_prd10.py --email demo@mydow.example --password demo123 --reset` 后 `python .tmp/seed_audit.py`。
> **原始报告**：`.tmp/seed_audit_report.txt`。

---

## 0. 总览

| 表 | 行数 | 字段缺口（待 P1 改 seed 或后端 worker 自动填） |
|---|---:|---|
| User | 1 | — |
| Folder (`kb_folders`) | 6 | `parent_id` 全 null（V1 只有根目录） |
| Document (`kb_documents`) | 20 | `source_id` null；`chunk_count` / `last_opened_at` 模型上没字段 |
| Card (`cards`) | 30 | `cover_url` / `source_id` / `inbox_item_id` 全 null |
| PRD10Task (`prd10_tasks`) | 5 | 真实 PRD10 §5.9 任务；`workspace_id` 可空，`extra.folder_id` 记录演示关联文件夹 |
| AIConversation | 3 | `context_scope` 空 dict（seed 默认不绑文件夹） |
| AIMessage | 18 | `citations` / `tool_calls` / `attachments` 空数组；`model` / `input_tokens` / `output_tokens` / `latency_ms` 全 null（seed 不调真模型） |
| Skill | 5 | — |
| Notification | 5 | 部分行 `object_type`/`object_id` null（system 类） |
| SearchIndex | 10 | `tags` 空数组；`embedding_id` / `embedding` 已写入 `hash64-v1` deterministic embedding |

---

## 1. 字段值分布（关键）

### User
```
id        : UUID
email     : 'demo@mydow.example'
username  : 'demo'
full_name : 'Demo User'
settings  : {seed}
```

### Folder（PRD10 §5.6）
```
id          : UUID
name        : '产品设计'                 ← 有 6 个真名
description : '产品设计 相关的 PRD10 演示资料 [seed]'
parent_id   : <null>                    ← V1 只有根目录
color       : 'blue'                    ← 6 种色（blue/violet/emerald/amber/rose/slate）
icon        : 'icon-product'
is_favorite : False                     ← 约 40% 概率为 True（rng.random()<0.4）
sort_order  : 0,10,20,30,40,50
```
**SPA 启示**：`parent_id` 不展示子目录树是 OK 的；`is_favorite` 在「我的收藏」侧栏可显示。

### Document（PRD10 §5.7）
```
id              : UUID
title           : 'Mydow 首页信息架构概览'   ← 20 篇真标题
summary         : 'XXX 的精炼摘要——演示用。'
content         : '# 标题\n\n这是 PRD10 演示文档的正文...'
document_type   : 'note' / 'markdown' / 'pdf' / 'link' / 'text'
status          : 'ready'
folder_id       : UUID（随机分配到 6 个文件夹之一）
source_id       : <null>                ← seed 不创建 Source
tags            : ['seed', '示例', folder.name]
word_count      : 300-4200 随机
chunk_count     : <no-attr>             ← 模型上字段不存在，PRD10 §5.7.chunk_count 实际未实现
is_favorite     : False                 ← 约 25%
last_opened_at  : <no-attr>             ← 模型上字段不存在
```
**SPA 启示**：渲染文档详情时不要尝试读 `chunk_count`/`last_opened_at`，会报 `undefined`。改为前端自己计算或显示「—」。

### Card（PRD10 §5.5）
```
id            : UUID
title         : '灵感卡片 #N'           ← 30 张
summary       : 10 句业务示例之一
content       : 'title\n\nsummary\n\n（PRD10 演示数据）'
cover_url     : <null>                  ← seed 不下封面图
content_type  : 'note' / 'article' / 'ai_output'
source_id     : <null>
inbox_item_id : <null>
folder_id     : UUID（随机）
tags          : ['seed', '示例', folder.name]
entities      : ['Mydow', 'PRD10', folder.first_doc.title]
is_favorite   : False                   ← 约 30%
is_archived   : False
visibility    : 'private'
```
**SPA 启示**：feed 卡片若设计了 `cover_url` 占位需要 fallback 到 `entities[0]` 或一个色块。

### PRD10Task（PRD10 §5.9）
```
title       : 5 条业务任务标题
description : '任务: TITLE (演示数据)'
status      : 'todo' / 'doing'
priority    : 'medium' / 'high' / 'urgent'
due_at      : 未来 1-5 天
source_type : 'manual' / 'ai' / 'inbox' / 'document' / 'insight'
source_id   : 关联 folder id 或 null
tags        : ['seed', '任务']
extra       : {seed, folder_id}
```
**SPA 启示**：`/today.tasks` 现在由 `prd10_tasks` 驱动；创建、更新、完成任务直接走 `/api/v1/tasks`、`PATCH /api/v1/tasks/{id}`、`POST /api/v1/tasks/{id}/complete`，不再把任务伪装成 `Prd10InboxItem(type=manual_task)`。

### AIConversation / AIMessage（PRD10 §5.11/5.12）
```
Conversation:
  title                : 3 个真标题
  mode                 : 'general'
  last_message_preview : 5 条业务示例之一
  message_count        : 6
  context_scope        : <empty>            ← seed 不绑 folder
  extra                : {marker, seed}

Message:
  role                 : 'user' 或 'assistant'
  content              : 5 条业务问/答之一
  status               : 'completed'
  citations            : <empty>            ← seed 不带引用
  tool_calls           : <empty>            ← seed 不带 tool 调用
  attachments          : <empty>
  model                : <null>             ← seed 不调真模型
  input_tokens         : <null>
  output_tokens        : <null>
  latency_ms           : <null>
  parent_message_id    : <null>             ← user msg 的 parent；seed 没串
```
**SPA 启示**：渲染 AI 会话时 **绝对不要** 假设 `citations` 非空——seed 数据全空。要触发真引用必须用真 LLM (`AGENTOS_AI_LLM=on`) 并经过 `context_scope.folder_ids`。

### Skill（PRD10 §5.13）
```
id              : UUID
name            : '访谈洞察提炼' / '周报生成器' / ...（5 个）
category        : 'interview' / 'report' / 'research' / 'format' / 'ideate'
icon            : 'icon-bulb' / ...
status          : 'published'
usage_count     : 0-10 随机
input_schema    : {type: 'object'}
output_schema   : {type: 'object'}
```
**SPA 启示**：Skill 卡片可直接渲染 name/description/icon/usage_count。

### Notification（PRD10 §5.16）
```
type        : 'system' / 'job_completed' / 'document_ready' / 'insight_generated' / 'ai_output_saved'
title       : 5 条业务示例
content     : 'TITLE (演示数据 [seed])'
object_type : 'document' (3 条) / null (2 条 system 类)
object_id   : 对应文档 UUID
is_read     : False                 ← seed 全未读
```
**SPA 启示**：`object_type=document` 的通知点击跳到 `#/kb/doc/:object_id`；`type=system` 的不跳转。

### SearchIndex（PRD10 §5.14）
```
item_type    : 'document' (5 条) / 'card' (5 条)
item_id      : 对应行
title/summary/content : 直接复制源行
tags         : <empty>              ← seed 没填
embedding_id : hash64-v1:<sha256>   ← B-13 已接入 deterministic embedding
embedding    : 64 维 float 数组      ← semantic / hybrid 排序可直接使用
```
**SPA 启示**：搜索高亮可用，`mode=keyword|semantic|hybrid` 都可启用；「按标签筛选」对 seed 数据仍无效，显示「全部结果」即可。

---

## 2. 给工程师 2 SPA 渲染时的 fallback 建议

| 字段 | 空时 fallback |
|---|---|
| `Card.cover_url` | 按 `tags[0]` 颜色渲染色块；或 `entities[0]` 文字封面 |
| `Card.source_id` / `inbox_item_id` | 不显示来源 chip（避免空 chip） |
| `Document.source_id` | 来源行隐藏；显示 `document_type` icon |
| `Document.chunks_preview` (来自 `/kb/documents/:id`) | 后端会拿；前端没拿到时显示 `summary + content[0..200]` |
| `AIMessage.citations` 空 | 隐藏「引用」抽屉；不要画占位 |
| `AIMessage.model/tokens` 空 | 隐藏开发者元数据栏；只在 settings 里显示真 LLM 时才出现 |
| `AIConversation.context_scope` 空 | 「全局上下文」标签 |
| `Notification.object_type` null | 不挂 onclick；只显示文字 |
| `SearchIndex.tags` 空数组 | 不展示 tag chip filter；保留 object_type / mode 筛选 |

---

## 3. 改 seed 的优先级（给 Agent 3 / Agent 1 决策）

**P0**（V1 demo 体验直接受影响）：
- 给 `AIConversation` 注入一个绑定文件夹的 `context_scope`，使前端的「上下文 chip」有真实数据可显示。
- 给若干 `AIMessage(role=assistant)` 写一条 `citations[]` 引用 `Document` 行，让 AI 引用 UI 有真数据。
- `Notification.object_type='document'` 行扩到至少 3 条，确保 SPA 通知跳转有覆盖率。

**P1**（体验更好）：
- 给 5 张 `Card` 加 `cover_url`（指向静态资源）。
- `Card.source_id` 至少 5 条不为 null（关联到 5 条 `prd10_sources`）。
- `SearchIndex.tags` 从对应 Card/Document 复制过来。

**P2**（V1 不阻塞，但留待 B-13）：
- `AIMessage.model/tokens` 由真 LLM provider 自动填。

---

## 4. 不要做的事

- **不要在 SPA 里硬编码字段非空假设**：`Card.cover_url` `AIMessage.citations` `Document.last_opened_at` 都可能 null/no-attr，必须先判空。
- **不要在前端 mock 字段**：找不到值就显示空态/占位，不要补假数据，否则 demo 会再次「看着像但不是真后端」。
- **`Document.chunk_count` 和 `last_opened_at` 在当前模型上不存在**——SPA 不要尝试读，否则 `instance.x === undefined`。如果产品需要，先和 Agent 2 协调加列。
