# PA 1.0 阶段三验收标准

**创建时间:** 2026-02-07
**阶段定位:** Demo 与能力成型阶段
**核心目标:** 从"能跑一次"走向"像一个 Agent 系统"

---

## 一、PA 1.0 的整体分期视角

在 PA 1.0 的整体分期中：

- **阶段一** (已完成)
  完成基础结构、规则冻结、数据模型冻结，跑通最小信息流（Inbox → Today）。

- **阶段二** (已完成)
  引入最小 Agent 行为，使系统能够对信息进行一次受控处理（Inbox → Card / Today）。

- **阶段三** (当前阶段)
  在阶段二基础上，引入多步 Agent 行为、决策结构与 Skill 抽象，形成可演示、可复用、可解释的 PA Demo 能力。

- **阶段四** (未来)
  Search / Ingestion / Insight 等系统能力收口，进入完整 PA 1.0。

**阶段三是 PA 从"能跑一次"走向"像一个 Agent 系统"的阶段。**

---

## 二、阶段三在 PA 1.0 中的产品定义

阶段三是 PA 1.0 的 Demo 与能力成型阶段，其产品定义为：

**在阶段二单步处理的基础上，**
**引入多步 Agent 行为、决策点与 Skill 抽象，**
**使系统能够围绕一个明确场景完成**
**"结构化判断 → 用户确认 → 结果产出 → 复用沉淀"。**

### 阶段三关注的重点

- ✅ Agent 是否具备多步处理能力
- ✅ 决策是否具备明确结构与确认点
- ✅ 系统是否开始沉淀可复用的能力单元（Skill）
- ✅ 是否可以支撑一个稳定可重复演示的 Demo 场景

### 阶段三不追求的内容

- ❌ 泛化智能
- ❌ 规模化能力

---

## 三、阶段三必须完成的系统范围

阶段三在阶段二基础上，**新增且仅新增**以下系统能力：

### 1. 多步 Agent 流程
- Agent 能够围绕一个任务执行多个步骤，而不是只处理一次。

### 2. 决策结构与确认机制
- 系统能够生成结构化选项，并在关键节点要求用户确认。

### 3. Skill 抽象与复用
- 系统能够将一次成功的处理流程抽象为 Skill，并在后续任务中复用。

### 4. Demo 场景闭环
- 系统能够围绕一个明确场景，从输入到结果完成完整流程。

### 阶段三不引入

- ❌ 大规模自动执行
- ❌ Agent-to-Agent 协作
- ❌ 搜索与外部信息抓取

---

## 四、阶段三后端验收标准

阶段三后端验收以 **"多步 Agent 行为是否稳定、可控、可复用"** 为核心。

---

### 1. 多步 Agent 流程（Agent Flow）

#### 必须实现

- ✅ 明确的 Agent Flow 定义（Step 1 / Step 2 / Step 3）
- ✅ 每个步骤有明确输入、输出与状态
- ✅ Flow 以 Task / Card 为上下文执行

#### 验收条件

- ✅ 同一任务可按固定顺序执行多个 Agent Step
- ✅ 每一步的输出可被下一步消费
- ✅ 流程中断后可继续执行或安全终止

---

### 2. 决策结构与用户确认

#### 必须实现

- ✅ Agent 输出结构化决策选项（如 `options[]`）
- ✅ 每个选项包含必要字段（描述、依据、风险或限制）
- ✅ 明确的用户确认接口或状态

#### 验收条件

- ✅ 未确认前，流程不能进入下一步
- ✅ 用户确认结果被持久化
- ✅ 决策结果可回溯

---

### 3. Skill 定义与运行（最小实现）

#### 必须实现

- ✅ Skill 数据模型（名称、适用场景、步骤定义、版本）
- ✅ Skill Runner（基于 Skill 定义执行 Agent Flow）
- ✅ Skill 与具体任务解耦

#### 验收条件

- ✅ 同一 Skill 可被用于多个任务
- ✅ Skill 版本变更不影响历史任务结果
- ✅ Skill 执行过程可被记录

---

### 4. Agent 行为记录与可解释性

#### 必须实现

- ✅ 每一步 Agent 行为被记录（输入、输出、时间）
- ✅ 决策与确认点被显式记录
- ✅ 可区分"系统生成"与"用户确认"的内容

#### 验收条件

- ✅ 可以回放一个任务的完整 Agent 行为过程
- ✅ 不存在无法解释的状态跳变

---

### 5. Demo 场景稳定性

#### 必须实现

- ✅ 至少 1 个完整 Demo 场景（如职业决策 / 项目决策）
- ✅ 场景流程固定，不依赖临时配置

#### 验收条件

- ✅ Demo 可重复演示 ≥3 次
- ✅ 每次演示流程一致、结果结构一致

---

## 五、阶段三前端验收标准

阶段三前端验收重点在于：
**用户是否能理解并参与 Agent 的决策过程。**

---

### 1. 决策视图展示

#### 必须实现

- ✅ 决策选项列表展示
- ✅ 每个选项的信息结构清晰
- ✅ 当前决策状态明确

#### 验收条件

- ✅ 用户清楚当前处于"待确认 / 已确认"状态
- ✅ 刷新页面后状态一致

---

### 2. 多步流程反馈

#### 必须实现

- ✅ 当前步骤提示
- ✅ 已完成步骤标识
- ✅ 处理中状态展示

#### 验收条件

- ✅ 用户可感知流程进展
- ✅ 不会误以为系统卡死

---

### 3. Skill 使用与结果展示

#### 必须实现

- ✅ 展示当前任务使用的 Skill
- ✅ 展示 Skill 产出的结果

#### 验收条件

- ✅ Skill 与任务关联清晰
- ✅ 不同任务使用同一 Skill 时表现一致

---

### 4. Demo 场景完整性

#### 必须实现

- ✅ 从输入到结果的完整 UI 流程
- ✅ 所有关键操作有明确反馈

#### 验收条件

- ✅ Demo 可在无解释情况下被完整走完
- ✅ 前端无阻塞性空页面

---

## 六、阶段三不纳入验收范围

以下内容**不作为阶段三完成条件**：

- ❌ Skill 市场或分发机制
- ❌ Agent-to-Agent 通信
- ❌ 自动执行高风险操作
- ❌ 搜索、向量检索、外部数据抓取
- ❌ 个性化推荐优化
- ❌ 性能与规模化优化

---

## 七、阶段三完成的最终判断标准

**阶段三视为完成，必须同时满足：**

1. ✅ Agent 支持稳定的多步流程
2. ✅ 决策过程具备明确结构与确认点
3. ✅ Skill 可被抽象并在多个任务中复用
4. ✅ 至少 1 个 Demo 场景可稳定重复演示
5. ✅ 系统行为全程可记录、可回溯

---

## 附录：关键数据模型定义

### DecisionPoint 模型

```python
class DecisionPoint(Base):
    """决策点模型 - 记录 Agent 生成的决策选项"""

    __tablename__ = "decision_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    step_name = Column(String(100), nullable=False)  # 属于哪个步骤

    # 决策选项（JSON 结构）
    options = Column(JSON, nullable=False)  # [{id, title, description, rationale, risks}]

    # 用户选择
    selected_option_id = Column(String(100), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### Skill 模型

```python
class Skill(Base):
    """Skill 模型 - 可复用的 Agent 流程定义"""

    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50))  # decision, analysis, synthesis 等

    # Skill 定义
    steps = Column(JSON, nullable=False)  # [{name, description, agent_action, requires_confirmation}]
    version = Column(String(20), nullable=False, default="1.0")

    # 适用场景
    applicable_item_types = Column(JSON)  # ["task", "decision"]
    min_confidence = Column(String(20), default="medium")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
```

### TaskExecutionLog 模型

```python
class TaskExecutionLog(Base):
    """任务执行日志 - 记录 Agent Flow 的每一步"""

    __tablename__ = "task_execution_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)

    # 步骤信息
    step_name = Column(String(100), nullable=False)
    step_order = Column(Integer, nullable=False)

    # 输入输出
    input_data = Column(JSON)
    output_data = Column(JSON)

    # 执行信息
    status = Column(String(20))  # pending, running, completed, failed, waiting_confirmation
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # 决策信息
    decision_point_id = Column(UUID(as_uuid=True), ForeignKey("decision_points.id"))
```

---

## 参考文档

- [PA 1.0 PRD](../../PRD4.md)
- [阶段一验收标准](stage1-acceptance-checklist.md)
- [阶段二验收标准](stage2-acceptance-checklist-final-100.md)

---

**文档版本:** v1.0
**最后更新:** 2026-02-07
**维护者:** Claude Sonnet 4.5
