# PRD4 vs 现有实现对比分析文档

**文档版本:** V1.0
**创建日期:** 2026-02-06
**分析目标:** 对比 PRD4 详细设计说明书与现有 AgentOS 实现，识别差异、未实现功能和冲突点

---

## 📊 执行摘要

### 总体完成度评估

| 类别 | 完成度 | 说明 |
|------|--------|------|
| **数据模型设计** | 30% | 基础模型存在，但缺少关键字段和多态设计 |
| **混合搜索策略** | 40% | 仅实现向量搜索，缺少关键词融合和加权逻辑 |
| **Connection 引擎** | 0% | 完全未实现 |
| **Insight 挖掘** | 0% | 完全未实现 |
| **灵感采集流程** | 60% | Inbox 存在，但异步处理不完整 |
| **微信集成** | 0% | 完全未实现 |
| **Agent 审计** | 0% | 完全未实现 |
| **非功能性需求** | 50% | 部分 ACL 和日志实现 |

**总体完成度: 约 25%**

---

## 一、核心数据库模型对比

### 1.1 统一内容索引 (Items)

#### PRD4 要求
```sql
CREATE TABLE items (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    creator_id UUID NOT NULL,
    type VARCHAR(20) NOT NULL,  -- note, task, resource, plan, insight

    title TEXT,
    content TEXT,
    summary TEXT,
    embedding VECTOR(1536),

    area_id UUID,
    project_id UUID,

    source_type VARCHAR(20),
    source_meta JSONB,

    status VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### 现有实现
- ✅ **存在:** `Card` 模型 (`src/agent_os/knowledge/models.py`)
- ✅ **存在:** `Task` 模型 (`src/agent_os/tasks/models.py`)
- ❌ **缺失:** 统一的 `items` 表（多态设计）
- ❌ **缺失:** `workspace_id` (使用 `organization_id`)
- ❌ **缺失:** `area_id` 和 `project_id` 字段
- ❌ **缺失:** `type` 字段的统一枚举
- ❌ **缺失:** `source_meta` JSONB 字段
- ⚠️ **差异:** `embedding` 维度不同 (384 vs 1536)

**差异分析:**
1. **架构冲突:** PRD4 要求所有内容类型统一到 `items` 表，现有实现使用独立的 `Card` 和 `Task` 表
2. **组织结构:** PRD4 使用 `workspace_id`，现有实现使用 `organization_id`
3. **层次结构:** PRD4 要求 `area_id` 和 `project_id`，现有实现完全缺失

#### 推荐解决方案
```sql
-- 方案 A: 迁移到统一表 (推荐，符合 PRD4)
CREATE TABLE items (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    creator_id UUID NOT NULL,
    type VARCHAR(20) NOT NULL,
    title TEXT,
    content TEXT,
    summary TEXT,
    embedding VECTOR(1536),
    area_id UUID,
    project_id UUID,
    source_type VARCHAR(20),
    source_meta JSONB,
    status VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 方案 B: 保持独立表，添加统一视图
CREATE VIEW unified_items AS
SELECT id, organization_id as workspace_id, user_id as creator_id,
       'card' as type, title, content, NULL as summary, embedding,
       NULL as area_id, NULL as project_id, 'manual' as source_type,
       '{}' as source_meta, status, created_at, updated_at
FROM cards
UNION ALL
SELECT id, organization_id, user_id, 'task', title, description,
       NULL, NULL, NULL, NULL, source, '{}'::jsonb, status,
       created_at, updated_at
FROM tasks;
```

---

### 1.2 任务与决策审计 (Agent Accountability)

#### PRD4 要求

**Task_Cards 扩展字段:**
- `goal` (Text): 任务目标
- `constraints` (Text): 约束条件
- `risk_level` (Enum): Low / Medium / High
- `execution_status`: Draft / Planning / Decision / Executing / Done

**Decision_Points 表:**
```sql
CREATE TABLE decision_points (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL,
    type VARCHAR(20),  -- Selection, Info, Boundary
    options JSONB,
    user_choice UUID,
    confirmed_at TIMESTAMP
);
```

**Ledger_Events 表 (Append Only):**
```sql
CREATE TABLE ledger_events (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL,
    event_type VARCHAR(50),
    snapshot JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 现有实现
- ✅ **存在:** `Task` 模型
- ❌ **缺失:** `goal` 字段
- ❌ **缺失:** `constraints` 字段
- ❌ **缺失:** `risk_level` 字段
- ⚠️ **差异:** `execution_status` 不匹配 (现有: pending/in_progress/completed)
- ❌ **完全缺失:** `Decision_Points` 表
- ❌ **完全缺失:** `Ledger_Events` 表

**影响分析:**
- 🔴 **严重:** 缺少审计功能无法满足"Agent 可回溯"需求
- 🔴 **严重:** 缺少决策点记录无法实现"风险提示"功能
- 🔴 **严重:** 缺少 Ledger 无法保证"不可篡改审计日志"

#### 推荐实现
```python
# 扩展 Task 模型
class Task(Base):
    # ... 现有字段 ...

    # PRD4 新增字段
    goal = Column(Text, nullable=True)
    constraints = Column(Text, nullable=True)
    risk_level = Column(Enum('low', 'medium', 'high'), default='low')
    execution_status = Column(
        Enum('draft', 'planning', 'decision', 'executing', 'done'),
        default='draft'
    )

# 新增 DecisionPoint 模型
class DecisionPoint(Base):
    __tablename__ = "decision_points"

    id = Column(UUID, primary_key=True)
    task_id = Column(UUID, ForeignKey("tasks.id"))
    type = Column(String(20))  # Selection, Info, Boundary
    options = Column(JSONB)
    user_choice = Column(UUID)
    confirmed_at = Column(DateTime(timezone=True))

# 新增 LedgerEvent 模型
class LedgerEvent(Base):
    __tablename__ = "ledger_events"

    id = Column(UUID, primary_key=True)
    task_id = Column(UUID, ForeignKey("tasks.id"))
    event_type = Column(String(50))
    snapshot = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 只增不改约束需要在应用层实现
    __table_args__ = (
        CheckConstraint("id IS NOT NULL"),  # 防止 UPDATE
    )
```

---

### 1.3 认知图谱 (Cognitive Graph)

#### PRD4 要求

```sql
CREATE TABLE graph_edges (
    id UUID PRIMARY KEY,
    from_node_id UUID NOT NULL,
    to_node_id UUID NOT NULL,
    weight FLOAT,
    relation_type VARCHAR(20),  -- Topic, Causal, Supplement
    is_strong BOOLEAN,
    created_at TIMESTAMP
);
```

#### 现有实现
- ❌ **完全缺失:** 没有任何图结构或连接关系表

**影响分析:**
- 🔴 **严重:** 无法实现"数字花园"功能
- 🔴 **严重:** 无法实现"Connection 逻辑"
- 🔴 **严重:** 无法计算"Neural Connections"

#### 推荐实现
```python
class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(UUID, primary_key=True)
    from_node_id = Column(UUID, nullable=False)
    to_node_id = Column(UUID, nullable=False)
    weight = Column(Float, default=0.0)
    relation_type = Column(String(20))  # Topic, Causal, Supplement
    is_strong = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_graph_from', 'from_node_id'),
        Index('idx_graph_to', 'to_node_id'),
        Index('idx_graph_strong', 'is_strong'),
        UniqueConstraint('from_node_id', 'to_node_id', name='unique_edge'),
    )
```

---

## 二、核心业务逻辑对比

### 2.1 混合搜索策略 (Hybrid Search)

#### PRD4 要求

**逻辑流程:**
1. 若 `q` 为空，按 `updated_at` 倒序返回
2. 并行召回:
   - 路 A (Semantic): pgvector Cosine Distance, Top 50
   - 路 B (Keyword): Postgres tsvector (BM25), Top 50
3. 融合排序: `Final Score = 0.7 * Semantic + 0.3 * Keyword + Freshness`
4. 高亮处理

#### 现有实现
- ✅ **存在:** `VectorSearchService` (`src/agent_os/knowledge/vector_search.py`)
- ✅ **存在:** 向量搜索 (pgvector Cosine Similarity)
- ❌ **缺失:** 关键词搜索 (BM25/tsvector)
- ❌ **缺失:** 并行召回机制
- ❌ **缺失:** 融合排序算法 (0.7/0.3 权重)
- ❌ **缺失:** 新鲜度加权 (Freshness Boost)
- ❌ **缺失:** 结果高亮功能

**代码分析:**
```python
# 现有实现 (仅向量搜索)
async def search_by_vector(db, query_embedding, limit=10):
    # 仅使用 pgvector cosine similarity
    query = """
        SELECT id, title, content,
               1 - (embedding <=> :query_embedding) as similarity
        FROM cards
        WHERE user_id = :user_id
        ORDER BY similarity DESC
        LIMIT :limit
    """
```

#### 推荐实现
```python
class HybridSearchService:
    """混合搜索服务 - 实现 PRD4 规范"""

    async def hybrid_search(
        self,
        db: AsyncSession,
        user_id: int,
        query: str,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        混合搜索实现
        1. 空 query -> 按 updated_at 倒序
        2. 并行召回: 语义 + 关键词
        3. 融合排序: 0.7 * semantic + 0.3 * keyword + freshness
        """

        # Step 1: 空 query 检查
        if not query or query.strip() == "":
            return await self._get_recent_items(db, user_id, limit)

        # Step 2: 并行召回
        semantic_results, keyword_results = await asyncio.gather(
            self._semantic_search(db, user_id, query, limit=50),
            self._keyword_search(db, user_id, query, limit=50)
        )

        # Step 3: 融合排序
        final_results = self._merge_and_rank(
            semantic_results,
            keyword_results,
            semantic_weight=0.7,
            keyword_weight=0.3
        )

        # Step 4: 高亮处理
        return self._apply_highlights(final_results, query)

    async def _semantic_search(self, db, user_id, query, limit):
        """语义搜索 - pgvector"""
        query_embedding = self.embeddings.embed_text(query)
        # ... pgvector 查询 ...

    async def _keyword_search(self, db, user_id, query, limit):
        """关键词搜索 - BM25"""
        # 需要添加 tsvector 列和 GIN 索引
        query = """
            SELECT id, title, content,
                   ts_rank(content_tsv, query) as keyword_score
            FROM cards
            WHERE content_tsv @@ to_tsquery(:query)
            ORDER BY keyword_score DESC
            LIMIT :limit
        """

    def _merge_and_rank(self, semantic, keyword, w1, w2):
        """RRF 或加权融合"""
        scores = {}

        # 归一化并融合
        for item in semantic:
            scores[item.id] = w1 * item.score

        for item in keyword:
            if item.id in scores:
                scores[item.id] += w2 * item.score
            else:
                scores[item.id] = w2 * item.score

        # 添加新鲜度加权
        # ...

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

**必要迁移:**
```sql
-- 添加 tsvector 列
ALTER TABLE cards ADD COLUMN content_tsv tsvector;
ALTER TABLE cards ADD COLUMN title_tsv tsvector;

-- 创建 GIN 索引
CREATE INDEX idx_cards_content_tsv ON cards USING GIN(content_tsv);
CREATE INDEX idx_cards_title_tsv ON cards USING GIN(title_tsv);

-- 触发器自动更新
CREATE OR REPLACE FUNCTION cards_tsv_update() RETURNS trigger AS $$
BEGIN
    NEW.content_tsv := to_tsvector('english', coalesce(NEW.content, ''));
    NEW.title_tsv := to_tsvector('english', coalesce(NEW.title, ''));
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER cards_tsv_trigger BEFORE INSERT OR UPDATE ON cards
    FOR EACH ROW EXECUTE FUNCTION cards_tsv_update();
```

---

### 2.2 Connection 计算引擎 (Neural Connections)

#### PRD4 要求

**计算公式:**
```python
score = (
    w1 * vector_similarity(a, b) +      # 语义相似
    w2 * keyword_overlap(a, b) +        # 关键词重叠
    w3 * entity_overlap(a, b) +         # 实体重叠
    w4 * is_same_area(a, b) +           # 结构一致性
    w5 * time_decay(a.time, b.time)     # 时间衰减
)

if score > THRESHOLD:
    create_edge(a, b, strong=True)
```

**实现要求:**
- 异步 Worker
- 监听 `Item Created/Updated` 事件
- 只创建强连接 (Strong Edge)

#### 现有实现
- ❌ **完全缺失:** 无 Connection 计算逻辑

**影响分析:**
- 🔴 **严重:** 无法实现"Neural Connections"核心功能
- 🔴 **严重:** 无法支持"数字花园"的关联推荐
- 🔴 **严重:** Profile 页面的"连接数"指标无法实现

#### 推荐实现
```python
# 新文件: src/agent_os/connections/engine.py

class ConnectionEngine:
    """连接计算引擎 - 异步 Worker"""

    def __init__(self):
        self.w1, self.w2, self.w3, self.w4, self.w5 = 0.4, 0.2, 0.2, 0.1, 0.1
        self.threshold = 0.75

    async def on_item_created(self, item_id: UUID):
        """监听 Item Created 事件"""
        # 获取新 Item
        new_item = await self.get_item(item_id)

        # 获取候选 Items (同 workspace, 最近30天)
        candidates = await self.get_candidates(new_item)

        # 并行计算相似度
        scores = await asyncio.gather(*[
            self.calculate_score(new_item, candidate)
            for candidate in candidates
        ])

        # 创建强连接
        for candidate, score in zip(candidates, scores):
            if score >= self.threshold:
                await self.create_edge(new_item, candidate, score, strong=True)

    async def calculate_score(self, a: Item, b: Item) -> float:
        """计算连接得分"""
        score = (
            self.w1 * self.vector_similarity(a, b) +
            self.w2 * self.keyword_overlap(a, b) +
            self.w3 * self.entity_overlap(a, b) +
            self.w4 * self.is_same_area(a, b) +
            self.w5 * self.time_decay(a.created_at, b.created_at)
        )
        return score

    def vector_similarity(self, a, b) -> float:
        """余弦相似度"""
        return cosine_similarity(a.embedding, b.embedding)

    def keyword_overlap(self, a, b) -> float:
        """关键词重叠度 (Jaccard)"""
        keywords_a = set(self.extract_keywords(a.content))
        keywords_b = set(self.extract_keywords(b.content))
        return len(keywords_a & keywords_b) / len(keywords_a | keywords_b)

    def entity_overlap(self, a, b) -> float:
        """实体重叠度 (人名/项目名)"""
        entities_a = self.extract_entities(a.content)
        entities_b = self.extract_entities(b.content)
        return len(set(entities_a) & set(entities_b)) / max(len(entities_a), len(entities_b))

    def is_same_area(self, a, b) -> float:
        """结构一致性"""
        return 1.0 if a.area_id == b.area_id else 0.0

    def time_decay(self, time_a, time_b) -> float:
        """时间衰减 (指数衰减, 半衰期 30 天)"""
        days_diff = abs((time_a - time_b).days)
        return math.exp(-days_diff / 30)

# 集成到事件系统
# src/agent_os/events/handlers.py
@event_handler("item.created")
async def handle_item_created(item_id: UUID):
    engine = ConnectionEngine()
    await engine.on_item_created(item_id)
```

---

### 2.3 Insight 挖掘引擎

#### PRD4 要求

**处理链:**
1. LLM 抽象: 输出 `Claim`, `Rationale`, `Implications`
2. Canonical Hash 去重
3. 写回: 创建 `Insight` 类型的 Item

#### 现有实现
- ❌ **完全缺失:** 无 Insight 挖掘逻辑

**影响分析:**
- 🟡 **中等:** 核心功能缺失，但不影响基本使用

#### 推荐实现
```python
# 新文件: src/agent_os/insights/miner.py

class InsightMiner:
    """洞察挖掘引擎"""

    async def mine_insights(self, cluster: List[Item]) -> List[Insight]:
        """从高密度连接集群挖掘洞察"""

        # 1. LLM 抽象
        prompt = f"""
        分析以下内容,提取关键洞察:
        {self.format_cluster(cluster)}

        输出格式:
        - Claim: [结论]
        - Rationale: [理由]
        - Implications: [行动含义]
        """

        llm_response = await self.llm.generate(prompt)
        parsed = self.parse_response(llm_response)

        # 2. Canonical Hash 去重
        claim_hash = self.canonical_hash(parsed['claim'])
        if await self.insight_exists(claim_hash):
            return []

        # 3. 写回
        insight = Insight(
            type='insight',
            claim=parsed['claim'],
            rationale=parsed['rationale'],
            implications=parsed['implications'],
            source_refs=[item.id for item in cluster],
            claim_hash=claim_hash
        )
        await self.create_insight(insight)
        return [insight]

    def canonical_hash(self, text: str) -> str:
        """归一化 Hash (去除停用词、标点,小写化)"""
        normalized = text.lower()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = ' '.join(w for w in normalized.split()
                             if w not in STOP_WORDS)
        return hashlib.md5(normalized.encode()).hexdigest()
```

---

## 三、系统交互流程对比

### 3.1 灵感采集与智能归档

#### PRD4 要求

**API 1: `/capture` (同步)**
- 接收 Text/Image/Link
- 立即写入 `inbox` 表,状态 `processing`
- 响应 < 50ms

**Worker (异步):**
- Step 1: 解析 (识别 Intent)
- Step 2: 归档 (匹配 Area/Project)
- Step 3: 向量化
- Step 4: 通知 (WebSocket 推送)

#### 现有实现
- ✅ **存在:** `InboxItem` 模型 (`src/agent_os/knowledge/models.py`)
- ✅ **存在:** `/inbox` API (`src/agent_os/knowledge/router.py`)
- ⚠️ **部分:** 异步处理不完整
- ❌ **缺失:** Intent 识别
- ❌ **缺失:** Area/Project 自动匹配
- ❌ **缺失:** WebSocket 通知

#### 推荐实现
```python
# 完善异步处理流程
class InboxProcessor:
    """Inbox 异步处理器"""

    async def process_inbox_item(self, item_id: int):
        """处理 Inbox Item"""
        item = await self.get_inbox_item(item_id)

        # Step 1: 解析 Intent
        intent = await self.identify_intent(item.content)

        # Step 2: 自动归档
        area_id, project_id = await self.auto_classify(item.content)

        # Step 3: 转换为 Card/Task
        if intent == 'task':
            await self.create_task(item, area_id, project_id)
        else:
            card = await self.create_card(item, area_id, project_id)
            await self.vectorize_card(card)

        # Step 4: 更新状态
        await self.update_status(item_id, 'processed')

        # Step 5: WebSocket 通知
        await self.notify_user(item.user_id, {
            "type": "insight_ready",
            "count": await self.get_today_insights_count(item.user_id)
        })
```

---

### 3.2 微信集成

#### PRD4 要求

**接入方式:** 企业微信机器人 Webhook

**解析逻辑:**
- 接收微信 XML/JSON
- 提取 Link -> 爬虫抓取 Title, Summary, Cover
- 映射为 `Resource` 类型 Item
- 打上 tag: `来自微信`

#### 现有实现
- ❌ **完全缺失:** 无任何微信相关代码

**影响分析:**
- 🟡 **中等:** PRD4 核心功能缺失，但不影响 Web 端使用

#### 推荐实现
```python
# 新文件: src/agent_os/integrations/wechat.py

class WeChatIntegration:
    """微信集成服务"""

    async def handle_webhook(self, data: dict):
        """处理微信 Webhook"""
        # 1. 解析消息
        msg_type = data.get('MsgType')
        content = data.get('Content')

        if msg_type == 'text':
            # 提取链接
            urls = self.extract_urls(content)
            if urls:
                await self.process_link(urls[0], data)

    async def process_link(self, url: str, wechat_data: dict):
        """处理链接"""
        # 1. 爬虫抓取
        metadata = await self.crawler.fetch(url)

        # 2. 创建 Resource Item
        item = Item(
            type='resource',
            title=metadata['title'],
            content=metadata['summary'],
            source_type='wechat',
            source_meta={
                'url': url,
                'wechat_sender': wechat_data.get('FromUserName'),
                'cover': metadata.get('cover')
            },
            tags=['来自微信']
        )
        await self.create_item(item)

        # 3. 向量化
        await self.vectorize_item(item)

# 新文件: src/agent_os/integrations/crawler.py
class WebCrawler:
    """网页爬虫"""

    async def fetch(self, url: str) -> dict:
        """抓取网页元数据"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, 'html.parser')
        return {
            'title': soup.find('title').text,
            'summary': soup.find('meta', {'name': 'description'})['content'],
            'cover': self.extract_cover_image(soup)
        }
```

**API 端点:**
```python
# src/agent_os/integrations/router.py
@router.post("/webhook/wechat")
async def wechat_webhook(request: Request):
    """微信 Webhook 端点"""
    data = await request.json()
    integration = WeChatIntegration()
    await integration.handle_webhook(data)
    return {"status": "ok"}
```

---

### 3.3 Agent 执行闭环

#### PRD4 要求

**路由逻辑:**
- Direct: 简单问答 -> LLM 直接回复
- RAG: 需要知识库 -> Search Service -> 组装 Prompt
- Skill: 需要工具 -> Skill Registry -> Function Call

**输出标准化:**
```json
{
  "summary": "...",
  "key_points": [],
  "actions": [],
  "references": []
}
```

**写回确认:** 用户点击"转为任务" -> 调用 `/items` 接口

#### 现有实现
- ✅ **存在:** Agent 系统 (`src/agent_os/agent.py`)
- ✅ **存在:** RAG Provider (`src/agent_os/knowledge/rag_provider.py`)
- ✅ **存在:** Skill Registry (`src/agent_os/skills/`)
- ⚠️ **部分:** 输出结构不完整
- ❌ **缺失:** "转为任务"快捷操作

#### 推荐实现
```python
# 标准化输出
class AgentResponse(BaseModel):
    """标准化 Agent 响应"""
    summary: str
    key_points: List[str]
    actions: List[str]
    references: List[ItemRef]

# Agent 路由增强
class AgentRouter:
    async def route(self, query: str, context: Context) -> AgentResponse:
        """智能路由"""

        # 1. 意图识别
        intent = await self.classify_intent(query)

        if intent == 'direct':
            # 简单问答
            response = await self.llm.generate(query)
            return AgentResponse(
                summary=response,
                key_points=[],
                actions=[],
                references=[]
            )

        elif intent == 'rag':
            # 知识库检索
            results = await self.search_service.search(query, context)
            prompt = self.build_rag_prompt(query, results)
            response = await self.llm.generate(prompt)
            return self.parse_to_structured(response, results)

        elif intent == 'skill':
            # 工具调用
            skill = await self.skill_registry.match(query)
            result = await skill.execute(query, context)
            return self.format_skill_result(result)
```

---

## 四、非功能性需求对比

### 4.1 性能指标 (SLAs)

#### PRD4 要求
- Agent 结构化返回: P75 ≤ 10s (超时 30s)
- 首屏加载 (LCP): ≤ 2.5s
- 输入响应: < 50ms (异步)

#### 现有实现
- ⚠️ **部分:** 部分接口缺少超时控制
- ❌ **缺失:** 输入响应异步化
- ❌ **缺失:** 性能监控 (P75/P99 统计)

#### 推荐实现
```python
# 添加超时控制
@router.post("/agent/query")
@timeout(10)  # P75 10s
async def agent_query(request: AgentRequest):
    response = await agent.process(request.query)
    return response

# 异步输入处理
@router.post("/capture")
async def capture_input(request: CaptureRequest):
    # 同步写入 inbox
    item = await inbox.create(request.content)

    # 异步处理 (后台任务)
    await background_tasks.queue(process_inbox_item, item.id)

    return {"id": item.id, "status": "processing"}  # < 50ms
```

---

### 4.2 数据安全与权限

#### PRD4 要求
- **ACL:** 强制校验 `workspace_id` 和 `user_id`
- **加密:** 敏感字段 (Token/Keys) 加密存储

#### 现有实现
- ✅ **存在:** `organization_id` 和 `user_id` 校验
- ✅ **存在:** 加密服务 (`src/agent_os/db/encryption.py`)
- ⚠️ **部分:** 加密未应用于所有敏感字段

#### 推荐实现
```python
# 统一 ACL 中间件
class ACLMiddleware:
    async def verify_access(self, user_id: int, resource_id: int):
        """验证访问权限"""
        # 强制校验 workspace_id 和 user_id
        resource = await db.get(Item, resource_id)
        if resource.workspace_id != user_ctx.workspace_id:
            raise Forbidden("Access denied")
```

---

### 4.3 可观测性

#### PRD4 要求
- **Trace:** 全局唯一 `request_id` 贯穿 API -> Worker -> LLM
- **Log:** 记录所有 LLM Input/Output Token 消耗

#### 现有实现
- ❌ **缺失:** request_id 追踪
- ❌ **缺失:** Token 消耗记录

#### 推荐实现
```python
# Request ID 中间件
class TracingMiddleware:
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # 注入到日志上下文
        logging_context.set(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

# Token 消耗记录
class LLMLogger:
    async def log_usage(
        self,
        request_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str
    ):
        await db.execute(
            """INSERT INTO llm_usage_logs
               (request_id, input_tokens, output_tokens, model, cost)
               VALUES (:request_id, :input, :output, :model, :cost)"""
        )
```

---

## 五、实施路线图

### 阶段 1: 数据模型重构 (优先级: 🔴 高)

**工期: 2-3 周**

1. **Week 1: 统一 Items 表**
   - [ ] 创建 `items` 表 (支持多态)
   - [ ] 数据迁移脚本 (Card/Task -> Items)
   - [ ] 更新所有 CRUD 操作
   - [ ] 添加 `area_id`, `project_id` 字段

2. **Week 2: 审计表**
   - [ ] 创建 `decision_points` 表
   - [ ] 创建 `ledger_events` 表
   - [ ] 扩展 `Task` 模型 (goal, constraints, risk_level)
   - [ ] 实现审计日志中间件

3. **Week 3: 认知图谱**
   - [ ] 创建 `graph_edges` 表
   - [ ] 创建图查询索引
   - [ ] 基础图遍历 API

**交付物:**
- 完整的数据模型
- 数据迁移脚本
- 单元测试覆盖率 > 80%

---

### 阶段 2: 混合搜索引擎 (优先级: 🔴 高)

**工期: 2 周**

1. **Week 1: 关键词搜索**
   - [ ] 添加 `content_tsv`, `title_tsv` 列
   - [ ] 创建 GIN 索引
   - [ ] 实现 BM25 算法
   - [ ] 性能测试

2. **Week 2: 融合排序**
   - [ ] 实现并行召回
   - [ ] 实现 RRF/加权融合
   - [ ] 添加新鲜度加权
   - [ ] 实现结果高亮

**交付物:**
- 混合搜索 API
- 性能基准测试 (P75 < 500ms)
- API 文档

---

### 阶段 3: Connection 引擎 (优先级: 🟡 中)

**工期: 2-3 周**

1. **Week 1: 计算引擎**
   - [ ] 实现 `ConnectionEngine`
   - [ ] 5 维度评分算法
   - [ ] 异步 Worker 框架

2. **Week 2: 事件集成**
   - [ ] Item Created/Updated 事件
   - [ ] 事件监听器
   - [ ] 增量计算

3. **Week 3: API 和优化**
   - [ ] 查询连接 API
   - [ ] 强连接查询优化
   - [ ] 性能测试

**交付物:**
- Connection 计算引擎
- 连接查询 API
- 性能测试报告

---

### 阶段 4: Insight 挖掘 (优先级: 🟢 低)

**工期: 1-2 周**

1. **Week 1: 挖掘引擎**
   - [ ] LLM 抽象 Prompt
   - [ ] Canonical Hash 去重
   - [ ] 写回逻辑

2. **Week 2: 调度和 API**
   - [ ] 周期性调度器
   - [ ] 手动触发 API
   - [ ] Insight 管理 API

**交付物:**
- Insight 挖掘引擎
- Insight API
- Prompt 模板

---

### 阶段 5: 集成与优化 (优先级: 🟡 中)

**工期: 2 周**

1. **Week 1: 微信集成**
   - [ ] Webhook 端点
   - [ ] 爬虫实现
   - [ ] Resource 入库

2. **Week 2: 可观测性**
   - [ ] Request ID 追踪
   - [ ] Token 消耗日志
   - [ ] 性能监控 Dashboard

**交付物:**
- 微信集成
- 可观测性系统
- 监控 Dashboard

---

## 六、风险与依赖

### 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| pgvector 性能瓶颈 | 搜索响应慢 | 使用缓存、分页、异步索引 |
| Connection 计算复杂度 O(n²) | 大数据集性能差 | 限制候选集、增量计算、定时批处理 |
| LLM 调用成本过高 | 运营成本超预算 | 使用缓存、Prompt 优化、小模型优先 |
| 数据迁移失败 | 数据丢失 | 完整备份、回滚方案、灰度迁移 |

### 依赖关系

```
阶段 1 (数据模型)
    ↓
阶段 2 (混合搜索) ← 阶段 3 (Connection) ← 阶段 4 (Insight)
    ↓
阶段 5 (集成与优化)
```

---

## 七、总结

### 关键发现

1. **架构冲突:** PRD4 要求统一 `items` 表,现有实现使用独立表
2. **核心功能缺失:** Connection 引擎、Insight 挖掘、微信集成完全未实现
3. **审计能力不足:** 缺少决策点和审计日志,无法满足"Agent 可回溯"
4. **搜索能力有限:** 仅向量搜索,缺少关键词融合和加权排序

### 建议优先级

**立即开始 (P0):**
1. 数据模型重构 (Items 表、审计表)
2. 混合搜索引擎 (关键词 + 融合排序)

**近期规划 (P1):**
3. Connection 计算引擎
4. 微信集成

**长期规划 (P2):**
5. Insight 挖掘引擎
6. 完整可观测性

### 预估工作量

| 阶段 | 工期 | 人力 |
|------|------|------|
| 阶段 1: 数据模型 | 2-3 周 | 2 人 |
| 阶段 2: 混合搜索 | 2 周 | 1 人 |
| 阶段 3: Connection | 2-3 周 | 1 人 |
| 阶段 4: Insight | 1-2 周 | 1 人 |
| 阶段 5: 集成优化 | 2 周 | 1 人 |

**总计: 9-12 周, 2-3 人团队**

---

**文档结束**

**下一步行动:**
1. 召开技术评审会议,确认实施优先级
2. 创建详细技术设计文档 (TDD)
3. 搭建开发分支和测试环境
