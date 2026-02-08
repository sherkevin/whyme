#!/bin/bash
# AgentOS Docker 构建和测试脚本

set -e

echo "=================================="
echo "AgentOS Docker 构建脚本"
echo "=================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

echo -e "${GREEN}✓ Docker 已安装${NC}"
docker --version
echo ""

# 构建镜像
echo "=================================="
echo "开始构建 Docker 镜像..."
echo "=================================="
echo ""

DOCKER_BUILDKIT=1 docker build \
  -f Dockerfile.app \
  -t agentos:latest \
  --progress=plain \
  . || {
    echo -e "${RED}✗ Docker 镜像构建失败${NC}"
    exit 1
  }

echo ""
echo -e "${GREEN}✓ Docker 镜像构建成功${NC}"
echo ""

# 显示镜像信息
echo "镜像信息:"
docker images agentos:latest
echo ""

# 询问是否运行容器
echo "=================================="
echo "是否要运行容器进行测试? (y/n)"
read -r response

if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo ""
    echo "启动容器..."

    # 停止并删除旧容器(如果存在)
    if docker ps -a --format '{{.Names}}' | grep -q '^agentos-test$'; then
        echo "删除旧容器..."
        docker rm -f agentos-test > /dev/null 2>&1 || true
    fi

    # 运行新容器
    docker run -d \
      --name agentos-test \
      -p 8003:8003 \
      -e AGENTOS_SANDBOX=local \
      agentos:latest || {
        echo -e "${RED}✗ 容器启动失败${NC}"
        exit 1
    }

    echo -e "${GREEN}✓ 容器已启动${NC}"
    echo ""

    # 等待容器启动
    echo "等待应用启动..."
    sleep 10

    # 检查容器状态
    echo "容器状态:"
    docker ps -f name=agentos-test
    echo ""

    # 查看日志
    echo "最近的应用日志:"
    docker logs --tail 20 agentos-test
    echo ""

    echo "=================================="
    echo -e "${GREEN}✓ 构建和测试完成!${NC}"
    echo "=================================="
    echo ""
    echo "应用访问地址: http://localhost:8003"
    echo ""
    echo "常用命令:"
    echo "  查看日志: docker logs -f agentos-test"
    echo "  停止容器: docker stop agentos-test"
    echo "  删除容器: docker rm agentos-test"
    echo ""
else
    echo ""
    echo "跳过运行测试"
    echo ""
    echo "要手动运行容器,请使用:"
    echo "  docker run -d --name agentos -p 8003:8003 agentos:latest"
    echo ""
fi
