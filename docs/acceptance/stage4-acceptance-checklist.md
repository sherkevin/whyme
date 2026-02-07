# PA 1.0 阶段四验收标准

**创建时间:** 2026-02-07
**阶段定位:** 工程化与能力整合阶段
**核心目标:** 从"Demo能力"走向"可上线系统"

---

## 一、PA 1.0 的整体分期视角

在 PA 1.0 的整体分期中：

- **阶段一** (已完成)
  冻结规则、数据模型和接口，跑通最小信息流（Inbox → Today）。

- **阶段二** (已完成)
  引入最小 Agent 行为，使系统能够对信息进行一次受控处理（Inbox → Card / Today）。

- **阶段三** (已完成)
  引入多步 Agent 流程、决策结构与 Skill 抽象，形成可演示、可复用的 Demo 能力。

- **阶段四** (当前阶段)
  引入 Search / Ingestion / Insight 等系统能力，完成 PA 1.0 的功能收口与工程化就绪。

**阶段四的目标是把已存在的 Agent 能力变成"可检索、可追溯、可分析、可上线"的系统。**

---

## 二、阶段四在 PA 1.0 中的产品定义

阶段四是 PA 1.0 的工程化与能力整合阶段，其产品定义为：

**在阶段三的 Agent 与 Skill 能力基础上，**
**引入统一搜索、数据抓取与分析能力，**
**并补齐安全、测试与部署能力，**
**使 PA 1.0 具备 可长期运行与对外交付的条件。**

### 阶段四关注的是：

- ✅ 已产生的数据是否可被统一检索
- ✅ 外部信息是否能被可靠引入系统
- ✅ Agent 行为是否能被分析与聚合
- ✅ 系统是否具备上线与运维条件

---

## 三、阶段四必须完成的系统范围

阶段四在阶段三基础上，**新增且仅新增**以下系统能力：

### 1. 统一搜索能力
对系统内的多种数据类型提供统一检索接口。

### 2. Ingestion（数据引入）能力
支持从外部来源抓取、解析并写入系统。

### 3. Insight（分析与聚合）能力
对已有数据进行聚合分析，生成结构化输出。

### 4. 安全、测试与部署收口
系统具备基本安全防护、测试覆盖与部署能力。

**阶段四不引入新的核心产品形态，仅对已有能力进行整合、补全与稳定化。**

---

## 四、阶段四后端验收标准

阶段四后端验收以 **"系统是否可检索、可抓取、可分析、可部署"** 为核心。

---

### 1. 统一搜索（Search）

#### 必须实现

- ✅ 统一的搜索数据模型（覆盖 Card / Task / Plan 等）
- ✅ 索引写入与更新机制
- ✅ 搜索接口（支持关键词 + 语义混合、分页、过滤）

#### 验收条件

- ✅ 不同类型数据可通过同一接口检索
- ✅ 搜索结果可按类型、时间或相关性排序
- ✅ 搜索结果可追溯到原始数据

---

### 2. Ingestion（抓取与解析）

#### 必须实现

- ✅ Ingestion Job 数据模型
- ✅ 支持至少一种外部来源（如 URL 或 PDF）
- ✅ 抓取 → 解析 → 切分 → 写入索引的完整链路

#### 验收条件

- ✅ 外部内容可被成功写入系统
- ✅ 每条内容可追溯来源与时间
- ✅ 抓取失败不会影响系统整体运行

---

### 3. Insight（分析与聚合）

#### 必须实现

- ✅ 基于现有数据的聚合分析接口
- ✅ 至少一种 Insight 输出形式（如总结、趋势或主题）

#### 验收条件

- ✅ Insight 输出来源明确
- ✅ 不引入不可解释的推断
- ✅ 输出结果可重复生成

---

### 4. Agent 行为与数据一致性

#### 必须实现

- ✅ Search / Ingestion / Insight 与 Agent 数据模型一致
- ✅ 新增能力不破坏已有 Agent Flow 与 Skill 执行

#### 验收条件

- ✅ 阶段三的 Demo 场景在阶段四依然可正常运行
- ✅ 无数据结构冲突或回退

---

### 5. 安全、测试与部署

#### 必须实现

- ✅ 基础输入校验与权限控制
- ✅ 关键业务路径的自动化测试
- ✅ 可部署产物（Docker / CI 流水线）

#### 验收条件

- ✅ 核心接口通过测试
- ✅ 系统可在目标环境部署
- ✅ 日志与监控可定位问题

---

## 五、阶段四前端验收标准

阶段四前端验收重点在于：
**用户是否可以使用新增能力而不破坏原有使用体验。**

---

### 1. 搜索界面与交互

#### 必须实现

- ✅ 搜索入口与搜索结果页
- ✅ 支持关键词输入、结果列表展示

#### 验收条件

- ✅ 搜索结果与后端返回一致
- ✅ 不同类型结果展示清晰

---

### 2. Ingestion 入口展示

#### 必须实现

- ✅ 外部内容导入入口（如 URL 输入）
- ✅ 导入状态反馈

#### 验收条件

- ✅ 用户可明确感知导入成功或失败
- ✅ 不出现无响应状态

---

### 3. Insight 展示

#### 必须实现

- ✅ Insight 输出展示区域
- ✅ 输出内容结构清晰

#### 验收条件

- ✅ Insight 与其来源数据关联明确
- ✅ 刷新后结果一致

---

### 4. 稳定性与兼容性

#### 必须实现

- ✅ 新增功能不影响原有页面
- ✅ 错误状态有明确提示

#### 验收条件

- ✅ 阶段三 Demo 场景前端流程保持可用
- ✅ 无关键阻塞 Bug

---

## 六、阶段四不纳入验收范围

以下内容**不作为阶段四完成条件**：

- ❌ 大规模性能优化
- ❌ 成本优化或模型路由优化
- ❌ 商业化计费系统
- ❌ Skill 市场或生态治理
- ❌ Agent-to-Agent 网络
- ❌ 高级个性化推荐

---

## 七、阶段四完成的最终判断标准

**阶段四视为完成，必须同时满足：**

1. ✅ 系统内数据可统一检索
2. ✅ 外部内容可稳定引入并追溯
3. ✅ 基础 Insight 能力可输出结构化结果
4. ✅ 原有 Agent 与 Demo 场景不被破坏
5. ✅ 系统具备上线与运维的基本条件

---

## 附录：关键数据模型定义

### SearchIndex 模型

```python
class SearchIndex(Base):
    """统一搜索索引 - 支持多类型数据检索"""

    __tablename__ = "search_indices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_type = Column(String(50), nullable=False)  # 'card', 'task', 'decision_point', etc.
    item_id = Column(UUID(as_uuid=True), nullable=False)

    # 搜索字段
    title = Column(Text)
    content = Column(Text)
    embedding = Column(JSON)  # 向量嵌入
    metadata = Column(JSON)   # 额外元数据

    # 索引字段
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('ix_search_item_type_id', 'item_type', 'item_id'),
        Index('ix_search_created_at', 'created_at'),
    )
```

### IngestionJob 模型

```python
class IngestionJob(Base):
    """数据引入任务 - 记录外部内容抓取"""

    __tablename__ = "ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url = Column(String(500))
    source_type = Column(String(50))  # 'url', 'pdf', 'markdown', etc.

    # 处理状态
    status = Column(String(20), default='pending')  # pending, running, completed, failed
    items_created = Column(Integer, default=0)

    # 结果
    result_summary = Column(JSON)
    error_message = Column(Text)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
```

### InsightCluster 模型

```python
class InsightCluster(Base):
    """洞察聚类 - 对数据的聚合分析结果"""

    __tablename__ = "insight_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_type = Column(String(50))  # 'summary', 'trend', 'topic', etc.

    # 来源数据
    source_item_ids = Column(JSON)  # [uuid1, uuid2, ...]

    # 洞察输出
    insight_data = Column(JSON)
    confidence = Column(Float)

    # 元数据
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
```

---

## 参考文档

- [PA 1.0 PRD](../../PRD4.md)
- [阶段一验收标准](stage1-acceptance-checklist.md)
- [阶段二验收标准](stage2-acceptance-checklist-final-100.md)
- [阶段三验收标准](stage3-acceptance-checklist.md)

---

**文档版本:** v1.0
**最后更新:** 2026-02-07
**维护者:** Claude Sonnet 4.5
