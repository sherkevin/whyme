# Mydow 云服务器部署 Runbook

> 目标：把当前 FastAPI + Postgres + Redis + nginx 的 Mydow 服务部署到一台普通云服务器上，先用最低运维成本完成可内测上线，后续再迁移到托管数据库、对象存储或 Kubernetes。

## 当前推荐

第一版推荐：**Ubuntu 24.04 LTS VPS + Docker Compose + nginx + Let's Encrypt**。

原因：

- 项目已经有 `Dockerfile.prd10` 和 `docker-compose.prd10.yml`，包含 app、Postgres、Redis、nginx、backup profile。
- 服务包含 SSE/streaming、上传文件卷、后台 worker、Postgres、Redis。单台 VPS 比拆到 Serverless/PaaS 更直接，也更容易排错和回滚。
- 当前还缺实际服务器、域名和生产密钥。VPS 方案的外部依赖最少，交接路径最清楚。

不建议第一版直接用 Vercel/Netlify 托管整个项目。它们更适合静态前端或 Serverless API，不适合作为当前这个有状态后端的完整运行环境。Render/Railway/Fly 可以作为备选，但要把 Postgres/Redis 改为托管服务，并把上传文件迁移到 S3/R2/OSS。

## 服务器规格

内测 50 人和早期公开访问建议：

- OS：Ubuntu 24.04 LTS。
- CPU / 内存：2 vCPU / 4 GB RAM 起步。
- 磁盘：40 GB SSD 起步，建议 80 GB。
- 防火墙：公网只开放 `22`、`80`、`443`。
- 地域：未备案优先香港、新加坡、美国；中国大陆服务器和域名访问需要 ICP 备案。

## 域名准备

1. 准备域名或子域名，例如 `app.example.com`。
2. 在 DNS 服务商添加 A 记录：

```text
Type: A
Name: app
Value: <VPS_PUBLIC_IP>
TTL: Auto
```

3. 等待 DNS 生效：

```bash
dig +short app.example.com
```

## 安装基础软件

登录服务器：

```bash
ssh root@<VPS_PUBLIC_IP>
```

安装 Docker Engine 和 Compose plugin。按 Docker 官方 Ubuntu 文档安装，不使用系统旧版 `docker.io`：

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
```

安装完成后验证：

```bash
docker --version
docker compose version
```

## 拉取项目

```bash
sudo mkdir -p /opt/mydow
sudo chown "$USER":"$USER" /opt/mydow
git clone <YOUR_REPO_URL> /opt/mydow
cd /opt/mydow
```

如果暂时用压缩包上传，也要保证目录结构与仓库根目录一致。

## 配置生产环境变量

```bash
cp .env.example .env
nano .env
```

至少修改这些项：

```bash
BASE_URL=https://app.example.com
CORS_ORIGINS=https://app.example.com
AGENTOS_CORS_ORIGINS=https://app.example.com
AGENTOS_CORS_ALLOW_ALL=false

ENVIRONMENT=production
AGENTOS_DEMO_MODE=off
AGENTOS_AI_LLM=on
AGENTOS_AI_OFFLINE_PLACEHOLDER=off

POSTGRES_USER=mydow
POSTGRES_DB=mydow_prd10
POSTGRES_PASSWORD=<strong-postgres-password>
REDIS_PASSWORD=<strong-redis-password>

SECRET_KEY=<strong-random-secret>
JWT_SECRET_KEY=<strong-random-secret>
DEEPSEEK_API_KEY=<real-key>
DEEPSEEK_API_BASE=https://api.deepseek.com
AGENTOS_LLM_DEFAULT_MODEL=mydow
AGENTOS_LLM_FALLBACK_MODEL=deepseek-v4-pro
```

生成强随机密钥：

```bash
python3 - <<'PY'
import secrets
for name in ["SECRET_KEY", "JWT_SECRET_KEY", "POSTGRES_PASSWORD", "REDIS_PASSWORD"]:
    print(f"{name}={secrets.token_urlsafe(48)}")
PY
```

可选但上线建议配置：

```bash
SENTRY_DSN=<sentry-dsn>
SMTP_HOST=<smtp-host>
SMTP_USER=<smtp-user>
SMTP_PASS=<smtp-pass>
SMTP_FROM=noreply@app.example.com
```

注意：

- 生产 `.env` 不要提交到 Git。
- `AGENTOS_DEMO_MODE` 必须为 `off`。
- `AGENTOS_AI_OFFLINE_PLACEHOLDER` 必须为 `off`，LLM 失败时要真实失败并暴露错误，不能生成占位数据。
- 如果启用邮箱验证码注册登录，SMTP 必须配好，否则注册链路无法发验证码。

## 预检

运行部署预检：

```bash
bash scripts/deploy/vps-preflight.sh .env
```

预检会检查：

- Docker Compose 是否可用。
- 必填 env 是否存在。
- 是否仍使用明显的示例密码、localhost 或 example.com。
- `AGENTOS_DEMO_MODE`、`AGENTOS_AI_OFFLINE_PLACEHOLDER`、`AGENTOS_CORS_ALLOW_ALL` 是否误开。
- compose 配置是否可渲染。
- app/Postgres/Redis/pgAdmin 是否默认只绑定到 `127.0.0.1`。

日志写入：

```text
.tmp/deploy/vps-preflight-<UTC>.log
```

交接要求：本地保留一份；服务器部署后也把同一份日志保存在服务器 `.tmp/deploy/` 目录，方便回查。

## 首次启动

```bash
docker compose --env-file .env -f docker-compose.prd10.yml --profile nginx up -d --build
docker compose --env-file .env -f docker-compose.prd10.yml ps
```

查看日志：

```bash
docker compose --env-file .env -f docker-compose.prd10.yml logs -f app
docker compose --env-file .env -f docker-compose.prd10.yml logs -f nginx
```

服务器内检查：

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
```

## HTTPS

现有 nginx 配置会在 `docker/nginx/ssl/fullchain.pem` 和 `docker/nginx/ssl/privkey.pem` 存在时启用 443。

简单做法是在宿主机使用 Certbot 申请证书，然后复制或软链接到项目目录：

```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone -d app.example.com

mkdir -p docker/nginx/ssl
sudo cp /etc/letsencrypt/live/app.example.com/fullchain.pem docker/nginx/ssl/fullchain.pem
sudo cp /etc/letsencrypt/live/app.example.com/privkey.pem docker/nginx/ssl/privkey.pem
sudo chown "$USER":"$USER" docker/nginx/ssl/*.pem

docker compose --env-file .env -f docker-compose.prd10.yml --profile nginx restart nginx
```

证书续期后要再次复制证书并重启 nginx。后续可以用 systemd timer 自动化。

## 公网验收

```bash
bash scripts/deploy/vps-smoke.sh https://app.example.com
```

如果是临时自签证书环境，可以显式允许跳过 TLS 校验：

```bash
CURL_INSECURE=1 bash scripts/deploy/vps-smoke.sh https://app.example.com
```

或手动：

```bash
curl -fsS https://app.example.com/health
curl -fsS https://app.example.com/ready
curl -fsSL https://app.example.com/mydow/ | head
```

浏览器访问：

```text
https://app.example.com/mydow/
```

至少手动走一遍：

- 注册 / 登录 / 记住登录态。
- 灵感采集。
- 网页剪藏。
- 文件上传。
- Mydow AI 对话和 RAG 背景选择。
- Skills 运行并生成文档。
- 知识库文档打开、收藏、移动、删除。
- 搜索、通知、个人设置。

## 备份

上线后立刻跑一次备份：

```bash
docker compose --env-file .env -f docker-compose.prd10.yml --profile backup run --rm backup
```

后续加 cron：

```cron
15 3 * * * cd /opt/mydow && docker compose --env-file .env -f docker-compose.prd10.yml --profile backup run --rm backup >> /opt/mydow/.tmp/deploy/backup-cron.log 2>&1
```

建议每月做一次恢复演练，流程见 `docs/11-deployment/backup.md`。

## 日常更新

```bash
cd /opt/mydow
git pull --ff-only
bash scripts/deploy/vps-preflight.sh .env
docker compose --env-file .env -f docker-compose.prd10.yml --profile nginx up -d --build
bash scripts/deploy/vps-smoke.sh https://app.example.com
```

## 回滚

如果刚刚的更新有问题：

```bash
git log --oneline -5
git checkout <last-good-commit>
docker compose --env-file .env -f docker-compose.prd10.yml --profile nginx up -d --build
bash scripts/deploy/vps-smoke.sh https://app.example.com
```

如果数据库也需要回滚，按 `docs/11-deployment/backup.md` 的 restore SOP 执行。生产库恢复前必须先备份当前库。

## 后续扩容路径

当单台 VPS 资源不足时，按这个顺序拆：

1. Postgres 迁移到托管数据库。
2. Redis 迁移到托管 Redis。
3. 上传文件迁移到 S3/R2/OSS。
4. app 多副本部署，nginx 或云负载均衡分发流量。
5. 再考虑 Fly/Render/Railway 或 Kubernetes。

## 当前仍被外部条件阻塞的事项

这些事项无法在本地仓库里替代完成：

- 真实 VPS 或云服务器账号。
- 公网 IP。
- 生产域名和 DNS 记录。
- 生产 `.env`，包括 `JWT_SECRET_KEY`、`POSTGRES_PASSWORD`、`REDIS_PASSWORD`、`DEEPSEEK_API_KEY`、SMTP、S3/R2/OSS 等。
- 是否部署在中国大陆，以及对应 ICP 备案策略。

具备这些条件后，§11.15 才能从 `blocked` 进入实际部署执行。

## 官方参考

- Docker Compose production: https://docs.docker.com/compose/how-tos/production/
- Docker Engine on Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Certbot: https://certbot.eff.org/
- Cloudflare DNS records: https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/
- Render Docker: https://render.com/docs/docker
- Railway data/storage: https://docs.railway.com/
- Fly.io launch: https://fly.io/docs/launch/
