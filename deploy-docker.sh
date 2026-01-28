#!/bin/bash

# Build and Deploy Script for AgentOS with Docker Isolation

set -e  # Exit on error

echo "======================================"
echo "  AgentOS Docker 多用户隔离部署脚本"
echo "======================================"
echo ""

# Check Docker
echo "[1/5] 检查 Docker 环境..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker Desktop"
    exit 1
fi

if ! docker ps &> /dev/null; then
    echo "❌ Docker daemon 未运行，请启动 Docker Desktop"
    exit 1
fi

echo "✅ Docker 环境正常"
echo ""

# Build image
echo "[2/5] 构建 Ubuntu 运行时镜像..."
docker build -t agentos-ubuntu:latest -f Dockerfile .
echo "✅ 镜像构建完成"
echo ""

# Check environment variables
echo "[3/5] 检查环境配置..."
if [ -f .env ]; then
    if grep -q "AGENTOS_SANDBOX=local" .env; then
        echo "⚠️  检测到 AGENTOS_SANDBOX=local，建议移除以使用 Docker 隔离"
        echo "   请编辑 .env 文件，删除或注释掉该行"
    else
        echo "✅ 环境配置正常"
    fi
else
    echo "⚠️  .env 文件不存在，将使用默认 Docker 配置"
fi
echo ""

# Install dependencies
echo "[4/5] 安装 Python 依赖..."
pip install -q -r requirements.txt
echo "✅ 依赖安装完成"
echo ""

# Start server
echo "[5/5] 启动服务器..."
echo ""
echo "======================================"
echo "  服务器配置信息"
echo "======================================"
echo "地址: http://localhost:8003"
echo "模式: Docker 多用户隔离"
echo "镜像: agentos-ubuntu:latest"
echo "资源限制: 512MB 内存, 50% CPU"
echo "======================================"
echo ""

# Check if server is already running
if lsof -Pi :8003 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  端口 8003 已被占用，请先停止现有服务器"
    echo "   运行: lsof -ti:8003 | xargs kill -9"
    exit 1
fi

# Start server
python scripts/start.py
