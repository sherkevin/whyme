# PRD6 - Stage 2 后端功能补充需求

**目标:** 将 PA 1.0 从阶段一（静态信息承接）推进到阶段二（可被系统推进的状态）

**当前完成度:** 约 30%
**目标完成度:** 100%

**时间估算:** 6-10 天

---

## 一、优先级 P0 - 阶段二核心验收功能（必须）

**时间估算:** 3-5 天

### 1.1 Agent Tick 机制

#### 1.1.1 POST /api/v1/agent/tick 端点

**功能描述:**
- 手动触发 Agent 处理一个或多个 InboxItem
- 只处理 `status='raw'` 的 InboxItem
- 处理后更新状态为 `status='processed'`
- 返回处理结果统计

**API 规范:**
```python
# Request
POST /api/v1/agent/tick

# Body (optional)
{
    "workspace_id": "uuid",
    "item_ids": ["uuid1", "uuid2"],  # 可选：指定要处理的 items
    "limit": 10  # 可选：最多处理多少个
}

# Response
{
    "processed": 5,
    "skipped": 2,
    "failed": 0,
    "results": [
        {
            "item_id": "uuid",
            "from_status": "raw",
            "to_status": "processed",
            "title": "Generated Title",
            "summary": "Generated summary...",
            "inferred_type": "task"
        }
    ]
}
```

**文件:**
- `src/agent_os/agent/router.py` - 新增 Agent 路由
- `src/agent_os/agent/schema.py` - Agent tick 请求/响应 schema
- `src/agent_os/agent/crud.py` - Agent 处理 CRUD 操作

**测试要求:**
- 测试只处理 raw 状态的 items
- 测试跳过非 raw 状态的 items
- 测试返回格式正确
- 测试并发调用不会重复处理

---

#### 1.1.2 Agent 处理器核心逻辑

**功能描述:**
- 接收一个 InboxItem (raw)
- 生成标题（如果没有或不满意）
- 生成摘要
- 推断类型（task/note/resource）
- 更新 Item 状态为 processed
- 写入处理记录

**实现位置:**
- `src/agent_os/agent/processor.py` - 新建文件

**核心函数:**
```python
async def process_inbox_item(
    db: AsyncSession,
    item_id: UUID
) -> ProcessResult:
    """
    处理单个 InboxItem

    流程:
    1. 检查状态是否为 raw，不是则跳过
    2. 生成标题（如果需要）
    3. 生成摘要
    4. 推断类型
    5. 更新 item 状态
    6. 写入处理记录
    7. 返回结果
    """
```

**测试要求:**
- 测试处理逻辑完整性
- 测试幂等性（重复调用不重复处理）
- 测试异常处理

---

### 1.2 状态值扩展

#### 1.2.1 添加 raw 和 processed 状态

**功能描述:**
- 扩展 Item 模型的 status 字段，支持 `raw` 和 `processed`
- 更新相关 schema
- 更新数据库约束

**实现位置:**
- `src/agent_os/items/models.py` - 更新 ItemStatus 枚举
- `src/agent_os/inbox/schema.py` - 更新 InboxItemStatusUpdate

**代码变更:**
```python
# 当前
class ItemStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

# 修改为
class ItemStatus(str, Enum):
    RAW = "raw"           # 新增：原始输入
    PROCESSED = "processed"  # 新增：已处理
    ACTIVE = "active"       # 保留：活跃
    ARCHIVED = "archived"   # 保留：已归档
    DELETED = "deleted"     # 保留：已删除
```

**测试要求:**
- 测试 raw 状态创建 InboxItem
- 测试 raw → processed 状态转换
- 测试向后兼容（active 状态仍然有效）

---

### 1.3 结构化结果生成

#### 1.3.1 标题生成逻辑

**功能描述:**
- 如果 InboxItem 没有标题，从内容提取或生成
- 如果标题不满意，优化标题
- 规则基础（可以是简单的字符串处理）

**实现位置:**
- `src/agent_os/agent/title_generator.py` - 新建文件

**核心函数:**
```python
def generate_title(content: str, max_length: int = 200) -> str:
    """
    从内容生成标题

    规则:
    1. 取前 N 个字符
    2. 或取第一行
    3. 或基于关键词生成
    """
```

**测试要求:**
- 测试空内容处理
- 测试长内容截断
- 测试特殊字符处理

---

#### 1.3.2 摘要生成逻辑

**功能描述:**
- 提取内容的关键信息
- 生成简短摘要（100-200 字）
- 规则基础（前 N 字、关键词提取等）

**实现位置:**
- `src/agent_os/agent/summarizer.py` - 新建文件

**核心函数:**
```python
def generate_summary(content: str, max_length: int = 200) -> str:
    """
    生成内容摘要

    规则:
    1. 取前 max_length 字符
    2. 或提取关键词
    3. 或基于句子分割
    """
```

**测试要求:**
- 测试短内容处理
- 测试长内容截断
- 测试特殊字符处理

---

#### 1.3.3 类型推断逻辑

**功能描述:**
- 基于内容特征推断类型
- 默认为 note
- 可选类型：task, note, resource

**实现位置:**
- `src/agent_os/agent/classifier.py` - 新建文件

**核心函数:**
```python
def infer_type(content: str, title: str = "") -> str:
    """
    推断内容类型

    规则:
    1. 包含任务关键词 → task
    2. 包含链接/附件 → resource
    3. 其他 → note
    """
```

**测试要求:**
- 测试不同内容类型的推断
- 测试边界情况
- 测试默认值

---

### 1.4 处理记录机制

#### 1.4.1 AgentProcessEvent 模型

**功能描述:**
- 记录每次 Agent 处理事件
- 追溯哪个 InboxItem 被处理、产出什么结果

**实现位置:**
- `src/agent_os/agent/models.py` - 新增模型

**数据模型:**
```python
class AgentProcessEvent(Base):
    """Agent 处理事件记录"""
    __tablename__ = "agent_process_events"

    id = Column(UUID(as_uuid=True), primary_key=True)
    item_id = Column(UUID(as_uuid=True), nullable=False)
    workspace_id = UUID(as_uuid=True), nullable=False)
    user_id = UUID(as_uuid=True), nullable=False)

    from_status = Column(String(20), nullable=False)
    to_status = Column(String(20), nullable=False)

    # 处理结果
    generated_title = Column(Text)
    generated_summary = Column(Text)
    inferred_type = Column(String(20))

    # 元数据
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
    processing_duration_ms = Column(Integer)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # 关联
    item = relationship("Item")
```

**测试要求:**
- 测试事件记录创建
- 测试事件查询
- 测试事件追溯

---

#### 1.4.2 审计日志集成

**功能描述:**
- 每次 Agent Tick 写入审计日志
- 记录触发用户、时间、处理数量

**实现位置:**
- `src/agent_os/agent/audit.py` - Agent 审计日志

**测试要求:**
- 测试审计日志写入
- 测试审计日志查询

---

## 二、优先级 P1 - 阶段二完善功能（重要）

**时间估算:** 2-3 天

### 2.1 幂等性控制

#### 2.1.1 状态检查机制

**功能描述:**
- 处理前检查状态是否为 raw
- 如果不是 raw，跳过处理
- 防止重复处理

**实现位置:**
- `src/agent_os/agent/processor.py`

**代码示例:**
```python
async def process_inbox_item(db: AsyncSession, item_id: UUID):
    # 获取 item
    item = await db.get(Item, item_id)
    if not item:
        raise ItemNotFoundError

    # 幂等性检查
    if item.status != ItemStatus.RAW:
        return ProcessResult(
            item_id=item_id,
            skipped=True,
            reason=f"Item status is {item.status}, not raw"
        )

    # 加锁处理
    # ... 处理逻辑
```

**测试要求:**
- 测试重复调用不重复处理
- 测试并发调用不重复处理
- 测试状态检查准确

---

#### 2.1.2 并发控制

**功能描述:**
- 使用数据库行锁防止并发处理
- 或使用分布式锁

**实现选项:**
```python
# 选项 A: 数据库行锁
SELECT ... FOR UPDATE

# 选项 B: Redis 分布式锁
# 如果项目使用 Redis

# 选项 C: 应用层锁
# asyncio.Lock
```

**测试要求:**
- 测试并发场景
- 测试锁释放
- 测试死锁预防

---

### 2.2 异常处理

#### 2.2.1 单条异常不影响其他

**功能描述:**
- try-catch 包裹每条 item 的处理
- 单条失败不影响其他 items
- 记录失败原因

**实现位置:**
- `src/agent_os/agent/processor.py`

**代码示例:**
```python
async def process_batch(item_ids: List[UUID]):
    results = []
    for item_id in item_ids:
        try:
            result = await process_inbox_item(db, item_id)
            results.append(result)
        except Exception as e:
            results.append(ProcessResult(
                item_id=item_id,
                success=False,
                error=str(e)
            ))
    return results
```

**测试要求:**
- 测试单条失败不影响批量
- 测试异常正确记录
- 测试错误信息完整

---

#### 2.2.2 异常后系统可继续运行

**功能描述:**
- Agent Tick 失败不影响系统
- 可以再次触发 Agent Tick
- 系统状态不被破坏

**测试要求:**
- 测试 Agent Tick 失败后系统仍可用
- 测试数据库状态一致
- 测试 API 仍可调用

---

### 2.3 处理历史查询

#### 2.3.1 GET /api/v1/agent/process-history

**功能描述:**
- 查询 Agent 处理历史
- 按时间、item、状态过滤
- 分页支持

**API 规范:**
```python
# Request
GET /api/v1/agent/process-history?workspace_id=xxx&item_id=xxx&page=1

# Response
{
    "total": 100,
    "page": 1,
    "page_size": 20,
    "events": [
        {
            "id": "uuid",
            "item_id": "uuid",
            "from_status": "raw",
            "to_status": "processed",
            "generated_title": "...",
            "generated_summary": "...",
            "inferred_type": "task",
            "processed_at": "2026-02-07T...",
            "success": true
        }
    ]
}
```

**文件:**
- `src/agent_os/agent/router.py` - 新增查询路由

**测试要求:**
- 测试查询参数正确
- 测试分页正确
- 测试过滤功能

---

## 三、优先级 P2 - 阶段二优化功能（可选）

**时间估算:** 1-2 天

### 3.1 批量处理优化

**功能描述:**
- 支持 Agent Tick 一次处理多个 items
- 批量更新状态
- 批量写入处理记录

---

### 3.2 异步处理

**功能描述:**
- Agent Tick 立即返回 task_id
- 后台异步处理
- 提供查询处理状态接口

**API 规范:**
```python
# Request
POST /api/v1/agent/tick-async

# Response
{
    "task_id": "uuid",
    "status": "processing"
}

# Query status
GET /api/v1/agent/tasks/{task_id}
```

---

### 3.3 性能优化

**功能描述:**
- 添加处理性能指标
- 记录处理耗时
- 优化批量处理性能

---

## 四、文件清单

### 需要创建的文件

```
src/agent_os/agent/
├── processor.py       # 核心处理逻辑
├── title_generator.py # 标题生成
├── summarizer.py      # 摘要生成
├── classifier.py       # 类型推断
├── crud.py            # Agent CRUD 操作
├── models.py          # AgentProcessEvent 模型
├── schema.py          # Agent API schemas
├── router.py          # Agent 路由
└── audit.py           # 审计日志
```

### 需要修改的文件

```
src/agent_os/items/models.py       # 添加 RAW/PROCESSED 状态
src/agent_os/inbox/schema.py       # 更新状态值
src/agent_os/server/app.py         # 注册 agent 路由
tests/test_agent_tick.py          # Agent Tick 集成测试
```

---

## 五、测试要求

### 单元测试

```
src/agent_os/agent/tests/
├── test_processor.py       # 测试处理逻辑
├── test_title_generator.py # 测试标题生成
├── test_summarizer.py     # 测试摘要生成
├── test_classifier.py      # 测试类型推断
└── test_idempotency.py     # 测试幂等性
```

### 集成测试

```
tests/test_agent_tick_integration.py  # Agent Tick 端到端测试
tests/test_stage2_agent.py             # 阶段二验收测试
```

**测试覆盖目标:**
- 单元测试覆盖率 > 80%
- 集成测试覆盖所有核心流程
- 所有 P0 功能必须有测试

---

## 六、验收检查清单

### 最终验收标准对照

| 标准 | 当前 | 目标 |
|------|------|------|
| Agent 可以稳定处理 InboxItem 一次 | ❌ | ✅ |
| Inbox → Card / Today 转换真实发生 | ❌ | ✅ |
| 所有 Agent 行为可回溯、可解释 | ❌ | ✅ |
| 系统在异常情况下不破坏整体状态 | ⚠️ | ✅ |
| 未引入超出阶段二范围的能力 | ✅ | ✅ |

---

## 七、实施顺序

### Week 1: 核心 P0 功能

1. **Day 1-2:** Agent Tick API + 状态扩展
   - 实现 POST /api/v1/agent/tick
   - 添加 raw/processed 状态
   - 编写基础测试

2. **Day 3-4:** 处理逻辑实现
   - 标题生成
   - 摘要生成
   - 类型推断
   - 集成到 processor

3. **Day 5:** 处理记录
   - AgentProcessEvent 模型
   - 审计日志
   - 查询 API

### Week 2: 完善 P1 功能

4. **Day 1-2:** 幂等性控制
   - 状态检查
   - 并发控制
   - 异常处理

5. **Day 3:** 测试和完善
   - 集成测试
   - 端到端测试
   - 性能测试

---

**总结:** PRD6 定义了从阶段一到阶段二所需的所有新增功能，优先级清晰，可按顺序实施。

*文档版本: 1.0*
*创建日期: 2026-02-07*
*基于:* stage2-verification-report.md
