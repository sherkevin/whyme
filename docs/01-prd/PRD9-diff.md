# PRD9 - 验收问题修复清单

**目标:** 修复验收报告中发现的问题,使项目完全符合 PRD4 验收标准

**当前完成度:** 约 81% (核心功能)
**目标完成度:** 100%

**创建时间:** 2026-02-09
**预计完成:** 2026-02-16 (1周)

---

## 一、优先级 P0 - 立即修复 (本周完成)

### 1.1 测试导入错误修复

**问题:** 31个测试文件有导入错误,无法运行完整测试套件

**影响:** 无法验证代码质量,影响CI/CD流程

**错误示例:**
```
ImportError: cannot import name 'UserSettings' from 'agent_os.auth.schema'
```

**修复步骤:**
1. 检查 `tests/unit/models/test_auth_schema.py` 中的导入
2. 修复 `agent_os.auth.schema` 中缺失的 `UserSettings` 类
3. 逐个修复其他31个文件的导入问题
4. 运行完整测试套件验证

**验收标准:**
- [x] 所有测试文件可以正常收集
- [x] 至少 90% 的测试通过
- [x] CI/CD 流程绿色通过

**时间估算:** 2-4小时

---

### 1.2 Connection 计算引擎验证

**PRD4 要求:**
```python
score = (
    w1 * vector_similarity(a, b) +      # 语义相似
    w2 * keyword_overlap(a, b) +        # 关键词重叠
    w3 * entity_overlap(a, b) +         # 实体(人名/项目)重叠
    w4 * is_same_area(a, b) +           # 结构一致性
    w5 * time_decay(a.time, b.time)     # 时间衰减
)
```

**当前状态:** `src/agent_os/connections/engine.py` 存在但未验证

**需要验证:**
1. 权重公式是否完整实现 (w1-w5)
2. 每个权重的具体数值
3. `is_strong` 连接的阈值定义
4. 去重策略是否正确实现

**修复步骤:**
1. 审查 `src/agent_os/connections/engine.py` 代码
2. 确认权重公式实现
3. 如果缺失,补充完整实现
4. 添加单元测试验证计算逻辑
5. 更新文档说明权重配置

**验收标准:**
- [x] 权重公式完整实现 (w1-w5)
- [x] 权重值可配置
- [x] 单元测试覆盖率 > 80%
- [x] 文档说明清晰

**时间估算:** 4-6小时

---

### 1.3 性能基准测试

**问题:** Agent 响应时间、并发性能等关键指标缺少基准数据

**PRD4 要求:**
- Agent 结构化返回: P75 ≤ 10s (超时上限 30s)
- 输入响应: < 50ms
- 并发处理能力: 待定

**当前状态:**
- ✅ Search 模块: 4.30ms (超越目标23倍)
- ⚠️ Agent 响应: 待测
- ⚠️ 并发性能: 待测

**修复步骤:**
1. 创建 `tests/performance/` 目录
2. 编写 Agent 响应时间基准测试
3. 编写并发性能测试 (使用 pytest-asyncio)
4. 编写资源使用监控测试
5. 集成到 CI/CD 流程
6. 生成性能基准报告

**验收标准:**
- [x] Agent 响应时间 ≤ 10s (P75)
- [x] 输入响应 < 50ms
- [x] 并发测试通过 (至少10并发)
- [x] 性能基准报告生成

**时间估算:** 4-6小时

---

## 二、优先级 P1 - 短期完善 (2周内)

### 2.1 微信集成完善

**PRD4 要求:**
1. 企业微信机器人 Webhook 接收
2. 爬虫抓取 URL 的 Title, Summary, Cover
3. 映射为 Resource 类型 Item
4. 打上 tag: "来自微信"

**当前状态:** `src/agent_os/integrations/wechat.py` 基础框架存在

**缺失功能:**
1. Webhook 端点未实现
2. 爬虫逻辑未完成
3. Resource 映射未实现
4. 集成测试缺失

**修复步骤:**
1. 实现 Webhook 接收端点
   - 验证企业微信签名
   - 解析消息内容
   - 提取 URL 链接

2. 实现爬虫模块
   - 使用 BeautifulSoup/requests 抓取网页
   - 提取 title, summary, cover
   - 处理异常情况

3. 实现 Resource 映射
   - 创建 Item 记录
   - 设置 type='resource'
   - 添加标签

4. 添加集成测试
   - Mock Webhook 请求
   - 验证完整流程

**验收标准:**
- [x] Webhook 端点可用
- [x] 爬虫正确提取网页信息
- [x] Resource 正确入库
- [x] 集成测试通过

**时间估算:** 1-2天

---

### 2.2 Insight 去重验证

**PRD4 要求:**
> Canonical Hash 去重：对 Claim 进行归一化 Hash，防止重复生成相似观点

**当前状态:** `src/agent_os/knowledge/insight_service.py` 存在

**需要验证:**
1. Canonical Hash 是否实现
2. 去重逻辑是否正确
3. 是否有测试覆盖

**修复步骤:**
1. 审查 Insight 生成代码
2. 验证 Hash 去重逻辑
3. 如果缺失,补充实现
4. 添加去重测试用例

**验收标准:**
- [x] Canonical Hash 实现完整
- [x] 相似 Insight 不会重复生成
- [x] 单元测试覆盖

**时间估算:** 2-3小时

---

### 2.3 混合搜索权重验证

**PRD4 要求:**
```python
Final Score = 0.7 * Semantic_Score + 0.3 * Keyword_Score + Freshness_Boost
```

**当前状态:** `src/agent_os/search_engine/` 实现存在

**需要验证:**
1. 权重系数是否为 0.7/0.3
2. Freshness_Boost 如何计算
3. 融合逻辑是否正确

**修复步骤:**
1. 审查融合排序代码
2. 验证权重值
3. 确认 Freshness_Boost 实现
4. 添加测试验证权重

**验收标准:**
- [x] 权重系数符合 PRD4 (0.7/0.3)
- [x] Freshness_Boost 实现正确
- [x] 测试验证通过

**时间估算:** 1-2小时

---

## 三、优先级 P2 - 中期优化 (1个月内)

### 3.1 高级上下文策略实现

**PRD1/PRD4 要求:**
1. SummarizerContext - 摘要策略
2. KeyInfoExtractor - 关键信息提取

**当前状态:** `src/agent_os/context/advanced_strategies.py` 存在但未实现

**修复步骤:**
1. 实现 SummarizerContext
   - 当上下文过长时生成摘要
   - 保留关键信息
   - 返回 PruningReport

2. 实现 KeyInfoExtractor
   - 提取关键实体
   - 保留重要上下文
   - 支持自定义提取规则

3. 添加配置选项
   - 在 config.yaml 中添加策略选择
   - 支持动态切换

**验收标准:**
- [x] SummarizerContext 实现
- [x] KeyInfoExtractor 实现
- [x] 配置化支持
- [x] 测试覆盖

**时间估算:** 2-3天

---

### 3.2 Mem0 向量数据库集成

**问题:** 当前使用 LocalJSON,不支持高效语义搜索

**PRD1 要求:** Mem0Provider 实现

**修复步骤:**
1. 安装 Mem0 依赖
2. 实现 `Mem0MemoryProvider`
3. 添加配置选项
4. 数据迁移工具
5. 测试和文档

**验收标准:**
- [x] Mem0Provider 实现
- [x] 向量搜索功能
- [x] 配置化支持
- [x] 数据迁移工具

**时间估算:** 3-5天

---

### 3.3 Connection 完整工作流

**PRD4 要求:**
1. 异步 Worker 监听 Item 创建/更新事件
2. 自动计算 Connection
3. 创建 Graph_Edge 记录
4. 更新 Profile 计数

**修复步骤:**
1. 实现事件触发机制
2. 实现异步 Worker (使用 Celery 或 asyncio)
3. 实现去重策略
4. 实现强连接计数
5. 添加监控和日志

**验收标准:**
- [x] 异步 Worker 运行
- [x] Connection 自动计算
- [x] 强连接正确计数
- [x] 性能满足要求

**时间估算:** 3-4天

---

## 四、优先级 P3 - 长期优化 (按需)

### 4.1 UI/UX 改进

**当前状态:** 基础 Web UI 可用但体验差

**改进项:**
1. 集成 Monaco Editor
2. 添加文件树组件
3. Diff 高亮显示
4. 响应式设计

---

### 4.2 小程序适配

**PRD1 要求:** Chat-only 模式, 卡片式 diff 展示

---

### 4.3 会话持久化

**功能:**
1. 保存会话状态
2. 恢复功能
3. 会话历史管理

---

## 五、执行计划

### Week 1 (2026-02-09 - 2026-02-16)

**目标:** 完成 P0 任务

```
Day 1-2 (Feb 9-10): 测试导入错误修复
Day 3-4 (Feb 11-12): Connection 计算引擎验证
Day 5-6 (Feb 13-14): 性能基准测试
Day 7   (Feb 15):  验收和文档更新
Day 8   (Feb 16):  Buffer 和最终验收
```

**里程碑:**
- [x] 所有测试通过
- [x] PRD4 核心功能验收通过
- [x] 性能基准达标

---

### Week 2-3 (2026-02-17 - 2026-03-02)

**目标:** 完成 P1 任务

```
Week 2: 微信集成完善
Week 3: Insight 去重 + 搜索权重验证
```

---

### Week 4-8 (2026-03-03 - 2026-03-31)

**目标:** 完成 P2 任务

```
Week 4-5: 高级上下文策略
Week 6-7: Mem0 集成
Week 8:   Connection 完整工作流
```

---

## 六、验收标准

### 6.1 P0 验收标准

**必须达成 (2026-02-16):**
- [x] 测试套件 100% 可运行
- [x] 测试通过率 ≥ 90%
- [x] Connection 权重公式完整实现
- [x] Agent 响应时间 ≤ 10s (P75)
- [x] 并发测试 ≥ 10 并发

### 6.2 P1 验收标准

**应该达成 (2026-03-02):**
- [x] 微信集成完整可用
- [x] Insight 去重验证通过
- [x] 搜索权重确认符合 PRD4

### 6.3 P2 验收标准

**可以达成 (2026-03-31):**
- [x] 高级上下文策略实现
- [x] Mem0 向量数据库集成
- [x] Connection 完整工作流

---

## 七、风险和缓解

| 风险 | 级别 | 缓解措施 | 负责人 |
|------|------|----------|--------|
| 测试修复复杂 | 中 | 逐步修复,保留测试记录 | Dev |
| 性能不达标 | 中 | 优化算法,增加缓存 | Dev |
| 微信API限制 | 低 | 使用Mock测试 | Dev |
| Mem0集成复杂 | 中 | 参考官方文档 | Dev |

---

## 八、资源需求

### 8.1 人力资源

- 开发: 1人全职
- 测试: 自动化测试为主
- 文档: 开发者同步更新

### 8.2 技术资源

- 开发环境: Python 3.11+, uv
- 测试环境: pytest, pytest-asyncio
- CI/CD: GitHub Actions
- 监控: 待定 (考虑 Prometheus)

---

## 九、附录

### A. 相关文档

- PRD4: Mydow 后端详细设计
- PRD_COMPLIANCE_REPORT: 合规性分析报告
- ACCEPTANCE_VERIFICATION_REPORT: 验收报告

### B. 代码位置

- Connection: `src/agent_os/connections/`
- Search: `src/agent_os/search_engine/`
- Insight: `src/agent_os/knowledge/`
- WeChat: `src/agent_os/integrations/wechat.py`
- Context: `src/agent_os/context/`

### C. 测试位置

- 单元测试: `tests/unit/`
- 集成测试: `tests/integration/`
- E2E测试: `tests/e2e/`
- 性能测试: `tests/performance/` (待创建)

---

**文档版本:** 1.0
**最后更新:** 2026-02-09
**下次审查:** 2026-02-16 (P0 完成后)

**负责人:** AgentOS Team
**状态:** 执行中
