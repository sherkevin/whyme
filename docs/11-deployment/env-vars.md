# 环境变量手册（PRD10 V1）

> **真理来源**：源码内 `os.getenv` / `os.environ.get` 调用 + `agent_os/core/config.py` + `.env.example`。
> **任务**：`todo-tasks.md` 8.14（Owner: Agent 3 @ 2026-05-05）。
>
> 部署 / 演示 / 投资人技术尽职都先看这一张。每一项都标出：用在哪、必填吗、改了会发生什么、默认值。

## 速查矩阵

| 环境 | 必须开 | 推荐 | 不要开 |
|---|---|---|---|
| **生产环境** | `DATABASE_URL` (Postgres) / `SECRET_KEY` / `JWT_SECRET_KEY` / `FIELD_ENCRYPTION_KEY` / `BASE_URL` (HTTPS) / `CORS_ORIGINS`（具体白名单）/ `REDIS_URL` / SMTP 全套 / `AGENTOS_PRD10_WORKER=on` | `AGENTOS_AI_LLM=on` + LLM key / `SENTRY_DSN` / S3 凭证 | `AGENTOS_DEMO_MODE`（除非是公开演示）/ `CORS_ALLOW_ALL` / `DEBUG` |
| **投资人演示环境** | 同上 + `AGENTOS_DEMO_MODE=on` | `AGENTOS_AI_LLM=on` + LLM key | 同上 |
| **本地开发** | `DATABASE_URL=sqlite+aiosqlite:///./data/agentos.db` 即可 | `AGENTOS_DEMO_MODE=on`（一键登录）/ Redis（验证码） | LLM key（默认走 placeholder）|
| **CI / 单测** | 全部默认值 | — | LLM key、生产 DB |

## 章节

### §1 应用基础

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `ENVIRONMENT` | 否 | `development` | `production` / `staging` / `development`，影响 CORS、debug、日志级别 |
| `LOG_LEVEL` | 否 | `info` | `debug` / `info` / `warning` / `error` |
| `DEBUG` | 否 | `false` | true 会暴露异常 stack 给前端，仅本地调试 |
| `API_PORT` | 否 | `8000` | uvicorn 监听端口 |
| `WS_PORT` | 否 | `8003` | 旧 WebSocket（PRD10 已弃用 SSE 取代） |
| `BASE_URL` | **是** | `http://localhost:8000` | 邮件链接、文件 commit 回调等都用它；HTTPS 必填正确域名 |
| `CORS_ORIGINS` | **是**（生产） | `http://localhost:3000,http://localhost:5173` | 多个用 `,` 分割。生产严格白名单 |
| `CORS_ALLOW_ALL` | 否 | `false` | 仅本地调试用，**生产绝对不要 true** |

### §2 数据库

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `DATABASE_URL` | **是**（生产） | `postgresql+asyncpg://agentos:agentos@localhost/agentos_db` | 异步驱动，Postgres 用 `asyncpg`，SQLite 用 `aiosqlite` |
| `POSTGRES_USER/PASSWORD/DB/PORT` | 否 | — | 仅 docker-compose 起 Postgres 容器时用 |
| `AGENTOS_DB_ECHO` / `DB_ECHO` | 否 | `false` | 打印 SQLAlchemy 原始 SQL，性能/调试用 |
| `TEST_DATABASE_URL` | 否 | `sqlite+aiosqlite:///./test.db` | 测试覆盖 DB |

### §3 安全 / Auth

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `SECRET_KEY` | **是**（生产） | `your-secret-key-change-in-production` | 应用主密钥；务必 rotate |
| `JWT_SECRET_KEY` | **是**（生产） | （继承 SECRET_KEY 占位） | JWT 签名密钥；rotate 后所有用户需重新登录 |
| `JWT_ALGORITHM` | 否 | `HS256` | — |
| `JWT_EXPIRE_MINUTES` | 否 | `60` | access token 有效期，单位分钟 |
| `FIELD_ENCRYPTION_KEY` | **是**（如启用敏感字段） | — | Fernet 32 byte key，base64 编码；生成命令见 `.env.example` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` / `SMTP_USE_TLS` | **是**（如启用邮箱验证码登录） | — | `agent_os/auth/mailer.py` 用 |

### §4 LLM Provider（三选一）

`agent_os/llm/litellm_impl.py` 的回退顺序：

```
api_key:  API_KEY → LITELLM_API_KEY → DEEPSEEK_API_KEY → OPENAI_API_KEY
base_url: BASE_URL → API_BASE → DEEPSEEK_OPENAI_BASE_URL
model:    LLM_MODEL → MODEL → DEEPSEEK_MODEL
```

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | 是（用 DeepSeek 时） | — | 推荐：默认 LLM，性价比最高 |
| `DEEPSEEK_OPENAI_BASE_URL` | 否 | `https://api.deepseek.com/v1` | DeepSeek 官方 OpenAI-兼容端点 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | — |
| `OPENAI_API_KEY` | 是（用 OpenAI 时） | — | — |
| `OPENAI_API_BASE` | 否 | `https://api.openai.com/v1` | — |
| `ANTHROPIC_API_KEY` | 是（用 Claude 时） | — | — |
| `API_KEY` / `BASE_URL` / `LLM_MODEL` | 否 | — | 通用别名，覆盖上述任意 provider |

### §5 PRD10 行为开关（核心 — 决定运行时形态）

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `AGENTOS_DEMO_MODE` | **是**（演示环境） | 关 | `on/1/true/enabled` 时启用 `/api/v1/demo/login` 一键登录 |
| `AGENTOS_AI_LLM` | **是**（生产 / 演示） | 关 | `on/1/true/enabled` 走真 LLM；其它值或不设走 placeholder 回复 |
| `AGENTOS_AI_TEMPERATURE` | 否 | `0.3` | 0.0–1.0 |
| `AGENTOS_AI_MAX_TOKENS` | 否 | `1000` | — |
| `AGENTOS_PRD10_WORKER` | **是**（生产） | 关 | `on/1/true/enabled` 时 FastAPI startup 起 Job 消费 worker（消化 ai_chat / parse_file / generate_report / skill_run）|
| `AGENTOS_PRD10_WORKER_INTERVAL` | 否 | `2` | worker 轮询间隔，秒 |
| `AGENTOS_SANDBOX` | 否 | （docker） | `local` 在宿主机直跑命令（开发用），其它值走 docker sandbox |
| `USE_LLM_PROCESSING` | 否 | `false` | 旧 inbox 处理流水线开关，PRD10 已用 capture/pipeline 取代 |
| `AGENTOS_RATE_LIMIT` | **否（默认关）** | `off` | PRD10 §29 token-bucket 限流总开关。`on/1/true/yes/enabled` 时启用 `RateLimitMiddleware`，按 `agent_os/common/rate_limit.py::DEFAULT_POLICIES` 给 auth/AI/search/capture/global 各分桶（详见下表）。触发时返回 PRD10 envelope `429 RATE_LIMITED` + `Retry-After` 头 |

#### PRD10 §11.9 生产 Seed（`scripts/production_seed.py`）

Docker / K8s 首次初始化 demo 账号与 §25.3 数据集的安全包装；栅栏顺序、exit code、`--profile seed` 用法详见 **`docs/11-deployment/production-seed.md`**。

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `AGENTOS_PROD_SEED_ON_BOOT` | 否 | `off` | `on/1/true/yes/enabled` 才执行；否则脚本 **exit 0** 且无任何 DB 写入 |
| `AGENTOS_PROD_SEED_FORCE` | 否 | （空） | `1` 跳过「生产式 `DATABASE_URL`」与「库内已有真实用户」两道栅栏；**仅限 staging/demo** |
| `AGENTOS_PROD_SEED_EMAIL` | 否 | `demo@whyme.local` | 种子 demo 账号邮箱 |
| `AGENTOS_PROD_SEED_PASSWORD` | 否 | `demo-password-123` | 种子 demo 密码；上线务必改为强口令 |
| `AGENTOS_PROD_SEED_FULLNAME` | 否 | `Demo User` | 种子 demo 显示名 |

#### 默认限流策略（PRD10 §29）

仅当 `AGENTOS_RATE_LIMIT=on` 时生效。每行的「桶」描述允许的爆发量（capacity），每分钟稳态等于 capacity（refill 按 capacity/60 秒）。多个 policy 同时存在时，**第一个匹配的 policy 生效**（特定路径优先于 `global`）。

| Policy | 匹配 | 配额 | 范围 (scope) |
|---|---|---:|---|
| `auth_login` | `POST /api/v1/auth/login` | 10/分钟 | 每 IP |
| `auth_register` | `POST /api/v1/auth/register` | 5/分钟 | 每 IP |
| `auth_send_code` | `POST /api/v1/auth/{send-code,forgot-password,resend-verification}` | 5/分钟 | 每 IP |
| `ai_messages` | `POST /api/v1/ai/conversations/...` 或 `/api/v1/ai/messages/...` | 30/分钟 | 每用户（无 token 时按 IP）|
| `search` | `ANY /api/v1/search...` | 120/分钟 | 每用户（无 token 时按 IP）|
| `capture` | `POST/PUT /api/v1/capture` 或 `/api/v1/uploads` | 120/分钟 | 每用户（无 token 时按 IP）|
| `global` | `ANY /api/v1/...`（兜底） | 600/分钟 | 每 IP |

**响应头**（无论是否触发限流）：

| Header | 含义 |
|---|---|
| `X-RateLimit-Policy` | 命中的 policy 名 |
| `X-RateLimit-Limit` | 桶容量 |
| `X-RateLimit-Remaining` | 剩余 token 数 |
| `Retry-After` | （仅 429）建议等待秒数 |

**429 响应体**（PRD10 envelope）：

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded for policy 'auth_login'. Please retry later.",
    "details": {
      "policy": "auth_login",
      "scope": "ip",
      "limit": 10,
      "retry_after_seconds": 6
    }
  },
  "request_id": "req_abc123def456"
}
```

> **多实例部署提醒**：当前默认实现为 in-memory（单进程）。多实例 / 多区域部署需要换成 Redis 后端（PRD10 §29 follow-up），否则限流计数不跨实例共享。代码已留 `InMemoryRateLimitStore` 抽象，替换后无需改 caller。

### §6 Redis

未配 Redis 时降级行为：

- 邮箱验证码 `/auth/send-code` 返回 `503`
- 限流相关功能直通（不限流）
- SSE 通知 broker 退化为进程内 in-memory（多实例部署会失同步）

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `REDIS_URL` | **是**（生产） | — | 完整 URL，优先级最高 |
| `REDIS_HOST` | 否 | `localhost` | 单独配 host/port/db 也可 |
| `REDIS_PORT` | 否 | `6379` | — |
| `REDIS_DB` | 否 | `0` | — |
| `REDIS_PASSWORD` | 否 | — | 如配置 ACL 必填 |

### §7 文件存储

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `PRD10_UPLOADS_BASE` | 否 | `data/uploads` | 本地存储根目录，单机部署用 |
| `PRD10_UPLOADS_MULTIPART_BASE` | 否 | `data/uploads/multipart` | 分片上传 staging 目录（PRD10 §12.5），complete/cancel 时自动清空 |
| `AGENTOS_UPLOAD_MULTIPART_CHUNK_SIZE` | 否 | `5242880`（5 MiB） | 单分片字节数；client 可在 init 时 override，server 钳到 64 KiB – 64 MiB |
| `AGENTOS_UPLOAD_MULTIPART_TTL_SECONDS` | 否 | `86400`（24 h） | multipart session 过期时间，过期 PUT/complete 返 400 |
| `AGENTOS_UPLOAD_MULTIPART_MAX_BYTES` | 否 | `2147483648`（2 GiB） | 单文件总大小硬上限，init 时检查 |
| `UPLOADS_BACKEND` | 否 | `local` | `s3` / `r2` / `oss`（待实现） |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_S3_BUCKET` / `AWS_S3_REGION` / `AWS_S3_ENDPOINT_URL` | 是（用 S3 时） | — | 投资人级别部署推荐：S3 + CloudFront |

### §8 第三方集成

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `WECHAT_APP_ID` / `WECHAT_APP_SECRET` / `WECHAT_WEBHOOK_TOKEN` | 否 | — | 微信公众号集成（PRD10 P2） |
| `SENTRY_DSN` | **是**（生产 / 演示） | — | Sentry 错误监控 DSN。空则整个 Sentry 模块 no-op；生产**强烈建议**接入（PRD10 §11.5 / Acceptance Gate 14.x） |
| `SENTRY_ENVIRONMENT` | 否 | `${ENVIRONMENT}` 或 `development` | Sentry 上区分 production / staging / demo / development 的标签 |
| `SENTRY_RELEASE` | 否 | — | 版本号或 git sha；让 Sentry 把错误关联到具体部署，强烈推荐 |
| `SENTRY_TRACES_SAMPLE_RATE` | 否 | `0.1` | 性能 trace 采样率 0.0-1.0；默认 10% |
| `SENTRY_SAMPLE_RATE` | 否 | `1.0` | 错误事件采样率；通常保留 100% |
| `SENTRY_SEND_DEFAULT_PII` | 否 | `false` | 是否允许 Sentry 关联用户身份；默认 false（PRD10 隐私合规） |

#### Sentry 集成行为（PRD10 §11.5）

启用条件：仅当 `SENTRY_DSN` 非空时初始化。空时整个模块 no-op，不引入任何性能开销或网络请求。

启用后自动捕获：

- FastAPI / Starlette 请求异常（含 422 / 500 / WebSocket 错误）
- SQLAlchemy 慢查询（默认阈值 1000ms）
- `logging.ERROR+` 日志（INFO+ 进 breadcrumb）
- 未捕获 Python 异常（含 startup 期间）

PII 安全剥离（`before_send` hook，发送前生效）：

| 类型 | 字段名（不区分大小写） |
|---|---|
| Headers | `authorization` / `cookie` / `set-cookie` / `x-api-key` / `x-mydow-token` / `x-auth-token` / `x-csrf-token` |
| Body / Extra | `password` / `current_password` / `new_password` / `password_hash` / `token` / `access_token` / `refresh_token` / `secret` / `api_key` / `private_key` / `client_secret` |

噪音过滤（`before_send_transaction` hook）：自动丢弃 `/health` / `/ready` / `/metrics` / `/favicon.ico` 的 transaction 事件，避免烧 quota。

健康检查暴露：`GET /ready` 响应体里有：

```json
{
  "status": "ready",
  "dependencies": {"db": "ok", "sentry": "active"},
  "observability": {
    "sentry": {"enabled": true, "environment": "production", "release": "v1.0.0"}
  }
}
```

### §9 调试

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `GARDEN_STRONG_EDGE_THRESHOLD` | 否 | `0.7` | 数字花园强连接阈值 0.0–1.0 |
| `RELOAD` | 否 | `false` | uvicorn auto-reload，仅开发 |
| `PROFILE` | 否 | `false` | 性能 profile，写 `./logs/profile-*.json` |

---

## 启动脚本（PowerShell）

### 本地开发（最小配置）

```powershell
$env:DATABASE_URL = "sqlite+aiosqlite:///./data/agentos.db"
$env:AGENTOS_DEMO_MODE = "on"
$env:AGENTOS_PRD10_WORKER = "on"
$env:AGENTOS_PRD10_WORKER_INTERVAL = "2"
$env:PYTHONPATH = "$PWD\src"

python scripts/seed_prd10.py --email demo@mydow.example --password demo123 --reset
python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8000
```

### 演示环境（带真 LLM）

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://agentos:agentos@postgres:5432/agentos_db"
$env:REDIS_URL = "redis://:redis123@redis:6379/0"
$env:AGENTOS_DEMO_MODE = "on"
$env:AGENTOS_AI_LLM = "on"
$env:DEEPSEEK_API_KEY = "<你的 DeepSeek key>"
$env:AGENTOS_PRD10_WORKER = "on"
$env:SECRET_KEY = "<rotate-this>"
$env:JWT_SECRET_KEY = "<rotate-this>"
$env:BASE_URL = "https://demo.example.com"
$env:CORS_ORIGINS = "https://demo.example.com"

python -m uvicorn agent_os.server.app:app --host 0.0.0.0 --port 8000
```

### 生产环境

参考 §5 / §6 必填项 + Sentry / 备份 / 健康检查（todo-tasks 11.5–11.8）。

---

## 验证清单（部署前）

- [ ] `python -c "from agent_os.core.config import load_config; load_config('config.yaml')"` 不抛异常
- [ ] `python -m uvicorn agent_os.server.app:app --port 8000` 在 5 秒内监听
- [ ] `curl http://localhost:8000/api/v1/today` 不返回 500（401 是预期的，说明 auth 在工作）
- [ ] 启动日志看到 `[prd10-worker] running` 行（说明 §5 worker 开关生效）
- [ ] AGENTOS_AI_LLM=on 时 `POST /api/v1/ai/conversations/{id}/messages` 不再返回 placeholder reply
- [ ] AGENTOS_DEMO_MODE=on 时 `POST /api/v1/demo/login` 返回 200 + access_token
- [ ] Redis 配通时 `POST /api/v1/auth/send-code` 不返回 503

发现任何偏差 → 加 `open` 任务到 `todo-tasks.md` §8 / §11，附 reproducer。
