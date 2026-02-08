# AgentOS Makefile - 开发和部署命令
# 支持 uv 包管理器的现代化 Python 项目

.PHONY: help start stop restart logs test build clean install
.PHONY: lint format type-check security-check
.PHONY: dev-install dev-server db-upgrade db-downgrade
.PHONY: docker-build docker-deploy docker-clean

# 默认目标
help:
	@echo "AgentOS 开发和部署命令:"
	@echo ""
	@echo "🚀 快速启动:"
	@echo "  make start           - 启动服务 (Docker)"
	@echo "  make stop            - 停止服务"
	@echo "  make restart         - 重启服务"
	@echo "  make logs            - 查看日志"
	@echo "  make dev-server      - 本地开发服务器"
	@echo ""
	@echo "📦 依赖管理:"
	@echo "  make install         - 安装依赖 (本地)"
	@echo "  make dev-install     - 安装开发依赖 (uv)"
	@echo ""
	@echo "🧪 测试:"
	@echo "  make test            - 运行测试 (Docker)"
	@echo "  make test-local      - 本地运行测试"
	@echo "  make test-cov        - 测试覆盖率报告"
	@echo "  make test-unit       - 单元测试"
	@echo "  make test-integration - 集成测试"
	@echo ""
	@echo "🔍 代码质量:"
	@echo "  make lint            - 代码检查"
	@echo "  make lint-fix        - 自动修复"
	@echo "  make format          - 格式化代码"
	@echo "  make type-check      - 类型检查"
	@echo "  make security-check  - 安全检查"
	@echo "  make check           - 运行所有检查"
	@echo ""
	@echo "🗄️ 数据库:"
	@echo "  make db-upgrade      - 升级数据库"
	@echo "  make db-downgrade    - 降级数据库"
	@echo "  make db-migrate      - 创建迁移"
	@echo ""
	@echo "🐳 Docker:"
	@echo "  make build           - 构建镜像"
	@echo "  make clean           - 清理容器和镜像"
	@echo "  make docker-deploy   - Docker 快速部署"
	@echo "  make docker-help     - Docker 命令帮助"
	@echo ""
	@echo "前端同学推荐:"
	@echo "  make start           - 一键启动后端API"
	@echo "  然后访问 http://localhost:8000/docs"

# 启动服务
start:
	@echo "🚀 启动AgentOS服务..."
	@mkdir -p data logs
	@docker-compose -f docker-compose.api.yml up -d
	@echo ""
	@echo "✅ 服务已启动!"
	@echo "📖 API文档: http://localhost:8000/docs"
	@echo "🔌 API地址: http://localhost:8000"
	@echo "📊 WebSocket: ws://localhost:8003"
	@echo ""
	@echo "查看日志: make logs"
	@echo "停止服务: make stop"

# 停止服务
stop:
	@echo "🛑 停止AgentOS服务..."
	@docker-compose -f docker-compose.api.yml down
	@echo "✅ 服务已停止"

# 重启服务
restart:
	@echo "🔄 重启AgentOS服务..."
	@docker-compose -f docker-compose.api.yml restart api
	@echo "✅ 服务已重启"

# 查看日志
logs:
	@docker-compose -f docker-compose.api.yml logs -f api

# 运行测试
test:
	@echo "🧪 运行测试套件..."
	@docker-compose -f docker-compose.api.yml exec api pytest tests/ -v

# 快速测试 (本地)
test-local:
	@echo "🧪 本地运行测试..."
	@uv run pytest tests/test_websocket_io.py \
	                tests/test_diff_confirmation.py \
	                tests/test_repo_map.py \
	                tests/test_json_render.py \
	                tests/test_skills.py \
	                tests/test_conversation_persistence.py -v

# 构建镜像
build:
	@echo "🔨 构建Docker镜像..."
	@docker-compose -f docker-compose.api.yml build

# 重建镜像
rebuild:
	@echo "🔨 重新构建Docker镜像..."
	@docker-compose -f docker-compose.api.yml build --no-cache

# 清理
clean:
	@echo "🧹 清理容器和镜像..."
	@docker-compose -f docker-compose.api.yml down -v
	@docker system prune -f
	@echo "✅ 清理完成"

# 安装依赖 (本地开发)
install:
	@echo "📦 安装Python依赖 (uv)..."
	@uv sync --dev
	@echo "✅ 依赖安装完成"
	@echo ""
	@echo "启动开发服务器:"
	@echo "  make dev-server"
	@echo "  或: uv run uvicorn agent_os.server.app:app --reload --host 0.0.0.0 --port 8000"

# 数据库迁移
migrate:
	@echo "🗄️ 运行数据库迁移..."
	@docker-compose -f docker-compose.api.yml exec api alembic upgrade head

# 创建迁移
create-migration:
	@echo "📝 创建新的数据库迁移..."
	@read -p "迁移名称: " name; \
	docker-compose -f docker-compose.api.yml exec api alembic revision --autogenerate -m "$$name"

# 进入容器
shell:
	@docker-compose -f docker-compose.api.yml exec api bash

# 检查健康状态
health:
	@echo "🏥 检查服务健康状态..."
	@curl -f http://localhost:8000/docs || echo "❌ 服务未响应"
	@docker-compose -f docker-compose.api.yml ps

# 显示端口占用
ports:
	@echo "🔌 检查端口占用..."
	@echo "端口 8000 (API):"
	@netstat -ano | findstr :8000 || echo "  ✅ 可用"
	@echo "端口 8003 (WebSocket):"
	@netstat -ano | findstr :8003 || echo "  ✅ 可用"
	@echo "端口 5432 (PostgreSQL):"
	@netstat -ano | findstr :5432 || echo "  ✅ 可用"

# 查看容器状态
status:
	@docker-compose -f docker-compose.api.yml ps

# 完整的启动流程 (首次使用)
init: | stop ports install build start
	@echo ""
	@echo "🎉 AgentOS初始化完成!"
	@echo ""
	@echo "下一步:"
	@echo "  1. 访问API文档: http://localhost:8000/docs"
	@echo "  2. 注册用户并获取token"
	@echo "  3. 使用token测试其他接口"
	@echo ""
	@echo "查看完整文档: docs/FRONTEND_INTEGRATION_GUIDE.md"

# ========================================
# 开发工具命令 (uv)
# ========================================

# 安装开发依赖
dev-install:
	@echo "📦 安装开发依赖 (uv)..."
	@uv sync --dev
	@echo "✅ 开发依赖安装完成"
	@uv run pre-commit install
	@echo "✅ Pre-commit hooks 已安装"

# 本地开发服务器
dev-server:
	@echo "🚀 启动开发服务器..."
	@uv run uvicorn agent_os.server.app:app --reload --host 0.0.0.0 --port 8000

# 代码检查
lint:
	@echo "🔍 运行代码检查 (ruff)..."
	@uv run ruff check src/ tests/

# 自动修复代码问题
lint-fix:
	@echo "🔧 自动修复代码问题..."
	@uv run ruff check --fix src/ tests/

# 代码格式化
format:
	@echo "✨ 格式化代码 (ruff format)..."
	@uv run ruff format src/ tests/

# 检查格式
format-check:
	@echo "✨ 检查代码格式..."
	@uv run ruff format --check src/ tests/

# 类型检查
type-check:
	@echo "🔬 运行类型检查 (mypy)..."
	@uv run mypy src/agent_os --ignore-missing-imports

# 安全检查
security-check:
	@echo "🔒 运行安全检查 (bandit)..."
	@uv run bandit -r src/agent_os -f screen -ll
	@echo "✅ 安全检查完成"

# 运行所有检查 (CI前检查)
check: lint format-check type-check
	@echo "✅ 所有检查通过!"

# 测试覆盖率
test-cov:
	@echo "🧪 运行测试并生成覆盖率报告..."
	@uv run pytest --cov=src/agent_os --cov-report=html --cov-report=term-missing
	@echo "✅ 覆盖率报告已生成: htmlcov/index.html"

# 快速测试 (仅单元测试)
test-unit:
	@echo "🧪 运行单元测试..."
	@uv run pytest -m unit -v

# 集成测试
test-integration:
	@echo "🧪 运行集成测试..."
	@uv run pytest -m integration -v

# 数据库升级
db-upgrade:
	@echo "🗄️ 升级数据库..."
	@uv run alembic upgrade head

# 数据库降级
db-downgrade:
	@echo "🗄️ 降级数据库..."
	@uv run alembic downgrade -1

# 创建迁移
db-migrate:
	@echo "📝 创建数据库迁移..."
	@read -p "迁移名称: " name; \
	uv run alembic revision --autogenerate -m "$$name"

# 数据库回滚
db-rollback:
	@echo "🔙 回滚数据库..."
	@uv run alembic downgrade base

# ========================================
# Docker 简化部署命令
# ========================================

# Docker 快速部署
docker-deploy:
	@echo "🐳 使用 Docker 快速部署..."
	@bash docker-deploy.sh

# Docker Compose 快速启动
docker-up:
	@echo "🐳 启动 Docker 服务..."
	@docker-compose -f docker-compose.simple.yml up -d
	@echo "✅ 服务已启动!"
	@echo "📍 访问地址: http://localhost:8003"
	@echo "📋 查看日志: make docker-logs"

# Docker Compose 停止
docker-down:
	@echo "🐳 停止 Docker 服务..."
	@docker-compose -f docker-compose.simple.yml down
	@echo "✅ 服务已停止"

# Docker Compose 日志
docker-logs:
	@docker-compose -f docker-compose.simple.yml logs -f

# Docker Compose 重启
docker-restart:
	@echo "🐳 重启 Docker 服务..."
	@docker-compose -f docker-compose.simple.yml restart
	@echo "✅ 服务已重启"

# Docker 构建快速版本
docker-build:
	@echo "🐳 构建 Docker 镜像 (快速版)..."
	@docker build -f Dockerfile.fast -t agentos:latest .
	@echo "✅ 镜像构建完成"

# Docker 运行容器
docker-run:
	@echo "🐳 运行 Docker 容器..."
	@docker run -d \
		--name agentos \
		-p 8003:8003 \
		-v agentos-data:/app/data \
		-e AGENTOS_SANDBOX=local \
		--restart unless-stopped \
		agentos:latest
	@echo "✅ 容器已启动"
	@echo "📍 访问地址: http://localhost:8003"

# Docker 进入容器
docker-shell:
	@docker exec -it agentos bash

# Docker 查看状态
docker-status:
	@echo "🐳 Docker 服务状态:"
	@echo ""
	@docker ps -f name=agentos --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@docker volume ls | grep agentos || true

# Docker 清理
docker-clean:
	@echo "🐳 清理 Docker 资源..."
	@docker stop agentos 2>/dev/null || true
	@docker rm agentos 2>/dev/null || true
	@docker rmi agentos:latest 2>/dev/null || true
	@echo "✅ 清理完成"

# Docker 备份
docker-backup:
	@echo "🐳 备份数据..."
	@mkdir -p backups
	@docker run --rm \
		-v agentos-data:/data \
		-v $(PWD)/backups:/backup \
		ubuntu tar czf /backup/agentos-backup-$$(date +%Y%m%d-%H%M%S).tar.gz /data
	@echo "✅ 备份完成 (backups/)"

# Docker 帮助
docker-help:
	@echo "🐳 Docker 快速命令:"
	@echo ""
	@echo "  make docker-deploy    - 一键部署 (推荐)"
	@echo "  make docker-up        - 启动服务"
	@echo "  make docker-down      - 停止服务"
	@echo "  make docker-restart   - 重启服务"
	@echo "  make docker-logs      - 查看日志"
	@echo "  make docker-build     - 构建镜像"
	@echo "  make docker-run       - 运行容器"
	@echo "  make docker-shell     - 进入容器"
	@echo "  make docker-status    - 查看状态"
	@echo "  make docker-clean     - 清理资源"
	@echo "  make docker-backup    - 备份数据"
	@echo ""
	@echo "更多文档: DOCKER_QUICKSTART.md"
