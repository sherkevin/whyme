# 50 人内测上线闸门

本文档是 PRD10 / Mydow v14 在 50 人内测前必须复跑的部署与容量检查。结论不靠截图或人工感觉，必须由脚本输出和日志证明。

## 1. 推荐部署形态

- Web/API：`docker-compose.prd10.yml` 的 `app` 服务，单机内测保持 `uvicorn --workers 1`，因为当前 PRD10 job worker 随 FastAPI lifespan 启动。多 worker 会重复启动内置 worker，正式线上放量前应拆成独立 `worker` 服务。
- 数据库：Postgres 16，不允许默认 SQLite。50 人内测建议至少 2 vCPU / 4GB RAM / 独立持久盘。
- Redis：必须开启，用于限流、验证码 TTL、SSE/pubsub 等能力。
- 上传：内测可继续 `local` volume；公网部署或多实例时切 `AGENTOS_UPLOAD_BACKEND=s3`，否则附件会被绑定到单台机器。
- 备份：每天 `backup` profile 跑 Postgres dump + uploads snapshot；打开 `AGENTOS_BACKUP_S3_BUCKET` 做异地备份。
- HTTPS：公网入口必须走 nginx profile 或上游负载均衡 TLS，`BASE_URL`、`CORS_ORIGINS` 必须是线上域名。

## 2. 容量参数

`.env` / `.env.docker.local` 建议：

```env
AGENTOS_DB_POOL_SIZE=20
AGENTOS_DB_MAX_OVERFLOW=40
AGENTOS_DB_POOL_TIMEOUT=30
AGENTOS_DB_POOL_RECYCLE=1800

AGENTOS_PRD10_WORKER=on
AGENTOS_PRD10_WORKER_INTERVAL=2
AGENTOS_PRD10_WORKER_BATCH_LIMIT=25

AGENTOS_AI_LLM=on
LLM_PROVIDER=deepseek
DEEPSEEK_OPENAI_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
LLM_MODEL_FALLBACK=deepseek-v4-pro

AGENTOS_RATE_LIMIT=on
```

说明：

- DB pool 最大并发连接约为 `pool_size + max_overflow`。50 人内测保守值为 60，需确保 Postgres `max_connections` 足够。
- Worker batch 控制每轮消费 queued jobs 的上限。LLM 限额紧张时先降到 10，避免 DeepSeek 被瞬时打爆。
- `BASE_URL` 只表示应用公开地址，不再作为 LLM endpoint 使用。

## 3. 压测命令

先启动真实栈：

```powershell
scripts\run_mydow_docker.ps1 -NoOpen
```

确认健康：

```powershell
curl.exe -fsS http://localhost:8000/health
docker compose --env-file .env.docker.local -f docker-compose.prd10.yml ps
```

跑 50 人真实链路检查：

```powershell
python scripts\prd10_beta_load_check.py `
  --base-url http://localhost:8000 `
  --users 50 `
  --concurrency 10 `
  --include-ai `
  --include-skills `
  --output tests\integration\api\prd10\beta_load_latest.json
```

如果只想先排除 DB/API/搜索/上传链路，不消耗 LLM 配额：

```powershell
python scripts\prd10_beta_load_check.py --users 50 --concurrency 10 --skip-ai --skip-skills
```

`--skip-ai/--skip-skills` 只能作为预检，不能作为正式内测放量验收。

## 4. 验收阈值

默认脚本阈值：

- 总错误率 `<= 2%`
- 全请求 P95 `<= 30000ms`，因为正式验收包含真实 LLM capture / AI / Skill 链路；如果使用 `--skip-ai --skip-skills` 做纯 API 预检，建议临时加 `--fail-p95-ms 5000`
- 用户完整场景 P95 `<= 300s`，用于捕捉 Skill worker 排队、LLM 超时等单请求 P95 看不出来的问题
- 注册、capture、search、kb、feed、upload、AI message、Skill run 不应出现系统性失败
- Skill run 在 `--skill-poll-seconds` 内必须进入 `completed/failed/canceled`，不能无限 queued/running

正式放量前还要人工检查：

- `docker compose logs app` 无 Traceback、无连续 provider timeout
- Postgres CPU/内存/连接数正常
- Redis 无 OOM / reconnect 风暴
- `tests/integration/api/test_prd10_user_isolation.py` 全绿
- `.env.docker.local` 没有提交到 Git，LLM key 只在部署环境中存在

## 5. 后续线上化拆分

50 人内测后，如果继续放量：

- 拆 `worker` 独立服务：Web 只处理请求，Worker 消费 `prd10_jobs`，并用数据库行锁或队列避免重复消费。
- 上传切对象存储：S3/R2/MinIO，开启私有 bucket + presigned URL。
- 数据库切托管 Postgres：开启自动备份、慢查询、连接池代理。
- 日志告警：Sentry DSN、Nginx access log、应用 JSON log、DeepSeek provider error rate 告警。
- 限流策略转生产值：按用户/IP 分层，AI/Skill 单独限速。

## 6. 本地内测基线记录

2026-05-10 在 `http://localhost:8000` 真实 Docker/Postgres/Redis/DeepSeek 环境完成：

- `beta_load_latest.json`：50 users / concurrency 10 / `--skip-ai --skip-skills`，600+ 请求，0 failed，P95 约 11s，完整用户场景 P95 约 20s。该基线仍会真实调用 capture enrichment，因此覆盖 LLM 生成标题/摘要/tag 的压力。
- `beta_load_ai_skill_smoke.json`：3 users / concurrency 3 / `--include-ai --include-skills`，0 failed，AI message P95 约 6.7s，Skill 完整场景 P95 约 65s。

正式 50 人放量前仍建议在目标机器上复跑完整命令：

```powershell
python scripts\prd10_beta_load_check.py --base-url https://<your-domain> --users 50 --concurrency 10 --include-ai --include-skills
```
