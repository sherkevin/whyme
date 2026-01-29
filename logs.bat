@echo off
REM AgentOS 日志查看脚本 (Windows)

echo ============================================
echo AgentOS 服务日志
echo ============================================
echo.
echo 按 Ctrl+C 停止查看日志
echo.

docker-compose -f docker-compose.api.yml logs -f api
