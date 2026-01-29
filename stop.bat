@echo off
REM AgentOS 停止服务脚本 (Windows)

echo ============================================
echo 停止 AgentOS 服务
echo ============================================
echo.

docker-compose -f docker-compose.api.yml down

if errorlevel 1 (
    echo ❌ 停止失败
    pause
    exit /b 1
)

echo.
echo ✅ 服务已停止
echo.
pause
