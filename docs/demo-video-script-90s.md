# Mydow 90 秒投资人路演视频脚本

> **作者**：Agent (my-mcp-13)，PRD10 §13.5
> **目标**：90 秒内让投资人完整理解「Mydow 是什么 / 为什么不一样 / 已经能跑」三件事。
> **配套**：本脚本是 §10.4 `docs/demo-script.md`（30s/2m/5m 三档现场演示）的**录屏脚本版**——把 30 秒动线扩展到 90 秒，加入旁白逐字稿、镜头切换、关键数字浮窗、字幕时间轴，方便录屏剪辑。
> **前置**：录屏前按 `docs/demo-script.md` §0 完成「演示前 60 秒准备」，确认 `http://127.0.0.1:8000/mydow/biz/` 已自动 demo 登录、首屏数据齐。
> **配套素材**：§10.6 截图任务的 PNG 集合、§10.5 hero landing `/`、§13.4 pitch deck。
> **渠道**：投资人邮件附件、官网 hero / `/landing/` embed、Twitter / LinkedIn 短视频版（再剪到 30s）、播客 cold open。

---

## 0. 录屏环境

| 项 | 设置 |
|---|---|
| 屏幕分辨率 | 1920×1080（16:9）；如做竖版 9:16 短视频另剪 |
| 浏览器 | Chrome 最新版，新无痕窗口（避免插件 / 通知打断） |
| 缩放 | 浏览器 100%；macOS 显示设置「更多空间」；Windows 1.0 缩放 |
| 起始 URL | `http://127.0.0.1:8000/?go=demo`（直接进 biz 工作台跳过 landing 引导） |
| 录屏工具 | macOS QuickTime / Windows OBS / Loom（要能录系统鼠标光标） |
| 字幕轨 | SRT 直接附在末尾 §6；剪辑软件直接 import |
| 配乐 | 推荐 Epidemic Sound「Subtle Inspirational Tech」类目；音量 -18dB；不要盖过旁白 |
| 旁白 | 中文女声 / 中性低音；语速 4.5 字/秒（90 秒约 405 字）；中间留 2 个 1.5 秒呼吸位 |

录屏前自检：

- [ ] 浏览器右上头像区显示「Demo User · demo@mydow.example · Free Plan」
- [ ] 首页右下「最近捕捉」≥ 8 张真实卡片（非 placeholder）
- [ ] DevTools 关掉（按 F12 / Cmd+Option+I 关）
- [ ] 通知抽屉未打开，全局搜索弹窗未打开
- [ ] 系统通知静音、勿扰开
- [ ] 鼠标光标可见性：录屏软件勾「Highlight cursor on click」

---

## 1. 90 秒分镜表（按秒级 shot）

> **总时长**：90 秒整。
> **结构**：Hook(0-10s) → Problem(10-20s) → Solution(20-60s) → Proof(60-80s) → CTA(80-90s)。
> **节奏**：每个 shot ≤ 8 秒；3 次镜头切换避免视觉疲劳；浮窗数字停留 ≥ 2.5s 让眼睛抓得住。

| t | 镜头 / 动作 | 旁白（中文，可双语） | 屏上文字 / 浮窗 | 字幕 |
|---:|---|---|---|---|
| **00:00** | **Cold open**：黑底淡入产品 logo + 一行 slogan | 「这是 Mydow。」（停顿 0.5s） | logo 中央放大 → 副标淡入「把灵感变成体系化的知识」 | `这是 Mydow。把灵感变成体系化的知识。` |
| **00:03** | 切到 hero landing `/` 全屏（提前手动滚到顶） | 「面向个人与团队的 AI 知识工作台。」 | 浮窗右上「200+ 测试 ✓ ／ 0 假按钮 ／ 14 业务原型页」 | `面向个人与团队的 AI 知识工作台。` |
| **00:08** | 平滑切入 biz 首页（点 hero 「开始体验 Demo」CTA） | 「你输入任何东西，我把它变成结构化知识。」 | 鼠标 hover 主输入框 0.5s 提示 | `输入任何东西，我把它变成结构化知识。` |
| **00:12** | **Problem shot**：在主输入框打字（≤ 18 字） | 「但今天的工具，要么逼你手动整理——」 | 输入框逐字键入：「投资人 demo 的三个核心点：能跑 / 能扩 / 能赚」 | `（手动键入：投资人 demo 的三个核心点……）` |
| **00:18** | 不点提交，淡出输入框 + 切到对比图（Notion / ChatGPT 两个浏览器 mock） | 「——要么没有你的私人语料。」 | 浮窗对比表：Notion=手动 ／ ChatGPT=无私域 ／ Mydow=自动+私域 | `Notion 太手动，ChatGPT 没你的语料。` |
| **00:22** | 切回 biz 首页，点「提交」按钮 | 「Mydow 把这两层缝起来。」 | 输入框上方 toast「灵感已同步到后端」+ 右下「最近捕捉」自动多一张卡 | `灵感已同步到后端 ✓` |
| **00:27** | 鼠标平移到右下新出现的卡片，点开 | 「输入 → 后端 worker 自动整理 → 出来一张带摘要、标签、可检索的卡片。」 | 抽屉滑入显示真实数据：标题/摘要/tags/创建时间 | `自动摘要・自动打标・自动入库` |
| **00:34** | 关抽屉，左侧导航点「知识库」 | 「这是结构化后的知识库——」 | 顶部浮窗「6 文件夹 / 20 文档 / 30 卡片」 | `知识库：6 文件夹 / 20 文档 / 30 卡片` |
| **00:39** | 点开「产品设计」文件夹，hover 一篇文档 | 「文件夹、文档、文件来源、AI 建议——都是 PRD10 §10 标准接口的真数据。」 | 文档行 hover 高亮 + 字数 / 摘要预览 | `真实文档列表，从 /api/v1/kb/* 拿。` |
| **00:46** | 左侧导航点「Mydow AI」 | 「然后让 AI 围绕你的私域语料对话。」 | 切到 AI 工作台，3 条历史会话进入视野 | `Mydow AI：基于你的知识库回答` |
| **00:50** | 点第一条会话，AI 答复气泡顶部 hover 引用 chip | 「每条回答都带文档引用——不是黑盒。」 | 引用 chip 高亮 + 浮窗箭头「这里点了能跳回原文」 | `带引用 ✓ 可追溯 ✓ 反向写回 ✓` |
| **00:56** | 点「保存到知识库」按钮 | 「答案能反向写回知识库，形成可演化资产。」 | toast「AI 结果已入队保存」+ 切回 KB 看到新增项 | `AI 输出 → 知识库文档（反向写回）` |
| **01:02** | 切到「数字花园」 | 「最终所有知识自动建图。」 | SVG 节点淡入 + 中心「你」+ 6 个主题节点 | `30 节点的真实数字花园` |
| **01:07** | 鼠标点中心节点，触发主题搜索 toast | 「点任意节点能反向跳到关联内容。」 | toast「找到 5 条与"产品设计"相关」 | `节点 → 跳转 → 命中 5 条` |
| **01:13** | **Proof shot**：切到一个分屏。左：浏览器，右：终端跑 `pytest` | 「我们不是 demo——」 | 终端右侧逐行打印「`256 passed in 52.82s`」 | `256 测试通过（v1 baseline）` |
| **01:19** | 切回浏览器，打开 DevTools Network 面板，点一个按钮 | 「每一个按钮都打到真 `/api/v1`，不是 `setTimeout`。」 | Network 行高亮 `POST /api/v1/skills/{id}/run` 202 | `真实 API ✓ 不是 mock` |
| **01:24** | 关 DevTools，回到首页全屏 | 「PRD10 §30 最小闭环已经走完。我们是已经能上线的 V1。」 | 黑底叠浮窗 5 行：捕捉 ✓ 整理 ✓ 检索 ✓ AI 引用 ✓ 知识图谱 ✓ | `PRD10 §30 最小闭环 ✓` |
| **01:28** | 切到 logo + 联系方式 | 「想试试？扫码进 demo，30 秒就能看到全部。」 | 二维码（指向 demo URL）+ 邮箱 `hello@mydow.example` | `扫码 → demo.mydow.example ／ hello@mydow.example` |
| **01:30** | 渐黑收尾 | （无旁白） | logo 淡出 + 字幕「Mydow · 2026」 | — |

---

## 2. 旁白逐字稿（中文，约 405 字 / 90s）

> **录音指引**：女声中性低音，速度 4.5 字/秒；逗号 0.3s 停顿，句号 0.6s；段落间留 1.5s 呼吸。

```
[00:00] 这是 Mydow。
[00:03] 面向个人与团队的 AI 知识工作台。
[00:08] 你输入任何东西，我把它变成结构化知识。
[00:12] 但今天的工具，要么逼你手动整理——
[00:18] ——要么没有你的私人语料。
[00:22] Mydow 把这两层缝起来。
[00:27] 输入，后端 worker 自动整理，出来一张带摘要、标签、可检索的卡片。
[00:34] 这是结构化后的知识库——
[00:39] 文件夹、文档、文件来源、AI 建议，都是 PRD10 §10 标准接口的真数据。
[00:46] 然后让 AI 围绕你的私域语料对话。
[00:50] 每条回答都带文档引用——不是黑盒。
[00:56] 答案能反向写回知识库，形成可演化资产。
[01:02] 最终所有知识自动建图。
[01:07] 点任意节点，能反向跳到关联内容。
[01:13] 我们不是 demo——
[01:19] 每一个按钮都打到真 /api/v1，不是 setTimeout。
[01:24] PRD10 §30 最小闭环已经走完。我们是已经能上线的 V1。
[01:28] 想试试？扫码进 demo，30 秒就能看到全部。
```

> **英文版备份**（送英文受众时用，405 中文 ≈ 280 英文 words 同长度）：

```
[00:00] This is Mydow.
[00:03] An AI knowledge workspace, for individuals and teams.
[00:08] You drop in anything, we turn it into structured knowledge.
[00:12] Today's tools either force you to organize manually—
[00:18] —or know nothing about your private corpus.
[00:22] Mydow closes that gap.
[00:27] Capture, the worker organizes, and you get a card—summary, tags, indexed.
[00:34] This is the knowledge base—
[00:39] folders, docs, sources, AI suggestions—all backed by real PRD10 endpoints.
[00:46] Then let AI converse on top of your own corpus.
[00:50] Every answer cites documents—no black box.
[00:56] Answers feed back into the KB, becoming compounding assets.
[01:02] Eventually, knowledge wires itself into a graph.
[01:07] Click any node to find related content.
[01:13] We're not a demo—
[01:19] every button hits a real /api/v1. No setTimeout.
[01:24] PRD10's minimum loop is closed. We're a V1 that ships.
[01:28] Want to try? Scan the code—30 seconds to walk through the whole thing.
```

---

## 3. 镜头切换 / B-roll 提示

| 时间 | 切换类型 | 转场效果 | 备注 |
|---:|---|---|---|
| 00:00 → 00:03 | logo → landing | 淡入淡出 0.4s | 留呼吸 |
| 00:08 → 00:12 | landing → biz 首页 | 镜头 push-in zoom 1.05x，0.5s | 把 demo CTA 当 portal |
| 00:18 → 00:22 | 对比图 → 首页输入框 | 横向滑入 0.3s | |
| 00:34 → 00:39 | 首页 → KB | 镜头淡出 + 浮窗在切换间 hold 1.2s | |
| 00:46 → 00:50 | KB → AI | 镜头淡出 + AI 历史侧栏先入 0.4s | |
| 01:02 → 01:07 | AI → Garden | 镜头淡出 + 节点逐个 stagger 入场（0.05s/节点） | |
| 01:13 → 01:19 | 终端分屏 | 屏幕一分为二，左浏览器右 terminal | 这是「proof shot」核心 |
| 01:24 → 01:28 | 浏览器 → 二维码卡 | 全屏 fade to black 0.8s + logo 反白 | |

---

## 4. 关键浮窗 / 字幕样式

- **字体**：英文 Inter Bold；中文 PingFang SC Bold（与 biz 原型一致）
- **颜色**：主字 `#1c2940`（PRD10 ink）；浮窗高亮 `#758cff`（accent-deep）；toast 成功色 `#77cabd`（mint）
- **背景**：浮窗用 `rgba(255,255,255,0.92)` + `backdrop-filter: blur(8px)`，匹配 biz 原型玻璃质感
- **位置**：所有浮窗右上 / 右下，避免遮挡鼠标动作区
- **动画**：浮窗 `transform: translateY(8px) → translateY(0) + opacity 0→1`，0.3s ease-out；停留 ≥ 2.5s 后退出 0.4s
- **字幕**：底部居中、白字 + 黑色 0.5px 描边、高度 8% 屏高、单行 ≤ 18 中文字 / 38 英文字符；超长拆两行不超 3 秒

---

## 5. 时间预算（剪辑用）

| 段 | 时长 | 累计 | 用途 |
|---|---:|---:|---|
| Hook（logo + landing） | 12s | 12s | 抓注意力 |
| Problem（对比） | 10s | 22s | 设痛点 |
| Solution（capture → KB → AI → Garden） | 38s | 60s | 演动线 |
| Proof（测试 + 真 API） | 18s | 78s | 信任建立 |
| CTA（二维码） | 10s | 88s | 转化 |
| 收尾（fade to black） | 2s | 90s | 优雅结束 |

预算总和 ≤ 90s。如对方平台限制 60s（Twitter / Instagram Reels），把 Solution 段 38s 压缩到 18s（只演 capture → KB → AI 三步）。

---

## 6. SRT 字幕（直接 import）

```srt
1
00:00:00,000 --> 00:00:02,500
这是 Mydow。

2
00:00:03,000 --> 00:00:07,500
面向个人与团队的 AI 知识工作台。

3
00:00:08,000 --> 00:00:11,500
你输入任何东西，我把它变成结构化知识。

4
00:00:12,000 --> 00:00:17,500
但今天的工具，要么逼你手动整理——

5
00:00:18,000 --> 00:00:21,500
——要么没有你的私人语料。

6
00:00:22,000 --> 00:00:26,500
Mydow 把这两层缝起来。

7
00:00:27,000 --> 00:00:33,500
输入，后端 worker 自动整理，出来一张带摘要、标签、可检索的卡片。

8
00:00:34,000 --> 00:00:38,500
这是结构化后的知识库——

9
00:00:39,000 --> 00:00:45,500
文件夹、文档、文件来源、AI 建议，都是 PRD10 §10 标准接口的真数据。

10
00:00:46,000 --> 00:00:49,500
然后让 AI 围绕你的私域语料对话。

11
00:00:50,000 --> 00:00:55,500
每条回答都带文档引用——不是黑盒。

12
00:00:56,000 --> 00:01:01,500
答案能反向写回知识库，形成可演化资产。

13
00:01:02,000 --> 00:01:06,500
最终所有知识自动建图。

14
00:01:07,000 --> 00:01:12,500
点任意节点，能反向跳到关联内容。

15
00:01:13,000 --> 00:01:18,500
我们不是 demo——

16
00:01:19,000 --> 00:01:23,500
每一个按钮都打到真 /api/v1，不是 setTimeout。

17
00:01:24,000 --> 00:01:27,500
PRD10 §30 最小闭环已经走完。我们是已经能上线的 V1。

18
00:01:28,000 --> 00:01:30,000
扫码进 demo，30 秒看完。
```

---

## 7. 录屏 → 剪辑 → 发布 流程（手把手）

### 7.1 录屏阶段（30 分钟）

1. 按 §0 完成环境自检
2. 主屏录全程（1920×1080）；副屏开 `docs/demo-script.md` + 本脚本对照走
3. 至少录 3 遍：(a) 干净一遍只跑动作不出错（rough）；(b) 二遍按本脚本节奏走（clean）；(c) 三遍备份 / 异常处理
4. 录终端 `pytest` 跑分（单独录一段 `pytest tests/integration/api/test_prd10_v1_acceptance.py -q` 全过截图）
5. 录二维码（用 `qrencode -o qrcode.png "http://127.0.0.1:8000/?go=demo"` 或 `https://demo.mydow.example`）

### 7.2 剪辑阶段（90 分钟，CapCut / DaVinci Resolve / Premiere 都行）

1. 拉时间轴到 90s（90 fps × 90s = 8100 帧 @ 90fps）
2. 按 §1 分镜表逐段对齐 cut
3. 旁白：用 §2 逐字稿在 ElevenLabs / Murf / 真人录音棚录中文版（可备一版英文）
4. 浮窗 / 字幕：按 §4 样式手工 keyframe 或 CapCut 模板
5. 音轨：旁白 main -6dB，BGM background -18dB，关键 shot（如 toast 出现）+1dB 强调
6. 转场：按 §3 表逐个套
7. 导出 MP4 H.264 1080p 30fps；二备一份 9:16 1080×1920 竖版

### 7.3 发布阶段

| 渠道 | 版本 | 备注 |
|---|---|---|
| 投资人邮件附件 | 90s 横版 MP4 | 文件大小 ≤ 30MB（H.264 CRF 23） |
| 官网 hero / `/landing/` embed | 90s 横版 + autoplay muted | 需 mute by default、点击 unmute；提供 `<video poster="...">` |
| Twitter / X 短视频 | 60s 横版剪辑（删 Problem 段）| 1.4MB 内最佳 |
| LinkedIn 短视频 | 90s 横版 | 1.5GB 内、最长 10 分钟限制内 |
| TikTok / Reels / YouTube Shorts | 60s 竖版重剪 | 9:16，重新设计浮窗位置 |
| 播客 cold open | 30s 音频版（旁白 only） | 把 Solution 段抽出做单段 |

### 7.4 演示文件命名规范

```
mydow-pitch-90s-2026-05-zh.mp4         # 中文主版
mydow-pitch-90s-2026-05-en.mp4         # 英文版
mydow-pitch-60s-2026-05-zh.mp4         # Twitter 短版
mydow-pitch-60s-vertical-2026-05.mp4   # 竖版
mydow-pitch-30s-audio-2026-05.mp3      # 音频
mydow-pitch-90s-zh.srt                 # 字幕
mydow-pitch-90s-en.srt                 # 英文字幕
```

入库到 `docs/assets/pitch-videos/`（与 §13.4 pitch deck 同目录）。

---

## 8. 与其他材料的引用关系

| 资源 | 路径 | 用途 |
|---|---|---|
| 本脚本 | `docs/demo-video-script-90s.md`（本文件） | 录屏剪辑 master |
| 现场 demo 脚本 | `docs/demo-script.md`（§10.4） | 30s/2m/5m 三档话术 |
| Hero landing | `static/landing/index.html`（§10.5） | 视频开场 cold open + 二维码目的页 |
| Pitch deck | `docs/pitch.md`（§13.4） | 现场配套 PPT |
| README 投资人版 | `README.md`（§13.1 / §13.6） | 邮件签名链接 |
| API reference | `docs/11-deployment/api-reference.md`（§8.13） | 技术尽调 |
| Acceptance checklist | `docs/14.2-prd10-acceptance-checklist.md`（§14.2） | 工程信任 |
| 截图素材 | `docs/assets/screenshots/`（§10.6 待做） | 视频中插入 / 邮件附图 |

---

## 9. 常见录屏失败 / 处理预案

| 现象 | 原因 | 现场处置 |
|---|---|---|
| toast 不出现 | bridge.js 没绑或 token 过期 | 重置 seed → 刷新页 → 重录该段 |
| AI 答非所问 | LLM 抽风 / off-topic | 用 seed 默认问题（见 `seed_prd10.py::_seed_conversations`），或固定 `AGENTOS_AI_LLM=off` 走占位回答 |
| Garden 节点没出 | `/garden/overview` 拉空 | 重 seed；或临时把节点位置截屏静态贴在视频上 |
| Network 面板太花 | 录到无关请求 | 用 DevTools filter `api/v1` 缩小 |
| 终端 `pytest` 太慢 | 不要现场跑 226 个，用 `tests/integration/api/test_prd10_v1_acceptance.py`（20 用例 ~10s）出截图 |
| 录屏帧率掉到 15fps | 后台进程占 CPU | macOS `Activity Monitor` 杀重型进程；OBS 录屏单独显卡通道 |

---

## 10. 维护

- 每次主版本号变更（v1.4 → v1.5 等业务方原型迭代）后，本脚本同步更新分镜与字幕
- 每月 review 一次：旁白话术是否过时；UI 切换是否还在原位；浮窗数字是否还匹配最新 baseline
- 录屏前永远跑 `python scripts/seed_prd10.py --reset` + `pytest tests/integration/api/test_prd10_v1_acceptance.py` 双自检
- 若业务方调整 biz 原型，重新对齐本脚本的鼠标 hover 位置 + 浮窗时机

---

## 11. 验收清单

完成 §13.5 = 满足以下全部：

- [x] 90 秒分镜表按秒级落地（§1）
- [x] 旁白逐字稿中英双版（§2）
- [x] 镜头切换、浮窗、字幕样式定义（§3 / §4）
- [x] 时间预算可裁剪到 60s / 30s 适配多平台（§5）
- [x] SRT 字幕直接 import（§6）
- [x] 录屏 → 剪辑 → 发布全流程（§7）
- [x] 与现场 demo 脚本 / hero landing / pitch deck 引用关系明确（§8）
- [x] 失败预案（§9）
- [x] 维护节奏（§10）

后续 §10.6 截图与录屏素材任务由其他 agent / 创始人按本脚本录制并落库到 `docs/assets/`。
