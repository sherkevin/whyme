#!/bin/bash
# AgentOS Quick Start Script
# 快速启动 AgentOS 服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# 打印标题
print_title() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  AgentOS Quick Start${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# 检查 Docker
check_docker() {
    print_info "检查 Docker..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker 未运行，请启动 Docker"
        exit 1
    fi
    
    print_success "Docker 已就绪"
}

# 检查 Docker Compose
check_docker_compose() {
    print_info "检查 Docker Compose..."
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose 未安装"
        exit 1
    fi
    
    print_success "Docker Compose 已就绪"
}

# 检查 .env 文件
check_env_file() {
    print_info "检查环境配置..."
    
    if [ ! -f .env ]; then
        print_warning ".env 文件不存在，从 .env.example 创建..."
        if [ -f .env.example ]; then
            cp .env.example .env
            print_success ".env 文件已创建"
            print_warning "请根据需要修改 .env 文件中的配置"
        else
            print_error ".env.example 文件不存在"
            exit 1
        fi
    else
        print_success ".env 文件已存在"
    fi
}

# 创建必要的目录
create_directories() {
    print_info "创建数据目录..."
    
    mkdir -p data logs
    print_success "目录已创建"
}

# 启动服务
start_services() {
    print_info "启动 AgentOS 服务..."
    
    # 使用 docker compose 或 docker-compose
    if docker compose version &> /dev/null; then
        docker compose -f docker-compose.quick.yml up -d
    else
        docker-compose -f docker-compose.quick.yml up -d
    fi
    
    print_success "服务启动成功"
}

# 等待服务就绪
wait_for_service() {
    print_info "等待服务启动..."
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
            print_success "服务已就绪"
            return 0
        fi
        
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done
    
    echo
    print_error "服务启动超时"
    return 1
}

# 显示服务信息
show_service_info() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}  AgentOS 服务已启动！${NC}"
    echo -e "${GREEN}========================================${NC}\n"
    
    echo -e "${BLUE}API 文档:${NC}   http://localhost:8000/docs"
    echo -e "${BLUE}API 端点:${NC}   http://localhost:8000"
    echo -e "${BLUE}WebSocket:${NC}  ws://localhost:8003"
    echo ""
    echo -e "${BLUE}查看日志:${NC}   docker-compose -f docker-compose.quick.yml logs -f api"
    echo -e "${BLUE}停止服务:${NC}   docker-compose -f docker-compose.quick.yml down"
    echo ""
}

# 主函数
main() {
    print_title
    
    check_docker
    check_docker_compose
    check_env_file
    create_directories
    start_services
    
    if wait_for_service; then
        show_service_info
        exit 0
    else
        print_error "启动失败，请查看日志"
        exit 1
    fi
}

# 运行主函数
main
