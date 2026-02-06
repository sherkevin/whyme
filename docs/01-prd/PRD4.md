# Mydow 后端详细设计说明书 (V1.0 Final)

**设计目标：** 确保后端实现完全覆盖 PRD 定义的“输入→解析→写回→可视化→周期复盘”全链路闭环，并严格落地复杂的混合检索与认知分析算法。

---

## 一、 核心数据库模型设计 (Schema Design)

此部分严格对应 `PA V1.0` 和 `PA PRD`  中的实体定义，特别是审计与任务追踪字段。

### 1. 统一内容索引 (Unified Knowledge Item)

**需求来源：** 全局搜索逻辑 , 知识库结构 , 微信分享入库 。
**设计说明：** 使用多态设计，所有内容（Note, Task, Resource, Plan）均视为 `Item`，但在 `meta` 中区分。

```sql
CREATE TABLE items (
    id UUID PRIMARY KEY,
    [cite_start]workspace_id UUID NOT NULL, -- [cite: 224] 单Workspace设计
    creator_id UUID NOT NULL,
    [cite_start]type VARCHAR(20) NOT NULL,  -- 枚举: note, task, resource, plan, insight [cite: 521]
    
    -- 核心内容 (参与混合检索)
    [cite_start]title TEXT,                 -- 权重最高 [cite: 522]
    [cite_start]content TEXT,               -- 原始内容 (Source of Truth) [cite: 213]
    summary TEXT,               -- Agent生成的摘要/结构化表达
    [cite_start]embedding VECTOR(1536),     -- 语义向量 [cite: 524]
    
    -- 结构化归属 (V1 冻结结构)
    [cite_start]area_id UUID,               -- [cite: 65]
    [cite_start]project_id UUID,            -- [cite: 66]
    
    -- 来源追踪 (WeChat/Web Clip)
    source_type VARCHAR(20),    -- 'manual', 'wechat', 'chrome_extension'
    [cite_start]source_meta JSONB,          -- { "url": "...", "wechat_sender": "...", "thumb": "..." } [cite: 441]
    
    -- 状态
    status VARCHAR(20),         -- active, archived, deleted
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

```

### 2. 任务与决策审计 (Agent Accountability)

**需求来源：** `PA V1.0` 核心定义，必须实现“可回溯”、“风险提示” 。
**设计说明：** 这是区别于普通 Todo 应用的核心，必须严格实现字段。

* **Task_Cards (扩展自 Items):**
* 
`goal` (Text): 任务目标 


* 
`constraints` (Text): 约束条件 


* 
`risk_level` (Enum): Low / Medium / High 


* 
`execution_status`: Draft / Planning / Decision / Executing / Done 




* **Decision_Points (决策点):**
* `task_id` (FK)
* 
`type`: Selection / Info / Boundary 


* 
`options`: JSONB (`[{ "summary": "...", "risks": "...", "cost": "..." }]`) 


* `user_choice`: 记录用户最终选择的 option_id
* 
`confirmed_at`: 时间戳 




* **Ledger_Events (不可篡改审计日志):**
* `task_id` (FK)
* 
`event_type`: AgentSuggested / UserConfirmed / DeliverableGenerated 


* 
`snapshot`: JSONB (记录当时的完整上下文快照) 


* **设计约束：** 此表只增不改 (Append Only)。



### 3. 认知图谱 (Cognitive Graph)

**需求来源：** 数字花园 , Connection 逻辑诠释 。
**设计说明：**

* **Graph_Edges:**
* `from_node_id`, `to_node_id`
* `weight`: Float (连接强度)
* 
`relation_type`: (Topic, Causal, Supplement) 


* 
`is_strong`: Boolean (是否为强连接，用于 Profile 计数) 





---

## 二、 复杂业务逻辑与算法实现 (Core Logic)

这部分是你文档中逻辑最复杂、很容易被遗漏的地方。

### 1. 混合搜索策略 (Hybrid Search Strategy)

**需求来源：** `顶部全局导航逻辑诠释` 。
**设计说明：** 搜索接口必须实现特定的加权逻辑，不能只做简单的向量搜索。

* **逻辑流程：**
1. 
**判断输入：** 若 `q` 为空，直接按 `updated_at` 倒序返回 。


2. **并行召回：**
* **路 A (Semantic):** 使用 `pgvector` 计算 Cosine Distance，取 Top 50。
* **路 B (Keyword):** 使用 Postgres `tsvector` (BM25) 进行关键词匹配，取 Top 50。


3. **融合排序 (RRF/Weighted Sum):**
* 
`Final Score = 0.7 * Semantic_Score + 0.3 * Keyword_Score + Freshness_Boost` 。




4. **高亮处理：**
* 若命中 Keyword，返回关键词高亮片段。
* 若仅命中 Semantic，返回语义相关摘要 。







### 2. Connection 计算引擎 (Neural Connections)

**需求来源：** `connection逻辑诠释` 。
**设计说明：** 这是一个异步 Worker，不能在写入时同步阻塞。

* **触发器：** 监听到 `Item Created/Updated` 事件。
* **计算公式 (后端必须实现此加权):**
```python
# [cite_start]伪代码实现 [cite: 1245]
score = (
    w1 * vector_similarity(a, b) +      # 语义相似
    w2 * keyword_overlap(a, b) +        # 关键词重叠
    w3 * entity_overlap(a, b) +         # 实体(人名/项目)重叠
    w4 * is_same_area(a, b) +           # 结构一致性
    w5 * time_decay(a.time, b.time)     # 时间衰减
)
if score > THRESHOLD:
    create_edge(a, b, strong=True)

```


* 
**去重策略：** 只有强连接（Strong Edge）才计入 Profile 页面的 "Neural Connections" 指标 。



### 3. Insight 挖掘引擎 (Insight Mining)

**需求来源：** `insight逻辑诠释` 。
**设计说明：** 这是一个周期性或事件触发的批处理任务。

* **输入：** 一个高密度连接的 Cluster 或用户在同一 Topic 下的连续输入。
* **处理链：**
1. 
**LLM 抽象：** Prompt 必须要求输出 `Claim` (结论), `Rationale` (理由), `Implications` (行动含义) 。


2. 
**Canonical Hash 去重：** 对 Claim 进行归一化 Hash，防止重复生成相似观点 。


3. 
**写回：** 生成类型为 `Insight` 的 Item，并记录 `source_refs` (来源引用) 。





---

## 三、 系统交互与流程设计 (Interaction Flows)

### 1. 灵感采集与智能归档 (Ingestion Pipeline)

**需求来源：** `PA PRD` , `无痛记录` , `前后端交互` 。
**设计说明：** 采用“快速写入 + 异步解析”模式。

* **API 1: `/capture` (同步):**
* 接收 Text / Image / Link。
* **立即** 写入 `inbox` 表 (Raw Data)，状态为 `processing`。
* 响应时间 < 50ms 。




* **Worker (异步):**
* 
**Step 1 解析:** 调用 LLM 识别 `Intent` (Task/Note/Plan) 。


* 
**Step 2 归档:** 自动匹配最可能的 `Area/Project` 。


* **Step 3 向量化:** 计算 Embedding 并更新。
* 
**Step 4 通知:** 通过 WebSocket/SSE 推送“今日洞察”计数 +1 。





### 2. 微信集成流程 (WeChat Integration)

**需求来源：** `无痛记录` 。
**设计说明：**

* 
**接入方式：** 优先支持 **企业微信机器人 Webhook** 。


* **解析逻辑：**
* 后端接收微信 XML/JSON。
* 提取 `Link` -> 启动爬虫抓取 `Title`, `Summary`, `Cover` 。


* 映射为 `Resource` 类型 Item，打上 tag: `来自微信` 。





### 3. Agent 执行闭环 (The Agent Flow)

**需求来源：** `PA PRD` , `PA V1.0` 。
**设计说明：**

* **输入：** 用户 Query + `@Context` (选中的文件/项目)。
* **路由：**
* **Direct:** 简单问答 -> LLM 直接回复。
* **RAG:** 需要知识库 -> 调用 Search Service -> 组装 Prompt。
* 
**Skill:** 需要工具 -> 匹配 `Skill Registry`  -> 执行 Function Call。




* **输出标准化：** 必须返回 JSON 结构：
* 
`{ summary: "...", key_points: [], actions: [], references: [] }` 。




* 
**写回确认：** 用户点击“转为任务”时，调用 `/items` 接口将临时的 Action 转化为持久化的 `Task` 。



---

## 四、 非功能性需求与架构约束 (NFRs)

**需求来源：** `PA PRD` 第五章 。

1. **性能指标 (SLAs):**
* 
**Agent 结构化返回：** P75 ≤ 10s (超时上限 30s) 。


* 
**首屏加载 (LCP):** 接口需支持按需加载，配合前端达到 ≤ 2.5s 。


* 
**输入响应：** < 50ms (后端必须异步处理) 。




2. **数据安全与权限:**
* 
**ACL:** 所有接口强制校验 `workspace_id` 和 `user_id` 。


* 
**加密:** 敏感字段 (Token/Keys) 必须加密存储 。




3. **可观测性:**
* 
**Trace:** 必须生成全局唯一的 `request_id`，贯穿 API -> Worker -> LLM 调用链 。


* **Log:** 记录所有 LLM 的 Input/Output Token 消耗（用于成本分析）。



---

### 文档总结
1. **审计字段 (Ledger/Decision):** 补全了 `PA V1.0` 中关于 Agent 责任边界的强制字段。
2. **算法权重公式:** 明确了搜索 (0.7/0.3) 和连接计算 (w1-w5) 的具体实现逻辑，不再是模糊的“AI计算”。
3. **微信集成链路:** 明确了从 Webhook 到 Resource 入库的转换逻辑。
4. **Insight 去重逻辑:** 增加了 Canonical Hash 机制，防止 Insight 泛滥。
5. **Skill 生态:** 明确了 Skill 的数据结构和调用方式。
