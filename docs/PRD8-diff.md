# PRD8-diff: PA 1.0 阶段四详细需求

**文档类型:** 产品需求文档 (PRD)
**对应阶段:** PA 1.0 阶段四
**创建时间:** 2026-02-07
**基于验收标准:** docs/acceptance/search_engine-acceptance-checklist.md

---

## 文档说明

本文档基于《阶段四验收标准》扩展,详细定义阶段四需要实现的所有后端功能。

**阶段四核心目标:** 在阶段三的Agent与Skill能力基础上,引入统一搜索、数据抓取与分析能力,并补齐安全、测试与部署能力,使PA 1.0具备可长期运行与对外交付的条件。

---

## 目录

1. [总体设计](#一总体设计)
2. [数据模型](#二数据模型)
3. [功能模块](#三功能模块)
4. [API设计](#四api设计)
5. [Demo场景](#五demo场景)
6. [测试要求](#六测试要求)
7. [部署与运维](#七部署与运维)
8. [交付清单](#八交付清单)

---

## 一、总体设计

### 1.1 阶段四定位

阶段四是在阶段三(多步Agent流程)基础上的**工程化与能力整合**阶段,不引入新的核心产品形态,而是:

1. **让数据可检索** - 统一搜索接口
2. **让外部数据可引入** - Ingestion能力
3. **让数据可分析** - Insight聚合能力
4. **让系统可上线** - 安全、测试、部署

### 1.2 架构原则

**不破坏已有能力:**
- 阶段三的所有Agent Flow和Skill必须继续正常工作
- 不改变已有的数据模型结构
- 新增能力通过扩展实现,而非替换

**最小化实现:**
- Search: 基于PostgreSQL全文搜索 + 可选向量搜索
- Ingestion: 支持URL和PDF两种来源
- Insight: 提供1-2种基础聚合类型

**可扩展性:**
- 预留扩展接口,便于阶段五增强
- 模块化设计,各能力可独立演进

### 1.3 技术选型

| 能力 | 技术选型 | 说明 |
|-----|---------|------|
| 搜索 | PostgreSQL Full-Text Search | 基础实现,可选pgvector |
| 向量 | pgvector (可选) | 语义搜索 |
| 爬虫 | requests + BeautifulSoup | URL抓取 |
| PDF解析 | PyPDF2 / pdfplumber | PDF文本提取 |
| 文本切分 | LangChain TextSplitter | 智能分块 |
| Insight | 聚合查询 + LLM摘要 | 基于现有数据 |

---

## 二、数据模型

### 2.1 统一搜索索引 (SearchIndex)

#### 模型定义

```python
class SearchIndex(Base):
    """统一搜索索引 - 支持多类型数据检索"""

    __tablename__ = "search_indices"

    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 索引对象
    item_type = Column(String(50), nullable=False, index=True)  # 'card', 'task', 'decision_point', 'note', etc.
    item_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 搜索内容
    title = Column(Text, nullable=False)
    content = Column(Text)
    tags = Column(JSON)  # ["tag1", "tag2"]

    # 元数据
    metadata = Column(JSON)  # {"author": "xxx", "workspace_id": "xxx", ...}

    # 向量嵌入 (可选)
    embedding = Column(JSON)  # [0.1, 0.2, ...] 或 pgvector向量类型

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 复合索引
    __table_args__ = (
        Index('ix_search_item_type_id', 'item_type', 'item_id'),
        Index('ix_search_created_at', 'created_at'),
        # PostgreSQL 全文搜索索引
        CheckConstraint('item_type IN ("card", "task", "note", "decision_point")', name='check_item_type'),
    )
```

#### 索引策略

```sql
-- PostgreSQL 全文搜索
CREATE INDEX ix_search_fulltext ON search_indices
USING gin(to_tsvector('english', title || ' ' || COALESCE(content, '')));

-- 复合查询索引
CREATE INDEX ix_search_type_created ON search_indices(item_type, created_at DESC);
```

#### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| item_type | String(50) | ✅ | 被索引的对象类型 |
| item_id | UUID | ✅ | 被索引的对象ID |
| title | Text | ✅ | 标题,用于搜索和展示 |
| content | Text | ⚠️ | 主要内容,全文搜索 |
| tags | JSON | ⚠️ | 标签列表,精确匹配 |
| metadata | JSON | ⚠️ | 其他元数据,过滤用 |
| embedding | JSON | ⚠️ | 向量嵌入,语义搜索 |

### 2.2 数据引入任务 (IngestionJob)

#### 模型定义

```python
class IngestionJob(Base):
    """数据引入任务 - 记录外部内容抓取"""

    __tablename__ = "ingestion_jobs"

    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 来源信息
    source_url = Column(String(500))
    source_type = Column(String(50), nullable=False)  # 'url', 'pdf', 'markdown'
    source_file_path = Column(String(500))  # 上传文件路径

    # 处理状态
    status = Column(String(20), default='pending', index=True)  # pending, running, completed, failed

    # 处理参数
    chunk_size = Column(Integer, default=1000)  # 文本切分大小
    overlap = Column(Integer, default=200)      # 重叠大小

    # 结果
    items_created = Column(Integer, default=0)
    item_ids = Column(JSON)  # [uuid1, uuid2, ...]

    # 错误信息
    error_message = Column(Text)
    error_stack = Column(Text)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # 关联用户
    created_by = Column(String(36), index=True)  # User UUID (兼容性设计)

    __table_args__ = (
        CheckConstraint('status IN ("pending", "running", "completed", "failed")', name='check_status'),
        CheckConstraint('source_type IN ("url", "pdf", "markdown")', name='check_source_type'),
    )
```

#### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| source_url | String(500) | ⚠️ | URL来源 |
| source_type | String(50) | ✅ | 来源类型 |
| source_file_path | String(500) | ⚠️ | 上传文件路径 |
| status | String(20) | ✅ | 任务状态 |
| chunk_size | Integer | ✅ | 切分块大小 |
| overlap | Integer | ✅ | 重叠大小 |
| items_created | Integer | ✅ | 创建的item数量 |
| item_ids | JSON | ⚠️ | 创建的item ID列表 |
| error_message | Text | ⚠️ | 错误信息 |
| created_by | String(36) | ⚠️ | 创建者ID |

### 2.3 洞察聚类 (InsightCluster)

#### 模型定义

```python
class InsightCluster(Base):
    """洞察聚类 - 对数据的聚合分析结果"""

    __tablename__ = "insight_clusters"

    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 聚类信息
    cluster_type = Column(String(50), nullable=False, index=True)  # 'summary', 'trend', 'topic', 'pattern'
    name = Column(String(200))
    description = Column(Text)

    # 来源数据
    source_item_type = Column(String(50))  # 'card', 'task', etc.
    source_item_ids = Column(JSON)  # [uuid1, uuid2, ...]
    date_range = Column(JSON)  # {"start": "2026-01-01", "end": "2026-01-31"}

    # 洞察输出
    insight_data = Column(JSON, nullable=False)  # 具体的洞察内容
    confidence = Column(Float)  # 置信度 0-1
    sample_count = Column(Integer)  # 样本数量

    # 元数据
    parameters = Column(JSON)  # 生成参数
    generated_by = Column(String(36))  # 生成者ID
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))  # 过期时间

    __table_args__ = (
        CheckConstraint('cluster_type IN ("summary", "trend", "topic", "pattern")', name='check_cluster_type'),
    )
```

#### Insight 数据结构示例

```json
{
  "cluster_type": "summary",
  "insight_data": {
    "total_items": 150,
    "summary_text": "本期主要关注产品设计和技术架构...",
    "key_topics": ["产品设计", "API设计", "数据库优化"],
    "sentiment": "positive"
  },
  "confidence": 0.85,
  "sample_count": 150
}

{
  "cluster_type": "trend",
  "insight_data": {
    "trend_name": "任务完成率",
    "values": [0.7, 0.75, 0.8, 0.82],
    "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
    "trend_direction": "up"
  },
  "confidence": 0.9,
  "sample_count": 200
}
```

### 2.4 数据模型关系图

```
SearchIndex
    ├─ item_type + item_id ─────> Card/Task/DecisionPoint (已有模型)
    └─ embedding (可选)

IngestionJob
    ├─ items_created ──────────> Card (创建的内容)
    └─ created_by ───────────────> User (已有模型)

InsightCluster
    ├─ source_item_ids ─────────> Card/Task (已有模型)
    └─ generated_by ─────────────> User (已有模型)
```

---

## 三、功能模块

### 3.1 统一搜索模块 (Search)

#### 3.1.1 功能概述

提供统一的搜索接口,支持对系统内多种数据类型(Card/Task/Note等)进行关键词搜索和语义搜索。

#### 3.1.2 核心功能

**A. 索引管理**

```python
class SearchService:
    """搜索服务"""

    async def index_item(
        self,
        item_type: str,
        item_id: str,
        title: str,
        content: str = None,
        tags: List[str] = None,
        metadata: Dict = None
    ) -> SearchIndex:
        """创建或更新搜索索引"""

    async def bulk_index_items(
        self,
        items: List[Dict]
    ) -> int:
        """批量创建索引"""

    async def delete_index(
        self,
        item_type: str,
        item_id: str
    ) -> bool:
        """删除索引"""

    async def rebuild_index(
        self,
        item_type: str = None
    ) -> int:
        """重建索引"""
```

**B. 搜索查询**

```python
class SearchQuery:
    """搜索查询参数"""

    query: str                    # 搜索关键词
    item_types: List[str]         # 过滤: 数据类型 ['card', 'task']
    tags: List[str]               # 过滤: 标签
    date_from: datetime            # 过滤: 起始时间
    date_to: datetime              # 过滤: 结束时间
    page: int = 1                 # 分页: 页码
    page_size: int = 20           # 分页: 每页大小
    sort_by: str = "relevance"     # 排序: relevance, date, -date
    include_vectors: bool = False  # 是否包含向量搜索
```

```python
class SearchResult:
    """搜索结果"""

    total: int                    # 总结果数
    page: int                     # 当前页
    page_size: int                # 每页大小
    results: List[SearchResultItem]  # 结果列表

class SearchResultItem:
    """单个搜索结果"""

    item_type: str
    item_id: str
    title: str
    content_snippet: str          # 内容摘要 (高亮关键词)
    score: float                  # 相关性得分
    tags: List[str]
    metadata: Dict
    created_at: datetime
```

**C. 搜索实现**

```python
class SearchEngine:
    """搜索引擎"""

    async def search(
        self,
        query: SearchQuery
    ) -> SearchResult:
        """执行搜索"""

        # 1. PostgreSQL 全文搜索
        if not query.include_vectors:
            return await self._text_search(query)

        # 2. 混合搜索 (文本 + 向量)
        else:
            text_results = await self._text_search(query)
            vector_results = await self._vector_search(query)
            return self._merge_results(text_results, vector_results)

    async def _text_search(
        self,
        query: SearchQuery
    ) -> SearchResult:
        """PostgreSQL 全文搜索"""

        # 使用 to_tsvector + tsquery
        # 支持中文分词 (zhparser)

    async def _vector_search(
        self,
        query: SearchQuery
    ) -> SearchResult:
        """向量语义搜索"""

        # 使用 pgvector <=> 余弦相似度
        # 返回 top-k

    def _merge_results(
        self,
        text_results: SearchResult,
        vector_results: SearchResult
    ) -> SearchResult:
        """合并文本和向量搜索结果"""

        # RRF (Reciprocal Rank Fusion) 算法
        # 或加权融合
```

#### 3.1.3 API设计

```
POST   /api/v1/search/index          # 创建索引
PUT    /api/v1/search/index/{id}     # 更新索引
DELETE /api/v1/search/index/{id}     # 删除索引
POST   /api/v1/search/rebuild        # 重建索引
GET    /api/v1/search                # 搜索
```

#### 3.1.4 技术实现要点

**PostgreSQL 全文搜索配置**

```sql
-- 安装中文分词插件
CREATE EXTENSION IF NOT EXISTS zhparser;

-- 创建文本搜索配置
CREATE TEXT SEARCH CONFIGURATION chinese_zh (COPY = simple);

-- 设置解析器
ALTER TEXT SEARCH CONFIGURATION chinese_zh
    PARSER = zhparser;

-- 索引示例
UPDATE search_indices
SET title_tsv = to_tsvector('chinese_zh', title),
    content_tsv = to_tsvector('chinese_zh', COALESCE(content, ''));

CREATE INDEX ix_search_title_tsv ON search_indices
USING gin(title_tsv);

CREATE INDEX ix_search_content_tsv ON search_indices
USING gin(content_tsv);
```

**向量搜索 (可选)**

```sql
-- 安装 pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 修改表结构
ALTER TABLE search_indices
ADD COLUMN embedding vector(1536);

-- 创建向量索引
CREATE INDEX ix_search_embedding ON search_indices
USING ivfflat (embedding vector_cosine_ops);
```

---

### 3.2 数据引入模块 (Ingestion)

#### 3.2.1 功能概述

支持从外部来源(URL/PDF)抓取内容,解析后写入系统,并自动创建搜索索引。

#### 3.2.2 核心功能

**A. 任务管理**

```python
class IngestionService:
    """数据引入服务"""

    async def create_job(
        self,
        source_type: str,
        source_url: str = None,
        source_file_path: str = None,
        chunk_size: int = 1000,
        overlap: int = 200,
        created_by: str = None
    ) -> IngestionJob:
        """创建引入任务"""

    async def start_job(
        self,
        job_id: str
    ) -> IngestionJob:
        """启动任务"""

    async def get_job_status(
        self,
        job_id: str
    ) -> Dict:
        """获取任务状态"""

    async def list_jobs(
        self,
        status: str = None,
        created_by: str = None,
        limit: int = 50
    ) -> List[IngestionJob]:
        """列出任务"""
```

**B. 内容抓取**

```python
class ContentFetcher:
    """内容抓取器"""

    async def fetch_url(
        self,
        url: str,
        timeout: int = 30
    ) -> str:
        """抓取URL内容"""

        # 使用 requests + asyncio
        # 支持:
        # - HTML: BeautifulSoup解析
        # - Markdown: 直接提取
        # - 纯文本: 直接提取

    async def fetch_pdf(
        self,
        file_path: str
    ) -> str:
        """提取PDF文本"""

        # 使用 PyPDF2 或 pdfplumber
        # 支持:
        # - 文本提取
        # - 多页合并
```

**C. 文本切分**

```python
class TextChunker:
    """文本切分器"""

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[str]:
        """切分文本"""

        # 使用 LangChain RecursiveCharacterTextSplitter
        # 按段落、句子优先切分

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap

        return chunks
```

**D. 数据写入**

```python
class IngestionPipeline:
    """数据引入流水线"""

    async def run(
        self,
        job: IngestionJob
    ) -> IngestionJob:
        """执行完整的引入流程"""

        # 1. 更新状态为 running
        job.status = "running"
        job.started_at = datetime.utcnow()

        try:
            # 2. 抓取内容
            if job.source_type == "url":
                content = await self.fetcher.fetch_url(job.source_url)
            elif job.source_type == "pdf":
                content = await self.fetcher.fetch_pdf(job.source_file_path)

            # 3. 切分文本
            chunks = self.chunker.chunk_text(
                content,
                job.chunk_size,
                job.overlap
            )

            # 4. 写入Card (或Note)
            item_ids = []
            for i, chunk in enumerate(chunks):
                card = Card(
                    title=f"{job.source_url} - Part {i+1}",
                    content=chunk,
                    para_type="ingested",
                    tags=["ingested", job.source_type],
                    source_inbox_item_id=job.id
                )
                self.db.add(card)
                await self.db.commit()
                item_ids.append(str(card.id))

                # 5. 创建搜索索引
                await self.search_service.index_item(
                    item_type="card",
                    item_id=str(card.id),
                    title=card.title,
                    content=card.content,
                    tags=card.tags
                )

            # 6. 更新状态为 completed
            job.status = "completed"
            job.items_created = len(item_ids)
            job.item_ids = item_ids
            job.completed_at = datetime.utcnow()

        except Exception as e:
            # 错误处理
            job.status = "failed"
            job.error_message = str(e)
            job.error_stack = traceback.format_exc()
            job.completed_at = datetime.utcnow()

        await self.db.commit()
        return job
```

#### 3.2.3 API设计

```
POST   /api/v1/ingestion/jobs               # 创建任务
POST   /api/v1/ingestion/jobs/{id}/start    # 启动任务
GET    /api/v1/ingestion/jobs/{id}          # 获取任务状态
GET    /api/v1/ingestion/jobs               # 列出任务
```

#### 3.2.4 请求/响应示例

**创建URL抓取任务**

```json
POST /api/v1/ingestion/jobs
{
  "source_type": "url",
  "source_url": "https://example.com/article",
  "chunk_size": 1000,
  "overlap": 200
}

Response 201:
{
  "id": "uuid",
  "source_type": "url",
  "source_url": "https://example.com/article",
  "status": "pending",
  "created_at": "2026-02-07T10:00:00Z"
}
```

**获取任务状态**

```json
GET /api/v1/ingestion/jobs/{id}

Response 200:
{
  "id": "uuid",
  "status": "completed",
  "items_created": 5,
  "item_ids": ["uuid1", "uuid2", ...],
  "started_at": "2026-02-07T10:00:00Z",
  "completed_at": "2026-02-07T10:01:00Z"
}
```

---

### 3.3 洞察分析模块 (Insight)

#### 3.3.1 功能概述

对系统内的数据进行聚合分析,生成结构化的洞察结果(总结、趋势、主题聚类等)。

#### 3.3.2 核心功能

**A. 洞察生成**

```python
class InsightService:
    """洞察服务"""

    async def generate_summary(
        self,
        item_type: str,
        item_ids: List[str] = None,
        date_range: Dict = None
    ) -> InsightCluster:
        """生成总结洞察"""

        # 1. 查询数据
        # 2. 使用LLM生成摘要
        # 3. 返回InsightCluster

    async def generate_trend(
        self,
        item_type: str,
        metric: str,  # "count", "completion_rate", etc.
        date_range: Dict,
        group_by: str = "day"  # "day", "week", "month"
    ) -> InsightCluster:
        """生成趋势洞察"""

        # 1. 按时间聚合数据
        # 2. 计算趋势方向
        # 3. 返回InsightCluster

    async def generate_topics(
        self,
        item_type: str,
        item_ids: List[str] = None,
        num_topics: int = 5
    ) -> InsightCluster:
        """生成主题聚类"""

        # 1. 提取文本内容
        # 2. 使用K-means或LLM聚类
        # 3. 返回主题分布
```

**B. 洞察查询**

```python
class InsightQuery:
    """洞察查询参数"""

    cluster_type: str           # 'summary', 'trend', 'topic'
    source_item_type: str       # 'card', 'task'
    source_item_ids: List[str]  # 特定items
    date_range: Dict            # {"start": "...", "end": "..."}
    limit: int = 10
    include_expired: bool = False
```

#### 3.3.3 实现示例

**总结洞察**

```python
async def generate_summary(
    self,
    item_type: str = "card",
    date_range: Dict = None
) -> InsightCluster:
    """生成内容总结"""

    # 1. 查询Card
    stmt = select(Card).where(
        Card.created_at >= date_range["start"],
        Card.created_at <= date_range["end"]
    ).limit(100)

    result = await self.db.execute(stmt)
    cards = result.scalars().all()

    # 2. 准备内容
    content_text = "\n\n".join([
        f"Title: {card.title}\nContent: {card.content}"
        for card in cards
    ])

    # 3. 调用LLM生成摘要
    summary = await self.llm_service.complete(
        prompt=f"""请总结以下内容,提取关键主题和趋势:

{content_text}

请以JSON格式返回:
{{
    "total_items": 数量,
    "summary_text": "总结内容",
    "key_topics": ["主题1", "主题2"],
    "sentiment": "positive/neutral/negative"
}}
"""
    )

    # 4. 创建InsightCluster
    insight = InsightCluster(
        cluster_type="summary",
        name=f"{item_type} summary",
        source_item_type=item_type,
        source_item_ids=[str(c.id) for c in cards],
        date_range=date_range,
        insight_data=summary,
        confidence=0.8,
        sample_count=len(cards)
    )

    self.db.add(insight)
    await self.db.commit()

    return insight
```

**趋势洞察**

```python
async def generate_trend(
    self,
    item_type: str = "task",
    metric: str = "count",
    date_range: Dict = None,
    group_by: str = "day"
) -> InsightCluster:
    """生成趋势分析"""

    # 1. 按日期聚合
    stmt = select(
        func.date(Item.created_at).label('date'),
        func.count(Item.id).label('count')
    ).where(
        Item.created_at >= date_range["start"],
        Item.created_at <= date_range["end"]
    ).group_by('date').order_by('date')

    result = await self.db.execute(stmt)
    rows = result.all()

    # 2. 提取数据
    labels = [str(row.date) for row in rows]
    values = [row.count for row in rows]

    # 3. 判断趋势
    if len(values) >= 2:
        if values[-1] > values[-2]:
            trend_direction = "up"
        elif values[-1] < values[-2]:
            trend_direction = "down"
        else:
            trend_direction = "stable"
    else:
        trend_direction = "unknown"

    # 4. 创建InsightCluster
    insight = InsightCluster(
        cluster_type="trend",
        name=f"{item_type} {metric} trend",
        source_item_type=item_type,
        insight_data={
            "trend_name": f"{metric} trend",
            "values": values,
            "labels": labels,
            "trend_direction": trend_direction
        },
        confidence=0.9,
        sample_count=sum(values)
    )

    self.db.add(insight)
    await self.db.commit()

    return insight
```

#### 3.3.4 API设计

```
POST   /api/v1/insights/generate         # 生成洞察
GET    /api/v1/insights                  # 列出洞察
GET    /api/v1/insights/{id}             # 获取洞察详情
DELETE /api/v1/insights/{id}             # 删除洞察
POST   /api/v1/insights/{id}/refresh     # 刷新洞察
```

#### 3.3.5 请求/响应示例

**生成总结洞察**

```json
POST /api/v1/insights/generate
{
  "cluster_type": "summary",
  "source_item_type": "card",
  "date_range": {
    "start": "2026-01-01T00:00:00Z",
    "end": "2026-01-31T23:59:59Z"
  }
}

Response 201:
{
  "id": "uuid",
  "cluster_type": "summary",
  "name": "card summary",
  "insight_data": {
    "total_items": 150,
    "summary_text": "本期主要关注产品设计...",
    "key_topics": ["产品", "技术", "设计"],
    "sentiment": "positive"
  },
  "confidence": 0.8,
  "sample_count": 150,
  "generated_at": "2026-02-07T10:00:00Z"
}
```

---

### 3.4 安全与权限模块

#### 3.4.1 功能概述

为新增的Search/Ingestion/Insight接口添加统一的输入校验和权限控制。

#### 3.4.2 核心功能

**A. 输入校验**

```python
from pydantic import BaseModel, Field, validator

class SearchQueryValidator(BaseModel):
    """搜索查询校验"""

    query: str = Field(..., min_length=1, max_length=200)
    item_types: List[str] = Field(
        default=["card", "task", "note"],
        max_items=5
    )
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="relevance")

    @validator('item_types')
    def validate_item_types(cls, v):
        valid_types = {"card", "task", "note", "decision_point"}
        for item_type in v:
            if item_type not in valid_types:
                raise ValueError(f"Invalid item_type: {item_type}")
        return v

class IngestionJobValidator(BaseModel):
    """引入任务校验"""

    source_type: str = Field(..., regex="^(url|pdf|markdown)$")
    source_url: str = Field(None, max_length=500)
    chunk_size: int = Field(default=1000, ge=100, le=10000)
    overlap: int = Field(default=200, ge=0, le=1000)

    @validator('source_url')
    def validate_source_url(cls, v, values):
        if values.get('source_type') == 'url' and not v:
            raise ValueError("source_url is required for url type")

        if v:
            # 简单URL格式校验
            if not v.startswith(('http://', 'https://')):
                raise ValueError("Invalid URL format")
        return v
```

**B. 权限控制**

```python
from agent_os.auth.dependencies import get_current_user

# 统一权限检查
async def check_search_permission(
    user: User,
    item_types: List[str]
):
    """检查搜索权限"""

    # 用户只能搜索自己有权限的数据
    # 例如: 同一个workspace的数据

    pass

async def check_ingestion_permission(
    user: User,
    source_type: str
):
    """检查引入权限"""

    # 只有特定角色可以引入外部数据
    # 或需要配额限制

    pass
```

**C. 速率限制**

```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/search")
@limiter.limit("60/minute")  # 每分钟60次
async def search(...):
    pass

@app.post("/api/v1/ingestion/jobs")
@limiter.limit("10/minute")  # 每分钟10次
async def create_ingestion_job(...):
    pass
```

---

## 四、API设计

### 4.1 统一搜索API

#### 创建索引

```
POST /api/v1/search/index

Request:
{
  "item_type": "card",
  "item_id": "uuid",
  "title": "Card Title",
  "content": "Card content...",
  "tags": ["tag1", "tag2"],
  "metadata": {"workspace_id": "uuid"}
}

Response 201:
{
  "id": "uuid",
  "item_type": "card",
  "item_id": "uuid",
  "created_at": "2026-02-07T10:00:00Z"
}
```

#### 搜索

```
GET /api/v1/search?query=关键词&type=card&tags=tag1&page=1&page_size=20

Response 200:
{
  "total": 150,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "item_type": "card",
      "item_id": "uuid",
      "title": "Card Title",
      "content_snippet": "匹配的内容摘要...",
      "score": 0.95,
      "tags": ["tag1", "tag2"],
      "metadata": {...},
      "created_at": "2026-02-07T10:00:00Z"
    }
  ]
}
```

### 4.2 Ingestion API

#### 创建任务

```
POST /api/v1/ingestion/jobs

Request:
{
  "source_type": "url",
  "source_url": "https://example.com/article",
  "chunk_size": 1000,
  "overlap": 200
}

Response 201:
{
  "id": "job-uuid",
  "source_type": "url",
  "source_url": "https://example.com/article",
  "status": "pending",
  "created_at": "2026-02-07T10:00:00Z"
}
```

#### 启动任务

```
POST /api/v1/ingestion/jobs/{id}/start

Response 200:
{
  "id": "job-uuid",
  "status": "running",
  "started_at": "2026-02-07T10:00:01Z"
}
```

#### 获取状态

```
GET /api/v1/ingestion/jobs/{id}

Response 200:
{
  "id": "job-uuid",
  "status": "completed",
  "items_created": 5,
  "item_ids": ["uuid1", "uuid2", ...],
  "started_at": "2026-02-07T10:00:01Z",
  "completed_at": "2026-02-07T10:01:00Z"
}
```

### 4.3 Insight API

#### 生成洞察

```
POST /api/v1/insights/generate

Request:
{
  "cluster_type": "summary",
  "source_item_type": "card",
  "date_range": {
    "start": "2026-01-01T00:00:00Z",
    "end": "2026-01-31T23:59:59Z"
  }
}

Response 201:
{
  "id": "insight-uuid",
  "cluster_type": "summary",
  "name": "card summary",
  "insight_data": {
    "total_items": 150,
    "summary_text": "本期主要关注...",
    "key_topics": ["产品", "技术"],
    "sentiment": "positive"
  },
  "confidence": 0.8,
  "sample_count": 150,
  "generated_at": "2026-02-07T10:00:00Z"
}
```

#### 列出洞察

```
GET /api/v1/insights?cluster_type=summary&limit=10

Response 200:
{
  "total": 25,
  "results": [
    {
      "id": "uuid",
      "cluster_type": "summary",
      "name": "card summary",
      "confidence": 0.8,
      "generated_at": "2026-02-07T10:00:00Z"
    }
  ]
}
```

---

## 五、Demo场景

### 5.1 场景一: 知识库搜索

**目标:** 展示统一搜索能力

**步骤:**

1. **准备数据**
   - 创建50个Cards,涵盖技术、产品、设计等主题
   - 自动创建搜索索引

2. **搜索测试**
   - 搜索关键词"API"
   - 验证返回相关结果
   - 测试过滤条件(按类型、标签、时间)

3. **验证点:**
   - ✅ 不同类型数据可通过同一接口检索
   - ✅ 搜索结果按相关性排序
   - ✅ 可追溯到原始Card

### 5.2 场景二: 文章抓取与索引

**目标:** 展示Ingestion能力

**步骤:**

1. **准备测试URL**
   - 选择3-5篇技术文章URL

2. **创建抓取任务**
   ```bash
   POST /api/v1/ingestion/jobs
   {
     "source_type": "url",
     "source_url": "https://example.com/article"
   }
   ```

3. **监控执行**
   - 查询任务状态
   - 验证创建的Cards数量
   - 检查搜索索引是否创建

4. **验证点:**
   - ✅ URL内容被成功抓取
   - ✅ 内容被切分并创建Cards
   - ✅ 搜索索引自动创建
   - ✅ 可通过搜索找到新内容

### 5.3 场景三: 周报生成

**目标:** 展示Insight能力

**步骤:**

1. **准备数据**
   - 确保系统内有100+条Cards/Items

2. **生成总结洞察**
   ```bash
   POST /api/v1/insights/generate
   {
     "cluster_type": "summary",
     "date_range": {
       "start": "2026-01-01",
       "end": "2026-01-07"
     }
   }
   ```

3. **生成趋势洞察**
   ```bash
   POST /api/v1/insights/generate
   {
     "cluster_type": "trend",
     "source_item_type": "task",
     "metric": "count"
   }
   ```

4. **验证点:**
   - ✅ 洞察数据来源明确
   - ✅ 输出结构化且可理解
   - ✅ 多次生成结果一致

---

## 六、测试要求

### 6.1 单元测试

**Search模块:**
- 索引创建/更新/删除
- 关键词搜索
- 分页和排序
- 向量搜索(可选)

**Ingestion模块:**
- URL抓取
- PDF解析
- 文本切分
- 完整Pipeline

**Insight模块:**
- 总结生成
- 趋势计算
- 主题聚类

### 6.2 集成测试

**端到端流程:**
- URL抓取 → 搜索 → 可检索
- 数据生成 → Insight → 可理解

### 6.3 回归测试

**验证不破坏已有功能:**
- 阶段三Demo场景仍可运行
- Agent Flow正常执行
- Skill CRUD正常工作

### 6.4 测试覆盖率目标

- 核心服务: >= 80%
- API路由: >= 70%
- 关键业务路径: 100%

---

## 七、部署与运维

### 7.1 Docker化

**Dockerfile更新**

```dockerfile
# 安装依赖
RUN apk add --no-cache \
    postgresql-client \
    curl

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装PostgreSQL扩展
RUN pip install --no-cache-dir \
    psycopg2-binary \
    pgvector  # 可选
```

### 7.2 CI/CD配置

**GitHub Actions示例**

```yaml
name: Stage 4 CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run tests
        run: |
          pytest tests/test_search_engine_*.py -v

      - name: Test coverage
        run: |
          pytest --cov=agent_os.search_engine --cov-report=xml
```

### 7.3 监控与日志

**关键指标:**

```
# Search
- 搜索响应时间 (p50, p95, p99)
- 搜索QPS
- 索引更新频率

# Ingestion
- 抓取成功率
- 平均处理时间
- 错误类型分布

# Insight
- 生成耗时
- 生成成功率
- Insight查询QPS
```

**日志规范:**

```python
import logging

logger = logging.getLogger(__name__)

# 统一日志格式
logger.info(
    "search_query_executed",
    extra={
        "query": query,
        "item_type": item_type,
        "results_count": len(results),
        "duration_ms": duration
    }
)
```

---

## 八、交付清单

### 8.1 新增代码文件

**数据模型:**
1. `src/agent_os/search_engine/models.py` - SearchIndex, IngestionJob, InsightCluster

**服务模块:**
2. `src/agent_os/search_engine/search_service.py` - 搜索服务
3. `src/agent_os/search_engine/ingestion_service.py` - 数据引入服务
4. `src/agent_os/search_engine/insight_service.py` - 洞察服务
5. `src/agent_os/search_engine/search_engine.py` - 搜索引擎
6. `src/agent_os/search_engine/content_fetcher.py` - 内容抓取
7. `src/agent_os/search_engine/text_chunker.py` - 文本切分

**API路由:**
8. `src/agent_os/search_engine/schema.py` - Pydantic schemas
9. `src/agent_os/search_engine/router.py` - FastAPI路由

**Demo:**
10. `src/agent_os/search_engine/demo_search.py` - 搜索Demo
11. `src/agent_os/search_engine/demo_ingestion.py` - 抓取Demo
12. `src/agent_os/search_engine/demo_insight.py` - 洞察Demo

### 8.2 测试文件

13. `tests/test_search_engine_models_unit.py`
14. `tests/test_search_service_unit.py`
15. `tests/test_ingestion_service_unit.py`
16. `tests/test_insight_service_unit.py`
17. `tests/test_search_engine_integration.py`

### 8.3 文档文件

18. `docs/search_engine-architecture.md` - 架构设计
19. `docs/search_engine-api-guide.md` - API使用指南
20. `docs/search_engine-deployment.md` - 部署文档
21. `docs/search_engine-progress-report.md` - 进度报告

### 8.4 配置文件

22. `.github/workflows/search_engine-ci.yml` - CI配置
23. `docker-compose.search_engine.yml` - Docker Compose配置
24. `requirements-search_engine.txt` - 新增依赖

---

## 九、实施时间表

### Week 1-2: 数据模型与基础设施

- 创建SearchIndex/IngestionJob/InsightCluster模型
- 配置PostgreSQL全文搜索
- 编写单元测试

### Week 3-4: Search模块

- 实现SearchService和SearchEngine
- 实现索引管理API
- 编写测试和Demo

### Week 5-6: Ingestion模块

- 实现ContentFetcher和TextChunker
- 实现IngestionPipeline
- 编写测试和Demo

### Week 7-8: Insight模块

- 实现InsightService
- 实现总结和趋势生成
- 编写测试和Demo

### Week 9-10: 集成与部署

- 端到端测试
- Docker化
- CI/CD配置
- 文档完善

### Week 11-12: 回归与优化

- 回归测试
- 性能优化
- Bug修复
- 验收准备

**总计:** 12周 (3个月)

---

## 十、依赖与风险

### 10.1 依赖项

**外部服务:**
- PostgreSQL 15+ (全文搜索)
- 可选: pgvector扩展
- 可选: OpenAI API (Insight生成)

**Python库:**
- requests, BeautifulSoup4 (爬虫)
- PyPDF2/pdfplumber (PDF)
- langchain (文本切分)
- slowapi (速率限制)

### 10.2 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|-----|------|------|---------|
| PostgreSQL性能不足 | 高 | 中 | 1. 限制索引大小<br>2. 添加缓存<br>3. 分表策略 |
| URL抓取失败 | 中 | 高 | 1. 超时机制<br>2. 重试策略<br>3. 错误隔离 |
| Insight生成慢 | 中 | 中 | 1. 异步生成<br>2. 缓存结果<br>3. 限制数据量 |
| 破坏已有功能 | 高 | 低 | 1. 回归测试<br>2. 特性开关<br>3. 灰度发布 |

---

## 十一、成功标准

阶段四视为成功交付,必须同时满足:

1. ✅ 所有数据模型实现并测试通过
2. ✅ Search/Ingestion/Insight API全部实现
3. ✅ 3个Demo场景可稳定运行
4. ✅ 单元测试覆盖率 >= 70%
5. ✅ 阶段三Demo场景仍正常运行
6. ✅ 系统可通过Docker部署
7. ✅ CI/CD流水线正常运行

---

**文档版本:** v1.0
**创建时间:** 2026-02-07
**维护者:** Claude Sonnet 4.5
**基于:** docs/acceptance/search_engine-acceptance-checklist.md
