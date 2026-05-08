# Mydow HTTPS / 反向代理部署指南

> PRD10 §11.3 / todo-tasks.md §11.3
>
> 本文覆盖：nginx 反代架构、HTTPS 证书获取（Let's Encrypt 自动 + 手动 + 自签）、部署步骤、安全头矩阵、cache 策略、SSE/WebSocket 兼容、限流配置、上线前自检清单。

---

## 1. 架构

```text
┌──────────┐  80/443    ┌────────────────┐  8000   ┌────────────┐
│  Client  │ ─────────► │  nginx (proxy) │ ─────► │  uvicorn   │
│ (browser)│            │  mydow.conf    │         │  app:8000  │
└──────────┘            └────────────────┘         └────────────┘
                                │
                                ├── HTTP server (port 80)
                                │     ├── ACME challenge passthrough
                                │     └── 301 → HTTPS（如证书可用）
                                │
                                └── HTTPS server (port 443)
                                      ├── TLS 1.2 + 1.3
                                      ├── HSTS / CSP / 安全头
                                      ├── 静态资源 immutable cache
                                      ├── SSE 不 buffer
                                      └── 限流 auth/AI/search
```

**关键文件**：

| 文件 | 用途 |
|---|---|
| `docker/nginx/mydow.conf` | server 块（:80 + :443） |
| `docker/nginx/locations.conf.inc` | 共享 location 块（HTTP/HTTPS 都引） |
| `docker/nginx/entrypoint.sh` | 启动时检测证书；无证书自动禁用 :443 |
| `docker/nginx/ssl/fullchain.pem` | 证书链（部署时挂载） |
| `docker/nginx/ssl/privkey.pem` | 私钥（部署时挂载） |

---

## 2. 三种证书获取方式

### 2.1 Let's Encrypt（推荐：免费、自动续期）

适用：拥有公网域名 + 服务器对外可达 80/443。

```bash
# 一次性签发（webroot 模式，不会中断 nginx）
docker run --rm \
  -v "$(pwd)/docker/nginx/ssl:/etc/letsencrypt" \
  -v mydow-prd10_nginx-acme:/var/www/certbot \
  certbot/certbot:latest \
  certonly --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@example.com \
    --agree-tos --no-eff-email \
    -d demo.mydow.example

# 续期（90 天有效，建议每天 cron）
docker run --rm \
  -v "$(pwd)/docker/nginx/ssl:/etc/letsencrypt" \
  -v mydow-prd10_nginx-acme:/var/www/certbot \
  certbot/certbot:latest renew --quiet

# 重启 nginx 让新证书生效
docker compose -f docker-compose.prd10.yml --profile nginx restart nginx
```

**自动续期（systemd timer 示例）** `/etc/systemd/system/certbot-renew.timer`：

```ini
[Unit]
Description=Mydow certbot renew (twice daily)
[Timer]
OnCalendar=*-*-* 02,14:00:00
RandomizedDelaySec=2h
Persistent=true
[Install]
WantedBy=timers.target
```

`/etc/systemd/system/certbot-renew.service`：

```ini
[Unit]
Description=Renew Mydow Let's Encrypt certs
[Service]
Type=oneshot
WorkingDirectory=/opt/mydow
ExecStart=/usr/bin/docker compose -f docker-compose.prd10.yml exec -T nginx \
    certbot renew --webroot --webroot-path=/var/www/certbot --quiet
ExecStartPost=/usr/bin/docker compose -f docker-compose.prd10.yml --profile nginx restart nginx
```

### 2.2 手动放置已有证书

适用：公司证书、付费证书、内网 CA。

```bash
# 把证书复制到挂载目录
cp /path/to/your/fullchain.pem docker/nginx/ssl/fullchain.pem
cp /path/to/your/privkey.pem   docker/nginx/ssl/privkey.pem
chmod 600 docker/nginx/ssl/privkey.pem

# 重启 nginx
docker compose -f docker-compose.prd10.yml --profile nginx restart nginx
```

### 2.3 自签证书（仅本地开发）

适用：本机开发联调 HTTPS、内部演示。**生产不可用**。

```bash
mkdir -p docker/nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/nginx/ssl/privkey.pem \
  -out    docker/nginx/ssl/fullchain.pem \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:demo.mydow.local,IP:127.0.0.1"

docker compose -f docker-compose.prd10.yml --profile nginx restart nginx
```

> 浏览器会显示「不安全」警告——首次访问时点「高级 → 继续」即可。

---

## 3. 部署步骤（一键）

### 3.1 首次部署（无证书 / dev）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env：至少改 SECRET_KEY / JWT_SECRET_KEY

# 2. 启动 app + postgres + redis（不带 nginx）
docker compose -f docker-compose.prd10.yml up -d

# 3. 直连测试
curl http://localhost:8000/health
```

### 3.2 生产部署（带 HTTPS）

```bash
# 1. 配置环境
cp .env.example .env
# 编辑 .env：填 BASE_URL=https://demo.mydow.example
#                CORS_ORIGINS=https://demo.mydow.example

# 2. 拉证书（见 §2.1 / §2.2）
docker run --rm \
  -v "$(pwd)/docker/nginx/ssl:/etc/letsencrypt" \
  -v mydow-prd10_nginx-acme:/var/www/certbot \
  certbot/certbot:latest \
  certonly --webroot --webroot-path=/var/www/certbot \
    --email admin@example.com --agree-tos --no-eff-email \
    -d demo.mydow.example

# 3. 启动全栈（带 nginx）
docker compose -f docker-compose.prd10.yml --profile nginx up -d

# 4. seed demo 数据
docker compose -f docker-compose.prd10.yml exec app \
  python scripts/seed_prd10.py --reset

# 5. 浏览器验证
curl -I https://demo.mydow.example/health
curl -I http://demo.mydow.example/  # 应返回 301 → https://...
```

---

## 4. 安全头矩阵

| Header | 值 | 作用 |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | 强制 HTTPS（仅 :443） |
| `X-Content-Type-Options` | `nosniff` | 禁 MIME 嗅探 |
| `X-Frame-Options` | `SAMEORIGIN` | 点击劫持防护 |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | 跨站只发 origin |
| `Permissions-Policy` | `camera=(), microphone=(self), geolocation=(), interest-cohort=()` | 关闭不需要的浏览器特性 |
| `Cross-Origin-Opener-Policy` | `same-origin` | 跨源隔离 |
| `Cross-Origin-Resource-Policy` | `same-origin` | 跨源隔离 |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'; ...` | 内容来源限制 |

> **HSTS 上线注意**：第一次启用 HTTPS 时**先把 max-age 设小**（如 300 秒）确认证书没问题，再升到 1 年 + `preload`。

---

## 5. Cache 策略

| 路径模式 | Cache-Control | 理由 |
|---|---|---|
| `/(mydow\|static)/*.{js,css,png,...}`（hashed 文件名） | `public, max-age=31536000, immutable` | 1 年长缓存；新版本走新 hash |
| `/(mydow\|static)/*.{js,css,...}`（无 hash） | `public, max-age=2592000, must-revalidate` | 30 天 + revalidate |
| `*.html` / `*.json` | `no-store, no-cache, must-revalidate` | demo 期 HTML 不缓存 |
| 其他 API | 默认（不加 Cache-Control） | 应用自行决定 |

---

## 6. SSE / WebSocket 兼容

PRD10 §11 / §15 用 SSE 做 AI streaming + 通知 push。nginx 默认会缓冲流，破坏 SSE 体验。`locations.conf.inc` 已对以下路径明确关闭 buffering：

- `/api/v1/notifications/stream`
- `/api/v1/ai/conversations/{id}/messages/stream`
- `/api/v1/ai/messages/{id}/stream`

关键设置：
- `proxy_buffering off`
- `proxy_cache off`
- `proxy_read_timeout 24h`（SSE 长连接）
- `chunked_transfer_encoding on`
- `add_header X-Accel-Buffering "no" always`

WebSocket 路径（`/ws`、`/api/sessions/{id}/ws`）走 `proxy_set_header Upgrade $http_upgrade; Connection "upgrade";`。

---

## 7. 限流（基础层）

`mydow.conf` 在反代层做粗粒度限流，作为应用层限流（PRD10 §12.2，TODO §11.5）的辅助保险：

| 路径 | zone | rate | burst |
|---|---|---|---|
| `/api/v1/auth/login` `/api/v1/auth/register` `/api/v1/demo/login` | `auth_zone` | 10 req/min | 5 |
| `/api/v1/ai/conversations/{id}/messages(/stream)?` | `ai_zone` | 30 req/min | 10 |
| `/api/v1/search` 系列 | `search_zone` | 120 req/min | 30 |

超限返回 429。

> 演示场景下阈值偏宽松（防止现场翻车）；上线后应根据真实流量收紧。

---

## 8. 上线前自检清单

```bash
# 1. nginx 配置语法
docker compose -f docker-compose.prd10.yml --profile nginx exec nginx nginx -t

# 2. HTTP → HTTPS 跳转
curl -I http://demo.mydow.example/
# 期望：HTTP/1.1 301 Moved Permanently
#        Location: https://demo.mydow.example/

# 3. HTTPS 证书 + TLS 协议
curl -I https://demo.mydow.example/
# 期望：HTTP/2 200
#        strict-transport-security: max-age=31536000; ...
echo | openssl s_client -connect demo.mydow.example:443 -servername demo.mydow.example 2>/dev/null \
  | openssl x509 -noout -dates -issuer
# 期望：Issuer 包含 "Let's Encrypt"

# 4. 安全头
curl -sI https://demo.mydow.example/mydow/biz/ | grep -E "(Strict-Transport|X-Frame|Content-Security|Permissions-Policy)"

# 5. 静态资源 immutable cache（带 hash 文件名）
curl -sI https://demo.mydow.example/mydow/biz/bridge.abc1234.js | grep -i cache-control
# 期望：cache-control: public, max-age=31536000, immutable

# 6. SSE 不 buffer
curl -N -H "Authorization: Bearer $TOKEN" \
  https://demo.mydow.example/api/v1/notifications/stream
# 期望：每 25s 一行 `event: ping`；不在等到完成才一次性看到

# 7. 健康检查
curl https://demo.mydow.example/health
# 期望：{"status":"healthy",...}
curl https://demo.mydow.example/ready
# 期望：{"status":"ready",...}（DB 连通）

# 8. 限流（敲 30 次 login，应该开始 429）
for i in {1..30}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://demo.mydow.example/api/v1/auth/login \
    -d '{"email":"x@x.com","password":"x"}'
done
# 期望：前 10 个 200/401，之后开始出 429
```

---

## 9. 故障排查

| 现象 | 排查 |
|---|---|
| nginx 起不来 + log 报 "cannot load certificate" | 没放证书或路径错。检查 `docker/nginx/ssl/{fullchain,privkey}.pem`。entrypoint.sh 应自动禁用 :443，如果没生效查 nginx 容器日志 `docker logs mydow-nginx` |
| HTTPS 访问 `ERR_CERT_AUTHORITY_INVALID` | 自签证书或证书域名不匹配。验证 `openssl s_client ... | openssl x509 -noout -text \| grep "Subject:"` |
| 浏览器控制台 CSP 报错 | `locations.conf.inc` 的 `Content-Security-Policy` 头需要按你的真实第三方资源调整。开发期可先临时改 `default-src 'self' *` |
| SSE 收不到 keepalive | nginx 没禁 buffering。`docker exec mydow-nginx grep "proxy_buffering off" /etc/nginx/conf.d/locations.conf.inc` |
| Let's Encrypt 续期失败 | 80 端口被防火墙拦了；webroot 挂载错。手动跑 `certbot renew --dry-run` |
| `/health` 200 但 `/ready` 503 | DB 连接失败。检查 `docker compose logs postgres` 与 `app.environment.DATABASE_URL` |

---

## 10. 相关 PRD10 章节

- §22.1 鉴权（`/api/v1/*` 默认登录态）
- §22.2 文件安全（`client_max_body_size 50M` 与 §22 单文件 50MB 上限对齐）
- §29 风险表（限流 / AI 调用缓存 / 上传分片）
- §11 V1 部署目标（5 分钟一键 + HTTPS）
