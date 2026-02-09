#!/usr/bin/env python3
"""
Toolkit Manager - 工具箱管理器

功能：
1. list - 列出所有可用工具
2. refresh - 扫描并更新工具注册表
3. new <name> - 创建新的 Skill 脚本模板
4. add-mcp <name> <command> - 添加 MCP Server 配置
5. call <tool_name> <args> - 统一调用入口
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any


class ToolkitManager:
    """工具箱管理器"""

    def __init__(self, toolkit_root: str = None):
        """初始化管理器

        Args:
            toolkit_root: toolkit 目录路径，默认为当前脚本所在目录
        """
        if toolkit_root:
            self.toolkit_root = Path(toolkit_root)
        else:
            self.toolkit_root = Path(__file__).parent

        self.bins_dir = self.toolkit_root / "bins"
        self.mcp_servers_dir = self.toolkit_root / "mcp_servers"
        self.registry_file = self.toolkit_root / "registry.json"
        self.summary_file = self.toolkit_root / "tools_summary.md"

        # 确保目录存在
        self.bins_dir.mkdir(parents=True, exist_ok=True)
        self.mcp_servers_dir.mkdir(parents=True, exist_ok=True)

    def list_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有可用工具

        Returns:
            包含 skills 和 mcp_servers 的字典
        """
        tools = {
            "skills": [],
            "mcp_servers": []
        }

        # 扫描 Skills
        if self.bins_dir.exists():
            for script in self.bins_dir.glob("*.py"):
                if script.name.startswith("_"):
                    continue

                # 读取脚本的 docstring
                docstring = self._extract_docstring(script)
                tools["skills"].append({
                    "name": script.stem,
                    "path": str(script.relative_to(self.toolkit_root)),
                    "description": docstring or "No description",
                    "type": "skill"
                })

        # 扫描 MCP Servers
        if self.mcp_servers_dir.exists():
            for config in self.mcp_servers_dir.glob("*.json"):
                try:
                    with open(config, 'r', encoding='utf-8') as f:
                        mcp_config = json.load(f)

                    tools["mcp_servers"].append({
                        "name": config.stem,
                        "path": str(config.relative_to(self.toolkit_root)),
                        "command": mcp_config.get("command", ""),
                        "description": mcp_config.get("description", "No description"),
                        "tools": mcp_config.get("tools", []),
                        "type": "mcp"
                    })
                except Exception as e:
                    print(f"Warning: Failed to load MCP config {config}: {e}", file=sys.stderr)

        return tools

    def refresh(self) -> Dict[str, Any]:
        """刷新工具注册表和摘要文档

        Returns:
            更新结果统计
        """
        tools = self.list_tools()

        # 保存 registry.json
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(tools, f, indent=2, ensure_ascii=False)

        # 生成 tools_summary.md
        self._generate_summary(tools)

        stats = {
            "skills_count": len(tools["skills"]),
            "mcp_servers_count": len(tools["mcp_servers"]),
            "total_tools": len(tools["skills"]) + sum(len(s.get("tools", [])) for s in tools["mcp_servers"])
        }

        return stats

    def new_skill(self, name: str) -> str:
        """创建新的 Skill 脚本模板

        Args:
            name: Skill 名称

        Returns:
            创建的文件路径
        """
        script_path = self.bins_dir / f"{name}.py"

        if script_path.exists():
            raise FileExistsError(f"Skill '{name}' already exists at {script_path}")

        template = f'''#!/usr/bin/env python3
"""
{name.title()} Skill

Description: Add your skill description here
Usage: python {name}.py <args>
"""

import sys


def main():
    """Main function for {name} skill"""
    if len(sys.argv) < 2:
        print("Usage: python {name}.py <args>")
        sys.exit(1)

    args = sys.argv[1:]

    # TODO: Implement your skill logic here
    print(f"{{name}} skill called with args: {{args}}")

    # Example: Return result
    result = {{"status": "success", "data": args}}
    print(result)


if __name__ == "__main__":
    main()
'''

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(template)

        # Make executable on Unix-like systems
        try:
            os.chmod(script_path, 0o755)
        except:
            pass

        return str(script_path)

    def add_mcp_server(self, name: str, command: str, description: str = "") -> str:
        """添加 MCP Server 配置

        Args:
            name: MCP Server 名称
            command: 启动命令
            description: 描述

        Returns:
            创建的配置文件路径
        """
        config_path = self.mcp_servers_dir / f"{name}.json"

        if config_path.exists():
            raise FileExistsError(f"MCP Server '{name}' already exists at {config_path}")

        config = {
            "name": name,
            "command": command,
            "description": description or f"MCP Server: {name}",
            "tools": []  # Will be populated when bridge connects
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        return str(config_path)

    def call_tool(self, tool_name: str, args: List[str]) -> int:
        """统一工具调用入口

        Args:
            tool_name: 工具名称
            args: 参数列表

        Returns:
            退出码
        """
        # 首先尝试作为 Skill 调用
        skill_path = self.bins_dir / f"{tool_name}.py"
        if skill_path.exists():
            cmd = [sys.executable, str(skill_path)] + args
            result = subprocess.run(cmd)
            return result.returncode

        # 尝试作为 MCP 工具调用
        # 格式: call mcp_server_name.tool_name <args>
        if "." in tool_name:
            server_name, tool_name_only = tool_name.split(".", 1)
            mcp_config = self.mcp_servers_dir / f"{server_name}.json"

            if mcp_config.exists():
                bridge_path = self.toolkit_root / "bridge.py"
                # 将 args 转换为 JSON 字符串
                args_json = json.dumps(args)
                cmd = [sys.executable, str(bridge_path), server_name, tool_name_only, args_json]
                result = subprocess.run(cmd)
                return result.returncode

        print(f"Error: Tool '{tool_name}' not found", file=sys.stderr)
        return 1

    def _extract_docstring(self, script_path: Path) -> str:
        """提取 Python 脚本的 docstring

        Args:
            script_path: 脚本路径

        Returns:
            Docstring 内容
        """
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 简单的 docstring 提取
            import ast
            tree = ast.parse(content)
            docstring = ast.get_docstring(tree)

            if docstring:
                # 只取第一行作为简短描述
                return docstring.split('\n')[0].strip()

            return ""
        except Exception as e:
            return f"Error reading docstring: {e}"

    def _generate_summary(self, tools: Dict[str, List[Dict[str, Any]]]):
        """生成工具摘要文档

        Args:
            tools: 工具字典
        """
        lines = [
            "# 🛠️ Toolkit Summary",
            "",
            "This document lists all available tools in the toolkit.",
            "",
            "## 📦 Skills (Local Python Scripts)",
            ""
        ]

        if tools["skills"]:
            for skill in tools["skills"]:
                lines.append(f"### {skill['name']}")
                lines.append(f"- **Path**: `{skill['path']}`")
                lines.append(f"- **Description**: {skill['description']}")
                lines.append(f"- **Usage**: `/run python {skill['path']} <args>`")
                lines.append("")
        else:
            lines.append("*No skills available*")
            lines.append("")

        lines.extend([
            "## 🌐 MCP Servers (Remote Tools)",
            ""
        ])

        if tools["mcp_servers"]:
            for server in tools["mcp_servers"]:
                lines.append(f"### {server['name']}")
                lines.append(f"- **Command**: `{server['command']}`")
                lines.append(f"- **Description**: {server['description']}")

                if server.get("tools"):
                    lines.append(f"- **Available Tools**: {', '.join(server['tools'])}")
                    lines.append(f"- **Usage**: `/run python toolkit/bridge.py {server['name']} <tool_name> '<json_args>'`")
                else:
                    lines.append("- **Tools**: Not yet discovered (run bridge to list)")

                lines.append("")
        else:
            lines.append("*No MCP servers configured*")
            lines.append("")

        lines.extend([
            "## 📝 How to Use",
            "",
            "1. **List all tools**: `/run python toolkit/manager.py list`",
            "2. **Call a skill**: `/run python toolkit/bins/<skill_name>.py <args>`",
            "3. **Call MCP tool**: `/run python toolkit/bridge.py <server_name> <tool_name> '<json_args>'`",
            "4. **Create new skill**: `/run python toolkit/manager.py new <skill_name>`",
            "5. **Add MCP server**: `/run python toolkit/manager.py add-mcp <name> <command>`",
            "6. **Refresh registry**: `/run python toolkit/manager.py refresh`",
            ""
        ])

        with open(self.summary_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


def main():
    """CLI 入口"""
    if len(sys.argv) < 2:
        print("Usage: python manager.py <command> [args]")
        print("\nCommands:")
        print("  list                    - List all available tools")
        print("  refresh                 - Refresh tool registry and summary")
        print("  new <name>              - Create a new skill template")
        print("  add-mcp <name> <cmd>    - Add a new MCP server configuration")
        print("  call <tool> [args]      - Call a tool")
        sys.exit(1)

    command = sys.argv[1]
    manager = ToolkitManager()

    try:
        if command == "list":
            tools = manager.list_tools()
            print(json.dumps(tools, indent=2, ensure_ascii=False))

        elif command == "refresh":
            stats = manager.refresh()
            print(f"[OK] Registry updated!")
            print(f"   Skills: {stats['skills_count']}")
            print(f"   MCP Servers: {stats['mcp_servers_count']}")
            print(f"   Total Tools: {stats['total_tools']}")

        elif command == "new":
            if len(sys.argv) < 3:
                print("Error: Missing skill name", file=sys.stderr)
                sys.exit(1)

            name = sys.argv[2]
            path = manager.new_skill(name)
            print(f"[OK] Created new skill: {path}")
            print(f"   Edit the file and run 'refresh' to register it.")

        elif command == "add-mcp":
            if len(sys.argv) < 4:
                print("Error: Missing MCP server name or command", file=sys.stderr)
                sys.exit(1)

            name = sys.argv[2]
            cmd = sys.argv[3]
            description = sys.argv[4] if len(sys.argv) > 4 else ""

            path = manager.add_mcp_server(name, cmd, description)
            print(f"[OK] Added MCP server: {path}")
            print(f"   Run 'refresh' to update the registry.")

        elif command == "call":
            if len(sys.argv) < 3:
                print("Error: Missing tool name", file=sys.stderr)
                sys.exit(1)

            tool_name = sys.argv[2]
            args = sys.argv[3:]

            exit_code = manager.call_tool(tool_name, args)
            sys.exit(exit_code)

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
