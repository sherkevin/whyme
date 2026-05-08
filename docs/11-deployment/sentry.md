# Sentry 错误监控接入手册

> **任务来源**：`todo-tasks.md` §11.5 / §11.5b（Owner: Agent my-mcp-24 @ 2026-05-06）
> **真理来源**：`src/agent_os/common/sentry_setup.py` + `src/agent_os/common/middleware.py::RequestIdMiddleware`
> **核心代码**：~420 行 sentry_setup.py + ~30 行 middleware patch + ~80 行 `__sentry_test__` smoke 端点
> **测试**：`tests/unit/common/test_sentry_setup.py`（31）+ `tests/integration/api/test_prd10_sentry_integration.py`（3）+ `test_prd10_sentry_request_id.py`（4）

---

## 1. 架构总览

PRD10 §11.5 错误监控走 [Sentry](https://sentry.io) SaaS（也可换私有部署 https://sentry.com/self-hosted/）。Mydow 后端的接入分四层：

```
                        [ Sentry SaaS ]
                              ▲
                              │ HTTPS POST /api/<project>/store/
                              │
   ┌──────────────────────────┴──────────────────────────────────┐
   │  agent_os.common.sentry_setup                                │
   │  - init_sentry()                — 启动期 idempotent 初始化   │
   │  - _before_send / scrub        — PII 剥离（headers + body）  │
   │  - _before_send_transaction    — 噪音过滤 (/health /ready)   │
   │  - capture_message / exception — 业务侧主动埋点              │
   └──────────────────────────────┬───────────────────────────────┘
                                  │
                                  │ sentry_sdk.init(integrations=[...])
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  Sentry SDK 集成（自动捕获）                                 │
   │  - FastApiIntegration   — 路由异常、HTTP 5xx                 │
   │  - StarletteIntegration — Middleware / WebSocket             │
   │  - SqlalchemyIntegration— 慢 SQL                             │
   │  - LoggingIntegration   — logging.ERROR+ → events            │
   │                                                              │
   │  agent_os.common.middleware.RequestIdMiddleware              │
   │  - sentry_sdk.set_tag("request_id", ...)                    │
   │  - sentry_sdk.set_context("request_meta", ...)              │
   └──────────────────────────────────────────────────────────────┘
```

---

## 2. 5 分钟接入

### 步骤 1：拿 DSN

去 https://sentry.io 创建 organization → 创建 project（建议用 `python` + FastAPI 模板）→ 在 Project Settings → Client Keys (DSN) 拿到 DSN，形如：

```
https://abcdef0123456789@o12345.ingest.us.sentry.io/1234567
```

### 步骤 2：配 `.env`

参考 `.env.example` §8 段。最小集：

```bash
SENTRY_DSN=https://abc@o12345.ingest.us.sentry.io/1234567
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=mydow@1.0.0   # 强烈推荐：用语义版本或 git sha
```

可选调优：

```bash
SENTRY_TRACES_SAMPLE_RATE=0.1     # 性能 trace 采样率，默认 10%
SENTRY_SAMPLE_RATE=1.0            # 错误事件采样，默认 100%
SENTRY_SEND_DEFAULT_PII=false     # 默认 false；只在合规审查后开
```

### 步骤 3：重启服务

```bash
# Docker compose
docker compose --env-file .env -f docker-compose.prd10.yml restart app

# 直接 uvicorn
$env:SENTRY_DSN = "https://..."
python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8000
```

启动期 stdout 应出现：

```
INFO sentry_initialized prd10_environment=production prd10_release=mydow@1.0.0 prd10_traces_sample_rate=0.1 prd10_sample_rate=1.0
```

### 步骤 4：验证（用 smoke endpoint）

```bash
# 仅当部署开关 + Sentry 都启用时才挂载
$env:AGENTOS_SENTRY_TEST = "on"
$env:SENTRY_DSN = "https://..."
# 重启服务

curl -i -X POST http://127.0.0.1:8000/api/v1/__sentry_test__
# → 返回 PRD10 envelope 500，error.code=INTERNAL_ERROR，details.synthetic=true
```

回到 Sentry UI 应该在 30 秒内看到一条 `ZeroDivisionError` event，关联：

- `request_id` tag（与 `X-Request-ID` header 一致）
- `environment=production`
- `release=mydow@1.0.0`

### 步骤 5：关闭 smoke 开关

```bash
$env:AGENTOS_SENTRY_TEST = ""
# 或从 .env 删除该行
```

smoke 端点是 opt-in 的（既需要 `AGENTOS_SENTRY_TEST=on`，又需要 Sentry init 成功），但仍建议验证完毕后关掉。

---

## 3. `/ready` 自检

`GET /ready` 返回体里有 `observability.sentry`，运维探针 / Kubernetes liveness probe 可读：

```json
{
  "status": "ready",
  "service": "agent-os",
  "version": "v1",
  "dependencies": {
    "db": "ok",
    "sentry": "active"
  },
  "observability": {
    "sentry": {
      "enabled": true,
      "environment": "production",
      "release": "mydow@1.0.0"
    }
  }
}
```

`dependencies.sentry == "disabled"` 在生产是告警信号（DSN 没配或 init 失败）。

---

## 4. PII 剥离规则

`agent_os.common.sentry_setup._before_send` 会在 SDK 把事件 POST 出去之前递归扫描 dict / list，对以下字段名（不区分大小写）替换为 `[Filtered]`：

### Headers

`authorization` / `cookie` / `set-cookie` / `x-api-key` / `x-mydow-token` / `x-auth-token` / `x-csrf-token`

### Body / Extra / Contexts / Breadcrumbs

`password` / `current_password` / `new_password` / `password_hash` / `token` / `access_token` / `refresh_token` / `secret` / `api_key` / `private_key` / `client_secret`

> **注意**：PRD10 用户内容（卡片标题、AI 消息内容、KB 文档摘要）**不在**剥离名单内 —— 调试需要这些上下文。如果业务有更严的要求，加 key 到 `_SECRET_BODY_KEYS` frozenset 即可。

---

## 5. 噪音过滤

`_before_send_transaction` 自动丢以下路径的 transaction 事件（不烧 quota）：

- `/health` — Kubernetes liveness probe
- `/ready` — 探针 + 自检
- `/metrics` — Prometheus 抓取（如启用）
- `/favicon.ico` — 浏览器自动请求

错误事件不受此过滤（异常仍会上报）。

---

## 6. Source maps（前端 SPA）

> Status：当前 SPA 走的是原生 ESM（`static/mydow/biz/bridge.js`），未走打包 + minify，无需 source map 上传。
> 后续若引入 webpack/vite，按 https://docs.sentry.io/platforms/javascript/sourcemaps/ 流程上传即可。

---

## 7. 推荐 Alert Rules

在 Sentry Project → Alerts 配以下规则（投资演示前必配）：

| Rule | 阈值 | Channel |
|---|---|---|
| 5xx error spike | 每分钟 > 10 个 | Slack #ops |
| New issue (不是 regression) | 第一次出现 | Email + Slack |
| AI streaming error | tag `event:ai.stream.failed` 出现任意 | Slack #ai |
| Rate limit triggered too often | log 级别 `prd10_rate_limited` 出现 > 100/min | Slack #ops（DDoS 信号）|
| Job dead-letter | tag `code:MAX_RETRIES_EXCEEDED` | Slack #ops |
| /ready returns 503 | 连续 3 分钟 | PagerDuty |

---

## 8. 与 §11.6 logging 的协同

PRD10 §11.6 已经把日志写成 JSON（`AGENTOS_LOG_FORMAT=json`），关键字段：

- `prd10_request_id`
- `prd10_method` / `prd10_path` / `prd10_status_code`
- `prd10_duration_ms`
- `prd10_client_host`
- `prd10_user_id`（部分端点）

Sentry `LoggingIntegration` 默认把 `INFO+` 的日志记录作为 breadcrumb，`ERROR+` 升级为 event。所以一个慢 5xx 请求在 Sentry 上看到的事件会包含：

1. **Tag**：`request_id` / `http.method` / `environment`
2. **Context.request_meta**：`{request_id, path, method}`
3. **Breadcrumbs**：从请求开始到错误为止所有 `INFO/WARNING` 日志
4. **Stack trace**：业务代码栈
5. **SQL**：`SqlalchemyIntegration` 自动注入

完整的 root-cause analysis 几乎不需要再去翻 stdout。

---

## 9. 常见故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| 启动日志没 `sentry_initialized` | `SENTRY_DSN` 未设 | 检查 .env / docker env |
| 启动日志有 `sentry_init_failed` | DSN 格式错 / 网络封 sentry.io | 验证 DSN，开放 outbound 443 |
| `/ready` 显示 `sentry: disabled` | 同上 | 同上 |
| Sentry UI 没事件，但调用了 `/__sentry_test__` | sample rate 为 0 / firewall | `SENTRY_SAMPLE_RATE=1.0` + 检查防火墙 |
| 看到一堆 `/health` transaction | 旧版 Mydow（< 2026-05-06） | 升级到 §11.5b 引入 `_before_send_transaction` 之后版本 |
| 事件里 Authorization 没被剥离 | 自定义 header 名没在 `_SECRET_HEADER_KEYS` | 加到 `agent_os/common/sentry_setup.py::_SECRET_HEADER_KEYS` |

---

## 10. 测试覆盖

```bash
# Unit + Integration
$env:PYTHONPATH = "d:\Codes\whyme\src"
python -m pytest tests/unit/common/test_sentry_setup.py tests/integration/api/test_prd10_sentry_integration.py -q

# 完整 PRD10 14 套件 + Sentry + Rate limit + 全 unit
python -m pytest tests/integration/api/test_prd10_*.py tests/integration/api/prd10/ tests/unit/common/ -q
```

关键覆盖点：

- **DSN 空 → 完全 no-op**（不调用 `sentry_sdk.init`，无网络开销）
- **DSN 有效 → init 一次**（idempotent，第二次调用不会双重注入）
- **before_send 剥离 11 个 body 字段 + 7 个 header 字段**
- **before_send_transaction 丢弃 health/ready/metrics**
- **init 抛异常 → 不让 startup 崩溃**（fall back to disabled state，记 warning 日志）
- **`/ready` 暴露 sentry block**（运维可读）
- **`__sentry_test__` 端点条件挂载**（仅 `AGENTOS_SENTRY_TEST=on` + `SENTRY_DSN` 同时存在时）
- **`RequestIdMiddleware` set_tag/set_context**（确保 request_id 进 Sentry scope）
