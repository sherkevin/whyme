# 国内平台最快部署方案调研

> 调研日期：2026-05-17 (UTC+8)
>
> 目标：在用户尚未购买服务器和域名的前提下，选择一套“最简单、最快捷、最少改代码”的国内平台部署路径，并保证当前 Mydow / PRD10 的完整功能可以实际跑起来。

## 结论

推荐第一版使用：

```text
腾讯云轻量应用服务器 Lighthouse（中国香港地域）
+ Docker CE 应用模板 / Ubuntu 24.04 LTS
+ Docker Compose
+ 腾讯云域名注册 / DNSPod 解析
+ 服务器本机 nginx + Let's Encrypt 证书
```

如果必须选择中国大陆地域，则仍推荐腾讯云轻量应用服务器或 CVM，但必须先完成域名实名认证和 ICP 备案；这不是最快路径。

## 为什么选腾讯云香港轻量应用服务器

当前项目不是纯静态站点，也不是单一无状态 API。它至少包含：

- FastAPI 后端；
- Postgres；
- Redis；
- nginx；
- 上传文件持久化卷；
- 后台 worker；
- SSE / streaming；
- 生产环境必须关闭 demo / mock / offline placeholder。

因此第一版最稳妥的部署形态是完整 VPS + Docker Compose。它可以直接复用仓库里的 `docker-compose.prd10.yml`、`Dockerfile.prd10`、部署预检和 smoke 脚本，改造成本最低。

腾讯云轻量应用服务器的 Docker CE 应用模板已经面向容器化部署，官方文档说明该模板底层基于 Ubuntu Server 24.04 LTS，并预置 Docker 环境。腾讯云轻量应用服务器也提供 Docker 容器管理、端口、环境变量和目录挂载能力，适合当前单机多容器首发。

中国香港地域的关键好处是：仍然在腾讯云这个国内云平台体系内购买和运维，但网站解析到非中国境内服务器时不需要 ICP 备案，可以最快上线公网访问。腾讯云备案文档也明确，中国香港及境外云服务器无需备案，也不能用于备案。

## 不推荐作为第一版的方案

### 腾讯云 CloudBase Run

不作为第一版。官方文档明确 CloudBase Run 不支持 Docker Compose，而且实例本身应按无状态服务设计。当前项目需要 Postgres、Redis、uploads 持久卷和多容器编排，迁移到 CloudBase Run 会引入额外数据库、缓存、对象存储和服务拆分工作，反而不快。

### Serverless / 前端托管

Vercel、Netlify、静态托管、对象存储静态站点等都不适合直接托管当前完整系统。它们适合拆出静态前端或无状态 API，但不能原样承载当前完整后端状态与 Docker Compose 编排。

### Sealos / Rainbond 等平台

这些平台可以做容器应用编排，有些也支持从 Docker Compose 转换或导入，但第一版仍有额外平台学习、配置转换、持久化和排障成本。等 VPS 版本跑稳后，再评估是否迁移更合适。

### 阿里云 / 华为云轻量服务器

也可以作为备选。阿里云轻量应用服务器有 Docker 与 Docker Compose 相关官方教程，华为云 Flexus L 也有 Portainer / Docker 场景。但为了减少账号、域名、DNS、备案和云产品切换成本，本项目第一版更建议统一在腾讯云体系内：Lighthouse + DNSPod + 后续可选 COS。

## 购买建议

最小可用配置：

```text
地域：中国香港
产品：腾讯云轻量应用服务器 Lighthouse
镜像：Docker CE 应用模板，或 Ubuntu 24.04 LTS 后手动安装 Docker
CPU / 内存：2 核 / 4 GB 起步
系统盘：40 GB 起步
公网带宽：5 Mbps 起步
防火墙：只开放 TCP 22、80、443
```

更稳推荐配置：

```text
CPU / 内存：4 核 / 8 GB
系统盘：80 GB
公网带宽：10 Mbps
```

原因：当前服务包含 Python 构建、数据库、Redis、上传文件、AI 调用和后台任务。2C4G 可以跑早期内测；4C8G 在构建、并发、数据库缓存和排障时余量更舒服。

## 如果选择北京地域

用户 2026-05-17 提供的截图配置为：

```text
创建方式：使用容器镜像
Docker：26.1.3
系统：Ubuntu Server 22.04 LTS 64bit
地域：北京
```

这套配置作为服务器底座是可用的，但有两个注意点：

1. 北京属于中国境内地域。只要使用域名对外提供网站 / APP 服务，必须先完成 ICP 备案并取得备案号。通过轻量应用服务器备案时，腾讯云要求购买中国境内轻量应用服务器，计费模式为包年包月，购买包月 3 个月及以上，备案期间剩余有效期大于或等于 1 个月。
2. 购买页里的“添加容器”更接近控制台生成 `docker run`，适合单容器应用。当前项目需要 app、Postgres、Redis、nginx、worker、backup 等多容器协同，因此不建议在购买页直接添加容器；建议创建实例后通过 SSH 登录服务器，在仓库目录使用 `docker compose` 启动整套服务。

如果坚持用北京，推荐操作是：

```text
1. 保留 Docker 26.1.3 / Ubuntu 22.04 LTS 这类 Docker 基础环境。
2. 购买时不要添加容器。
3. 购买时长至少 3 个月，便于备案。
4. 防火墙只放开 TCP 22、80、443。
5. 完成域名实名认证和 ICP 备案后，再把域名 A 记录解析到北京服务器公网 IP。
6. Codex SSH 登录服务器后，用 docker compose 部署完整项目。
```

如果没有备案完成，北京服务器可以先做技术部署和 IP 级 smoke，但不应作为“马上公开给所有人通过域名访问”的最快方案。

## 域名建议

最简单路径：

1. 在腾讯云或 DNSPod 购买域名。
2. 完成域名实名认证。
3. 使用 DNSPod 解析。
4. 添加 A 记录：

```text
主机记录：app
记录类型：A
记录值：<腾讯云香港服务器公网 IP>
TTL：默认 / 自动
```

上线地址建议：

```text
https://app.<your-domain>/mydow/
```

如果还没想好域名，可以先用服务器公网 IP 做 HTTP smoke；但正式公开给用户访问、申请 HTTPS 证书和配置 CORS 时，建议尽快确定域名。

### 命名候选

用户 2026-05-17 要求为项目起域名。结合北京地域备案、腾讯云购买和当前产品名 Mydow，推荐：

```text
首选：maidaoai.com
保护：maidaoai.cn
产品中文名：麦岛 AI
产品英文名：Mydow
正式访问：app.maidaoai.com/mydow/
```

理由：

- `maidao` 对中文用户更好读，可以解释为“麦岛 / 迈道”，和个人知识岛、AI 工作台的定位相合。
- `maidaoai.com` 在 2026-05-17 的 Verisign `.com` RDAP 初查中返回 `not-found`，但最终可购买性仍以腾讯云域名购买页为准。
- `mydow.com` 已有注册记录，且注册方为 Dow Chemical；`mydow.cn` 也有 DNS / 历史痕迹，不建议作为主域名押注。
- 如果想保留 Mydow 字面品牌，可同时尝试购买 `mydowai.com` / `mydowai.cn`，作为跳转或备用域名。

备选排序：

```text
1. maidaoai.com / maidaoai.cn
2. mydowai.com / mydowai.cn
3. usemydow.com / usemydow.cn
4. mydowapp.com / mydowapp.cn
5. maidaotech.com / maidaotech.cn
```

备案优先建议：第一版只买 `.com` 和 `.cn`，不要优先选择 `.ai`、`.app` 等后缀，避免备案核验和国内用户记忆成本增加。

## 用户需要提供的信息

不要在聊天里直接发送主账号密码或服务器 root 密码。推荐使用 SSH key 或临时子账号。

需要用户提供或确认：

- 选择路线：`腾讯云香港快速上线`，还是 `中国大陆服务器 + ICP 备案`。
- 服务器公网 IP。
- SSH 用户名和端口，默认通常是 `root` + `22`。
- SSH key 接入方式：推荐由 Codex 生成公钥，用户把公钥添加到腾讯云服务器。
- 域名或子域名，例如 `app.example.com`；如果暂时没有域名，确认先用 IP 临时测试。
- DeepSeek API Key。
- SMTP 邮件配置；如果注册、验证码、通知邮件需要完整可用，这是生产必需项。
- 是否需要初始化管理员账号 / 内测账号。
- 是否要启用腾讯云 COS 做上传文件和备份的异地存储；第一版可以先用服务器本地卷 + 定时备份。

如需 Codex 代为在腾讯云控制台操作，需要创建最小权限临时子账号，不要提供主账号密码。

## Codex 部署执行步骤

服务器和域名准备好后，按以下流程执行：

1. SSH 登录服务器，创建 `/opt/mydow`。
2. 拉取仓库或上传代码包。
3. 写入生产 `.env`，确保：
   - `ENVIRONMENT=production`
   - `AGENTOS_DEMO_MODE=off`
   - `AGENTOS_AI_LLM=on`
   - `AGENTOS_AI_OFFLINE_PLACEHOLDER=off`
   - `AGENTOS_CORS_ALLOW_ALL=false`
   - `BASE_URL`、`CORS_ORIGINS` 指向真实域名
4. 运行预检：

```bash
bash scripts/deploy/vps-preflight.sh .env
```

5. 启动服务：

```bash
docker compose --env-file .env -f docker-compose.prd10.yml --profile nginx up -d --build
```

6. 配置 DNS 和 HTTPS。
7. 运行公网 smoke：

```bash
bash scripts/deploy/vps-smoke.sh https://app.example.com
```

8. 手工验证主功能：
   - 注册 / 登录；
   - 灵感采集；
   - 网页剪藏；
   - 文件上传；
   - AI 对话和 SSE 流式输出；
   - 知识库保存 / 搜索；
   - Skills 运行；
   - 通知和设置。
9. 配置每日数据库与上传文件备份。
10. 把部署日志、smoke 日志和剩余风险更新回 `todo-tasks.md`。

## 证据边界

截至本调研，代码侧已经具备 VPS + Docker Compose 部署底座和部署脚本，但公网部署仍然 blocked，因为缺少实际服务器、公网 IP、域名、生产密钥和用户对备案路线的选择。

## 调研来源

- 腾讯云轻量应用服务器 Docker CE 应用模板：https://cloud.tencent.com/document/product/1207/60423
- 腾讯云轻量应用服务器 Docker 容器管理：https://cloud.tencent.com.cn/document/product/1207/60329
- 腾讯云 CloudBase Run 部署限制：https://cloud.tencent.cn/document/product/1243/49235
- 腾讯云 CloudBase Run 服务开发说明：https://cloud.tencent.com/document/product/1243/53551
- 腾讯云 ICP 备案云资源：https://cloud.tencent.com/document/product/243/18908
- 腾讯云 ICP 备案常见问题 PDF：https://main.qcloudimg.com/raw/document/product/pdf/243_6206_cn.pdf
- 腾讯云 ICP 备案前准备 PDF：https://main.qcloudimg.com/raw/document/product/pdf/243_35819_cn.pdf
- DNSPod 文档中心：https://docs.dnspod.cn/
- DNSPod 实名认证通知：https://docs.dnspod.cn/account/auth-notice/
- 阿里云轻量应用服务器 Docker Compose 教程：https://www.alibabacloud.com/help/zh/doc-detail/2842479.html
- 华为云 Flexus L 实例产品文档：https://support.huaweicloud.com/productdesc-flexusl/pd_01_0002.html
