# 🛠️ Toolkit Summary

This document lists all available tools in the toolkit.

## 📦 Skills (Local Python Scripts)

### weather
- **Path**: `bins/weather.py`
- **Description**: Weather Skill - 获取天气信息
- **Usage**: `/run python bins/weather.py <args>`

### calculator
- **Path**: `bins/calculator.py`
- **Description**: Calculator Skill - 安全的数学计算器
- **Usage**: `/run python bins/calculator.py <args>`

## 🌐 MCP Servers (Remote Tools)

*No MCP servers configured*

## 📝 How to Use

1. **List all tools**: `/run python toolkit/manager.py list`
2. **Call a skill**: `/run python toolkit/bins/<skill_name>.py <args>`
3. **Call MCP tool**: `/run python toolkit/bridge.py <server_name> <tool_name> '<json_args>'`
4. **Create new skill**: `/run python toolkit/manager.py new <skill_name>`
5. **Add MCP server**: `/run python toolkit/manager.py add-mcp <name> <command>`
6. **Refresh registry**: `/run python toolkit/manager.py refresh`
