# PRD4 实施开发计划

**文档版本:** V1.0
**创建日期:** 2026-02-06
**预计总工期:** 10-12 周
**团队配置:** 2-3 名全栈开发工程师

---

## 📋 目录

- [一、总体规划](#一总体规划)
- [二、阶段一：数据模型重构](#二阶段一数据模型重构-p0)
- [三、阶段二：混合搜索引擎](#三阶段二混合搜索引擎-p0)
- [四、阶段三：Connection计算引擎](#四阶段三connection计算引擎-p1)
- [五、阶段四：微信集成](#五阶段四微信集成-p1)
- [六、阶段五：Insight挖掘引擎](#六阶段五insight挖掘引擎-p2)
- [七、阶段六：可观测性与优化](#七阶段六可观测性与优化-p2)
- [八、测试与验收标准](#八测试与验收标准)
- [九、风险管理](#九风险管理)

---

## 一、总体规划

### 1.1 开发原则

- **渐进式重构:** 不破坏现有功能，逐步迁移
- **向后兼容:** 保留旧 API，新标记为 deprecated
- **测试先行:** 每个 feature 必须有单元测试
- **文档同步:** 代码与文档同步更新

### 1.2 里程碑规划

| 里程碑 | 周期 | 交付物 | 状态 |
|--------|------|--------|------|
| M1: 数据模型重构 | Week 1-3 | 统一 Items 表、审计表 | 🔴 未开始 |
| M2: 混合搜索 | Week 4-5 | 混合搜索 API | 🔴 未开始 |
| M3: Connection 引擎 | Week 6-8 | 连接计算服务 | 🔴 未开始 |
| M4: 微信集成 | Week 9 | 微信 Webhook | 🔴 未开始 |
| M5: Insight 引擎 | Week 10-11 | 洞察挖掘服务 | 🔴 未开始 |
| M6: 优化与部署 | Week 12 | 性能优化、监控 | 🔴 未开始 |

### 1.3 技术栈确认

```yaml
后端框架: FastAPI 0.115+
数据库: PostgreSQL 14+ (pgvector)
Python: 3.11+
向量搜索: pgvector + sentence-transformers
异步任务: Celery + Redis
监控: Prometheus + Grafana
日志: structlog
测试: pytest + pytest-asyncio
```

### 1.4 分支策略

```bash
main              # 生产分支
├── develop       # 开发主分支
│   ├── feature/items-table          # Feature: 统一 Items 表
│   ├── feature/hybrid-search        # Feature: 混合搜索
│   ├── feature/connection-engine    # Feature: Connection 引擎
│   ├── feature/wechat-integration   # Feature: 微信集成
│   ├── feature/insight-miner        # Feature: Insight 挖掘
│   └── feature/observability        # Feature: 可观测性
```

---

## 二、阶段一：数据模型重构 (P0)

**周期:** Week 1-3 (3周)
**优先级:** 🔴 P0 - 最高优先级
**依赖:** 无
**负责人:** Backend Lead + 1 Backend Developer

### 2.1 目标

1. 创建统一的 `items` 表替代现有的 `cards` 和 `tasks` 表
2. 实现审计系统 (`decision_points`, `ledger_events`)
3. 创建 Area 和 Project 层次结构
4. 数据迁移脚本

### 2.2 详细任务

#### Task 1.1: 设计统一数据模型 (3天)

**负责人:** Backend Lead

**子任务:**

```yaml
- [ ] 1.1.1 设计 items 表结构 (4h)
  文件: src/agent_os/knowledge/models.py -> Item
  字段:
    - id: UUID (PK)
    - workspace_id: UUID (FK -> workspaces.id)
    - creator_id: UUID (FK -> users.id)
    - type: Enum('note', 'task', 'resource', 'plan', 'insight')
    - title: Text
    - content: Text
    - summary: Text (nullable)
    - embedding: VECTOR(1536) (nullable)
    - area_id: UUID (FK -> areas.id, nullable)
    - project_id: UUID (FK -> projects.id, nullable)
    - source_type: VARCHAR(20) (nullable)
    - source_meta: JSONB (default {})
    - status: VARCHAR(20) (default 'active')
    - created_at: TIMESTAMP
    - updated_at: TIMESTAMP
  索引:
    - idx_items_workspace_user: (workspace_id, creator_id)
    - idx_items_type: (type)
    - idx_items_area: (area_id)
    - idx_items_project: (project_id)
    - idx_items_embedding: ivfflat (embedding)

- [ ] 1.1.2 设计 areas 表结构 (2h)
  文件: src/agent_os/workspaces/models.py -> Area
  字段:
    - id: UUID (PK)
    - workspace_id: UUID (FK)
    - name: VARCHAR(100)
    - description: TEXT
    - color: VARCHAR(7) (hex color)
    - icon: VARCHAR(50)
    - parent_id: UUID (nullable, for sub-areas)
    - sort_order: INTEGER (default 0)
    - created_at: TIMESTAMP
  索引: idx_areas_workspace, idx_areas_parent

- [ ] 1.1.3 设计 projects 表结构 (2h)
  文件: src/agent_os/workspaces/models.py -> Project
  字段:
    - id: UUID (PK)
    - workspace_id: UUID (FK)
    - area_id: UUID (FK -> areas.id)
    - name: VARCHAR(100)
    - description: TEXT
    - status: Enum('active', 'archived', 'completed')
    - start_date: DATE (nullable)
    - end_date: DATE (nullable)
    - created_at: TIMESTAMP
  索引: idx_projects_workspace, idx_projects_area

- [ ] 1.1.4 设计 decision_points 表结构 (2h)
  文件: src/agent_os/tasks/models.py -> DecisionPoint
  字段:
    - id: UUID (PK)
    - task_id: UUID (FK -> items.id)
    - type: Enum('selection', 'info', 'boundary')
    - options: JSONB (default [])
    - user_choice: UUID (nullable)
    - confirmed_at: TIMESTAMP (nullable)
    - created_at: TIMESTAMP
  索引: idx_decision_points_task

- [ ] 1.1.5 设计 ledger_events 表结构 (2h)
  文件: src/agent_os/tasks/models.py -> LedgerEvent
  字段:
    - id: UUID (PK)
    - task_id: UUID (FK -> items.id)
    - event_type: VARCHAR(50)
    - snapshot: JSONB
    - created_at: TIMESTAMP
  索引: idx_ledger_events_task

- [ ] 1.1.6 设计 graph_edges 表结构 (2h)
  文件: src/agent_os/connections/models.py -> GraphEdge
  字段:
    - id: UUID (PK)
    - from_node_id: UUID (FK -> items.id)
    - to_node_id: UUID (FK -> items.id)
    - weight: FLOAT (default 0.0)
    - relation_type: Enum('topic', 'causal', 'supplement')
    - is_strong: BOOLEAN (default False)
    - created_at: TIMESTAMP
  索引:
    - idx_graph_from: (from_node_id)
    - idx_graph_to: (to_node_id)
    - idx_graph_strong: (is_strong)
    - unique_edge: UNIQUE(from_node_id, to_node_id)

- [ ] 1.1.7 创建 Alembic 迁移脚本 (4h)
  文件: alembic/versions/001_create_unified_items.py
  操作:
    - 创建 workspaces 表
    - 创建 areas 表
    - 创建 projects 表
    - 创建 items 表
    - 创建 decision_points 表
    - 创建 ledger_events 表
    - 创建 graph_edges 表
```

**验收标准:**
- [ ] 所有模型定义完成
- [ ] Alembic 迁移脚本通过 `alembic upgrade head`
- [ ] 可以成功创建表结构和索引
- [ ] 单元测试覆盖所有模型

---

#### Task 1.2: 实现 CRUD 操作 (5天)

**负责人:** Backend Developer

**子任务:**

```yaml
- [ ] 1.2.1 实现 Item CRUD (8h)
  文件: src/agent_os/items/crud.py
  函数:
    - async def create_item(...)
    - async def get_item(item_id: UUID)
    - async def update_item(item_id: UUID, ...)
    - async def delete_item(item_id: UUID)
    - async def list_items(
        workspace_id: UUID,
        type: Optional[Item_Type],
        area_id: Optional[UUID],
        project_id: Optional[UUID],
        page: int = 1,
        page_size: int = 20
      )
  测试: tests/test_items_crud.py

- [ ] 1.2.2 实现 Area CRUD (4h)
  文件: src/agent_os/workspaces/crud.py
  函数:
    - async def create_area(...)
    - async def get_area(area_id: UUID)
    - async def update_area(...)
    - async def delete_area(area_id: UUID)
    - async def list_areas(workspace_id: UUID)
    - async def get_area_tree(workspace_id: UUID)  # 递归查询
  测试: tests/test_areas_crud.py

- [ ] 1.2.3 实现 Project CRUD (4h)
  文件: src/agent_os/workspaces/crud.py
  函数:
    - async def create_project(...)
    - async def get_project(project_id: UUID)
    - async def update_project(...)
    - async def delete_project(project_id: UUID)
    - async def list_projects(
        workspace_id: UUID,
        area_id: Optional[UUID]
      )
  测试: tests/test_projects_crud.py

- [ ] 1.2.4 实现 DecisionPoint CRUD (4h)
  文件: src/agent_os/tasks/crud.py (扩展)
  函数:
    - async def create_decision_point(...)
    - async def get_decision_points(task_id: UUID)
    - async def confirm_decision(
        decision_id: UUID,
        user_choice: UUID
      )
  测试: tests/test_decision_points_crud.py

- [ ] 1.2.5 实现 LedgerEvent 记录 (4h)
  文件: src/agent_os/tasks/audit.py
  函数:
    - async def record_agent_suggestion(
        task_id: UUID,
        suggestion: dict
      )
    - async def record_user_confirmation(
        task_id: UUID,
        decision: dict
      )
    - async def record_deliverable_generated(
        task_id: UUID,
        deliverable: dict
      )
    - async def get_task_ledger(task_id: UUID)
  约束: 只增不改 (在应用层实现)
  测试: tests/test_ledger_events.py

- [ ] 1.2.6 实现 GraphEdge CRUD (4h)
  文件: src/agent_os/connections/crud.py
  函数:
    - async def create_edge(...)
    - async def get_edges(node_id: UUID)
    - async def get_strong_connections(node_id: UUID)
    - async def delete_edge(edge_id: UUID)
  测试: tests/test_graph_edges_crud.py

- [ ] 1.2.7 实现 API 路由 (8h)
  文件:
    - src/agent_os/items/router.py
    - src/agent_os/workspaces/router.py
    - src/agent_os/connections/router.py
  端点:
    - POST   /items                 # 创建 Item
    - GET    /items/{id}            # 获取 Item
    - PUT    /items/{id}            # 更新 Item
    - DELETE /items/{id}            # 删除 Item
    - GET    /items                 # 列表 Item
    - POST   /areas                 # 创建 Area
    - GET    /areas                 # 列表 Area
    - GET    /areas/{id}/tree       # Area 树
    - POST   /projects              # 创建 Project
    - GET    /projects              # 列表 Project
    - GET    /connections/{node_id} # 查询连接
  测试: tests/test_api_routes.py
```

**验收标准:**
- [ ] 所有 CRUD 函数实现完成
- [ ] API 端点响应时间 < 200ms
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过

---

#### Task 1.3: 数据迁移脚本 (4天)

**负责人:** Backend Lead

**子任务:**

```yaml
- [ ] 1.3.1 编写 cards -> items 迁移脚本 (8h)
  文件: migrations/migrate_cards_to_items.py
  逻辑:
    1. 读取所有 cards
    2. 转换为 items:
       - type = 'note'
       - 保留 title, content, embedding
       - para_type -> tags
    3. 批量插入 items 表
    4. 验证数据完整性
  测试:
    - 在测试数据库运行
    - 对比迁移前后数据量
    - 验证 embedding 数据

- [ ] 1.3.2 编写 tasks -> items 迁移脚本 (6h)
  文件: migrations/migrate_tasks_to_items.py
  逻辑:
    1. 读取所有 tasks
    2. 转换为 items:
       - type = 'task'
       - title -> title
       - description -> content
       - 新增字段: goal, constraints, risk_level
       - execution_status 映射:
         - pending -> draft
         - in_progress -> executing
         - completed -> done
    3. 批量插入 items 表
    4. 保留原 tasks 表 (重名为 tasks_legacy)
  测试: 同上

- [ ] 1.3.3 编写回滚脚本 (4h)
  文件: migrations/rollback_items_migration.py
  逻辑:
    1. 删除 items 表数据
    2. 恢复 tasks_legacy -> tasks
    3. 验证回滚成功

- [ ] 1.3.4 灰度迁移方案 (6h)
  文件: migrations/gray_migration.py
  策略:
    1. 双写模式: 同时写 cards/tasks 和 items
    2. 双读模式: 优先读 items, 降级读 cards/tasks
    3. 切换开关: features.USE_ITEMS_TABLE
  实现:
    - 中间件层自动路由
    - 监控数据一致性
    - 自动告警

- [ ] 1.3.5 迁移验证工具 (4h)
  文件: migrations/validate_migration.py
  功能:
    - 对比迁移前后记录数
    - 随机抽样对比数据内容
    - 验证外键关系
    - 生成验证报告

- [ ] 1.3.6 生产环境迁移计划 (2h)
  文件: migrations/PRODUCTION_MIGRATION_PLAN.md
  内容:
    - 前置检查项
    - 迁移时间窗口 (凌晨 2-4 点)
    - 回滚预案
    - 值班安排
```

**验收标准:**
- [ ] 迁移脚本在测试环境通过
- [ ] 数据完整性验证 100% 通过
- [ ] 回滚脚本测试成功
- [ ] 灰度迁移方案通过评审

---

#### Task 1.4: 文档与培训 (2天)

**负责人:** Backend Lead

**子任务:**

```yaml
- [ ] 1.4.1 编写数据模型文档 (4h)
  文件: docs/DATA_MODEL_V2.md
  内容:
    - ER 图
    - 表结构说明
    - 字段含义
    - 索引策略
    - 查询示例

- [ ] 1.4.2 编写迁移操作手册 (3h)
  文件: docs/MIGRATION_GUIDE.md
  内容:
    - 迁移步骤
    - 验证方法
    - 回滚操作
    - 故障排查

- [ ] 1.4.3 更新 API 文档 (3h)
  文件: docs/API_V2_CHANGES.md
  内容:
    - 新增端点
    - 废弃端点
    - 参数变更
    - 响应格式变更

- [ ] 1.4.4 团队培训 (2h)
  形式: 技术分享会
  内容:
    - 新数据模型介绍
    - 迁移方案说明
    - Q&A
```

**验收标准:**
- [ ] 文档完整清晰
- [ ] 团队成员理解新模型
- [ ] API 文档自动生成 (OpenAPI)

---

### 2.3 里程碑检查点

**Week 3 结束时检查:**

```yaml
- [ ] items 表创建成功,包含所有字段
- [ ] areas 和 projects 表创建成功
- [ ] 审计表 (decision_points, ledger_events) 创建成功
- [ ] graph_edges 表创建成功
- [ ] 所有 CRUD API 实现完成
- [ ] 单元测试覆盖率 > 80%
- [ ] 迁移脚本准备就绪
- [ ] 文档完成
- [ ] 代码审查通过
```

---

## 三、阶段二：混合搜索引擎 (P0)

**周期:** Week 4-5 (2周)
**优先级:** 🔴 P0 - 最高优先级
**依赖:** 阶段一完成
**负责人:** Backend Developer + Algorithm Engineer

### 3.1 目标

1. 实现关键词搜索 (BM25)
2. 实现并行召回机制
3. 实现融合排序算法 (0.7/0.3 + Freshness)
4. 实现结果高亮

### 3.2 详细任务

#### Task 2.1: 数据库准备 (2天)

```yaml
- [ ] 2.1.1 添加 tsvector 列 (3h)
  SQL:
    ALTER TABLE items ADD COLUMN content_tsv tsvector;
    ALTER TABLE items ADD COLUMN title_tsv tsvector;

- [ ] 2.1.2 创建 GIN 索引 (2h)
  SQL:
    CREATE INDEX idx_items_content_tsv
    ON items USING GIN(content_tsv);
    CREATE INDEX idx_items_title_tsv
    ON items USING GIN(title_tsv);

- [ ] 2.1.3 创建更新触发器 (3h)
  SQL:
    CREATE OR REPLACE FUNCTION items_tsv_update()
    RETURNS trigger AS $$
    BEGIN
      NEW.content_tsv :=
        to_tsvector('english', coalesce(NEW.content, ''));
      NEW.title_tsv :=
        to_tsvector('english', coalesce(NEW.title, ''));
      RETURN NEW;
    END
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER items_tsv_trigger
    BEFORE INSERT OR UPDATE ON items
    FOR EACH ROW EXECUTE FUNCTION items_tsv_update();

- [ ] 2.1.4 回填现有数据 (2h)
  Python:
    - 批量更新现有 items 的 tsv 字段
    - 使用 asyncio 批处理

- [ ] 2.1.5 性能测试 (2h)
  - 1000 条记录搜索性能
  - 10000 条记录搜索性能
  - 优化索引配置
```

**验收标准:**
- [ ] tsvector 列添加成功
- [ ] GIN 索引创建成功
- [ ] 触发器自动更新生效
- [ ] 现有数据回填完成
- [ ] 搜索性能 < 100ms (10000 条)

---

#### Task 2.2: 关键词搜索实现 (3天)

```yaml
- [ ] 2.2.1 实现 BM25 搜索 (6h)
  文件: src/agent_os/search/keyword_search.py
  类: KeywordSearchService
  方法:
    async def search(
        self,
        db: AsyncSession,
        query: str,
        workspace_id: UUID,
        limit: int = 50
      ) -> List[KeywordResult]
  逻辑:
    1. 解析 query 为 tsquery
    2. 执行 ts_rank 搜索
    3. 返回 Top 50 结果
  SQL:
    SELECT id, title, content,
           ts_rank(content_tsv, query) as score
    FROM items
    WHERE workspace_id = :workspace_id
      AND content_tsv @@ to_tsquery('english', :query)
    ORDER BY score DESC
    LIMIT :limit

- [ ] 2.2.2 查询优化 (4h)
  - 添加查询缓存 (Redis)
  - 实现查询结果预取
  - 优化查询计划

- [ ] 2.2.3 高亮实现 (4h)
  文件: src/agent_os/search/highlighter.py
  类: Highlighter
  方法:
    def highlight(
        self,
        text: str,
        query: str,
        max_length: int = 200
      ) -> str
  逻辑:
    1. 使用 ts_headline 函数
    2. 标记匹配关键词 <mark>...</mark>
    3. 截取上下文片段

- [ ] 2.2.4 单元测试 (2h)
  文件: tests/test_keyword_search.py
  测试用例:
    - 基础搜索
    - 短语搜索
    - 布尔搜索 (AND/OR/NOT)
    - 高亮功能
```

**验收标准:**
- [ ] BM25 搜索正确率 > 90%
- [ ] 搜索响应时间 < 100ms
- [ ] 高亮功能正确显示
- [ ] 单元测试通过

---

#### Task 2.3: 混合搜索融合 (4天)

```yaml
- [ ] 2.3.1 实现并行召回 (6h)
  文件: src/agent_os/search/hybrid_search.py
  类: HybridSearchService
  方法:
    async def parallel_recall(
        self,
        db: AsyncSession,
        query: str,
        workspace_id: UUID
      ) -> Tuple[List[SemanticResult], List[KeywordResult]]
  逻辑:
    1. 使用 asyncio.gather 并行执行
    2. 语义搜索 Top 50
    3. 关键词搜索 Top 50
    4. 返回两个结果集

- [ ] 2.3.2 实现融合排序算法 (8h)
  方法:
    def merge_and_rank(
        self,
        semantic_results: List[SemanticResult],
        keyword_results: List[KeywordResult],
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
      ) -> List[HybridResult]
  逻辑:
    1. 归一化分数到 [0, 1]
    2. 加权融合: score = w1*semantic + w2*keyword
    3. 添加新鲜度加权:
       freshness = 1 / (1 + days_since_update / 30)
       final_score = score * (1 + 0.1 * freshness)
    4. 排序返回 Top 20

- [ ] 2.3.3 实现空查询处理 (2h)
  方法:
    async def handle_empty_query(
        self,
        db: AsyncSession,
        workspace_id: UUID,
        limit: int = 20
      ) -> List[Item]
  逻辑:
    - 按 updated_at DESC 返回
    - 限制 workspace 范围

- [ ] 2.3.4 实现搜索 API (4h)
  文件: src/agent_os/search/router.py
  端点: POST /search/hybrid
  请求:
    {
      "query": "str",
      "workspace_id": "uuid",
      "filters": {
        "type": ["note", "task"],
        "area_id": "uuid",
        "project_id": "uuid"
      },
      "limit": 20
    }
  响应:
    {
      "results": [
        {
          "item_id": "uuid",
          "title": "str",
          "snippet": "str with highlights",
          "score": 0.85,
          "match_type": "hybrid|semantic|keyword"
        }
      ],
      "total": 150,
      "search_time_ms": 45
    }

- [ ] 2.3.5 性能优化 (4h)
  - 添加查询缓存
  - 实现结果预取
  - 优化数据库查询
  - 添加性能监控

- [ ] 2.3.6 集成测试 (2h)
  文件: tests/test_hybrid_search.py
  测试用例:
    - 混合搜索正确性
    - 融合排序验证
    - 性能基准测试
    - 并发测试
```

**验收标准:**
- [ ] 混合搜索准确率 > 单一搜索 15%
- [ ] P95 响应时间 < 500ms
- [ ] 并发 100 QPS 性能不降级
- [ ] 缓存命中率 > 30%

---

#### Task 2.4: 文档与部署 (1天)

```yaml
- [ ] 2.4.1 更新 API 文档 (2h)
- [ ] 2.4.2 编写搜索使用指南 (2h)
- [ ] 2.4.3 性能测试报告 (2h)
- [ ] 2.4.4 部署到测试环境 (2h)
```

---

### 3.3 里程碑检查点

**Week 5 结束时检查:**

```yaml
- [ ] BM25 关键词搜索实现
- [ ] 并行召回机制实现
- [ ] 融合排序算法实现
- [ ] 结果高亮功能实现
- [ ] 混合搜索 API 部署
- [ ] 性能指标达标 (P95 < 500ms)
- [ ] 集成测试通过
```

---

## 四、阶段三：Connection计算引擎 (P1)

**周期:** Week 6-8 (3周)
**优先级:** 🟡 P1 - 高优先级
**依赖:** 阶段一、阶段二完成
**负责人:** Algorithm Engineer + Backend Developer

### 4.1 目标

1. 实现 5 维度连接计算
2. 实现异步 Worker 框架
3. 实现 Connection 事件监听
4. 实现强连接查询 API

### 4.2 详细任务

#### Task 3.1: 计算引擎核心 (5天)

```yaml
- [ ] 3.1.1 实现 ConnectionEngine 类 (12h)
  文件: src/agent_os/connections/engine.py
  类: ConnectionEngine

  方法:
    async def calculate_score(
        self,
        item_a: Item,
        item_b: Item
      ) -> float

  5 维度计算:
    1. vector_similarity (40%)
       - 余弦相似度
       - 使用 embedding 字段

    2. keyword_overlap (20%)
       - Jaccard 系数
       - 提取关键词 (TF-IDF)
       - 计算重叠度

    3. entity_overlap (20%)
       - NER 提取实体
       - 人名、地名、组织名
       - 计算重叠度

    4. is_same_area (10%)
       - 布尔值
       - area_id 相同返回 1.0

    5. time_decay (10%)
       - 指数衰减
       - exp(-|days| / 30)
       - 30 天半衰期

  配置:
    THRESHOLD = 0.75  # 强连接阈值

- [ ] 3.1.2 实现关键词提取 (4h)
  文件: src/agent_os/connections/extractors.py
  方法:
    def extract_keywords(text: str, top_k: int = 10)
  算法: TF-IDF 或 YAKE

- [ ] 3.1.3 实现实体提取 (6h)
  文件: src/agent_os/connections/extractors.py
  方法:
    def extract_entities(text: str) -> List[str]
  工具: spaCy 或 Hugging Face NER

- [ ] 3.1.4 单元测试 (4h)
  文件: tests/test_connection_engine.py
  测试用例:
    - 各维度计算正确性
    - 边界条件测试
    - 性能测试
```

**验收标准:**
- [ ] 5 维度计算实现完成
- [ ] 计算结果可复现
- [ ] 单次计算时间 < 100ms

---

#### Task 3.2: 异步 Worker 框架 (5天)

```yaml
- [ ] 3.2.1 搭建 Celery 框架 (6h)
  文件:
    - src/agent_os/worker/celery_app.py
    - src/agent_os/worker/config.py

  配置:
    - broker: Redis
    - backend: Redis
    - worker: 4 并发
    - task_timeout: 300s

- [ ] 3.2.2 实现事件监听 (8h)
  文件: src/agent_os/connections/listeners.py
  类: ItemEventListener

  监听事件:
    - item.created
    - item.updated

  Celery 任务:
    @celery_app.task
    async def on_item_created(item_id: UUID)
      1. 获取新 Item
      2. 查询候选 Items (同 workspace, 最近30天)
      3. 并行计算相似度
      4. 创建强连接

- [ ] 3.2.3 实现候选查询优化 (4h)
  - 限制候选集大小 (最多 1000)
  - 使用索引加速
  - 分批处理

- [ ] 3.2.4 实现增量计算 (4h)
  - 仅计算新/变化的 Item
  - 避免全量重算
  - 使用缓存

- [ ] 3.2.5 实现批量重算 (4h)
  文件: src/agent_os/connections/batch_recalc.py
  用途: 全量重算连接
  策略:
    - 定时任务 (每周日凌晨)
    - 手动触发
    - 增量更新

- [ ] 3.2.6 监控与告警 (2h)
  - 任务队列长度
  - 任务执行时间
  - 失败告警

- [ ] 3.2.7 集成测试 (2h)
  文件: tests/test_connection_worker.py
```

**验收标准:**
- [ ] Worker 稳定运行
- [ ] 事件处理延迟 < 5s
- [ ] 失败任务自动重试

---

#### Task 3.3: Connection API (3天)

```yaml
- [ ] 3.3.1 实现连接查询 API (6h)
  文件: src/agent_os/connections/router.py
  端点:
    - GET /connections/{node_id}
      查询某个节点的所有连接

    - GET /connections/{node_id}/strong
      仅查询强连接

    - GET /connections/{node_id}/path/{target_id}
      查询两节点间最短路径

  响应:
    {
      "node_id": "uuid",
      "connections": [
        {
          "target_id": "uuid",
          "weight": 0.85,
          "relation_type": "topic",
          "is_strong": true
        }
      ],
      "strong_count": 15
    }

- [ ] 3.3.2 实现连接可视化数据 (4h)
  端点: GET /connections/{node_id}/graph
  响应:
    {
      "nodes": [{"id": "...", "label": "...", "type": "..."}],
      "edges": [{"from": "...", "to": "...", "weight": 0.8}]
    }

- [ ] 3.3.3 实现手动触发连接计算 (2h)
  端点: POST /connections/recalculate
  请求: {"item_id": "uuid"}

- [ ] 3.3.4 集成测试 (2h)
```

**验收标准:**
- [ ] API 响应时间 < 200ms
- [ ] 支持分页查询
- [ ] 集成测试通过

---

#### Task 3.4: 文档与优化 (2天)

```yaml
- [ ] 3.4.1 算法文档 (4h)
- [ ] 3.4.2 API 文档 (2h)
- [ ] 3.4.3 性能优化 (6h)
  - 批量计算优化
  - 缓存策略
  - 数据库索引优化
- [ ] 3.4.4 监控面板 (4h)
```

---

### 4.3 里程碑检查点

**Week 8 结束时检查:**

```yaml
- [ ] Connection 计算引擎实现
- [ ] 异步 Worker 稳定运行
- [ ] Connection API 部署
- [ ] 强连接查询准确
- [ ] 性能指标达标
```

---

## 五、阶段四：微信集成 (P1)

**周期:** Week 9 (1周)
**优先级:** 🟡 P1 - 高优先级
**依赖:** 阶段一完成
**负责人:** Backend Developer

### 5.1 详细任务

```yaml
- [ ] 4.1.1 实现微信 Webhook 接收 (4h)
  文件: src/agent_os/integrations/wechat.py
  端点: POST /webhook/wechat
  功能:
    - 接收微信 XML/JSON
    - 验证签名
    - 解析消息

- [ ] 4.1.2 实现链接提取 (3h)
  - 正则表达式提取 URL
  - 支持多种 URL 格式

- [ ] 4.1.3 实现网页爬虫 (8h)
  文件: src/agent_os/integrations/crawler.py
  功能:
    - 抓取网页
    - 提取元数据
    - 下载封面图
  依赖: aiohttp, BeautifulSoup

- [ ] 4.1.4 实现 Resource Item 创建 (4h)
  - 映射微信消息到 Item
  - 打标签: "来自微信"
  - 自动向量化

- [ ] 4.1.5 实现消息推送 (4h)
  - 主动推送消息到微信
  - 发送"今日洞察"摘要

- [ ] 4.1.6 集成测试 (2h)
  文件: tests/test_wechat_integration.py

- [ ] 4.1.7 部署文档 (2h)
```

---

## 六、阶段五：Insight挖掘引擎 (P2)

**周期:** Week 10-11 (2周)
**优先级:** 🟢 P2 - 中优先级
**依赖:** 阶段一、阶段三完成
**负责人:** Algorithm Engineer

### 6.1 详细任务

```yaml
- [ ] 5.1.1 设计 Insight 数据模型 (2h)
  扩展 items 表, type='insight'
  新增字段:
    - claim: Text
    - rationale: Text
    - implications: JSONB
    - claim_hash: VARCHAR(64)
    - source_refs: UUID[]

- [ ] 5.1.2 实现 LLM 抽象 (8h)
  文件: src/agent_os/insights/miner.py
  Prompt 模板:
    - 输入: 高密度连接集群
    - 输出: Claim, Rationale, Implications

- [ ] 5.1.3 实现 Canonical Hash 去重 (4h)
  - 归一化 Claim
  - 计算 Hash
  - 防止重复

- [ ] 5.1.4 实现挖掘触发器 (6h)
  - 事件触发: 新增强连接时
  - 定时触发: 每周
  - 手动触发

- [ ] 5.1.5 实现 Insight CRUD (4h)
  - 创建、查询、更新、删除
  - 关联 Source Items

- [ ] 5.1.6 Insight API (4h)
  端点:
    - GET /insights
    - POST /insights/{id}/approve
    - POST /insights/mine

- [ ] 5.1.7 集成测试 (2h)
```

---

## 七、阶段六：可观测性与优化 (P2)

**周期:** Week 12 (1周)
**优先级:** 🟢 P2 - 中优先级
**依赖:** 所有前置阶段完成
**负责人:** DevOps Engineer

### 7.1 详细任务

```yaml
- [ ] 6.1.1 实现 Request ID 追踪 (4h)
  - 中间件注入
  - 日志上下文
  - 跨服务传递

- [ ] 6.1.2 实现 LLM Token 日志 (4h)
  - 记录 Input/Output Tokens
  - 计算成本
  - 成本分析 Dashboard

- [ ] 6.1.3 性能监控 (6h)
  - Prometheus 指标
  - Grafana 面板
  - 告警规则

- [ ] 6.1.4 日志聚合 (4h)
  - structlog 配置
  - ELK 集成

- [ ] 6.1.5 性能优化 (6h)
  - 数据库查询优化
  - 缓存策略优化
  - API 响应优化

- [ ] 6.1.6 压力测试 (4h)
  - 并发测试
  - 性能基准
```

---

## 八、测试与验收标准

### 8.1 单元测试要求

```yaml
覆盖率要求:
  - 核心模块: > 90%
  - CRUD 模块: > 80%
  - API 层: > 70%

测试工具:
  - pytest
  - pytest-asyncio
  - pytest-cov
  - faker (生成测试数据)
```

### 8.2 集成测试要求

```yaml
- [ ] API 端到端测试
- [ ] 数据库迁移测试
- [ ] Worker 任务测试
- [ ] 性能基准测试
```

### 8.3 性能指标

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| API P95 响应时间 | < 500ms | Prometheus |
| 数据库查询 P95 | < 100ms | pg_stat_statements |
| Worker 延迟 | < 5s | Celery 监控 |
| 搜索准确率 | > 90% | 人工评估 |
| 并发 QPS | > 100 | 压力测试 |

### 8.4 验收流程

```yaml
1. 自测 (Developer)
   - 单元测试通过
   - 本地集成测试通过
   - 代码自查完成

2. 代码审查 (Code Review)
   - 至少 1 人 Review
   - 所有 Comment 解决
   - 安全检查通过

3. 测试环境验证 (QA)
   - 部署到测试环境
   - 冒烟测试通过
   - 回归测试通过

4. 性能测试 (Performance)
   - 压力测试通过
   - 性能指标达标

5. 生产部署 (Production)
   - 灰度发布
   - 监控告警
   - 回滚预案
```

---

## 九、风险管理

### 9.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 数据迁移失败 | 中 | 高 | 完整备份、回滚方案、灰度迁移 |
| pgvector 性能瓶颈 | 高 | 中 | 使用缓存、分页、异步索引 |
| Connection 计算 O(n²) | 高 | 中 | 限制候选集、增量计算 |
| LLM 调用成本过高 | 中 | 中 | 缓存、Prompt 优化、小模型 |
| 微信 API 变更 | 低 | 低 | 版本锁定、适配层 |

### 9.2 进度风险

| 风险 | 缓解措施 |
|------|----------|
| 需求变更 | 锁定 PRD4 范围,变更走评审 |
| 人员变动 | 知识共享、结对编程 |
| 技术难点 | 提前 PoC、专家咨询 |

### 9.3 质量风险

| 风险 | 缓解措施 |
|------|----------|
| Bug 泄漏 | 强制 Code Review、自动化测试 |
| 性能问题 | 持续监控、性能测试 |
| 安全漏洞 | 安全扫描、依赖审计 |

---

## 十、沟通与协作

### 10.1 会议节奏

```yaml
每日站会 (15min):
  - 昨天完成什么
  - 今天计划什么
  - 有什么阻碍

周例会 (1h):
  - 本周进度回顾
  - 下周计划
  - 风险讨论

里程碑评审 (2h):
  - 演示成果
  - 验收标准检查
  - 经验总结
```

### 10.2 文档规范

```yaml
代码必须包含:
  - Docstring (Google Style)
  - 类型注解
  - 示例用法

文档必须包含:
  - 设计文档
  - API 文档 (OpenAPI)
  - 运维手册
```

### 10.3 协作工具

```yaml
项目管理: Jira / GitHub Projects
文档协作: Notion / Confluence
代码管理: GitHub / GitLab
即时通讯: Slack / 飞书
监控告警: Grafana / PagerDuty
```

---

## 十一、附录

### 11.1 参考文档

```yaml
- PRD4.md: 详细设计说明书
- PRD4-diff.md: 差异分析文档
- DATABASE_ARCHITECTURE.md: 数据库架构
- API_ENDPOINTS_COMPLETE.md: API 文档
```

### 11.2 环境配置

```yaml
开发环境:
  Python: 3.11
  PostgreSQL: 14+
  Redis: 7+
  Node: 18+ (前端)

测试环境:
  同开发环境

生产环境:
  PostgreSQL: 15 (主从)
  Redis: Cluster
  负载均衡: Nginx
```

### 11.3 联系人

```yaml
项目经理: [姓名] - [邮箱]
技术负责人: [姓名] - [邮箱]
DevOps: [姓名] - [邮箱]
测试负责人: [姓名] - [邮箱]
```

---

**文档结束**

**下一步行动:**
1. 召开项目启动会
2. 确认团队成员分工
3. 创建开发分支
4. 开始阶段一开发
