# Mydow Demo 演示脚本（投资人 / 客户现场用）

> **作者**：Agent 4
> **场景**：投资人路演、客户演示、内部 review。
> **目标**：让对方在 30 秒 / 2 分钟 / 5 分钟三档时间内分别看到「能用」「能闭环」「能拉投资」三层产品力。
> **基础**：本脚本要求 PRD10 backend + SPA 已起、demo 模式已开、seed 数据已注入。
> **配套文档**：`docs/agent-2-spa-binding-guide.md`（SPA 接入）、`docs/agent-2-seed-field-audit.md`（demo 数据样貌）、`agent-progress-report.md`（最新里程碑）。

---

## 0. 演示前 60 秒准备（每次都要做）

```pwsh
# 0-1) 后端环境（demo 模式 + worker 开 + seed reset）
$env:DATABASE_URL = "sqlite+aiosqlite:///d:/Codes/whyme/.tmp/smoke.db"
$env:AGENTOS_PRD10_WORKER = "on"
$env:AGENTOS_PRD10_WORKER_INTERVAL = "2"
$env:AGENTOS_DEMO_MODE = "on"
$env:AGENTOS_AI_LLM = "off"            # 投资人现场不烧 token；要展示真 LLM 时改 "on"
$env:PYTHONPATH = "d:\Codes\whyme\src"

# 0-2) Reset seed（保证 demo 账号永远干净，30s）
python scripts/seed_prd10.py --email demo@mydow.example --password demo123 --reset

# 0-3) 起 uvicorn（后台）
python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8000

# 0-4) 浏览器开 http://127.0.0.1:8000/mydow/
#       页面会自动 demo_login，无需手动登录
```

**演示前自检**（30 秒内打勾，缺哪条立即报警，不要硬演）：

- [ ] `http://127.0.0.1:8000/api/v1/demo/status` 返回 `{"enabled":true,"email":"demo@mydow.example"}`
- [ ] 浏览器打开 `/mydow/` 后右上头像区显示 `demo / demo@mydow.example`
- [ ] 首页能看到 30 张 seed 卡片
- [ ] 知识库能看到 6 个文件夹
- [ ] AI 页能看到 3 个会话
- [ ] Skills 页能看到 5 个 skill
- [ ] 数字花园能看到节点

如果有任何一条对不上，立刻 `python scripts/seed_prd10.py --reset` 然后刷新浏览器重试。

---

## 1. 30 秒版（电梯 demo）

> 适用：**第一次见**、人多嘴杂、对方只想看「这是个真东西吗」。
> **节奏**：每 5 秒一个动作，绝不停留。
> **核心信息**：「Mydow 是把灵感变知识资产的 AI 工作台。」

### 演示动线

| 时段 | 动作 | 你说的话 | 对方看到 |
|---|---|---|---|
| 0–5s | 直接打开 `http://127.0.0.1:8000/mydow/` | 「这是 Mydow，AI 时代的个人知识工作台。」 | 首屏：左侧 5 个一级页 + 右侧 30 张内容卡片 |
| 5–10s | 在首页输入框打 `准备投资人 demo 的 3 个核心点` | 「我现在记一条灵感。」 | 卡片入栈 |
| 10–15s | 点 `提交` | 「后端 worker 正在自动整理它。」 | toast「灵感已同步到后端」+ 最近捕捉列表多一条 |
| 15–20s | 切到 `知识库` | 「这是结构化后的知识库，6 个文件夹、20 篇文档。」 | 6 个文件夹卡片 |
| 20–25s | 切到 `Mydow AI`，点已有会话 | 「这里是带知识库上下文的 AI 助手，能引用文档。」 | AI 对话气泡 |
| 25–30s | 切到 `数字花园` | 「最终所有知识自动建图。」 | SVG 节点图 |

### 收尾一句

> 「整个产品 V1 已经能跑通：捕捉 → 整理 → 检索 → AI 引用 → 知识图谱。后端、前端、worker、AI 全部跑通了真实流程，不是 demo mock。」

---

## 2. 2 分钟版（Coffee chat）

> 适用：**1on1 / VC 偶遇**、对方有兴趣听更细的「这怎么用」。
> **节奏**：4 个 30 秒块，每块演 1 个核心闭环。
> **核心信息**：「PRD10 §30 最小闭环走通。」

### 闭环 1（0–30s）：Capture → Card → Feed

```
1. 首页输入：「Mydow 想拿来给 50 个 KOL 做产品观察笔记」
2. 点提交 → toast「灵感已同步到后端」
3. 5 秒后：最近捕捉里就出现这条新卡片，自动带摘要 + 标签
4. 点这张卡片 → 抽屉打开，看到来源、标签、AI 建议
```

**你说**：「真后端。worker 每 2 秒拉一次任务队列，会把灵感整理成可检索的卡片。我们从 capture 到 KB 整个 pipeline 都是 PRD10 §19 标准的——Receive → Parse → Summarize → Classify → Chunk → Embed → Index → Notify。」

### 闭环 2（30–60s）：Web 剪藏 → 文档

```
1. 点首页右上「网页剪藏」
2. 粘 https://example.com/your-favorite-article
3. 点保存 → toast「网页剪藏已提交后端」
4. 切知识库 → 文件夹里多了一篇文档（处理中）
5. 演示结束时它会变成 ready
```

**你说**：「文件、链接、语音、文本都走同一个 pipeline。投资人最关心的是这能不能扩——我们的存储抽象层支持本地 / S3 / R2 / OSS，无需改 API。」

### 闭环 3（60–90s）：Mydow AI → save-to-kb

```
1. 点 Mydow AI → 选已有会话或新建
2. 输入「请总结产品策略文件夹里的核心思路」
3. 看 AI 流式回答（如果开了 AGENTOS_AI_LLM=on）
4. 点回答下方「保存到知识库」
5. 5 秒后切知识库 → 多一篇 AI 生成文档
```

**你说**：「AI 不是黑盒——每一条回答都带引用（PRD10 §11.4 message.citation 事件），并且能反向写回知识库形成可追溯资产。这是我们和 ChatGPT 的本质区别。」

### 闭环 4（90–120s）：Skill 运行 → Garden 更新

```
1. 切 Skills 广场 → 点「访谈洞察提炼」
2. 在弹窗里贴一段访谈记录（或用 seed 默认）
3. 点运行 → toast「Skill 运行任务已入队」
4. 切回首页通知抽屉 → 看到「AI 已生成任务」通知
5. 切数字花园 → 节点+1
```

**你说**：「Skills 是我们对 GPT Store 的应答——预制的 AI 工作流，未来可以做交易。所有结果落库、走通知、入图谱。」

### 收尾一句

> 「以上四个闭环对应 PRD10 §26 的全部验收要求；后端 187 个集成测试稳定通过；浏览器内每个按钮都打到真 `/api/v1`。我们不是 demo——是已经能上线的 V1。」

---

## 3. 5 分钟版（深度路演）

> 适用：**Term sheet 前**、Sandhill Road 一对一、客户试用。
> **节奏**：5 段 1 分钟，每段一个层次。
> **核心信息**：「产品 + 工程 + 数据 + 团队 + 路线图。」

### 第 1 分钟：产品定位

> 边讲边打开首页，但不点。让对方看左侧 5 个导航。

「Mydow 是 AI-native 的个人知识工作台。和 Notion 不同——Notion 是手动整理；和 ChatGPT 不同——ChatGPT 没有你的私人语料。Mydow 把这两层缝起来：你输入任何东西（文本、链接、文件、语音），AI 自动整理成结构化知识，再让你随时通过 AI 对话调用它。」

> 这一分钟末尾点首页 → 让对方看真实数据流的卡片瀑布。

### 第 2 分钟：捕捉到 KB（演 §26.1 闭环）

> 跟 2 分钟版「闭环 1」一样的 capture text。**但加一步**：

「我现在 capture 一条 → 切到 worker 日志 → 大家看 PRD10_jobs 表 1 秒后多了 1 行 → 2 秒后变成 completed → KB 文档表也多了一行。这是真的 worker，不是 setTimeout。」

**底气**：可以打开 Chrome devtools network 面板让对方看请求是 `/api/v1/capture/text` 而不是 `setTimeout`。

### 第 3 分钟：KB + Mydow AI（演 §26.2 + §26.3）

```
1. 切到知识库，进一个文件夹，打开一篇文档
2. 看摘要、来源、关联卡片、AI 建议
3. 点「让 Mydow AI 总结」 → 直接跳到 AI 对话，自动带上下文
4. 看 AI 回答带引用 chip
5. 点引用 chip → 跳回那篇文档
```

「PRD10 §10.7 要求文档详情包含 chunks_preview / related_cards / ai_suggestions——我们三项都做了。AI 引用是结构化的 citation 对象，不是字符串拼接，所以它能精确指向文档里的第几个 chunk。」

### 第 4 分钟：Skills + Garden（演 §17 + §18）

```
1. Skills 广场点「周报生成器」运行
2. 等 5 秒看通知里出现「AI 已生成任务」
3. 切回首页 → /today.tasks 多 2 条
4. 切数字花园 → 节点已联动更新（点中心节点能看到关联）
```

「Skills 是工作流原语，未来可以社区化。每一个 Skill 运行都写 `Job` 表 + `SkillRun` 表 + `Notification`，全程可追溯。这是 ChatGPT plugin 解决不了的——它没有我们的数据底座。」

### 第 5 分钟：技术 / 团队 / 路线图

> 边打开 README 边讲（如果 README 投资人版还没做就用 PRD10 §24 + §27）。

**技术底座**：

- 后端 FastAPI + 异步 SQLAlchemy + PostgreSQL + Redis + Worker pipeline
- 前端原生 ESM SPA（不锁框架，未来可拆成 native app）
- AI provider 抽象层：DeepSeek（默认，便宜）/ OpenAI / Anthropic 一键切
- 测试矩阵：187 个 PRD10 集成测试稳定通过；双引擎绿章（SQLite + Postgres 16）

**已经走通**：

- §24 P0 全部 10 项后端能力（Auth/Today/Capture/Feed/KB/Job/Notification/AI Chat/Search/Permissions）
- §25 验收：首屏 5 个并发接口、性能目标、seed 数据
- §26 验收：首页 / KB / Mydow AI / 搜索 / 通知 / 异步任务全部测试覆盖
- SPA 9 条 hash 路由 + 21 节点真图谱 + Demo 一键登录

**路线图**：

- Q1：上线 + 100 内测（已就绪）
- Q2：embedding 语义检索 + 移动端 + 暗色模式
- Q3：Skills 市场（B-19）+ 多 workspace（B-17）+ 订阅（B-18）
- Q4：API 平台（开发者通过我们的 worker 跑 AI agent）

**团队介绍**（占位，按需填）：略。

### 收尾一句

> 「我们 V1 已经达到 PRD10 §30 最小可运行闭环的所有要求。这意味着我们不是在拿 idea 拉投资——我们是在拿可上线的产品拉投资。」

---

## 4. 演示后的常见问题（FAQ）

| Q | 准备好的 A |
|---|---|
| 「数据安全？」 | PRD10 §22：用户隔离基于 user_id；上传走签名 URL；AI 调用全程 audit log；用户可关「使用知识库作为 AI 上下文」开关。 |
| 「AI 成本？」 | 默认 DeepSeek（每千 tokens ~ $0.0001 量级），有 24h 缓存（§12.3 任务），用户超量限速（§12.2）。 |
| 「跟 ChatGPT 比？」 | 我们有结构化知识库 + 引用追溯 + 反向写回 + 工作流（Skills），ChatGPT 三个都没有。 |
| 「跟 Notion AI 比？」 | Notion AI 仅做文档内 AI；我们做的是「跨文档 + 跨来源」的整理 + 检索。 |
| 「能多人协作？」 | V1 个人版；多 workspace 在 §24 P2 路线图（B-17）。 |
| 「移动端？」 | SPA 已响应式（§9.3 任务在做），未来可包成 PWA 或 React Native。 |
| 「为什么是你们？」 | 我们的 PRD10 是带验收的工程文档，不是 vision 幻灯。187 个测试 + 双引擎绿章 + Chrome MCP 浏览器实测，证明我们工程实力。 |
| 「商业模式？」 | 个人订阅 / 团队 license / API 调用 / Skills 市场分成。Q3 起跑订阅。 |
| 「TAM？」 | 全球生产力工具 SaaS 2024 年 ~$700B；个人知识管理 + AI 工作台细分赛道增速 50%+。具体 TAM/SAM 在 pitch deck（§13.4）。 |
| 「现场报错怎么办？」 | 立刻 `python scripts/seed_prd10.py --reset` 重置 seed 后刷新；如还有问题切预录视频（§10.6 任务）。 |

---

## 5. 备选演示路径（视情况切）

- **被问到具体功能**：直接切到那个页面演，不要硬走脚本顺序。
- **被打断让看代码**：打开 `docs/agent-2-spa-binding-guide.md`，证明产品有完整工程契约。
- **被问到测试**：在终端跑一遍 `.tmp/baseline-tests.txt` 里的命令，让对方看 187 passed。
- **网络/服务挂了**：演 `static/mydow/legacy-prototype.html` 静态原型作为 backup（虽然没真后端，但可看视觉）。

---

## 6. 演示后必做（48 小时内）

- 把 demo 录屏（90 秒精剪）发给对方（§10.6 任务）。
- 把 README 投资人版（§13.1 任务）的链接发给对方。
- pitch deck（§13.4 任务）发给对方。
- 在 todo-tasks.md 加新任务跟进对方反馈。

---

## 维护

- 每次 demo 后总结「卡哪儿了」，加进 §4 FAQ。
- 每月 review 一次：Q & 答案是否过时；功能动线是否过时；时间是否还能压缩。
- 演示前永远跑 `python scripts/seed_prd10.py --reset` + Chrome MCP 自检（§11.12 任务）。
