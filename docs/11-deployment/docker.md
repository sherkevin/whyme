# Docker 一键部署（PRD10 V1）

> **任务来源**：`todo-tasks.md` 11.1（Owner: Agent 3 @ 2026-05-05）。
>
> 本文档面向：投资人 demo 环境运维 / 客户私有化部署 / 临时压测。

## 文件清单

| 文件 | 用途 |
|---|---|
| `Dockerfile.prd10` | 应用镜像（FastAPI + 静态前端） |
| `docker-compose.prd10.yml` | 一键栈：app + Postgres + Redis + nginx + pgadmin |
| `docker/nginx/mydow.conf` | nginx 反代配置 |
| `.env.example` | 环境变量模板（参考 [`env-vars.md`](env-vars.md)） |

## 5 分钟最速部署

### 1. 准备 `.env`

```powershell
cp .env.example .env

# 必改三项（命令生成 secret）：
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
# 把上面输出粘贴到 .env

# 可选：启用真 LLM
# 在 .env 里设：
#   AGENTOS_AI_LLM=on
#   DEEPSEEK_API_KEY=<你的 key>
```

### 2. 启动栈

```bash
# 不带 nginx（直连 8000）
docker compose -f docker-compose.prd10.yml up -d

# 带 nginx（走 :80）
docker compose -f docker-compose.prd10.yml --profile nginx up -d

# 带 pgAdmin
docker compose -f docker-compose.prd10.yml --profile pgadmin up -d
```

### 3. seed demo 数据

```bash
docker compose -f docker-compose.prd10.yml exec app \
  python scripts/seed_prd10.py --email demo@mydow.example --password demo123 --reset
```

### 4. 访问

- 直连 FastAPI： http://localhost:8000/mydow/
- 走 nginx：http://localhost/mydow/
- API 文档（Swagger）：http://localhost:8000/docs
- pgAdmin（如果起了）：http://localhost:5050

### 5. 检查健康

```bash
curl http://localhost:8000/health
docker compose -f docker-compose.prd10.yml ps
docker compose -f docker-compose.prd10.yml logs app | tail -50
```

期待：`app` 服务状态 `healthy`，日志看到 `[prd10-worker] running`。

## 生产域名与 `/mydow/` 入口（Acceptance Gate §14.9）

目标：执行 `docker compose -f docker-compose.prd10.yml --profile nginx up -d` 并完成 TLS（见下文与 [`https.md`](https.md)）后，在公网 HTTPS 上可以打开 Mydow 业务壳。验收 URL 常以 `https://demo.example.com/mydow/` 表示（把域名换成你的真实 FQDN）。

### 必配 `.env`

| 变量 | 示例 | 说明 |
|---|---|---|
| `BASE_URL` | `https://demo.example.com` | 邮件链接、上传回调、服务端生成绝对 URL |
| `CORS_ORIGINS` | `https://demo.example.com` | 生产环境逗号分隔白名单，须含浏览器实际 origin |

### DNS 与证书

1. 将 `demo.example.com` 的 A/AAAA 指到宿主机或负载均衡。
2. 将 `fullchain.pem` / `privkey.pem` 放入 `docker/nginx/ssl/`；`docker/nginx/entrypoint.sh` 会检测证书并启用 `:443`（无证书时仅 HTTP `:80`，便于本地联调）。
3. 完整步骤、HSTS 与自检 curl 清单见 **[`docs/11-deployment/https.md`](https.md)**。

### 本地用 hosts 模拟（可选）

在开发机 hosts 中加一行 `127.0.0.1 demo.example.com`，再用同一套 compose 栈自测 TLS 或 HTTP。

### 验收命令（TLS 就绪后）

```bash
curl -fsS -o /dev/null -w "%{http_code}\n" https://demo.example.com/mydow/
# 期望：200 或 3xx（与 app 默认入口重定向策略一致，如 307 → /mydow/biz/）

curl -fsS -o /dev/null -w "%{http_code}\n" https://demo.example.com/health
# 期望：200
```

**路由说明**：`docker/nginx/locations.conf.inc` 中 `location /` 与 `^/(mydow|static)/` 相关块均 `proxy_pass` 到 `upstream mydow_app`（`app:8000`），因此 `/mydow/`、`/api/v1/*` 同源经 nginx 终结 TLS 后即可完整联调。

## 服务架构

```
                                  ┌──────────┐
                                  │  浏览器  │
                                  └─────┬────┘
                                        │ :80 (nginx) / :8000 (直连)
                                        ▼
                            ┌───────────────────────┐
                            │   nginx (可选)        │
                            │   docker/nginx/       │
                            │   mydow.conf          │
                            │   - SSE 不 buffer    │
                            │   - 静态资源长缓存   │
                            └───────────┬───────────┘
                                        │ proxy_pass
                                        ▼
   ┌──────────────────────────────────────────────────────┐
   │              app  (mydow-app:prd10)                  │
   │              FastAPI + 静态前端                       │
   │              - PRD10 §6 envelope                     │
   │              - PRD10 §16 Job worker                  │
   │              - SSE: notifications + AI streaming     │
   └────┬─────────────────────┬───────────────────────────┘
        │                     │
        ▼                     ▼
   ┌─────────┐          ┌─────────┐
   │postgres │          │ redis   │
   │  16     │          │  7      │
   │         │          │         │
   │ 数据   │          │ - 限流  │
   │ 持久化 │          │ - SSE   │
   │ volume │          │   pubsub│
   └─────────┘          │ - 邮件  │
                        │   验证码│
                        └─────────┘
```

## 端口占用

| 服务 | 端口 | 备注 |
|---|---|---|
| `app` | 8000 | FastAPI 直连 |
| `nginx` | 80 / 443 | 仅 `--profile nginx` |
| `postgres` | 5432 | 可改 `POSTGRES_PORT` |
| `redis` | 6379 | 可改 `REDIS_PORT` |
| `pgadmin` | 5050 | 仅 `--profile pgadmin` |

## 持久化卷

| Volume | 用途 |
|---|---|
| `postgres-data` | DB 数据 |
| `redis-data` | Redis AOF |
| `app-uploads` | 用户上传文件（`PRD10_UPLOADS_BASE`） |
| `app-sqlite` | SQLite fallback（如果 `DATABASE_URL` 切到 sqlite） |
| `app-logs` | 应用日志 |
| `nginx-logs` | nginx 访问 / 错误日志 |
| `pgadmin-data` | pgAdmin 配置 |

## 常用运维命令

```bash
# 查看实时日志
docker compose -f docker-compose.prd10.yml logs -f app

# 重启 app（保持 DB / Redis 不动）
docker compose -f docker-compose.prd10.yml restart app

# 进 app 容器
docker compose -f docker-compose.prd10.yml exec app bash

# 跑数据库 migration（如果用 alembic）
docker compose -f docker-compose.prd10.yml exec app alembic upgrade head

# 备份 DB
docker compose -f docker-compose.prd10.yml exec -T postgres \
  pg_dump -U agentos agentos_db | gzip > backup-$(date +%F).sql.gz

# 恢复 DB
gunzip -c backup-2026-05-05.sql.gz | \
  docker compose -f docker-compose.prd10.yml exec -T postgres \
  psql -U agentos agentos_db

# 清空全部数据并重启（谨慎！）
docker compose -f docker-compose.prd10.yml down -v
docker compose -f docker-compose.prd10.yml up -d
```

## HTTPS 配置（生产必做）

仓库已内置 **:80 + :443 双 server**（`docker/nginx/mydow.conf`）与 **无证书时自动退化为 HTTP-only**（`docker/nginx/entrypoint.sh`）。生产环境只需：

1. 把证书放到 `docker/nginx/ssl/fullchain.pem` 与 `docker/nginx/ssl/privkey.pem`。
2. `docker compose -f docker-compose.prd10.yml --profile nginx up -d`（或 `restart nginx`）。
3. 按 **[`docs/11-deployment/https.md`](https.md)** 完成 Let's Encrypt / 商业证书、`certbot renew`、以及上线前自检清单。

不推荐再手工「取消注释」HTTPS 块：`mydow.conf` 已默认携带 TLS server；缺的只是证书文件挂载。

## 升级版本

```bash
# 拉新代码
git pull

# 重新构建 + 滚动更新
docker compose -f docker-compose.prd10.yml build app
docker compose -f docker-compose.prd10.yml up -d app

# 数据库 schema 变更（如果有 alembic 迁移）
docker compose -f docker-compose.prd10.yml exec app alembic upgrade head
```

## 故障排查

| 症状 | 排查 |
|---|---|
| `app` 起不来 | `docker compose logs app` 看启动错误；最常见是 `SECRET_KEY` / `JWT_SECRET_KEY` 没填 |
| `/api/v1/auth/send-code` 返回 503 | Redis 没连上；检查 `REDIS_PASSWORD` 是否一致 |
| AI 回答还是 placeholder | 没设 `AGENTOS_AI_LLM=on` 或 `DEEPSEEK_API_KEY` 没填 |
| `seed_prd10.py` 失败 | DB 还没起好；等 30s 再跑；或先 `docker compose ps` 确认 postgres healthy |
| SSE 实时推送不工作 | 走了 nginx 但 nginx 配置没 `proxy_buffering off`；用 `mydow.conf` 提供的版本 |
| 上传大文件 413 | 改 `mydow.conf` 的 `client_max_body_size` |

## 健康检查清单（部署后必跑）

- [ ] `curl http://localhost:8000/health` → 200
- [ ] `curl http://localhost:8000/api/v1/today` → 401（说明 auth 工作）
- [ ] `docker compose -f docker-compose.prd10.yml ps` → 全部 `healthy`
- [ ] `docker compose logs app | grep prd10-worker` → 看到 worker 启动行
- [ ] AGENTOS_AI_LLM=on 时：调一次 AI conversation/messages → 不返回 placeholder
- [ ] AGENTOS_DEMO_MODE=on 时：`POST /api/v1/demo/login` → 200 + token

发现偏差 → 在 `todo-tasks.md` §11 加 `open` 任务，附 reproducer。

## 与旧 docker-compose.yml 的关系

仓库里还有一个旧 `docker-compose.yml`（指向 `Dockerfile`，是 Ubuntu 沙箱镜像，**不是**应用镜像），保留作为历史参考。

PRD10 V1 部署一律用 `docker-compose.prd10.yml`。
