# 🛠️ AgentOS Toolkit

工具箱系统，支持 Skills (本地 Python 脚本) 和 MCP Servers (远程工具协议)。

## 📁 目录结构

```
toolkit/
├── bins/               # Skills - 本地 Python 脚本
│   ├── weather.py     # 天气查询
│   ├── calculator.py  # 计算器
│   └── ...
├── mcp_servers/       # MCP Server 配置
│   ├── filesystem.json
│   └── ...
├── bridge.py          # MCP 协议桥接器
├── manager.py         # 工具管理器
├── registry.json      # 工具注册表（自动生成）
└── tools_summary.md   # 工具摘要（自动生成）
```

## 🚀 快速开始

### 1. 列出所有工具

```bash
python manager.py list
```

### 2. 刷新工具注册表

```bash
python manager.py refresh
```

### 3. 创建新 Skill

```bash
python manager.py new my_skill
# 编辑 bins/my_skill.py
python manager.py refresh
```

### 4. 添加 MCP Server

```bash
python manager.py add-mcp filesystem "npx -y @modelcontextprotocol/server-filesystem /path/to/dir"
python manager.py refresh
```

### 5. 调用工具

**调用 Skill:**
```bash
python bins/weather.py Beijing
python bins/calculator.py "2 + 3 * 4"
```

**调用 MCP 工具:**
```bash
python bridge.py filesystem list
python bridge.py filesystem call read_file '{"path": "test.txt"}'
```

## 📦 Skills 开发指南

### Skill 模板

```python
#!/usr/bin/env python3
"""
My Skill - 简短描述

详细说明
Usage: python my_skill.py <args>
"""

import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python my_skill.py <args>")
        sys.exit(1)

    args = sys.argv[1:]

    # 实现你的逻辑
    result = process(args)
    print(result)

if __name__ == "__main__":
    main()
```

### 最佳实践

1. **Docstring**: 第一行是简短描述，会被自动提取
2. **参数处理**: 使用 `sys.argv` 接收参数
3. **错误处理**: 捕获异常并输出到 stderr
4. **输出格式**: 纯文本或 JSON
5. **依赖管理**: 在 `requirements.txt` 中声明依赖

## 🌐 MCP Server 配置

### 配置文件格式

```json
{
  "name": "filesystem",
  "command": "npx -y @modelcontextprotocol/server-filesystem /path/to/dir",
  "description": "File system operations",
  "tools": []
}
```

### 常用 MCP Servers

1. **Filesystem**: 文件系统操作
   ```bash
   python manager.py add-mcp filesystem "npx -y @modelcontextprotocol/server-filesystem ."
   ```

2. **Git**: Git 仓库操作
   ```bash
   python manager.py add-mcp git "npx -y @modelcontextprotocol/server-git"
   ```

3. **Brave Search**: 网络搜索
   ```bash
   python manager.py add-mcp brave "npx -y @modelcontextprotocol/server-brave-search"
   ```

## 🔧 Manager API

### 命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `list` | 列出所有工具 | `python manager.py list` |
| `refresh` | 刷新注册表 | `python manager.py refresh` |
| `new <name>` | 创建新 Skill | `python manager.py new weather` |
| `add-mcp <name> <cmd>` | 添加 MCP Server | `python manager.py add-mcp fs "npx ..."` |
| `call <tool> [args]` | 调用工具 | `python manager.py call weather Beijing` |

## 🌉 Bridge API

### 命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `list` | 列出 Server 的工具 | `python bridge.py filesystem list` |
| `call <tool> <args>` | 调用工具 | `python bridge.py filesystem call read_file '{"path":"test.txt"}'` |

## 📝 在 Aider 中使用

Aider 会自动读取 `tools_summary.md` 来了解可用工具。

### 查看工具

```
/run python toolkit/manager.py list
```

### 调用 Skill

```
/run python toolkit/bins/weather.py Beijing
```

### 调用 MCP 工具

```
/run python toolkit/bridge.py filesystem call read_file '{"path": "README.md"}'
```

### 创建新工具

```
/run python toolkit/manager.py new my_tool
# 然后编辑 toolkit/bins/my_tool.py
/run python toolkit/manager.py refresh
```

## 🔄 热插拔机制

工具的增删改都会立即生效：

1. **添加**: 创建新脚本 → `refresh` → 立即可用
2. **修改**: 直接编辑脚本 → 立即生效（无需 refresh）
3. **删除**: 删除脚本 → `refresh` → 从注册表移除

## 🛡️ 安全性

### Skills 安全

- Skills 在当前 Python 环境中执行
- 建议使用虚拟环境隔离依赖
- 避免执行不可信的脚本

### MCP 安全

- MCP Servers 在独立进程中运行
- 通过 stdio 通信，隔离性较好
- 注意 Server 的权限配置

## 📚 示例

### 示例 1: 天气查询

```bash
$ python bins/weather.py Beijing
Beijing: ☀️ +15°C
```

### 示例 2: 计算器

```bash
$ python bins/calculator.py "2 ** 10"
2 ** 10 = 1024.0
```

### 示例 3: MCP 文件读取

```bash
$ python bridge.py filesystem call read_file '{"path": "README.md"}'
{
  "content": "# AgentOS Toolkit\n..."
}
```

## 🐛 故障排查

### 工具未显示

```bash
# 刷新注册表
python manager.py refresh

# 检查注册表
cat registry.json
```

### MCP Server 连接失败

```bash
# 测试 Server 命令
npx -y @modelcontextprotocol/server-filesystem .

# 检查配置
cat mcp_servers/filesystem.json
```

### 依赖缺失

```bash
# 安装依赖
pip install -r requirements.txt
```

## 📖 更多资源

- [MCP 协议文档](https://modelcontextprotocol.io/)
- [Aider 文档](https://aider.chat/)
- [AgentOS 文档](../docs/)

---

**版本**: 0.1.0
**更新**: 2026-01-25
