### 🧱 模块一：核心数据架构 (Core Schema & Infrastructure)

**目标**：建立支持 PARA、双向链接和 AI 治理的数据库模型。

#### Task 1.1: 搭建基础数据库模型 (SQLAlchemy/Pydantic)

* **输入给 Claude 的指令**：基于 PRD 第 8 章节，创建以下核心表结构：
* `User`: 基础用户信息 + `preferences` (JSON, 存储 PRD 7.8 中的配置)。
* 
`InboxItem`: 字段包括 `content`, `source_type` (text/url/voice), `status` (raw/processed/archived), `ai_tags` (List), `ai_summary`. 


* 
`Card` (核心知识单元): 字段包括 `one_liner` (核心洞察), `body` (Markdown), `para_type` (Enum: Project/Area/Resource/Archive), `output_status` (drafted/published). 


* 
`CardRelation`: 关联表，字段 `from_card_id`, `to_card_id`, `relation_type` (related_to/supports/contradicts). 


* 
`Task`: 字段 `type` (daily_system/ai_suggestion/user_created), `status`, `due_date`, `related_ref_id` (关联 Inbox 或 Card). 





#### Task 1.2: 实现“信任账本” (Trust Ledger) 模型

* **背景**：这是你负责的“信任系统”核心，用于记录 AI 为什么给出建议。
* **开发要求**：
* 创建 `LedgerEvent` 表：
* `event_type`: `AI_SUGGESTION` (宜/忌), `AUTO_TAGGING` (自动打标), `STRATEGY_GENERATION`.
* `context_snapshot`: JSON 字段，记录当时 AI 看到的上下文快照。
* `user_action`: 用户是接受了还是拒绝了。
* `reasoning`: AI 的思维链记录。





---

### 🧠 模块二：AI 业务管线 (AI Pipelines)

**目标**：实现 PRD 中“每日捕获”和“内容分析”的自动化逻辑。

#### Task 2.1: 灵感采集处理流 (Inbox Processing Pipeline)

* 
**对应功能**：PRD 7.2 灵感采集 。


* **Logic**：
1. **Parser**: 接收 URL，爬取正文（需处理反爬或使用 Reader API）。
2. **AI Worker**: 调用 LLM 进行预处理：
* 提取 `Title`, `Summary`, `Keywords`.
* 生成 `suggested_para_category` (基于历史数据推荐).
* 查重逻辑：计算 Embedding，并在 Vector DB 中查找相似度 > 0.8 的历史记录。





#### Task 2.2: “每日知识捕获” 状态机 (Daily Capture Flow)

* 
**对应功能**：PRD 7.3 。这是整个 App 最核心的 Agent 交互。


* **Logic**：
* 创建一个 `SessionManager` 来管理“4 问”对话状态。
* **State 1 (Initiate)**: 扫描 `InboxItem` 中 `status=raw` 的条目，选取 N 条。
* **State 2 (Q&A Loop)**: 依次抛出 4 个问题（新信息? 关联? 洞察? 应用?）。
* **State 3 (Synthesis)**: 将用户回复 + 原文，组装成一张结构化的 `Card`。
* **State 4 (Commit)**: 写入 `Card` 表，更新 `InboxItem` 为 `processed`，写入 `LedgerEvent`。



#### Task 2.3: 内容分析与聚类引擎 (Insight Engine)

* 
**对应功能**：PRD 7.5 内容分析 。


* **Logic**：
* **Clustering**: 每天定时任务，获取最近 7 天的 Cards，使用 LLM 或 Embedding 进行聚类，生成 `Topic`。
* **Gap Analysis**: 统计每个 Topic 下的卡片数量。如果 `count > 5` 且 `output_status == null`，标记为“输出缺口”。



---

### ⚙️ 模块三：业务逻辑 API (Backend API)

**目标**：为前端页面提供数据支撑。

#### Task 3.1: 首页 Dashboard 聚合接口 (`GET /dashboard/summary`)

* 
**对应功能**：PRD 7.1 Mydow 首页 。


* **API 逻辑**：
* 计算 `health_score`: 基于 Inbox 积压数和任务完成率。
* 生成 **宜/忌 (Do/Don't)**: 这是一个 Rule-based + AI 的混合逻辑。
* *规则示例*: 如果 `Inbox > 10` -> 宜: "清理收件箱"; 忌: "新增订阅".
* *AI 生成*: 根据 `Ledger` 历史，动态生成一条建议。


* 返回 `today_tasks`: 聚合系统任务（如“每日捕获”）和用户任务。



#### Task 3.2: 知识图谱数据接口 (`GET /knowledge/graph`)

* 
**对应功能**：PRD 7.4 知识库 。


* **API 逻辑**：
* 返回 `Nodes` (Cards/Projects) 和 `Edges` (Relations)。
* 支持按 `Area` 或 `Tag` 过滤，避免一次性返回全量数据导致前端卡死。



#### Task 3.3: Skills 执行接口 (`POST /skills/execute`)

* 
**对应功能**：PRD 7.7 Skills 广场 。


* **API 逻辑**：
* 接收 `skill_id` 和 `input_context` (如某张卡片的 ID)。
* 加载对应的 Prompt Template。
* 执行 LLM 任务。
* 返回结果（可能是生成的文本，也可能是创建了一组新 Task）。



---

### 🕒 模块四：定时任务与调度 (Scheduling)

**目标**：实现 Agent 的“主动性”。

#### Task 4.1: 定时触发器 (Cron Jobs)

* **开发要求**：
* 
`Daily_2130`: 触发“每日知识捕获”提醒，生成系统级 Task 。


* 
`Weekly_Review`: 每周五生成周报数据快照 。





---

### 🤝 协作与接口规范 (Collaboration)

**目标**：定义你与前端的交互标准。

#### Task 5.1: 生成 OpenAPI (Swagger) 文档

* **行动**：在编写任何具体逻辑前，先定义 Pydantic Schemas，自动生成 Swagger UI。
* **关键点**：明确 `Card` 和 `Inbox` 的 JSON 结构，因为前端需要根据这些结构渲染复杂的编辑器和图谱。

#### Task 5.2: Mock 数据生成器

* **行动**：编写一个 `populate_mock_data.py` 脚本。
* **内容**：生成 10 条 Inbox 记录（包含不同来源），5 个 Project，20 张已关联的 Card。让前端不需要等待后端逻辑完成即可调试 UI。

---

### 🚀 给 Claude Code 的执行建议
1. **第一波 (Schema)**: "作为后端负责人，请基于 FastAPI 和 SQLAlchemy，为我设计 Mydow 项目的 `models.py`。请严格遵循以下字段定义..." (复制 Task 1.1 和 1.2)。
2. **第二波 (CRUD)**: "基于上面的 models，生成 `inbox_router.py` 和 `card_router.py`，实现基础增删改查。"
3. **第三波 (Agent)**: "现在我们要实现核心 Agent 逻辑。请写一个 `DailyCaptureService` 类，模拟 PRD 7.3 中的 4 问流程。请设计一个状态机..." (复制 Task 2.2)。
4. **第四波 (Dashboard)**: "编写 `dashboard_router.py`，实现聚合逻辑，特别是‘宜/忌’的规则引擎..." (复制 Task 3.1)。