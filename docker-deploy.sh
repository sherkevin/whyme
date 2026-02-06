#!/bin/bash
# AgentOS Docker 一键部署脚本

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          AgentOS Docker 一键部署脚本                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 检查 Docker
echo -e "${BLUE}1. 检查 Docker 环境...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker 未安装${NC}"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓ Docker 版本: $(docker --version | cut -d' ' -f3)${NC}"
echo ""

# 检查 docker-compose (可选)
if command -v docker-compose &> /dev/null; then
    HAS_COMPOSE=true
    echo -e "${GREEN}✓ Docker Compose 版本: $(docker-compose --version | cut -d' ' -f3)${NC}"
else
    HAS_COMPOSE=false
    echo -e "${YELLOW}⚠ Docker Compose 未安装,将使用纯 Docker 命令${NC}"
fi
echo ""

# 询问部署方式
echo "请选择部署方式:"
echo "  1) Docker Compose (推荐,简单易用)"
echo "  2) Docker 原生命令 (适合高级用户)"
echo ""
read -p "请输入选项 [1-2]: " deploy_option

case $deploy_option in
    1)
        if [ "$HAS_COMPOSE" = false ]; then
            echo -e "${RED}✗ 需要安装 Docker Compose 才能使用此选项${NC}"
            exit 1
        fi

        echo ""
        echo -e "${BLUE}2. 使用 Docker Compose 启动...${NC}"

        # 检查 .env 文件
        if [ ! -f .env ]; then
            echo -e "${YELLOW}⚠ 未找到 .env 文件,从 .env.example 创建...${NC}"
            cp .env.example .env
            echo -e "${GREEN}✓ 已创建 .env 文件${NC}"
            echo -e "${YELLOW}  请编辑 .env 文件添加你的 API 密钥${NC}"
        fi

        # 启动服务
        echo "构建并启动服务..."
        docker-compose -f docker-compose.simple.yml up -d --build

        echo ""
        echo -e "${GREEN}✓ 服务已启动${NC}"
        echo ""
        echo "服务状态:"
        docker-compose -f docker-compose.simple.yml ps
        ;;

    2)
        echo ""
        echo -e "${BLUE}2. 使用 Docker 原生命令启动...${NC}"

        # 构建镜像
        echo "构建 Docker 镜像..."
        docker build -f Dockerfile.fast -t agentos:latest .

        echo ""
        echo -e "${GREEN}✓ 镜像构建完成${NC}"

        # 停止并删除旧容器
        if docker ps -a --format '{{.Names}}' | grep -q '^agentos$'; then
            echo "停止并删除旧容器..."
            docker rm -f agentos > /dev/null 2>&1 || true
        fi

        # 创建数据卷
        docker volume create agentos-data > /dev/null 2>&1 || true

        # 运行容器
        echo "启动容器..."
        docker run -d \
          --name agentos \
          -p 8003:8003 \
          -v agentos-data:/app/data \
          -e AGENTOS_SANDBOX=local \
          --restart unless-stopped \
          agentos:latest

        echo ""
        echo -e "${GREEN}✓ 容器已启动${NC}"
        echo ""
        echo "容器状态:"
        docker ps -f name=agentos
        ;;

    *)
        echo -e "${RED}✗ 无效选项${NC}"
        exit 1
        ;;
esac

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo -e "${GREEN}║          部署成功! 🎉                                       ║${NC}"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${BLUE}📍 访问地址:${NC}"
echo "   http://localhost:8003"
echo ""
echo -e "${BLUE}📋 常用命令:${NC}"
if [ "$deploy_option" = "1" ]; then
    echo "   查看日志: docker-compose -f docker-compose.simple.yml logs -f"
    echo "   停止服务: docker-compose -f docker-compose.simple.yml down"
    echo "   重启服务: docker-compose -f docker-compose.simple.yml restart"
else
    echo "   查看日志: docker logs -f agentos"
    echo "   停止容器: docker stop agentos"
    echo "   启动容器: docker start agentos"
    echo "   删除容器: docker rm -f agentos"
fi
echo ""
echo -e "${BLUE}📚 更多信息:${NC}"
echo "   请查看 DOCKER.md 文档"
echo ""
echo -e "${YELLOW}⚠ 提示:${NC}"
echo "   如需使用完整功能,请在 .env 文件中配置 API 密钥"
echo ""
