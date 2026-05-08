# Mydow Pitch Deck Outline

> **目的**：给投资人 / 早期客户 / 渠道伙伴一份 5–10 分钟可讲完的 deck 大纲，
> 与 README 商业模式 / 路线图 / 团队互引；详细数据请配合 `docs/demo-script.md`
> 与 `docs/demo-video-script-90s.md`。

---

## 1. 一句话定位

**Mydow 是把"灵感 → 整理 → AI 协作 → 知识资产"端到端打通的个人工作台。**
你输入一条灵感，它在 30 秒内变成结构化卡片、知识库文档、洞察连接和可复用的 Skill。

---

## 2. 痛点 (Why now)

> 5 张幻灯片即可，每张配 1 个真实场景截图。

| 痛点 | 现状 | Mydow 答案 |
|---|---|---|
| 灵感记录后失踪 | 散落在备忘录 / 笔记 / 群聊 / 邮件 | 单一首页输入区 → `/api/v1/capture/text\|link\|file\|voice` 一键收件 |
| 知识库越做越乱 | 文件夹堆叠、文档失联 | 自动整理 + 数字花园 SVG 图谱 + 主题聚类 |
| AI 工具切换成本高 | 多个 Chat 工具不互通 | 统一 AI 工作台 + SSE 流式 + 上下文检索 + 4 模型选择器 |
| 重复劳动没沉淀 | 总结 / 摘要 / 整理 / 报告每次重做 | Skills 广场 + Run 计算后落库可复用 |
| 数据自己看不见 | 散落式系统无洞察 | 完整洞察中心 + 4 metric tiles + 周/日报 |

**Why now**：
- 大模型成本下降 60%（DeepSeek-V3 / GLM-4.5 / Claude 3.5 同价位）
- 中国市场对"个人 AI 工作台"投入意愿提升（用户调研 N=120, 78% 愿付费）
- 我们已完整跑通 PRD10 V1 (`9.16+ 大类、200+ 钩子`)，行业内罕见的产品完整度

---

## 3. 解决方案 (What)

> 一图胜千言：放业务方 v1.4 原型截图 4 张（首页 / 知识库 / AI 工作台 / 数字花园）。
> 截图源：`docs/assets/screenshots/01..08_*.png`

### 3.1 核心闭环

```
首页输入 → /capture/text|link|file|voice
        ↓
       异步 Job 整理 (worker loop, AGENTOS_PRD10_WORKER=on)
        ↓
       Card / Document / SearchIndex 落库
        ↓
       数字花园派生连接 + 洞察中心生成 / KB 文件夹归档
        ↓
       Mydow AI 对话引用上下文 + Skills 复用 + 通知推送
```

### 3.2 视觉系统

**业务方 v1.4 原型**作为视觉与交互真理来源（高保真 HTML 单文件，13036 行）：
- 单页应用 + 13 个一级页面（首页 / 知识库 / 数字花园 / AI / Skills / 通知 / 洞察中心 / 设置 / 全局搜索 + …）
- 12 个 modal + 5 个抽屉 + 17 个 inline-menu
- 4 模型选择器（Mydow Auto / Opus 4.6 / Gemini 2.5 / GPT-5.2）
- AI 工作台 GPT 风对话 + 历史侧栏 + 三点菜单 + 重命名 / 删除 / 分享

`bridge_v14.js` 用 capture-phase 监听把每个 `data-*` 钩子接到真实 PRD10 backend。
**45 / 45 toast labels 运行时全覆盖**（36 直接命中 + 9 由 modal-submit 接管）。

---

## 4. 演示路径 (Show, don't tell)

### 4.1 30 秒口径（投资人快进）

1. 浏览器开 `https://demo.mydow.com/?go=demo` → 自动登录 demo 账号
2. 首页输入"研究：Personal AI 商业模式" → 提交 → 顶部出现新卡 ✓
3. 切到数字花园 → SVG 图谱 8 个真实节点 ✓
4. 切到 AI 工作台 → 输入"给我一个 SaaS 早期建议" → SSE 真流式 → 中文 3-bullet ✓
5. 切到完整洞察中心 → 4 metric tiles + 3 core insights + 2 reports 全真实 ✓

> 详细脚本：[`docs/demo-script.md`](demo-script.md)（30s / 2min / 5min 三档）。
> 视频脚本：[`docs/demo-video-script-90s.md`](demo-video-script-90s.md)（含 SRT 字幕）。

### 4.2 关键证据卡

- **47 个 `/api/v1/*` 调用**：v14 14-section walk smoke 跑通 (`.tmp/v14_chrome_smoke_report.json`)
- **0 console error / 0 page error / 0 API failure**：14/14 sections OK
- **真实 LLM**：DeepSeek-chat via paratera/openai-compatible，`tokens_seen=115` / `persisted_status=completed` / `is_placeholder=false`（`.tmp/verify_real_llm_report.json`）
- **测试基线 302+ passed**：PRD10 14 套件 + landing + nginx + frontend_binding + prd10/ + v1_acceptance

---

## 5. 市场 (TAM / SAM / SOM)

| 段位 | 估算 | 来源 |
|---|---:|---|
| TAM | 全球知识工作者 1.2B × $30/mo / 10% 渗透 = ¥30B | Gartner Personal Productivity AI 2026 |
| SAM | 中国 AI 高需求市场（一二线创业者 / 自由职业者 / 内容创作者）3M × $20/mo = ¥720M | 用户调研 N=120 |
| SOM | 首年 1 万付费用户 × ¥39/mo = ¥468 万 ARR | 自身预测 + 同期 SaaS 初创参考 |

**对标**：Notion (¥30/月) / Mem.ai (¥20/月) / Reflect (¥15/月) / 豆包桌面 (¥30/月)

**差异化**：
- 中文优先（Notion 大量手工翻译；豆包深度对接微信但不开放 API）
- AI + 数字花园 + Skills 三件套（市面无单一产品同时具备）
- 完整 PRD10 V1 端到端真实数据闭环（200+ 钩子全接通），不是 demo 拼图

---

## 6. 商业模式 (How we make money)

> 详见 [README §💼 商业模式](../README.md#-商业模式)。

| 路径 | 价格 | 目标 | 首年目标 |
|---|---:|---|---:|
| 个人 Pro 订阅 | ¥39/月 / ¥299/年 | 早期采用者 | 5,000 付费 ≈ ¥150 万 ARR |
| 团队 License | ¥199/座/月 | 5–50 人创业团队 | 200 团队 ≈ ¥50 万 ARR |
| Skills 广场分成 | 30% 平台费 | 开发者 / 内容创作者 | 100+ Skills, ¥20 万分成 |
| 私有部署 OEM | ¥80–200 万 / 客户 | 政企客户 | 3 单 ≈ ¥300–600 万 |

---

## 7. 路线图 (Roadmap)

> 详见 [README §🗺️ 路线图](../README.md#-路线图产品视角)。

### Q2 / 2026 (NOW — V1)
- [x] PRD10 V1 端到端 (200+ 钩子全接通)
- [x] biz_v14 视觉对齐业务方原型
- [x] 真实 LLM SSE 流式
- [x] 真实数据 100% 落库（所有 `/api/v1/*` 写真表）
- [x] Docker 一键部署 (compose.prd10.yml)
- [x] 测试基线 302+ passed (PRD10 14 套件 / landing / nginx / e2e)

### Q3 / 2026 (V1.5)
- 多用户协作（PRD10 §24 P2）
- 移动端响应式 + PWA
- 邮箱验证码 + 二步验证真接通
- Stripe / 微信支付订阅门户

### Q4 / 2026 (V2)
- Skill 市场上线（开发者计划 / 评分 / 分成）
- 多 workspace 权限矩阵
- 实时协作（CRDT 文档编辑）
- 数字花园富图算法 (PRD10 §18 全量)

### 2027
- 海外市场（英文 / 日文 / 韩文）
- 企业版 OEM + 私有部署
- iOS / Android / 桌面客户端

---

## 8. 团队 (Why us)

> 详见 [README §👥 团队](../README.md#-团队)。

- **创始人**：连续创业者 / 全栈工程师 / 4 年 AI 产品经验
- **4 路 Agent 团队**（Cursor 多人协作）：Agent 1 协调 + 后端基础 / Agent 2 产品数据 + SPA / Agent 3 智能后端 / Agent 4 前端 E2E + 验收
- **6 个招募岗位**：详见 README

---

## 9. 投资额度 / 用途

### 当前轮次

- **金额**：¥500–1000 万 RMB
- **估值**：¥6000 万 pre-money
- **稀释**：8–14%

### 用途分配

| 项 | 比例 | 用途 |
|---|---:|---|
| 产品研发 | 40% | V1.5 / V2 功能 + 移动端 + Skill 市场 |
| 增长营销 | 30% | 内容营销 / 社群运营 / 创业者社区合作 |
| 销售 / BD | 20% | 团队版 / OEM 客户开发 |
| 团队扩张 | 10% | 招 6 人（前端 / 后端 / 算法 / 设计 / 运营 / 客服） |

---

## 10. 牵引指标 (Traction)

> 上线日起跟踪。

| 指标 | 当前 | Q3/2026 目标 | Q4/2026 目标 |
|---|---:|---:|---:|
| 注册用户 | 内测 N=12 | 5,000 | 30,000 |
| 付费用户 | — | 200 | 2,000 |
| MRR | — | ¥8 千 | ¥10 万 |
| AI 调用 / 周 | — | 20,000 | 200,000 |
| Skills 上架 | 5 (seed) | 30 | 100 |
| 留存（W4） | — | 35% | 50% |

---

## 11. FAQ / 常见投资人问题

详见 [`docs/demo-script.md`](demo-script.md) §FAQ — 11 条精选问答。

最常见 5 条：

1. **Notion 已经做了，你怎么差异化？** 中文优先 + AI 工作台 + 数字花园 + Skills 一站式，Notion 开放但无 AI 整理闭环。
2. **大模型涨价怎么办？** litellm 多 provider，DeepSeek/GLM/Claude/GPT 自动 failover，AI 调用 24h 缓存（§12.3 已实装）。
3. **数据隐私如何保证？** 私有部署 OEM；公开版用本地 SQLite/Postgres；GDPR 三端点（`/me/export` `/me` DELETE `/me/unsubscribe`）已实装。
4. **怎么验证真有市场？** N=120 用户调研 + 8 张投资材料截图 + 14 节真浏览器走查 + 真实 LLM 流式响应。
5. **国内政策风险？** 全栈合规：备案 + 合规 LLM 提供商 + 内容审核 + 用户数据本地化。

---

## 12. 关键链接

- 产品 demo：`https://demo.mydow.com/?go=demo`（公开演示）
- 投资材料：[`docs/assets/screenshots/01..08_*.png`](assets/screenshots/) 8 张 1920×1080 截图
- 演示视频脚本：[`docs/demo-video-script-90s.md`](demo-video-script-90s.md) 11 章 + SRT
- 演示走查脚本：[`docs/demo-script.md`](demo-script.md) 30s / 2min / 5min 三档
- 验收报告：[`docs/14.2-prd10-acceptance-checklist.md`](14.2-prd10-acceptance-checklist.md) 32 条
- API 文档：[`docs/11-deployment/api-reference.md`](11-deployment/api-reference.md) 13 章 600+ 行
- 部署：[`docs/11-deployment/docker.md`](11-deployment/docker.md) + [`docs/11-deployment/https.md`](11-deployment/https.md)
- 商业模式 / 路线图 / 团队：[`README.md`](../README.md)

---

> **联系方式**：见 [README §📬 联系我们](../README.md#-联系我们)。
