# 项目结构重组计划

**创建时间:** 2026-02-09
**目标:** 符合软件工程最佳实践的项目结构

---

## 📊 当前问题分析

### 根目录混乱 ⚠️

```
whyme/
├── alembic/          # ❌ 数据库迁移应在源码内
├── archives/         # ❌ 应在 docs/ 下
├── data/             # ❌ 运行时数据，不应提交
├── docker/           # ✅ 正确
├── docs/             # ✅ 正确
├── global_toolkit/   # ❌ 应在 src/ 或 config/
├── screenshots/      # ❌ 应在 docs/ 下
├── scripts/          # ✅ 正确
├── src/              # ✅ 正确
└── tests/            # ✅ 正确
```

### 主要问题

1. **根目录污染** - archives, global_toolkit, screenshots 不应在根目录
2. **数据库迁移位置** - alembic 应在 src/agent_os/db/
3. **配置文件分散** - 多处配置未统一
4. **文档不完整** - 缺少标准文件 (如 ARCHITECTURE.md, CONTRIBUTING.md 等)

---

## 🎯 目标结构

### Python 项目标准结构

参考: https://docs.python-guide.org/writing/structure/

```
whyme/
├── .github/                  # GitHub 配置
│   ├── workflows/            # CI/CD
│   └── dependabot.yml
├── .vscode/                  # VS Code 配置
├── alembic/                  # 数据库迁移 (保留，考虑移入 src)
├── config/                   # 配置文件 (新增)
│   ├── settings/             # 环境配置
│   ├── toolkit/              # 从 global_toolkit 迁移
│   └── examples/             # 配置示例
├── data/                     # 运行时数据 (.gitignore)
│   └── .gitkeep
├── docker/                   # Docker 配置
│   ├── api/
│   ├── postgres/
│   └── README.md
├── docs/                     # 文档 (已重组)
│   ├── 00-start.md
│   ├── 01-prd/
│   ├── ...
│   ├── screenshots/          # 从根目录迁移
│   └── _static/              # 静态资源
├── scripts/                  # 工具脚本
│   ├── setup/
│   ├── deploy/
│   ├── migration/
│   └── README.md
├── src/                      # 源代码
│   └── agent_os/             # 主包
│       ├── __init__.py
│       ├── agent/            # Agent 模块
│       ├── api/              # FastAPI 路由
│       ├── auth/             # 认证
│       ├── connections/      # 连接
│       ├── context/          # 上下文
│       ├── core/             # 核心工具
│       ├── db/               # 数据库
│       │   ├── alembic/      # 迁移脚本 (考虑)
│       │   ├── models/       # 数据模型
│       │   └── repositories/ # 数据访问
│       ├── inbox/            # 收件箱
│       ├── integrations/     # 集成
│       ├── items/            # Items
│       ├── knowledge/        # 知识库
│       ├── llm/              # LLM 抽象
│       ├── memory/           # 记忆系统
│       ├── observability/    # 可观测性
│       ├── search_engine/    # 搜索
│       ├── server/           # FastAPI 应用
│       ├── skills/           # Skills
│       ├── tasks/            # Tasks
│       └── utils/            # 工具函数
├── tests/                    # 测试
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   ├── e2e/                  # E2E 测试
│   ├── performance/          # 性能测试
│   ├── fixtures/             # 测试固件
│   ├── conftest.py           # pytest 配置
│   └── README.md
├── web/                      # 前端 (如存在)
│   └── ...
├── .dockerignore
├── .env.example              # 环境变量示例
├── .gitattributes
├── .gitignore
├── .pre-commit-config.yaml
├── CHANGELOG.md
├── CONTRIBUTING.md           # 贡献指南
├── docker-compose.yml
├── docker-compose.api.yml
├── LICENSE
├── Makefile
├── pyproject.toml
├── QUICKSTART.md
├── README.md
├── SECURITY.md               # 安全政策
├── └── VERSION                # 版本号
```

---

## 📋 重组步骤

### Phase 1: 配置和工具 (30分钟)

**1.1 创建 config/ 目录**
```bash
mkdir -p config/settings
mkdir -p config/toolkit
mkdir -p config/examples
```

**1.2 迁移 global_toolkit/**
```bash
mv global_toolkit/* config/toolkit/
```

**1.3 添加标准配置文件**
- 创建 `config/settings/__init__.py`
- 添加 `.env.example`
- 添加 `config/settings/development.py`
- 添加 `config/settings/production.py`

### Phase 2: 文档整理 (20分钟)

**2.1 创建文档资源目录**
```bash
mkdir -p docs/_static
mkdir -p docs/screenshots
mkdir -p docs/diagrams
```

**2.2 迁移 screenshots/**
```bash
mv screenshots/* docs/screenshots/
```

**2.3 迁移 archives/**
```bash
mv archives docs/archives
```

### Phase 3: 源代码重组 (1小时)

**3.1 优化 src/agent_os/ 结构**
- 确保模块清晰分离
- 添加 `src/agent_os/core/` 用于共享工具
- 添加 `src/agent_os/api/` 统一 API 路由

**3.2 数据库层重组**
- 考虑移动 alembic 到 `src/agent_os/db/alembic/`
- 添加 `src/agent_os/db/repositories/`
- 添加 `src/agent_os/db/migrations/`

### Phase 4: 测试结构优化 (30分钟)

**4.1 添加测试辅助**
```bash
mkdir -p tests/fixtures
mkdir -p tests/helpers
```

**4.2 添加测试 README**
- 创建 `tests/README.md`
- 说明测试运行方式
- 添加测试覆盖率目标

### Phase 5: 脚本组织 (20分钟)

**5.1 重组 scripts/**
```bash
mkdir -p scripts/setup
mkdir -p scripts/deploy
mkdir -p scripts/migration
mkdir -p scripts/dev
```

**5.2 添加脚本说明**
- 创建 `scripts/README.md`

### Phase 6: 添加标准文件 (30分钟)

**6.1 添加缺失的标准文件**
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `VERSION`
- `ARCHITECTURE.md`

**6.2 更新现有文件**
- 更新 `CONTRIBUTING.md`
- 更新 `README.md`
- 更新 `.gitignore`

### Phase 7: 更新引用 (1小时)

**7.1 更新导入路径**
- 更新 Python 导入
- 更新文档链接
- 更新配置引用

**7.2 测试验证**
- 运行测试套件
- 验证导入
- 检查文档链接

---

## ✅ 验收标准

- [ ] 根目录只包含标准文件
- [ ] 所有配置集中在 config/
- [ ] 文档资源在 docs/_static/
- [ ] 源代码模块清晰分离
- [ ] 测试结构符合 pytest 最佳实践
- [ ] 脚本按功能分类
- [ ] 所有测试通过
- [ ] 文档链接正确

---

## 📝 注意事项

### Git 操作

使用 `git mv` 保留历史：
```bash
git mv old_path new_path
```

### 批量移动

对于大量文件，使用脚本：
```bash
#!/bin/bash
# move_toolkit.sh
for file in global_toolkit/*; do
    git mv "$file" "config/toolkit/$(basename $file)"
done
```

### 测试验证

每个阶段后运行：
```bash
pytest tests/ -v
python -m agent_os.server.app
```

---

## 🎯 预期收益

1. **清晰性** - 标准结构易于理解
2. **可维护性** - 模块分离清晰
3. **可扩展性** - 易于添加新功能
4. **专业性** - 符合行业最佳实践
5. **协作友好** - 新人快速上手

---

**创建者:** Claude (AI Assistant)
**预计时间:** 4 小时
**优先级:** P1 - 高
**状态:** 计划中
