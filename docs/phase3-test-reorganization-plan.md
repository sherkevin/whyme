# Phase 3: 测试重组计划

**日期**: 2026-02-08
**阶段**: Phase 3 - 测试重组
**预计时间**: 1周

---

## 当前测试结构问题

### 问题分析

**当前状态**:
```
tests/
├── conftest.py
├── e2e_scenarios.py
├── embedding_unit.py
├── ingestion_unit.py
├── integration.py
├── models_unit.py
├── search_engine_*.py (6个文件)
├── test_agent_*.py (3个文件)
├── test_auth_*.py (5个文件)
├── test_card_*.py (3个文件)
├── test_*.py (其他60+个文件)
└── ...
```

**主要问题**:
1. ❌ 所有测试文件平铺在 `tests/` 根目录
2. ❌ 测试文件命名不一致
3. ❌ 无法区分单元测试、集成测试、E2E测试
4. ❌ 缺少按功能模块分类

---

## 目标结构

```
tests/
├── conftest.py                    # 共享fixture
├── __init__.py
│
├── unit/                          # 单元测试
│   ├── services/                  # 服务层单元测试
│   │   ├── test_search_service.py
│   │   ├── test_insight_service.py
│   │   ├── test_ingestion_service.py
│   │   ├── test_auth_service.py
│   │   └── test_task_service.py
│   ├── repositories/              # 数据访问层单元测试
│   │   ├── test_search_repository.py
│   │   ├── test_knowledge_repository.py
│   │   └── test_task_repository.py
│   ├── models/                    # 模型单元测试
│   │   ├── test_search_models.py
│   │   ├── test_knowledge_models.py
│   │   └── test_auth_models.py
│   └── utils/                     # 工具函数单元测试
│       ├── test_text_chunker.py
│       ├── test_content_fetcher.py
│       └── test_card_generator.py
│
├── integration/                   # 集成测试
│   ├── api/                       # API集成测试
│   │   ├── test_search_api.py
│   │   ├── test_knowledge_api.py
│   │   ├── test_auth_api.py
│   │   └── test_task_api.py
│   └── workflows/                 # 工作流集成测试
│       ├── test_search_workflow.py
│       ├── test_ingestion_workflow.py
│       └── test_agent_workflow.py
│
├── e2e/                           # 端到端测试
│   ├── scenarios/                 # 用户场景测试
│   │   ├── test_researcher_workflow.py
│   │   ├── test_analyst_workflow.py
│   │   └── test_content_creator_workflow.py
│   └── performance/               # 性能测试
│       ├── test_search_performance.py
│       └── test_insight_performance.py
│
└── legacy/                        # 旧版测试（待重构）
    └── ...
```

---

## 执行计划

### 第一步：分类测试文件（已分析）

**搜索引擎测试** (search_engine):
- `search_engine_search_unit.py` → unit/services/
- `search_engine_insight_unit.py` → unit/services/
- `embedding_unit.py` → unit/services/
- `ingestion_unit.py` → unit/services/
- `models_unit.py` → unit/models/
- `test_search_engine_stage2.py` → integration/api/
- `test_search_engine_stage2_simple.py` → integration/api/
- `test_search_engine_vector.py` → integration/api/
- `e2e_scenarios.py` → e2e/scenarios/
- `integration.py` → integration/workflows/

**认证测试** (auth):
- `test_auth_api.py` → integration/api/
- `test_auth_crud.py` → integration/api/
- `test_auth_integration.py` → integration/api/
- `test_auth_jwt.py` → unit/services/
- `test_auth_schema.py` → unit/models/
- `test_auth_security.py` → integration/api/

**知识管理测试** (knowledge):
- `test_knowledge_crud.py` → integration/api/
- `test_knowledge_schema.py` → unit/models/
- `test_card_generation_integration.py` → integration/workflows/
- `test_card_generator.py` → unit/services/
- `test_card_generator_unit.py` → unit/services/
- `test_rag_interface.py` → integration/workflows/

**任务管理测试** (tasks):
- `test_tasks_crud.py` → integration/api/
- `test_tasks_schema.py` → unit/models/

**Agent测试** (agent):
- `test_agent_api_basic.py` → integration/api/
- `test_agent_api_integration.py` → integration/api/
- `test_agent_api.py` → integration/api/
- `test_agent_models.py` → unit/models/
- `test_processor.py` → unit/services/
- `test_classifier.py` → unit/utils/
- `test_summarizer.py` → unit/utils/
- `test_title_generator.py` → unit/utils/

**Stage 3测试** (stage3):
- `test_stage3_api_integration.py` → integration/api/
- `test_stage3_demo.py` → e2e/scenarios/
- `test_stage3_models_unit.py` → unit/models/
- `test_stage3_routes_unit.py` → unit/services/

**其他测试**:
- `test_app.py` → integration/
- `test_connection_engine.py` → integration/
- `test_observability_integration.py` → integration/
- `test_skill_service_unit.py` → unit/services/
- `test_skills.py` → integration/api/
- `test_repo_map.py` → integration/
- `test_websocket_io.py` → integration/

---

## 执行步骤

### Step 1: 创建目录结构

```bash
cd tests/
mkdir -p unit/services unit/repositories unit/models unit/utils
mkdir -p integration/api integration/workflows
mkdir -p e2e/scenarios e2e/performance
mkdir -p legacy
```

### Step 2: 移动测试文件

**搜索引擎测试**:
```bash
# Unit tests
mv search_engine_search_unit.py unit/services/test_search_service.py
mv search_engine_insight_unit.py unit/services/test_insight_service.py
mv embedding_unit.py unit/services/test_embedding_service.py
mv ingestion_unit.py unit/services/test_ingestion_service.py
mv models_unit.py unit/models/test_search_models.py

# Integration tests
mv test_search_engine_stage2.py integration/api/test_search_api.py
mv test_search_engine_stage2_simple.py integration/api/test_search_api_simple.py
mv test_search_engine_vector.py integration/api/test_vector_search_api.py
mv integration.py integration/workflows/test_search_workflow.py

# E2E tests
mv e2e_scenarios.py e2e/scenarios/test_user_workflows.py
```

### Step 3: 更新导入路径

```python
# 更新测试中的导入
# from agent_os.search_engine import ...
# 保持不变（模块路径未变）
```

### Step 4: 更新 conftest.py

确保所有测试能正确找到 fixtures。

---

## 验证计划

### 1. 运行所有测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v

# 运行E2E测试
pytest tests/e2e/ -v
```

### 2. 检查测试覆盖率

```bash
pytest --cov=agent_os tests/unit/ --cov-report=html
```

### 3. 验证pytest能发现所有测试

```bash
pytest --collect-only | grep "test session starts"
```

---

## 预期结果

### 改进指标

| 指标 | 改进前 | 改进后 | 改善 |
|------|--------|--------|------|
| 测试目录层级 | 1层 | 3层 | ✅ |
| 测试分类 | 无 | 按类型/功能 | ✅ |
| 命名一致性 | 低 | 高 | ✅ |
| 可维护性 | 低 | 高 | ✅ |

### 质量提升

- ✅ 清晰的测试组织结构
- ✅ 易于找到特定测试
- ✅ 便于并行测试执行
- ✅ 提高代码可读性

---

## 风险评估

**风险等级**: 🟡 中等

**潜在问题**:
1. 导入路径可能需要更新
2. pytest discovery 需要验证
3. CI/CD 配置可能需要更新

**缓解措施**:
1. 分批移动，每次验证
2. 保留 Git 历史便于回滚
3. 更新 CI/CD 配置

---

**创建时间**: 2026-02-08
**状态**: 准备执行
**预计完成**: Phase 3 Week 7
