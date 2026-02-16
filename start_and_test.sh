#!/bin/bash
# PRD5 测试启动脚本
# 帮助您快速启动服务并运行测试

set -e

echo "🚀 AgentOS PRD5 测试环境启动脚本"
echo "=================================="
echo ""

# 检查端口
PORT=${PORT:-8003}
echo "📋 检查端口 $PORT..."
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  端口 $PORT 已被占用"
    echo "   请先停止其他服务或修改 PORT 环境变量"
    exit 1
fi
echo "✅ 端口 $PORT 可用"
echo ""

# 检查 Redis
echo "📋 检查 Redis..."
if redis-cli ping >/dev/null 2>&1; then
    echo "✅ Redis 正在运行"
else
    echo "❌ Redis 未运行"
    echo "   请启动 Redis: sudo systemctl start redis"
    echo "   或使用 Docker: docker run -d -p 6379:6379 redis"
    exit 1
fi
echo ""

# 检查虚拟环境
echo "📋 检查虚拟环境..."
if [ ! -d ".venv" ]; then
    echo "❌ 虚拟环境不存在"
    echo "   请先创建: python3 -m venv .venv"
    exit 1
fi
echo "✅ 虚拟环境存在"
echo ""

# 检查依赖
echo "📋 检查依赖..."
source .venv/bin/activate

# 检查关键依赖
MISSING=0

if ! python -c "import fastapi" 2>/dev/null; then
    echo "❌ 缺少 fastapi"
    MISSING=1
fi

if ! python -c "import sqlalchemy" 2>/dev/null; then
    echo "❌ 缺少 sqlalchemy"
    MISSING=1
fi

if ! python -c "import redis" 2>/dev/null; then
    echo "❌ 缺少 redis"
    echo "   安装: pip install redis"
    MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "❌ 缺少必要依赖，请安装"
    exit 1
fi

echo "✅ 所有依赖已安装"
echo ""

# 检查环境变量
echo "📋 检查环境变量..."
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件"
    echo "   创建示例配置..."
    cat > .env.example << EOF
# 数据库配置
DATABASE_URL=postgresql+asyncpg://user:password@localhost/agentos

# Redis 配置
REDIS_URL=redis://localhost:6379/0

# JWT 密钥
SECRET_KEY=your-secret-key-change-in-production

# SMTP 配置（用于 PRD5）
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASS=password
SMTP_FROM=noreply@example.com
SMTP_USE_TLS=true
EOF
    echo "   ✅ 已创建 .env.example"
    echo ""
    echo "   请配置 SMTP 服务后创建 .env 文件："
    echo "   cp .env.example .env"
    echo "   然后编辑 .env 填入真实配置"
else
    echo "✅ 找到 .env 文件"
fi
echo ""

echo "✅ 环境检查完成！"
echo ""
echo "=================================="
echo "🚀 启动服务器..."
echo "=================================="
echo ""

# 启动服务器
cd /root/whyme

# 使用 uvicorn 启动
echo "启动 Uvicorn 服务器在端口 $PORT..."
echo "日志将输出到: logs/server.log"
echo ""

# 创建日志目录
mkdir -p logs

# 后台启动服务器
nohup .venv/bin/uvicorn agent_os.server.app:app \
    --host 0.0.0.0 \
    --port $PORT \
    --reload \
    > logs/server.log 2>&1 &

SERVER_PID=$!
echo $SERVER_PID > .server.pid

echo "✅ 服务器已启动 (PID: $SERVER_PID)"
echo ""
echo "=================================="
echo "📊 服务器信息"
echo "=================================="
echo "  URL:     http://localhost:$PORT"
echo "  API文档: http://localhost:$PORT/docs"
echo "  PID:     $SERVER_PID"
echo "  日志:    logs/server.log"
echo ""
echo "停止服务器: kill $SERVER_PID"
echo "或:        kill \$(cat .server.pid)"
echo ""
echo "查看日志:   tail -f logs/server.log"
echo ""
echo "=================================="
echo "🧪 运行测试"
echo "=================================="
echo ""

# 等待服务器启动
echo "等待服务器启动..."
sleep 3

# 检查服务器是否成功启动
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "✅ 服务器进程运行中"
    echo ""

    # 运行测试
    echo "执行 PRD5 测试..."
    .venv/bin/python test_prd5.py http://localhost:$PORT
else
    echo "❌ 服务器启动失败"
    echo "   查看日志: tail -n 50 logs/server.log"
    exit 1
fi
