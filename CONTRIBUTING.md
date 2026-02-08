# Contributing to AgentOS

感谢您对 AgentOS 的贡献兴趣！我们欢迎所有形式的贡献。

## 开发环境设置

### 前置要求
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (推荐的 Python 包管理器)
- Docker (用于容器化部署)
- Git

### 安装步骤

1. **Fork 并克隆仓库**
```bash
git clone https://github.com/your-username/agent-os.git
cd agent-os
```

2. **安装 uv** (如果尚未安装)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. **安装依赖**
```bash
uv sync --dev
```

4. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件,填入必要的配置
```

## 开发工作流

### 分支策略
- `master` - 主分支,保持稳定
- `develop` - 开发分支
- `feature/*` - 功能分支
- `bugfix/*` - 修复分支
- `hotfix/*` - 紧急修复分支

### 提交规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型 (type):**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式(不影响代码运行)
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具链相关

**示例:**
```bash
git commit -m "feat(memory): add vector store support"
git commit -m "fix(auth): resolve JWT token expiration issue"
git commit -m "docs: update API documentation"
```

### 代码规范

#### Linting
```bash
# 运行 ruff linter
uv run ruff check src/ tests/

# 自动修复
uv run ruff check --fix src/ tests/
```

#### 格式化
```bash
# 检查格式
uv run ruff format --check src/ tests/

# 自动格式化
uv run ruff format src/ tests/
```

#### 类型检查
```bash
uv run mypy src/agent_os --ignore-missing-imports
```

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定类型的测试
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m e2e

# 运行特定文件
uv run pytest tests/unit/test_config.py

# 带覆盖率报告
uv run pytest --cov=src/agent_os --cov-report=html
```

### 运行应用

```bash
# 开发模式
uv run python -m agent_os.server.app

# 或使用 Docker
docker-compose up
```

## Pull Request 流程

### 1. 创建功能分支
```bash
git checkout -b feature/your-feature-name
```

### 2. 进行开发和测试
```bash
# 开发
# 运行测试
uv run pytest
# 运行 lint
uv run ruff check src/ tests/
```

### 3. 提交变更
```bash
git add .
git commit -m "feat: add your feature"
```

### 4. 推送到你的 Fork
```bash
git push origin feature/your-feature-name
```

### 5. 创建 Pull Request
- 访问原始仓库
- 点击 "New Pull Request"
- 填写 PR 模板
- 等待 Code Review

### PR 检查清单
- [ ] 代码通过所有 CI 检查
- [ ] 添加了必要的测试
- [ ] 更新了相关文档
- [ ] 遵循代码规范
- [ ] 提交信息符合规范

## 报告 Bug

1. 检查 [Issues](https://github.com/your-org/agent-os/issues) 是否已存在
2. 如果没有,创建新 Issue 并包含:
   - 清晰的标题和描述
   - 复现步骤
   - 期望行为 vs 实际行为
   - 环境信息(OS, Python 版本等)
   - 相关日志或错误信息

## 提出新功能

1. 先创建 [Discussion](https://github.com/your-org/agent-os/discussions) 讨论
2. 获得反馈后创建 Feature Request Issue
3. 等待维护者确认后再开始开发

## 代码审查准则

审查者会关注:
- **功能性**: 代码是否实现了预期功能
- **可读性**: 代码是否易于理解
- **可维护性**: 是否容易修改和扩展
- **测试覆盖**: 是否有足够的测试
- **性能**: 是否有明显的性能问题
- **安全性**: 是否存在安全漏洞

## 许可证

提交贡献即表示您同意您的贡献将根据项目的 [MIT License](LICENSE) 进行许可。

## 联系方式

- GitHub Issues: 报告 bug 和功能请求
- GitHub Discussions: 一般问题交流
- Email: dev@example.com

感谢您的贡献！
