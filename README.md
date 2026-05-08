<div align="center">

# Mydow

**让灵感不再溜走的 AI 工作台**

灵感采集 · 知识库 · Mydow AI 对话 · Skills 广场 · 数字花园 · 全局搜索

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRD10 V1](https://img.shields.io/badge/PRD10-V1%20MVP-2546d8.svg)](docs/01-prd/PRD10.md)
[![Tests](https://img.shields.io/badge/tests-260%2B%20passed-16a34a.svg)](#-测试与质量)

[**🚀 5 分钟体验**](#-5-分钟体验) ·
[产品介绍](#-产品介绍) ·
[技术架构](#-技术架构) ·
[商业模式](#-商业模式) ·
[路线图](#-路线图产品视角) ·
[团队](#-团队) ·
[投资材料](#-投资材料) ·
[联系我们](#-联系我们)

</div>

---

## 💡 产品介绍

**Mydow 是一个把"灵感 → 整理 → AI 协作 → 知识资产"端到端打通的个人工作台。**

| 痛点 | 现状（碎片化工具）| Mydow 解法 |
|---|---|---|
| 灵感记下了找不回来 | 备忘录 / Notion / 微信收藏散落各处 | 统一收件箱 + 异步整理成卡片 + 全局搜索 |
| AI 对话历史是孤岛 | ChatGPT 没有你的知识库上下文 | AI 对话直接引用知识库内容 + 一键存为文档 / 任务 |
| 知识库不会"长大" | 文档堆积无关联 | 数字花园：卡片 / 文档 / 主题之间自动建立 connection |
| 重复工作占满时间 | 写周报、写纪要、做总结都靠手 | Skills 广场：可调用、可组合、可保存的工作流 |

**面向人群**：研究者 / 知识工作者 / 内容创作者 / 产品经理 / 创业者。

**当前状态**：PRD10 V1 后端 + SPA 已跑通最小闭环（采集 → 整理 → 提问 → 回答 → 保存为文档），260+ 集成测试绿。

---

## 🚀 5 分钟体验

### 一键起本地（开发者）

```powershell
# 1. 克隆 + 安装依赖
git clone https://github.com/yourusername/whyme.git
cd whyme
pip install -e .

# 2. 配 .env（最少改 SECRET_KEY 和 DEEPSEEK_API_KEY，其他默认即可）
cp .env.example .env

# 3. 种子数据 + 启动
python scripts/seed_prd10.py --email demo@mydow.example --password demo123 --reset
python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8000

# 4. 浏览器打开
#    http://127.0.0.1:8000/mydow/  → 直接进 demo 主界面
#    http://127.0.0.1:8000/docs    → 完整 API 文档（Swagger）
```

### 看核心闭环（PRD10 §30）

1. 顶部输入框敲 `今天产品评审决定 V1 必须打通最小闭环` → 回车
2. **2 秒**后首页内容流多出一张卡片（异步整理完成）
3. 切到 **Mydow AI** → 新对话 → 问 `本周关于 V1 我有什么想法？`
4. AI 引用刚才的卡片回答（开 `AGENTOS_AI_LLM=on` 是真 LLM；否则是 placeholder）
5. 点回答右下角 **保存为文档** → 选文件夹 → 提交
6. 切到 **知识库** → 看到这份 AI 生成的文档
7. 顶部 **通知** 看到「文件解析完成 / AI 报告生成完成」

详细演示脚本：[`docs/demo-script.md`](docs/demo-script.md)（30 秒 / 2 分钟 / 5 分钟三档）。

---

## 🏗️ 技术架构

```
┌──────────────────────────────────────────────────────────┐
│                       Mydow Web SPA                      │
│    static/mydow/{index.html, app.js, style.css}          │
│           原生 ESM · 无 React/Vue 依赖                    │
└────────────────────────┬─────────────────────────────────┘
                         │  /api/v1/*
┌────────────────────────▼─────────────────────────────────┐
│              FastAPI · agent_os.server.app                │
│  ┌────────────────────────────────────────────────────┐  │
│  │   PRD10 §6 envelope · RequestId · 限流 · 鉴权      │  │
│  ├────────────────────────────────────────────────────┤  │
│  │  Capture · Feed · KB · Today · Notifications · AI │  │
│  │  Skills · Garden · Search · Insights · Jobs · Auth │  │
│  └────────────────────────────────────────────────────┘  │
└─────┬────────────┬──────────┬──────────────────┬─────────┘
      │            │          │                  │
   ┌──▼──┐   ┌────▼────┐  ┌──▼──┐         ┌─────▼─────┐
   │ PG  │   │  Redis  │  │ S3/ │         │  LLM      │
   │16   │   │ 缓存+SSE│  │ 本地│         │ (DeepSeek/│
   │     │   │         │  │ 存储│         │  OpenAI/  │
   └─────┘   └─────────┘  └─────┘         │  Claude)  │
                                          └───────────┘
                  Job 消费 worker（ai_chat / parse_file /
              generate_report / skill_run 异步消化）
```

**关键技术决策**：

- **PRD10 envelope** 全栈统一，每个响应都带 `success` / `data` / `request_id`，错误带 `code` 枚举。
- **异步先行**：所有可能慢的操作（解析、AI、Skill）都返回 `Job`，前端轮 `/jobs/{id}` 看进度。
- **SSE 而非 WebSocket**：通知 + AI 流式回答都走 `text/event-stream`，更易跨代理稳定。
- **Pluggable LLM**：通过 LiteLLM 一行切 DeepSeek / OpenAI / Anthropic。`AGENTOS_AI_LLM=off` 时走 placeholder，开发离线友好。

---

## 📚 文档

| 文档 | 受众 | 用途 |
|---|---|---|
| [PRD10](docs/01-prd/PRD10.md) | 产品 / 投资人 / 工程 | 产品 V1 完整需求规格 |
| [API Reference](docs/11-deployment/api-reference.md) | 后端 / SDK / 第三方 | 600+ 行 curl 示例集合 |
| [环境变量手册](docs/11-deployment/env-vars.md) | 运维 / 部署 | `.env.example` 逐字段说明 |
| [Demo 演示脚本](docs/demo-script.md) | 投资人 / 销售 | 30s / 2m / 5m 三档动线 |
| [SPA 接入手册](docs/agent-2-spa-binding-guide.md) | 前端工程师 | SPA 与后端契约 |
| [todo-tasks.md](todo-tasks.md) | 全员 | 任务池总表（唯一来源） |
| [progress report](agent-progress-report.md) | 全员 | 滚动 milestone 日志 |

---

## ✅ 测试与质量

```powershell
# PRD10 V1 验收（260+ 通过）
python -m pytest tests/integration/api/test_prd10_*.py tests/integration/api/prd10/ -q

# 全仓回归（已 ignore 外部依赖测试）
python -m pytest -q
```

最近一次测试基线：`.tmp/baseline-tests.txt`（187+ 单元 + 集成测试）。

---

## 💼 商业模式

Mydow 提供 **4 条商业化路径**，覆盖个人 → 团队 → 平台三层；首年聚焦「个人订阅 PMF + 团队 License 早期客户」，不烧钱补贴：

| 路径 | 目标用户 | 定价 | 核心价值 | 收入特性 |
|---|---|---|---|---|
| **个人订阅（Pro）** | 知识工作者 / 研究者 / 创作者 / 产品经理 | ¥39 / 月 ｜ ¥399 / 年 | 无限灵感采集 · 高级 AI 模型（DeepSeek/Claude/GPT）· 知识库无上限 · 数字花园全图 · 定制 Skills | SaaS 月度循环；预期 LTV ≥ 12× ARPU |
| **团队 License** | 5–50 人产品 / 研究 / 咨询 / 投研团队 | ¥199 / 席位 / 月 起 | 多 workspace · 文档共享 · Skills 私有部署 · SSO · 审计日志 · 自定义品牌 | 年度合同 + per-seat；目标 LTV/CAC ≥ 4 |
| **API 调用** | 开发者 / 第三方 SaaS / Agent 平台 | 按 1K tokens 计费（输入 ¥0.5 / 输出 ¥1.5） | `/api/v1/*` 全接口对外 · Webhook · Skills SDK · `Job` 异步 worker | Pay-as-you-go；毛利 60–70% |
| **Skills 市场分成** | Skill 开发者 / MCP 作者 | 70% 给作者 / 30% 平台 | 上架 · 评论 · 订阅 · 一键安装 · 跨工作台分发 | 平台撮合 + 复购率高 |

**首年（2026）目标**：

- Q2：100 paying user · Pre-A 意向 · ARR 触底 ¥0.5M
- Q3：5 个团队签约 · DAU 1k · ARR ¥1.5M
- Q4：API 月调用 1M+ · Skills 上架 50+ · ARR ¥3M+
- 毛利 60% 起步、目标 65%+；获客主要来自 PRD10 demo 直接转化 + 内容社区。

---

## 🗺️ 路线图（产品视角）

> 每季度 demo 节奏：季度末公开 30 秒 video + release notes；季度内 2 周一次 minor release，月 / 周固定 demo day。所有里程碑都对应 `todo-tasks.md` 章节，可被外部跟踪。

| 季度 | 主题 | 关键交付 | 商业里程碑 |
|---|---|---|---|
| **2026 Q2（当前）** | **V1 GA · 投资人就绪版** | PRD10 §26 全验收（已绿，见 [`docs/14.2-prd10-acceptance-checklist.md`](docs/14.2-prd10-acceptance-checklist.md)）· SPA 全 nav sweep 0 issue · 部署一键（[`docs/11-deployment/docker.md`](docs/11-deployment/docker.md)）· 移动端最低可用 · Demo 公开 | 100 paying user · Pre-A 意向 · ARR ¥0.5M |
| **2026 Q3** | V1.2 协作 + 移动端 | 多 workspace（PRD10 B-17）· 团队邀请 · 评论 · iOS PWA · Notion / 飞书 / 微信收藏导入 · 暗色模式 · 国际化 zh/en | 团队 License 首批 5 单 · DAU 1k · ARR ¥1.5M |
| **2026 Q4** | V2 智能化 | 语义搜索（B-13）· Insights AI 主动推（PRD10 §12）· Skills 市场公开（B-19）· 富媒体 Artifact · 模型自动路由 | API 月调用 1M+ · Skills 上架 50+ · ARR ¥3M+ |
| **2027 Q1** | V2.5 平台化 | 计费 / Subscription（B-18）· 多语言（5 种）· 企业 SSO / SAML · 行业定制版（学术 / 律师 / 投研 / 销售）· 数据导出与合规审计 | ARR ¥6M+ · 毛利 65%+ · A 轮启动 |
| **2027 H2 (远期视野)** | V3 智能体协作 | Agent 编排（多 Agent 任务流）· 跨域知识图谱（联通个人 / 团队 / 公开 KB）· 行业 AI 模型 fine-tune · 收购 / 整合社区 Skills | 服务 ≥ 10k 团队 / ≥ 100k 个人 · ARR ¥30M+ |

**已交付的产品里程碑（截至 2026-05-05）**：

- PRD10 V1 P0 后端 MVP（capture / feed / KB / AI / search / skills / garden / notifications）已端到端跑通（`agent-progress-report.md` Milestones 1–24）
- Mydow Web SPA 重写完成（原生 ESM；8 个一级 view + 12 个 modal/抽屉）
- 真实 LLM provider（DeepSeek via litellm）+ AI 流式 SSE
- 双引擎绿章：SQLite + Postgres 16 (Docker) 71/71 PRD10 dedicated suite
- Chrome MCP 投资人 demo 闭环脚本（[`scripts/chrome-mcp-smoke.ps1`](scripts/chrome-mcp-smoke.ps1)，12 步 26s 自动化）

---

## 👥 团队

> Mydow 由一支「小而精的工程 × 产品 × AI」复合团队驱动；当前正在为 V1 GA 与 Pre-A 扩募首批早期工程合伙人。

| 角色 | 状态 | 联系 |
|---|---|---|
| 创始人 · 产品 + 技术 | 在岗 | 见下方 [📬 联系我们](#-联系我们) |
| 多 Agent 工程团队 | 在岗 · 4 路并行 | Agent 1（协调 + 后端基础）/ Agent 2（产品数据 + SPA）/ Agent 3（智能后端 + 部署）/ Agent 4（前端 E2E + 验收）；详见 [`agent-collaboration.md`](agent-collaboration.md) |
| 全栈 / 前端工程师 | **招募中** | `careers@mydow.example` · 期望 3+ 年 React/Vue 或原生 ESM SPA 经验 |
| AI / Search 工程师 | **招募中** | `careers@mydow.example` · 期望熟悉 LiteLLM / 向量检索 / RAG |
| DevOps / SRE | **招募中** | `careers@mydow.example` · 期望熟悉 Docker / Postgres / SSE / 监控 |
| 增长 / 内容合伙人 | **招募中** | `growth@mydow.example` · 期望有 SaaS 0→1 经验 |
| 顾问 / 投资伙伴 | **招募中** | `invest@mydow.example` |

**协作模式**：本仓库由多 Agent（人类 + AI 工程师）并行开发，遵循以下强一致协议：

- 唯一任务池：[`todo-tasks.md`](todo-tasks.md)（`open` / `doing` / `done` / `blocked` 四态机）
- 协作规则：[`.cursor/rules/whyme-multiagent-workflow.mdc`](.cursor/rules/whyme-multiagent-workflow.mdc)
- 滚动 milestone：[`agent-progress-report.md`](agent-progress-report.md)
- 全部交付都必须有 **Chrome MCP 真浏览器证据 + 可重现测试基线**，不允许「toast 闪一下、状态没动」类伪交付

---

## 💰 投资材料

| 资料 | 路径 |
|---|---|
| 产品介绍 | 本 README + [`docs/01-prd/PRD10.md`](docs/01-prd/PRD10.md) |
| 30 秒 / 2 分钟 / 5 分钟 演示动线 | [`docs/demo-script.md`](docs/demo-script.md) |
| **PRD10 §26 验收清单**（投资 review 必读） | [`docs/14.2-prd10-acceptance-checklist.md`](docs/14.2-prd10-acceptance-checklist.md) |
| 截图 / 录屏 | `.tmp/screenshots/`（Chrome MCP 自动化产出） |
| Chrome MCP demo 闭环脚本 | [`scripts/chrome-mcp-smoke.ps1`](scripts/chrome-mcp-smoke.ps1)（12 步 26s 全绿） |
| API 参考（600+ 行 curl 示例） | [`docs/11-deployment/api-reference.md`](docs/11-deployment/api-reference.md) |
| 部署手册 | [`docs/11-deployment/docker.md`](docs/11-deployment/docker.md) |
| 商业模式 / 路线图 / 团队 | 本 README §[商业模式](#-商业模式) · [路线图](#-路线图产品视角) · [团队](#-团队) |
| Pitch deck（投资人 1-pager + 完整 deck） | 见 [`todo-tasks.md`](todo-tasks.md) §13.4（在做） |

> **想要 30 分钟现场 demo？** 邮件 `invest@mydow.example` 或参考下方 [📬 联系我们](#-联系我们)；72 小时内回复，可线上 / 线下任选。

---

## 📬 联系我们

| 用途 | 联系方式 | 回复 SLA |
|---|---|---|
| **投资 / 战略合作** | `invest@mydow.example` | 72 小时内回复 + 主动约 30 分钟 demo & Q&A |
| **企业试用 / 团队 License** | `sales@mydow.example` | 14 天免费试用；可定制 demo 数据 + 私有部署 PoC |
| **Skill 上架 / 开发者** | `developers@mydow.example` | Skills SDK 在 Q3 开放；可提前申请预览 |
| **媒体 / 内容合作** | `press@mydow.example` | 一周内回复 |
| **求职 / 加入团队** | `careers@mydow.example` | 一周内回复 + 异步小作业 + 现场 / 远程面试 |
| **Demo 预约** | 邮件以上任一地址，附场景 + 期望时段 | — |
| **Bug / Feature 反馈** | [GitHub Issues](https://github.com/yourusername/whyme/issues) | 工作日 48 小时内 triage |
| **Twitter / X · 微信公众号** | 待开通 — 关注 [github.com/yourusername/whyme](https://github.com/yourusername/whyme) 获取首发 | — |

> **隐私声明**：上述邮箱（`*.mydow.example`）为占位地址，生产联系方式将在 V1 公开后通过 [github.com/yourusername/whyme](https://github.com/yourusername/whyme) 与官网（待发布）同步公布。如需现在直接联系，请在 GitHub Issue 中 @ 维护者或在 [`agent-collaboration.md`](agent-collaboration.md) 内的协调通道留言。

---

## 🤝 贡献

本项目采用**多 Agent 并行协作**模式：

- **唯一任务池**：[`todo-tasks.md`](todo-tasks.md)（`open` / `doing` / `done` / `blocked`）
- **协作规则**：[`.cursor/rules/whyme-multiagent-workflow.mdc`](.cursor/rules/whyme-multiagent-workflow.mdc)
- **滚动日志**：[`agent-progress-report.md`](agent-progress-report.md)

新加任务请直接编辑 `todo-tasks.md`，从 `open` 起，认领时改 `doing` + 写 Owner。

---

<details>
<summary><b>📖 旧版 AgentOS Core 文档（Mydow 之前的微内核架构）</b></summary>

下面保留 Mydow 之前的 AgentOS Core 微内核架构说明，部分能力（沙箱、Skills、Aider 集成）在 Mydow 内部继续使用。

## 项目简介

AgentOS Core 是一个高度模块化的 AI 代理内核，采用**微内核 + 插件架构**设计。通过严格的接口抽象和动态配置加载，实现核心模块的随意插拔，支持多种 LLM 提供商、记忆系统、上下文管理策略和编码能力。

### 核心特点

- **一切皆插件** - 所有核心模块均为接口，通过 `config.yaml` 动态加载实现
- **Skills System** - Coze风格的开放技能系统，支持动态角色切换 🆕
- **Server-Side Sandbox** - Docker/本地容器化隔离环境
- **Virtual IO** - WebSocket 通信，支持 Web/App/小程序多端
- **多模型支持** - 通过 LiteLLM 支持 OpenAI、Anthropic 等多种 LLM
- **编码能力** - 集成 Aider 的代码编辑和 Git 工作流
- **智能上下文** - Summarizer和KeyInfoExtractor策略 🆕

---

## 功能特性

### 已实现 ✅

| 模块 | 功能 | 状态 |
|------|------|------|
| **核心架构** | 接口定义、类型系统、动态配置 | ✅ 完成 |
| **LLM 集成** | LiteLLM 多模型支持 | ✅ 完成 |
| **Skills System** | 技能管理器、解析器、3个示例技能 | ✅ 完成 🆕 |
| **上下文管理** | 滑动窗口、Summarizer、KeyInfoExtractor | ✅ 完成 🆕 |
| **记忆系统** | Mem0 向量数据库、本地 JSON | 🟡 部分 |
| **工具系统** | 统一工具注册表 | ✅ 完成 |
| **编码能力** | Aider 适配器 | 🟡 部分 |
| **沙箱系统** | Docker/本地沙箱 | ✅ 完成 |
| **Web 服务器** | FastAPI + WebSocket | ✅ 完成 |
| **Web 前端** | Monaco Editor + 文件树 | ✅ 完成 |

### 总体完成度：90% (+5% Skills System)

详见 [开发进度追踪](docs/PROGRESS.md)

---

## 快速开始

### 🐳 方式一: Docker 部署 (推荐,无需安装 Python)

最简单的方式,无需手动安装任何依赖!

```bash
# 克隆项目
git clone https://github.com/yourusername/whyme.git
cd whyme

# 一键启动
bash docker-deploy.sh
```

或者手动启动:

```bash
# 使用 Docker Compose
docker-compose -f docker-compose.simple.yml up -d

# 或使用 Docker 原生命令
docker build -f Dockerfile.fast -t agentos:latest .
docker run -d --name agentos -p 8003:8003 agentos:latest
```

访问 http://localhost:8003 即可使用!

📖 **详细文档**: [DOCKER_QUICKSTART.md](./DOCKER_QUICKSTART.md) | [DOCKER.md](./DOCKER.md)

---

### 方式二: 本地安装

#### 环境要求

- Python 3.11 或更高版本
- pip 或 uv

#### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/whyme.git
cd whyme

# 安装依赖
pip install -e .

# 或使用 uv（推荐）
uv pip install -e .
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 添加 API 密钥
# OPENAI_API_KEY=sk-xxx
# ANTHROPIC_API_KEY=sk-ant-xxx
```

### 启动服务器

```bash
# 方式1：使用启动脚本（推荐）
python scripts/start.py

# 方式2：使用服务器脚本
python scripts/run_server.py

# 方式3：直接运行uvicorn
uvicorn src.agent_os.server.app:app --reload --port 8003
```

服务器将：
1. 自动使用 LocalSandbox（无需 Docker）
2. 在浏览器中打开 http://localhost:8003
3. 启用热重载

### 基本使用

1. 打开 http://localhost:8003
2. 在聊天框中输入指令，例如：
   - "创建一个 hello.py 文件，打印 Hello World"
   - "帮我写一个快速排序算法"
   - "分析当前目录的代码结构"
3. Agent 将自动执行并显示结果

### Skills System 使用 🆕

AgentOS Core 现在支持动态技能切换，让你可以快速改变AI助手的专业领域：

```python
from agent_os.agent import Agent

# 初始化Agent
agent = Agent.from_config_file("config.yaml")
agent.initialize_skills()

# 列出可用技能
skills = agent.list_skills()
for skill in skills:
    print(f"{skill['name']}: {skill['description']}")

# 应用技能 - 切换为数据分析专家
agent.apply_skill("data_analyst")
response = await agent.chat("分析这个CSV文件的数据趋势")

# 切换为Web开发专家
agent.apply_skill("web_developer")
response = await agent.chat("创建一个React组件显示用户列表")

# 清除技能，回到默认模式
agent.clear_skill()
```

**内置技能**:
- `default_coder` - 全栈开发专家
- `data_analyst` - 数据分析专家
- `web_developer` - Web开发专家

详见 [Skills System Guide](docs/03-toolkit/skills-system-guide.md)

---

## 配置说明

### config.yaml

```yaml
agent:
  name: "DevBot"

memory:
  provider: "agent_os.memory.local_json.LocalJSONProvider"
  # 或使用向量数据库
  # provider: "agent_os.memory.mem0_impl.Mem0Provider"
  config:
    storage_path: "./data/memory"

context:
  provider: "agent_os.context.sliding_window.SlidingWindowContext"
  config:
    max_tokens: 8000

llm:
  provider: "agent_os.llm.litellm_impl.LiteLLMProvider"
  config:
    model: "gpt-4"
    temperature: 0.7

coding:
  provider: "agent_os.capabilities.coding.aider_adapter.AiderAdapter"

sandbox:
  runtime: "local"  # 或 "docker"
  workspace: "./workspace"
```

---

## 📚 文档

### 核心文档
- **[快速开始](QUICKSTART.md)** - 5分钟上手指南
- **[测试指南](TESTING_GUIDE.md)** - 测试运行和最佳实践
- **[架构文档](ARCHITECTURE.md)** - 系统架构设计
- **[变更日志](CHANGELOG.md)** - 版本更新记录

### 用户指南
- **[部署指南](docs/guides/deployment.md)** - Docker部署详细步骤

### 开发文档
- **[API参考](docs/03-toolkit/api-reference.md)** - 完整的API接口文档
- **[系统架构](docs/03-toolkit/architecture.md)** - 技术架构设计
- **[最新进度](docs/02-progress/latest-status.md)** - 当前实现状态

### 历史报告
- **[性能报告](docs/reports/performance/)** - 性能基线和测试结果
- **[PRD合规](docs/reports/prd/)** - PRD合规性审计
- **[测试报告](docs/reports/testing/)** - 测试完成和改进报告
- **[微信集成](docs/reports/wechat/)** - 微信集成实现文档

---

## 架构设计

### 核心接口

```python
class MemoryProvider(ABC):
    async def add(self, ctx: RuntimeContext, content: str) -> str: ...
    async def search(self, ctx: RuntimeContext, query: str) -> List[Dict]: ...

class ContextManager(ABC):
    async def process(self, messages: List[Dict], max_tokens: int) -> tuple: ...

class ToolRegistry(ABC):
    async def register_python_tool(self, func: callable): ...
    async def execute(self, tool_name: str, arguments: Dict) -> Any: ...

class CodingCapability(ABC):
    async def apply_edit(self, ctx: RuntimeContext, instructions: str) -> str: ...
```

### 项目结构

```
.
├── src/agent_os/            # 核心代码
│   ├── core/               # 核心接口和类型定义
│   ├── memory/             # 记忆系统实现
│   ├── context/            # 上下文管理策略
│   ├── tools/              # 工具注册表
│   ├── llm/                # LLM 集成
│   ├── sandbox/            # 沙箱环境
│   ├── capabilities/       # 能力扩展（编码等）
│   ├── server/             # FastAPI 服务器和前端
│   └── agent.py            # Agent 主逻辑
│
├── tests/                  # 测试套件
│   ├── unit/               # 单元测试
│   ├── integration/        # 集成测试
│   ├── e2e/                # 端到端测试
│   └── temp/               # 临时测试
│
├── docs/                   # 文档
│   ├── 01-prd/             # 产品需求文档
│   ├── 02-progress/        # 进度报告
│   ├── 03-toolkit/         # Toolkit技术文档
│   ├── 04-guides/          # 用户指南
│   └── 05-testing/         # 测试报告
│
├── scripts/                # 可执行脚本
│   ├── run_server.py       # 启动服务器
│   └── start.py            # 备用启动脚本
│
├── logs/                   # 服务器日志（运行时生成）
├── tests-temp/             # 临时测试文件
├── screenshots/            # UI截图
│
├── config.yaml             # 主配置文件
├── pyproject.toml          # Python项目配置
├── docker-compose.yml      # Docker编排
├── Dockerfile              # Docker镜像
└── README.md               # 本文件
```

---

## 开发计划

### 最新完成 (2026-01-28) ✅

- ✅ **Skills System** (PRD2) - Coze风格开放技能系统
- ✅ **SummarizerContext** - LLM驱动的对话摘要
- ✅ **KeyInfoExtractor** - 关键信息提取策略
- ✅ **完整测试** - 22个单元测试 + 手动测试

### 高优先级 🔴

1. **WebSocketIO 线程安全修复**
   - 修复同步/异步混合调用问题
   - 确保线程安全的事件队列

2. **Diff 确认流程**
   - 实现后端 Diff 生成和发送
   - 处理用户确认/拒绝操作

3. **RepoMap 集成**
   - 集成Aider的RepoMap功能
   - 代码库结构理解

### 中优先级 🟡

4. **富媒体可视化** (PRD2)
   - Artifact协议定义
   - @json-render前端集成

5. **完整 Aider 集成**
   - 实例化 Aider Coder 类
   - Git 工作流支持
   - Tree-sitter语法解析

6. **记忆系统增强**
   - HippoRAG 集成
   - Mem0 云服务支持

详见 [开发进度追踪](docs/FINAL_DEVELOPMENT_SUMMARY.md)

---

## 技术栈

### 后端
- Python 3.11+
- FastAPI + Uvicorn
- LangGraph, LiteLLM
- Pydantic, YAML

### 前端
- Monaco Editor (VS Code 内核)
- WebSocket, REST API

### AI/ML
- sentence-transformers
- FAISS

---

## 贡献

欢迎贡献！请先阅读 [开发进度追踪](docs/PROGRESS.md) 了解当前的开发状态。

### 开发流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 致谢

- [Aider](https://github.com/paul-gauthier/aider) - AI 编码助手
- [LiteLLM](https://github.com/BerriAI/litellm) - 统一 LLM API
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web 框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - LLM 应用框架

</details>

---

<div align="center">

**[⬆ 返回顶部](#mydow)**

Made with ❤️ by the Mydow / WhyMe Team — 2026

</div>
