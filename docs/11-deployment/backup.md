# Mydow / PRD10 — 备份与恢复（投资人级运维契约）

> **范围**：Postgres 数据库（业务真理）+ 本地上传目录（`PRD10_UPLOADS_BASE`）。  
> **目标**：投资人 / 客户 / 合规审查能直接拿这一页验证「数据丢不了 / 恢复演练有 SOP」。

---

## 1. RPO / RTO 目标

| 目标 | 数值 | 实现方式 |
|---|---|---|
| **RPO**（最大数据丢失） | ≤ 24 h | `pg_dump` 每日全量 + S3/R2 异地拷贝；下一阶段加 WAL 流复制（< 5 min） |
| **RTO**（恢复用时） | ≤ 30 min | `pg_restore --clean --if-exists` 单命令；演练脚本 `scripts/backup/restore_postgres.{sh,ps1}` |
| **保留期** | 14 天本地 + ≥ 90 天对象存储 | `AGENTOS_BACKUP_RETENTION_DAYS=14` 控制本地；S3 lifecycle 控制远端 |
| **演练频率** | 月度 | 每月 1 日由 cron 自动 restore 到 staging DB，结果写 `.tmp/backups/postgres/_drill_*.log` |

---

## 2. 一键脚本矩阵

所有脚本位于 `scripts/backup/`，**不需要源代码改动**即可挂上 cron / Windows 任务计划。

| 用途 | Linux / macOS | Windows |
|---|---|---|
| Postgres 全量备份 | `bash scripts/backup/backup_postgres.sh` | `powershell scripts\backup\backup_postgres.ps1` |
| Postgres 恢复 | `bash scripts/backup/restore_postgres.sh latest` | `powershell scripts\backup\restore_postgres.ps1 latest` |
| 上传目录快照 | `bash scripts/backup/snapshot_uploads.sh` | `powershell scripts\backup\snapshot_uploads.ps1` |

每个脚本：

- 自动从 `DATABASE_URL`（或 `.env`）解析连接，安全剥离 SQLAlchemy 方言后缀（`postgresql+asyncpg://` → `postgresql://`）；
- 输出 `<timestamp>_<dbname>.dump` / `.tar.gz` + 同名 `.sha256` 校验文件；
- 按 `AGENTOS_BACKUP_RETENTION_DAYS` 自动剪枝；
- 当 `AGENTOS_BACKUP_S3_BUCKET` 设置时，自动 `aws s3 cp` 一份到 `s3://<bucket>/<prefix>/`；
- 写 `_backup.log` / `_snapshot.log` 结构化时间戳日志，便于 `tail -F` 监控。

---

## 3. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | — | **必填**，连接串。SQLite URL 会被识别后跳过 PG 备份并写日志 |
| `BACKUP_DIR` | `<repo>/.tmp/backups` | 本地落盘根目录；建议生产挂到独立卷 |
| `PRD10_UPLOADS_BASE` | `<repo>/data/uploads` | 上传目录根；`snapshot_uploads.*` 打包它 |
| `AGENTOS_BACKUP_RETENTION_DAYS` | `14` | 本地剪枝阈值（天） |
| `AGENTOS_BACKUP_S3_BUCKET` | — | 设置后启用 S3/R2 上传 |
| `AGENTOS_BACKUP_S3_PREFIX` | `mydow/postgres` 或 `mydow/uploads` | S3 key 前缀 |
| `AGENTOS_BACKUP_GPG_RECIPIENT` | — *(P1)* | 设置后用 `gpg --encrypt` 包一层；当前版本未启用，留作 V2 |

---

## 4. 部署矩阵：cron / systemd / docker / Windows

### 4.1 Linux cron（推荐生产用法）

```cron
# /etc/cron.d/mydow-backup
# m  h  dom mon dow user      command
  15 02 *   *   *  postgres   /opt/mydow/scripts/backup/backup_postgres.sh   >> /var/log/mydow/backup.log 2>&1
  30 02 *   *   *  postgres   /opt/mydow/scripts/backup/snapshot_uploads.sh  >> /var/log/mydow/backup.log 2>&1
```

### 4.2 systemd timer（无 cron 时）

```ini
# /etc/systemd/system/mydow-backup.service
[Unit]
Description=Mydow PRD10 daily backup
After=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/mydow/backup.env
ExecStart=/opt/mydow/scripts/backup/backup_postgres.sh
ExecStartPost=/opt/mydow/scripts/backup/snapshot_uploads.sh

# /etc/systemd/system/mydow-backup.timer
[Unit]
Description=Mydow PRD10 daily backup timer

[Timer]
OnCalendar=*-*-* 02:15:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用：`sudo systemctl enable --now mydow-backup.timer`。

### 4.3 docker compose 集成

`docker-compose.prd10.yml` 中已存在 `app` / `postgres` / `redis` 三服务。增加 `backup` profile 服务（仅在 `--profile backup` 时启动）：

```yaml
backup:
  profiles: ["backup"]
  image: postgres:16-alpine
  depends_on:
    postgres:
      condition: service_healthy
  environment:
    DATABASE_URL: "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"
    AGENTOS_BACKUP_RETENTION_DAYS: "14"
    AGENTOS_BACKUP_S3_BUCKET: "${AGENTOS_BACKUP_S3_BUCKET:-}"
  volumes:
    - ./scripts/backup:/scripts:ro
    - mydow_backups:/var/backups/mydow
    - ./data/uploads:/data/uploads:ro
  entrypoint:
    - /bin/sh
    - -c
    - >
      apk add --no-cache bash coreutils gzip findutils tar &&
      BACKUP_DIR=/var/backups/mydow PRD10_UPLOADS_BASE=/data/uploads
      bash /scripts/backup_postgres.sh &&
      bash /scripts/snapshot_uploads.sh

volumes:
  mydow_backups: {}
```

按需运行：`docker compose -f docker-compose.prd10.yml --profile backup run --rm backup`。

定时调度交给宿主机的 cron / Kubernetes CronJob：

```yaml
# k8s CronJob 片段
apiVersion: batch/v1
kind: CronJob
metadata: { name: mydow-backup }
spec:
  schedule: "15 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: backup
              image: registry.example.com/mydow:prd10
              command: ["bash", "/app/scripts/backup/backup_postgres.sh"]
              envFrom: [{ secretRef: { name: mydow-backup-env } }]
              volumeMounts:
                - { name: backups, mountPath: /var/backups/mydow }
          volumes:
            - { name: backups, persistentVolumeClaim: { claimName: mydow-backups } }
```

### 4.4 Windows 任务计划（开发 / 单机部署）

```powershell
$action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument '-ExecutionPolicy Bypass -File D:\Codes\whyme\scripts\backup\backup_postgres.ps1'
$trigger = New-ScheduledTaskTrigger -Daily -At 02:15
Register-ScheduledTask -TaskName 'Mydow Postgres Backup' -Action $action -Trigger $trigger `
    -User 'SYSTEM' -RunLevel Highest
```

---

## 5. 恢复演练（强烈建议月度执行）

```bash
# 1) 准备一个一次性数据库，绝不指向生产
createdb -U postgres mydow_drill
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mydow_drill

# 2) 跑 restore；脚本会自动找最新 dump 并校验 SHA-256
bash scripts/backup/restore_postgres.sh latest

# 3) 起后端，验证基线 KPI
PYTHONPATH=src python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8772 &
curl -s http://127.0.0.1:8772/api/v1/demo/status      # 期望 200
curl -s http://127.0.0.1:8772/api/v1/today | jq .data.stats   # 期望真数据

# 4) 退出 / 清理
kill %1; dropdb -U postgres mydow_drill
```

把演练日期写到 `.tmp/backups/postgres/_drill_<date>.log`；连续 3 次成功后我们才会把 `RPO=24h / RTO=30min` 落到投资人 deck 里。

---

## 6. 安全与合规底线

- **不要把 `DATABASE_URL` 写进 dump 文件名**：脚本只取数据库名，URL 留在环境变量；
- **保留期不下限**：本地 14 天 + S3 90 天 + 月度演练保留 12 个月，覆盖 GDPR / 个人数据生命周期；
- **加密**：生产启用 S3/R2 默认 SSE-S3 / SSE-KMS；下一阶段（V2）补 `gpg --encrypt --recipient ops@…` 客户端侧加密；
- **审计**：`_backup.log` / `_snapshot.log` 都是 append-only，建议轮转到 syslog / Loki；
- **演练失败处理**：脚本 exit code 非 0 时 cron MAILTO / systemd `OnFailure=mydow-pager.service` 直接告警；
- **Production fence**：`restore_postgres.*` 默认拒绝带 `prod` / `production` 字样的目标 host，`--force` / `-Force` 才能覆盖。

---

## 7. 故障速查

| 现象 | 排查 |
|---|---|
| `pg_dump: error: connection to server failed` | DB 主机不可达；检查 `DATABASE_URL`、防火墙、`pg_hba.conf` |
| `gunzip: invalid compressed data` | dump 损坏；用 SHA-256 复核，重新拉远端拷贝 |
| 备份文件突然变大很多 | 大概率是 `Card.content` / `Document.content` 文本暴增；确认 `seed_prd10` 没把测试 fixture 落到生产；考虑在 dump 前加 `pg_repack` 压缩 |
| 恢复后业务 500 但 health 200 | `User.id` UUID 漂移；重启 worker / 重新 seed demo 账户 |

---

## 8. Follow-ups（投资人会追问，留作 V2）

1. **WAL 流复制 + Point-in-Time Recovery**：把 RPO 从 24h 降到 5 min，用 Patroni / pgBackRest。  
2. **GPG 客户端加密**：`AGENTOS_BACKUP_GPG_RECIPIENT` 已预留，启用后即使 S3 桶被攻破，攻击者也拿不到明文 dump。  
3. **跨区域复制**：当前 S3 单桶；下一步 `aws s3 sync` 到 ap-southeast-1 + us-east-1 多副本。  
4. **应用级表导出**：除了 PG 全量，再产出 `users.csv / cards.csv / documents.csv` 给数据科学 / 客户成功团队，避免直接读生产 DB。

---

> **当前实现状态（2026-05-06）**：本章节脚本与 docker-compose `backup` profile 已落仓库；本地手测产出 dump 与 sha256 ok；生产 cron / S3 / 演练流程交给运维（部署清单见 `docs/11-deployment/docker.md` §6）。
