@echo off
REM AgentOS 一键启动脚本 (Windows)
REM 前端同学使用此脚本快速启动后端服务

echo ============================================
echo AgentOS 后端服务启动脚本
echo ============================================
echo.

REM 检查Docker是否运行
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: Docker未运行
    echo 请先启动Docker Desktop
    pause
    exit /b 1
)

echo ✅ Docker已运行
echo.

REM 创建必要目录
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo 📦 目录已创建
echo.

REM 启动服务
echo 🚀 启动AgentOS服务...
docker-compose -f docker-compose.api.yml up -d

if errorlevel 1 (
    echo ❌ 启动失败
    pause
    exit /b 1
)

echo.
echo ============================================
echo ✅ 服务启动成功!
echo ============================================
echo.
echo 📖 API文档: http://localhost:8000/docs
echo 🔌 API地址: http://localhost:8000
echo 📊 WebSocket: ws://localhost:8003
echo.
echo 常用命令:
echo   查看日志: docker-compose -f docker-compose.api.yml logs -f api
echo   停止服务: docker-compose -f docker-compose.api.yml down
echo   重启服务: docker-compose -f docker-compose.api.yml restart api
echo.
echo 按任意键打开API文档...
pause >nul

start http://localhost:8000/docs

echo.
echo 如需查看日志，请运行: logs.bat
pause
