# AgentOS Studio - 快速开始指南

**版本**: v1.0.0
**更新时间**: 2026-01-26

---

## 🚀 5分钟快速开始

### 第1步: 启动服务器

```bash
# 进入项目目录
cd D:\Codes\whyme

# 配置环境变量（首次运行）
cp .env.example .env
# 编辑 .env 文件，设置你的 API_KEY

# 启动服务器
python start.py
```

服务器将在 http://127.0.0.1:8003 启动

### 第2步: 打开浏览器

浏览器会自动打开，或手动访问：http://127.0.0.1:8003

### 第3步: 创建你的第一个项目

1. 点击"✨ New Project"按钮
2. 输入项目名称（例如: "My AI Assistant"）
3. 点击创建

### 第4步: 开始对话

在聊天框中输入：
```
你: 写一个Python贪吃蛇游戏
```

AI Agent会自动创建游戏文件并运行！

---

## 📚 核心功能概览

### 1. 文件管理
- 📁 **文件浏览器**: 查看项目文件
- ➕ **新建文件**: 创建新文件
- 📝 **编辑文件**: Monaco Editor代码编辑
- 💾 **自动保存**: 实时保存更改

### 2. AI编程助手
- 💬 **自然语言交互**: 用对话方式编写代码
- 🤖 **自动执行**: AI直接操作文件系统
- 🔄 **实时反馈**: 看到AI的每一步操作
- 📊 **进度跟踪**: 实时显示任务进度

### 3. Toolkit管理
- 🛠️ **Skills**: 添加Python技能扩展
- 🌐 **MCP服务器**: 集成外部工具和服务
- 📤 **文件上传**: 上传.py和.json配置
- ✏️ **在线编辑**: 在浏览器中编辑工具

---

## 🎯 典型使用场景

### 场景1: Web开发

```
你: 创建一个Flask网站，主页显示"Hello World"

AI: 我来帮你创建Flask网站...
[创建app.py]
[创建templates/index.html]
[运行服务器]
✅ 完成！网站已在 http://localhost:5000 运行
```

### 场景2: 数据处理

```
你: 处理data.csv文件，计算销售总额

AI: 我来处理数据文件...
[分析CSV结构]
[编写处理脚本]
[执行计算]
💰 销售总额: $123,456.78
```

### 场景3: 自动化脚本

```
你: 写一个脚本，每天备份重要文件

AI: 我来创建备份脚本...
[创建backup.py]
[添加定时任务]
[测试脚本]
✅ 备份脚本已就绪，每天凌晨2点自动运行
```

### 场景4: 使用自定义技能

```
你: 使用calculator技能计算 (15 + 27) * 3

AI: 我来使用calculator技能...
[调用toolkit/bins/calculator.py]
[传递参数]
[获取结果]
✅ 结果: 126
```

---

## 🛠️ Toolkit快速指南

### 添加Skills

**什么是Skills？**
Skills是Python脚本，可以扩展AI Agent的能力。

**快速添加**:
1. 点击左侧🛠️图标
2. 点击"+ New Skill"
3. 输入名称（例如: `translator`）
4. 编写Python代码
5. 按Ctrl+S保存

**示例Skill**:
```python
#!/usr/bin/env python3
"""
Translator Skill - 翻译文本
"""

import sys

def translate(text, target_lang="zh"):
    """翻译文本到目标语言"""
    # 这里集成翻译API
    return f"[翻译到{target_lang}] {text}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        print(translate(text))
```

**使用Skill**:
```
你: 使用translator技能翻译 "Hello World"
AI: [调用translator skill]
[翻译到zh] Hello World
```

### 配置MCP服务器

**什么是MCP？**
MCP (Model Context Protocol) 提供外部工具集成。

**快速配置**:
1. 在Toolkit面板，切换到"MCP Servers"标签
2. 点击"+ Add Server"
3. 输入配置：
   - Name: `filesystem`
   - Command: `npx -y @modelcontextprotocol/server-filesystem D:\MyData`
4. 点击OK

**使用MCP工具**:
```
你: 使用filesystem工具列出 D:\MyData 的文件
AI: [调用MCP filesystem服务器]
[文件列表]
```

---

## 💡 高效技巧

### 1. 项目切换

**快速切换项目**:
1. 点击📂 Projects按钮
2. 选择项目名称
3. 自动切换并加载项目文件

### 2. 文件操作

**常用快捷键**:
- `Ctrl+S` - 保存文件
- `Ctrl+N` - 新建文件
- `Ctrl+W` - 关闭标签
- `Ctrl+F` - 搜索

### 3. 对话技巧

**明确指令**:
```
✅ 好的指令: "创建一个Flask应用，主页显示欢迎消息"
❌ 模糊的指令: "做个网站"
```

**分步骤**:
```
你: 第一步，创建项目结构
AI: [创建文件夹和基础文件]

你: 第二步，添加主应用代码
AI: [编写app.py]

你: 第三步，创建HTML模板
AI: [创建templates/index.html]
```

### 4. 调试技巧

**查看错误**:
- 系统消息区域会显示错误详情
- 浏览器控制台显示调试信息
- 服务器日志记录完整操作历史

**回滚操作**:
如果AI生成了错误的代码，告诉它：
```
你: 这段代码有错误，请修复
或: 回滚到上一个版本
```

---

## 🔧 配置选项

### 环境变量

编辑`.env`文件:
```bash
# LLM配置
API_KEY=your_api_key_here
BASE_URL=https://api.deepseek.com

# 服务器配置
HOST=127.0.0.1
PORT=8003

# 沙箱配置
SANDBOX_MODE=local  # local 或 docker
```

### YAML配置

编辑`config.yaml`:
```yaml
llm:
  provider: deepseek
  model: deepseek-chat
  temperature: 0.7

sandbox:
  mode: local
  workspace_root: ./data/workspaces

toolkit:
  enabled: true
  auto_discover: true
```

---

## 📖 延伸阅读

### 完整文档
- [Toolkit管理指南](toolkit-management.md) - 详细的Toolkit使用说明
- [UI可视化指南](ui-visual-guide.md) - 界面截图和步骤
- [API文档](http://127.0.0.1:8003/docs) - 完整API参考

### 技术文档
- [系统架构](../03-toolkit/architecture.md) - 技术架构详解
- [项目进度](../02-progress/latest-status.md) - 开发进度报告
- [测试报告](../05-testing/test-summary.md) - 功能测试结果

---

## ❓ 获取帮助

### 常见问题

**Q: 服务器启动失败？**
A: 检查端口8003是否被占用，或查看`.env`配置

**Q: AI不响应？**
A: 检查API_KEY是否正确配置，查看浏览器控制台错误

**Q: 文件保存失败？**
A: 确保有写入权限，检查磁盘空间

### 联系方式

- **GitHub Issues**: [AgentOS/Issues](https://github.com/your-org/agent-os/issues)
- **文档**: [完整文档](./)
- **API文档**: http://127.0.0.1:8003/docs

---

## 🎉 开始使用

现在你已经了解了基础知识，开始使用AgentOS Studio吧！

**推荐的学习路径**:
1. ✅ 完成快速开始（本指南）
2. ✅ 尝试基本对话和编程
3. ✅ 探索Toolkit功能
4. ✅ 阅读[完整用户指南](toolkit-management.md)
5. ✅ 集成自己的Skills和MCP服务器

**祝使用愉快！** 🚀

---

**文档版本**: 1.0
**最后更新**: 2026-01-26
**维护者**: AgentOS Development Team
