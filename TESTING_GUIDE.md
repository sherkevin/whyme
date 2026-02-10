# AgentOS 测试指南

## 测试分类

AgentOS 测试分为三类：

### 1. 单元测试 (Unit Tests)

快速、独立的测试，不依赖外部服务或完整集成。

- **位置:** `tests/unit/`
- **运行时间:** ~30秒
- **通过率:** 100% (331/331)
- **运行命令:**
  ```bash
  # 运行所有单元测试
  uv run pytest tests/unit -m "not integration"

  # 运行特定模块
  uv run pytest tests/unit/models
  uv run pytest tests/unit/services/test_card_generator.py
  ```

### 2. 集成测试 (Integration Tests)

测试多个模块之间的集成，可能需要 LLM 或数据库。

- **位置:** `tests/unit/services/test_processor.py` (标记为 `@pytest.mark.integration`)
- **运行时间:** ~2-5分钟
- **通过率:** 22% (4/18)
- **运行命令:**
  ```bash
  # 运行所有集成测试
  uv run pytest tests/unit -m "integration"

  # 或使用 pytest 标记
  uv run pytest -m integration
  ```

**注意:** Processor 测试需要 LLM 集成或 mocking 才能完全通过。

### 3. 性能测试 (Performance Tests)

验证系统性能符合 PRD4 要求。

- **位置:** `tests/performance/`
- **运行时间:** ~2秒
- **通过率:** 100% (12/12)
- **运行命令:**
  ```bash
  uv run pytest tests/performance -v -m performance
  ```

## 快速开始

### 运行所有单元测试（推荐）

```bash
uv run pytest tests/unit -m "not integration" -v
```

**预期结果:** 331 passed ✅

### 运行性能测试

```bash
uv run pytest tests/performance -v -m performance
```

**预期结果:** 12 passed ✅

### 运行特定模块

```bash
# Models
uv run pytest tests/unit/models -v

# Services (excluding integration)
uv run pytest tests/unit/services -m "not integration" -v

# 特定文件
uv run pytest tests/unit/services/test_auth_jwt.py -v
```

## 测试通过率

### 当前状态

| 测试类型 | 总数 | 通过 | 通过率 |
|---------|------|------|--------|
| **单元测试** | 331 | 331 | 100% ✅ |
| **集成测试** | 18 | 4 | 22% ⚠️ |
| **性能测试** | 12 | 12 | 100% ✅ |
| **总计** | 361 | 347 | 96% 🏆 |

### 模块详情

#### 单元测试（100% 通过率）

| 模块 | 测试数 | 状态 |
|------|--------|------|
| performance | 12 | ✅ 100% |
| config | 6 | ✅ 100% |
| tool_registry | 11 | ✅ 100% |
| utils | 96 | ✅ 100% |
| models | 106 | ✅ 100% |
| auth_jwt | 15 | ✅ 100% |
| card_generator_unit | 15 | ✅ 100% |
| card_generator | 15 | ✅ 100% |
| embedding_service | 12 | ✅ 100% |
| ingestion_service | 21 | ✅ 100% |
| insight_service | 19 | ✅ 100% |
| stage3_routes | 3 | ✅ 100% |

#### 集成测试（需要 LLM）

| 模块 | 测试数 | 状态 | 说明 |
|------|--------|------|------|
| processor | 18 | 22% | 需要 LLM 集成 |

## CI/CD 集成

### GitHub Actions 配置示例

```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      - name: Run unit tests
        run: uv run pytest tests/unit -m "not integration" -v

  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      - name: Run performance tests
        run: uv run pytest tests/performance -v -m performance
```

## 性能基线

### PRD4 性能目标

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| 搜索 200 项 | <100ms | 5.49ms | ✅ |
| 混合向量搜索 | <100ms | 1.14ms | ✅ |
| 并发 4 次搜索 | <500ms | 2.21ms | ✅ |
| Agent 框架响应 | ≤10s | 1.08ms | ✅ |

所有性能目标大幅超越 🏆

## 故障排除

### pytest-asyncio 错误

如果看到 `ScopeMismatch` 错误，确保：
1. `pyproject.toml` 中设置了 `asyncio_default_fixture_loop_scope = "function"`
2. Fixtures 使用 `scope="function"` 而不是 `"session"`

### 数据库约束错误

如果看到 `CHECK constraint failed: check_search_item_type`，确保：
1. 数据库模型已更新
2. 删除旧的测试数据库 `rm test.db`
3. 重新运行测试

### LLM 相关错误

Processor 测试失败是因为需要 LLM 集成。这是预期的：
- 这些测试标记为 `@pytest.mark.integration`
- 从单元测试中排除：`pytest tests/unit -m "not integration"`

## 更多信息

- **性能报告:** `PERFORMANCE_BASELINE_REPORT.md`
- **测试改进报告:** `TEST_PASS_RATE_IMPROVEMENT_REPORT.md`
- **最终完成报告:** `FINAL_TEST_COMPLETION_REPORT.md`
- **会话总结:** `SESSION_SUMMARY.md`

---

**Generated with [Claude Code](https://claude.ai/code)**
**via [Happy](https://happy.engineering)**
