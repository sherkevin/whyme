# 测试套件

AgentOS 使用 pytest 作为测试框架。

## 测试结构

```
tests/
├── unit/              # 单元测试
│   ├── models/        # 数据模型测试
│   ├── services/      # 服务层测试
│   ├── api/           # API 端点测试
│   └── utils/         # 工具函数测试
├── integration/       # 集成测试
│   ├── workflows/     # 工作流测试
│   └── api/           # API 集成测试
├── e2e/               # 端到端测试
│   └── scenarios/     # 用户场景测试
├── performance/       # 性能测试
│   └── test_performance.py
├── fixtures/          # 测试固件
│   ├── db.py          # 数据库固件
│   ├── auth.py        # 认证固件
│   └── data.py        # 测试数据
├── conftest.py        # pytest 配置
└── README.md          # 本文件
```

## 运行测试

### 运行所有测试

```bash
# 使用 uv
uv run pytest

# 或使用 pytest
pytest
```

### 运行特定测试

```bash
# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/

# E2E 测试
pytest tests/e2e/

# 性能测试
pytest tests/performance/ -m performance
```

## 测试覆盖率

生成覆盖率报告：

```bash
# 生成终端报告
pytest --cov=src/agent_os --cov-report=term

# 生成 HTML 报告
pytest --cov=src/agent_os --cov-report=html
```

## 最佳实践

1. **隔离性**: 每个测试应该独立运行
2. **清晰性**: 测试名称应该描述测试内容
3. **快速性**: 单元测试应该快速运行
4. **可维护性**: 使用 fixtures 避免重复代码

---
**维护者**: AgentOS Team
**最后更新**: 2026-02-09
