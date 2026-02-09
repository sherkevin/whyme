# PRD7-diff: 阶段三后端需求详细说明

**文档类型:** 需求差异文档 (PRD2 → PRD7)
**创建时间:** 2026-02-07
**阶段:** PA 1.0 阶段三 (Demo 与能力成型)
**范围:** 仅包含后端需求

---

## 一、阶段三在 PA 1.0 中的定位

### 从阶段二到阶段三的演进

**阶段二 (已完成)**: 单步 Agent 处理
- InboxItem → Agent (处理一次) → Card / Today
- 核心能力：分类、摘要、卡片生成

**阶段三 (当前)**: 多步 Agent 流程
- Task → Agent Flow (多步处理 + 决策) → 结果
- 核心能力：多步流程、决策确认、Skill 复用

### 阶段三的产品目标

在阶段二单步处理的基础上，引入：
1. **多步 Agent 行为** - Agent 能执行多个步骤
2. **决策结构与确认** - 关键节点需要用户确认
3. **Skill 抽象与复用** - 成功流程可沉淀为 Skill
4. **Demo 场景闭环** - 可演示的完整场景

**使系统能够围绕一个明确场景完成：**
`结构化判断 → 用户确认 → 结果产出 → 复用沉淀`

---

## 二、核心数据模型需求

### 2.1 DecisionPoint (决策点模型)

**用途**: 记录 Agent 生成的决策选项及用户确认结果

**表结构**:
```python
class DecisionPoint(Base):
    """决策点模型 - 记录 Agent 生成的决策选项"""

    __tablename__ = "decision_points"

    # 主键与关联
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    step_name = Column(String(100), nullable=False)  # 属于哪个步骤 (如 "step_1_analyze")

    # 决策选项 (JSON 结构)
    options = Column(JSON, nullable=False)
    # 示例:
    # [
    #   {
    #     "id": "option_a",
    #     "title": "接受项目",
    #     "description": "项目收益高且风险可控",
    #     "rationale": "ROI > 50%, 风险评分 < 3",
    #     "risks": ["需要投入 20 人月"],
    #     "confidence": 0.85
    #   },
    #   {
    #     "id": "option_b",
    #     "title": "拒绝项目",
    #     "description": "项目风险过高",
    #     "rationale": "技术栈不熟悉，团队经验不足",
    #     "risks": ["学习成本高", "交付风险大"],
    #     "confidence": 0.65
    #   }
    # ]

    # 用户选择
    selected_option_id = Column(String(100), nullable=True)  # 用户选择的 option id
    confirmed_at = Column(DateTime(timezone=True), nullable=True)  # 确认时间
    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))  # 确认人

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 索引
    __table_args__ = (
        Index('idx_decision_task_step', 'task_id', 'step_name'),
        Index('idx_decision_status', 'task_id', 'selected_option_id'),
    )
```

**关键约束**:
- `options` 字段必须包含至少 2 个选项
- 未确认前 `selected_option_id` 为 NULL
- 一旦确认，不允许修改 (通过应用层控制)

**API 操作**:
- `POST /api/v1/decisions/{decision_id}/confirm` - 确认选择
- `GET /api/v1/tasks/{task_id}/decisions` - 获取任务的所有决策点

---

### 2.2 Skill (技能模型)

**用途**: 定义可复用的 Agent 流程

**表结构**:
```python
class Skill(Base):
    """Skill 模型 - 可复用的 Agent 流程定义"""

    __tablename__ = "skills"

    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 基本信息
    name = Column(String(200), nullable=False)  # 如 "职业决策助手"
    description = Column(Text)  # 技能描述
    category = Column(String(50), nullable=False)  # decision, analysis, synthesis

    # Skill 定义 (核心)
    steps = Column(JSON, nullable=False)
    # 示例:
    # [
    #   {
    #     "order": 1,
    #     "name": "analyze_context",
    #     "description": "分析决策背景",
    #     "agent_action": "classify_and_summarize",
    #     "requires_confirmation": false,  # 不需要用户确认
    #     "output_schema": {"context_type", "priority", "complexity"}
    #   },
    #   {
    #     "order": 2,
    #     "name": "generate_options",
    #     "description": "生成决策选项",
    #     "agent_action": "generate_decision_options",
    #     "requires_confirmation": true,  # 需要用户确认
    #     "output_schema": {"options": [], "recommended_option_id"}
    #   },
    #   {
    #     "order": 3,
    #     "name": "finalize_decision",
    #     "description": "生成最终决策文档",
    #     "agent_action": "synthesize_decision",
    #     "requires_confirmation": false,
    #     "output_schema": {"decision_text", "next_steps", "risks"}
    #   }
    # ]

    # 适用场景
    applicable_item_types = Column(JSON)  # ["task", "decision"]
    min_confidence = Column(String(20), default="medium")  # low, medium, high
    required_tags = Column(JSON)  # ["career", "project"]

    # 版本控制
    version = Column(String(20), nullable=False, default="1.0")
    parent_skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"))  # 父版本

    # 创建信息
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)  # 是否启用

    # 索引
    __table_args__ = (
        Index('idx_skill_category', 'category', 'is_active'),
        Index('idx_skill_version', 'id', 'version'),
    )
```

**关键约束**:
- `steps` 必须包含至少 1 个步骤
- 步骤必须按 `order` 排序
- 版本号遵循语义化版本 (SemVer)
- 删除 Skill 时只标记 `is_active=False` (软删除)

**API 操作**:
- `POST /api/v1/skills` - 创建 Skill
- `GET /api/v1/skills/{skill_id}` - 获取 Skill 定义
- `GET /api/v1/skills?category=decision` - 列出 Skills
- `POST /api/v1/skills/{skill_id}/apply` - 将 Skill 应用到 Task

---

### 2.3 TaskExecutionLog (任务执行日志)

**用途**: 记录 Agent Flow 的每一步执行

**表结构**:
```python
class TaskExecutionLog(Base):
    """任务执行日志 - 记录 Agent Flow 的每一步"""

    __tablename__ = "task_execution_logs"

    # 主键与关联
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)

    # 步骤信息
    step_name = Column(String(100), nullable=False)  # 对应 Skill.steps[].name
    step_order = Column(Integer, nullable=False)  # 执行顺序

    # 输入输出
    input_data = Column(JSON)  # 步骤输入
    output_data = Column(JSON)  # 步骤输出

    # 执行信息
    status = Column(String(20), nullable=False)  # pending, running, completed, failed, waiting_confirmation
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)  # 执行时长 (毫秒)

    # 错误信息
    error_message = Column(Text)
    error_stack = Column(Text)

    # 决策关联
    decision_point_id = Column(UUID(as_uuid=True), ForeignKey("decision_points.id"))

    # Agent 信息
    agent_action = Column(String(100))  # 执行的 Agent 动作
    agent_version = Column(String(20))  # Agent 版本

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 索引
    __table_args__ = (
        Index('idx_exec_log_task_step', 'task_id', 'step_order'),
        Index('idx_exec_log_status', 'task_id', 'status'),
        Index('idx_exec_log_decision', 'decision_point_id'),
    )
```

**关键约束**:
- 同一 `task_id` 和 `step_order` 只能有一条记录
- `status` 必须是预定义的枚举值
- `waiting_confirmation` 状态必须有对应的 `decision_point_id`

**API 操作**:
- `GET /api/v1/tasks/{task_id}/execution-logs` - 获取执行日志
- `GET /api/v1/tasks/{task_id}/execution-logs/stream` - 流式获取执行日志 (SSE)

---

### 2.4 Task 模型扩展

在现有 `Task` 模型基础上新增字段：

```python
# 在现有 Task 模型中添加：

# Skill 关联
skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"))  # 使用的 Skill
skill_version = Column(String(20))  # Skill 版本

# 执行状态
execution_status = Column(String(20), default="not_started")  # not_started, running, paused, completed, failed
current_step = Column(Integer, default=0)  # 当前执行到第几步

# 统计信息
total_steps = Column(Integer)  # 总步骤数
completed_steps = Column(Integer, default=0)  # 已完成步骤数

# 结果
final_output = Column(JSON)  # 最终输出

# 索引
__table_args__ = (
    # ... 现有索引
    Index('idx_task_skill', 'skill_id'),
    Index('idx_task_execution_status', 'execution_status'),
)
```

---

## 三、核心后端功能需求

### 3.1 Agent Flow 执行引擎

**需求描述**: 实现多步 Agent 流程的调度与执行

**核心功能**:

1. **Flow 解析与验证**
   - 输入: Skill 定义 + Task 上下文
   - 验证步骤依赖关系
   - 检查必要输入参数

2. **步骤调度**
   - 按顺序执行步骤
   - 处理 `requires_confirmation` 标志
   - 支持暂停与恢复

3. **状态管理**
   - 维护当前执行状态
   - 记录每步输入输出
   - 处理异常与回滚

**API 设计**:

```python
# 1. 启动 Agent Flow
POST /api/v1/agent/flow/start
Request:
{
  "task_id": "uuid",
  "skill_id": "uuid",
  "initial_context": {...}  # 初始上下文
}
Response:
{
  "execution_id": "uuid",
  "current_step": 1,
  "status": "running",
  "total_steps": 3
}

# 2. 获取执行状态
GET /api/v1/agent/flow/{execution_id}/status
Response:
{
  "execution_id": "uuid",
  "status": "waiting_confirmation",  # running, paused, completed, failed
  "current_step": 2,
  "completed_steps": [1],
  "current_decision": {
    "decision_id": "uuid",
    "options": [...],
    "expires_at": "timestamp"
  }
}

# 3. 确认决策后继续
POST /api/v1/agent/flow/{execution_id}/continue
Request:
{
  "decision_id": "uuid",
  "selected_option_id": "option_a"
}
Response:
{
  "status": "running",
  "current_step": 3
}

# 4. 暂停执行
POST /api/v1/agent/flow/{execution_id}/pause

# 5. 恢复执行
POST /api/v1/agent/flow/{execution_id}/resume
```

**实现要点**:
- 使用异步任务队列 (Celery 或 asyncio)
- 实现幂等性控制
- 超时自动暂停机制
- 执行日志实时写入

---

### 3.2 决策生成与管理

**需求描述**: Agent 在关键步骤生成结构化决策选项

**核心功能**:

1. **决策生成**
   - 根据上下文生成选项
   - 计算每个选项的置信度
   - 标注风险与限制

2. **决策验证**
   - 选项互斥性检查
   - 必要字段完整性检查
   - 置信度阈值过滤

3. **确认管理**
   - 记录用户选择
   - 防止重复确认
   - 超时处理

**Agent 动作示例**:

```python
# Agent 动作: generate_decision_options
async def generate_decision_options(
    context: dict,
    num_options: int = 3,
    min_confidence: float = 0.6
) -> DecisionPoint:
    """生成决策选项"""

    # 1. 分析上下文
    analysis = await analyze_context(context)

    # 2. 生成候选选项
    candidates = []
    for strategy in DECISION_STRATEGIES:
        options = await strategy.generate(analysis)
        candidates.extend(options)

    # 3. 评分与排序
    scored_options = [
        {
            **opt,
            "confidence": calculate_confidence(opt, analysis),
            "risks": identify_risks(opt, analysis)
        }
        for opt in candidates
    ]
    scored_options = sorted(
        scored_options,
        key=lambda x: x["confidence"],
        reverse=True
    )

    # 4. 过滤与选择
    selected = [
        opt for opt in scored_options
        if opt["confidence"] >= min_confidence
    ][:num_options]

    # 5. 创建决策点
    decision = DecisionPoint(
        task_id=context["task_id"],
        step_name=context["current_step"],
        options=selected
    )

    return decision
```

**API 设计**:

```python
# 1. Agent 内部调用
decision = await generate_decision_options(context)
db.add(decision)
await db.commit()

# 2. 用户查询决策
GET /api/v1/tasks/{task_id}/decisions
Response:
{
  "decisions": [
    {
      "id": "uuid",
      "step_name": "step_2_generate_options",
      "options": [...],
      "status": "pending",  # pending, confirmed, expired
      "created_at": "timestamp"
    }
  ]
}

# 3. 用户确认
POST /api/v1/decisions/{decision_id}/confirm
Request:
{
  "selected_option_id": "option_a",
  "note": "选择理由..."  # 可选
}
Response:
{
  "id": "uuid",
  "status": "confirmed",
  "confirmed_at": "timestamp"
}

# 4. Agent 读取确认结果
decision = await db.get(DecisionPoint, decision_id)
if decision.selected_option_id:
    # 继续执行下一步
    await execute_next_step(context, decision.selected_option_id)
```

---

### 3.3 Skill 抽象与复用

**需求描述**: 将成功流程抽象为 Skill，支持跨任务复用

**核心功能**:

1. **Skill 创建**
   - 定义步骤序列
   - 标注适用场景
   - 版本管理

2. **Skill 匹配**
   - 根据任务类型推荐 Skill
   - 检查前置条件
   - 版本兼容性检查

3. **Skill 执行**
   - 实例化 Skill 为 Flow
   - 注入任务上下文
   - 执行并记录日志

**API 设计**:

```python
# 1. 创建 Skill
POST /api/v1/skills
Request:
{
  "name": "职业决策助手",
  "description": "帮助用户做出职业相关决策",
  "category": "decision",
  "steps": [...],  # 详见 Skill 模型
  "applicable_item_types": ["task"],
  "required_tags": ["career", "decision"]
}
Response:
{
  "id": "uuid",
  "version": "1.0",
  "created_at": "timestamp"
}

# 2. 列出 Skills
GET /api/v1/skills?category=decision&is_active=true
Response:
{
  "skills": [
    {
      "id": "uuid",
      "name": "职业决策助手",
      "version": "1.0",
      "steps": [...],
      "usage_count": 42  # 使用次数
    }
  ]
}

# 3. 推荐适用 Skills
POST /api/v1/skills/recommend
Request:
{
  "task_context": {
    "item_type": "task",
    "tags": ["career", "decision"],
    "content": "..."
  }
}
Response:
{
  "recommended": [
    {
      "skill_id": "uuid",
      "name": "职业决策助手",
      "match_score": 0.95,  # 匹配度
      "reason": "任务类型和标签完全匹配"
    }
  ]
}

# 4. 应用 Skill 到 Task
POST /api/v1/tasks/{task_id}/apply-skill
Request:
{
  "skill_id": "uuid",
  "initial_context": {...}
}
Response:
{
  "execution_id": "uuid",
  "status": "running",
  "estimated_steps": 3
}
```

**Skill 匹配算法**:

```python
async def recommend_skills(
    item_type: str,
    tags: List[str],
    content: str
) -> List[Skill]:
    """推荐适用的 Skills"""

    # 1. 基础过滤
    query = select(Skill).where(
        and_(
            Skill.is_active == True,
            Skill.applicable_item_types.contains(item_type)
        )
    )
    candidates = await db.execute(query)
    skills = candidates.scalars().all()

    # 2. 计算匹配分数
    scored = []
    for skill in skills:
        score = 0.0

        # 标签匹配 (权重 0.6)
        if skill.required_tags:
            matched_tags = set(skill.required_tags) & set(tags)
            tag_score = len(matched_tags) / len(skill.required_tags)
            score += tag_score * 0.6

        # 内容相似度 (权重 0.4)
        # ... 使用 embedding 相似度

        scored.append({"skill": skill, "score": score})

    # 3. 排序与返回
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [s["skill"] for s in scored if s["score"] > 0.7]
```

---

### 3.4 Demo 场景支持

**需求描述**: 支持至少 1 个完整可演示的场景

**推荐 Demo 场景: 职业决策助手**

**场景描述**:
用户输入一个职业决策问题（如"是否跳槽到新公司"），系统通过多步分析生成决策建议。

**流程定义**:

```python
Skill: "职业决策助手"
Steps:
  1. analyze_context (分析背景)
     - 输入: 用户描述、当前职位、机会详情
     - 输出: 上下文分析 {行业、阶段、关键因素}
     - 确认: 否

  2. generate_options (生成选项)
     - 输入: 上下文分析
     - 输出: 决策选项 [
         {
           id: "stay",
           title: "留在当前公司",
           rationale: "职业发展路径清晰",
           risks: ["晋升可能较慢"]
         },
         {
           id: "jump",
           title: "跳槽到新公司",
           rationale: "薪资涨幅 30%，技术栈升级",
           risks: ["文化不适应风险"]
         },
         {
           id: "negotiate",
           title: "谈判当前公司",
           rationale: "可争取更好条件",
           risks: ["谈判可能失败"]
         }
       ]
     - 确认: 是 (用户必须选择一个选项)

  3. synthesize_decision (生成决策文档)
     - 输入: 用户选择 + 上下文
     - 输出: 决策文档 {
         decision: "跳槽到新公司",
         reasoning: "...",
         next_steps: ["准备面试", "了解新公司文化"],
         risks_mitigation: ["提前了解团队", "设定试用期目标"]
       }
     - 确认: 否
```

**API 演示流程**:

```bash
# 1. 用户创建决策任务
POST /api/v1/tasks
{
  "title": "是否跳槽到字节跳动",
  "type": "decision",
  "content": "目前在中厂，字节跳动给了 30% 涨薪，但担心 WLB...",
  "tags": ["career", "decision"]
}

# 2. 系统推荐 Skill
GET /api/v1/skills/recommend?task_id={task_id}
# 返回: "职业决策助手" (match_score: 0.92)

# 3. 应用 Skill
POST /api/v1/tasks/{task_id}/apply-skill
{
  "skill_id": "{skill_id}"
}
# 返回: execution_id, 开始执行

# 4. 查询执行状态
GET /api/v1/agent/flow/{execution_id}/status
# Step 1 完成 → Step 2 等待确认

# 5. 获取决策选项
GET /api/v1/tasks/{task_id}/decisions
# 返回 3 个选项

# 6. 用户确认
POST /api/v1/decisions/{decision_id}/confirm
{
  "selected_option_id": "jump",
  "note": "技术成长更重要"
}

# 7. 自动继续执行 Step 3
# 完成后生成最终决策文档

# 8. 获取最终结果
GET /api/v1/tasks/{task_id}/result
{
  "decision": "跳槽到新公司",
  "reasoning": "...",
  "next_steps": [...],
  "risks_mitigation": [...]
}
```

---

## 四、非功能性需求

### 4.1 可靠性

- **幂等性**: 所有 API 操作支持幂等
- **超时控制**: 每个步骤超时 5 分钟，总流程超时 30 分钟
- **状态一致性**: 使用数据库事务保证状态一致性
- **错误恢复**: 支持从任意步骤恢复执行

### 4.2 可观测性

- **完整日志**: 每个步骤记录输入、输出、时间
- **可追溯**: 可回放完整执行过程
- **可解释**: 决策选项包含生成依据
- **可审计**: 记录所有用户确认操作

### 4.3 性能

- **响应时间**:
  - API 查询 < 200ms
  - Flow 启动 < 500ms
  - 决策生成 < 3s
- **并发**: 支持 100 个并发 Flow 执行
- **数据量**: 单个 Flow 日志 < 10MB

### 4.4 安全性

- **权限控制**:
  - 只有 Task 创建者可以确认决策
  - Skill 创建需要认证
- **数据隔离**: 多租户数据完全隔离
- **输入验证**: 所有 JSON 输入验证格式与大小

---

## 五、测试验收要求

### 5.1 单元测试

- ✅ DecisionPoint 模型 CRUD
- ✅ Skill 模型 CRUD
- ✅ TaskExecutionLog 模型 CRUD
- ✅ Flow 执行引擎核心逻辑
- ✅ 决策生成算法
- ✅ Skill 匹配算法

### 5.2 集成测试

- ✅ 完整 Flow 执行 (含决策确认)
- ✅ Skill 创建与应用
- ✅ 暂停与恢复执行
- ✅ 异常处理与回滚
- ✅ 并发执行隔离

### 5.3 Demo 测试

- ✅ 职业决策场景完整演示
- ✅ 重复演示 3 次结果一致
- ✅ 前后端联调通过
- ✅ 无数据残留

---

## 六、交付物清单

### 6.1 数据模型

- [x] `DecisionPoint` 模型定义
- [x] `Skill` 模型定义
- [x] `TaskExecutionLog` 模型定义
- [x] `Task` 模型扩展

### 6.2 核心模块

- [x] Agent Flow 执行引擎
- [x] 决策生成模块
- [x] Skill 匹配与执行
- [x] 日志记录模块

### 6.3 API 端点

- [x] `/api/v1/agent/flow/*` - Flow 执行
- [x] `/api/v1/decisions/*` - 决策管理
- [x] `/api/v1/skills/*` - Skill 管理
- [x] `/api/v1/tasks/{id}/execution-logs` - 执行日志

### 6.4 文档

- [x] API 文档
- [x] 数据模型文档
- [x] Demo 场景说明
- [x] 测试报告

---

## 七、里程碑与时间线

| 里程碑 | 交付内容 | 时间 |
|--------|---------|------|
| M1: 数据模型 | DecisionPoint, Skill, TaskExecutionLog | Week 1 |
| M2: Flow 引擎 | 基础 Flow 执行 (无决策) | Week 2 |
| M3: 决策机制 | 决策生成与确认 | Week 3 |
| M4: Skill 复用 | Skill 抽象与匹配 | Week 4 |
| M5: Demo 集成 | 职业决策场景完整演示 | Week 5 |
| M6: 测试验收 | 全部测试通过 | Week 6 |

---

**文档版本:** v1.0
**最后更新:** 2026-02-07
**维护者:** Claude Sonnet 4.5
**审核状态:** 待审核
