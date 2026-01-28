#!/usr/bin/env python3
"""
MCP Bridge - Model Context Protocol 桥接器

功能：
1. 连接到 MCP Server (通过 stdio)
2. 列出可用工具
3. 调用工具并返回结果
"""

import sys
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class MCPBridge:
    """MCP 协议桥接器"""

    def __init__(self, toolkit_root: str = None):
        """初始化桥接器

        Args:
            toolkit_root: toolkit 目录路径
        """
        if toolkit_root:
            self.toolkit_root = Path(toolkit_root)
        else:
            self.toolkit_root = Path(__file__).parent

        self.mcp_servers_dir = self.toolkit_root / "mcp_servers"

    def load_server_config(self, server_name: str) -> Dict[str, Any]:
        """加载 MCP Server 配置

        Args:
            server_name: Server 名称

        Returns:
            配置字典
        """
        config_path = self.mcp_servers_dir / f"{server_name}.json"

        if not config_path.exists():
            raise FileNotFoundError(f"MCP Server config not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def connect_and_call(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: int = 30
    ) -> Dict[str, Any]:
        """连接到 MCP Server 并调用工具

        Args:
            server_name: Server 名称
            tool_name: 工具名称
            arguments: 工具参数
            timeout: 超时时间（秒）

        Returns:
            工具调用结果
        """
        config = self.load_server_config(server_name)
        command = config.get("command", "")

        if not command:
            raise ValueError(f"No command specified for MCP Server '{server_name}'")

        # 解析命令（支持 shell 命令）
        if isinstance(command, str):
            cmd_parts = command.split()
        else:
            cmd_parts = command

        try:
            # 启动 MCP Server 进程
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # 发送初始化请求
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "agentos-mcp-bridge",
                        "version": "0.1.0"
                    }
                }
            }

            await self._send_request(process, init_request)
            init_response = await asyncio.wait_for(
                self._read_response(process),
                timeout=timeout
            )

            if "error" in init_response:
                raise RuntimeError(f"MCP initialization failed: {init_response['error']}")

            # 发送 initialized 通知
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            await self._send_request(process, initialized_notification)

            # 调用工具
            call_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            await self._send_request(process, call_request)
            call_response = await asyncio.wait_for(
                self._read_response(process),
                timeout=timeout
            )

            # 清理进程
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except:
                process.kill()
                await process.wait()

            if "error" in call_response:
                raise RuntimeError(f"Tool call failed: {call_response['error']}")

            return call_response.get("result", {})

        except asyncio.TimeoutError:
            if process:
                process.kill()
                await process.wait()
            raise TimeoutError(f"MCP Server '{server_name}' timed out after {timeout}s")

        except Exception as e:
            if process:
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
            raise

    async def list_tools(self, server_name: str, timeout: int = 30) -> List[Dict[str, Any]]:
        """列出 MCP Server 的可用工具

        Args:
            server_name: Server 名称
            timeout: 超时时间（秒）

        Returns:
            工具列表
        """
        config = self.load_server_config(server_name)
        command = config.get("command", "")

        if not command:
            raise ValueError(f"No command specified for MCP Server '{server_name}'")

        if isinstance(command, str):
            cmd_parts = command.split()
        else:
            cmd_parts = command

        process = None

        try:
            # 启动 MCP Server 进程
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # 初始化
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "agentos-mcp-bridge",
                        "version": "0.1.0"
                    }
                }
            }

            await self._send_request(process, init_request)
            await asyncio.wait_for(self._read_response(process), timeout=timeout)

            # 发送 initialized 通知
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            await self._send_request(process, initialized_notification)

            # 列出工具
            list_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }

            await self._send_request(process, list_request)
            list_response = await asyncio.wait_for(
                self._read_response(process),
                timeout=timeout
            )

            # 清理进程
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except:
                process.kill()
                await process.wait()

            if "error" in list_response:
                raise RuntimeError(f"Failed to list tools: {list_response['error']}")

            tools = list_response.get("result", {}).get("tools", [])
            return tools

        except asyncio.TimeoutError:
            if process:
                process.kill()
                await process.wait()
            raise TimeoutError(f"MCP Server '{server_name}' timed out after {timeout}s")

        except Exception as e:
            if process:
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
            raise

    async def _send_request(self, process: asyncio.subprocess.Process, request: Dict[str, Any]):
        """发送 JSON-RPC 请求

        Args:
            process: 子进程
            request: 请求字典
        """
        message = json.dumps(request) + "\n"
        process.stdin.write(message.encode('utf-8'))
        await process.stdin.drain()

    async def _read_response(self, process: asyncio.subprocess.Process) -> Dict[str, Any]:
        """读取 JSON-RPC 响应

        Args:
            process: 子进程

        Returns:
            响应字典
        """
        line = await process.stdout.readline()
        if not line:
            stderr = await process.stderr.read()
            raise RuntimeError(f"MCP Server closed connection. Stderr: {stderr.decode()}")

        try:
            return json.loads(line.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response: {line.decode()}")


async def main_async():
    """异步主函数"""
    if len(sys.argv) < 3:
        print("Usage: python bridge.py <server_name> <command> [args]")
        print("\nCommands:")
        print("  list                           - List available tools")
        print("  call <tool_name> <json_args>   - Call a tool")
        sys.exit(1)

    server_name = sys.argv[1]
    command = sys.argv[2]

    bridge = MCPBridge()

    try:
        if command == "list":
            tools = await bridge.list_tools(server_name)
            print(json.dumps(tools, indent=2, ensure_ascii=False))

        elif command == "call":
            if len(sys.argv) < 5:
                print("Error: Missing tool name or arguments", file=sys.stderr)
                sys.exit(1)

            tool_name = sys.argv[3]
            args_json = sys.argv[4]

            # 解析参数
            try:
                arguments = json.loads(args_json)
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON arguments: {args_json}", file=sys.stderr)
                sys.exit(1)

            result = await bridge.connect_and_call(server_name, tool_name, arguments)
            print(json.dumps(result, indent=2, ensure_ascii=False))

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """CLI 入口"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
