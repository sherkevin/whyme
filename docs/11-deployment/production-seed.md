# Mydow 生产环境 Seed 指南

> PRD10 §11.9 / todo-tasks.md §11.9
>
> 本文覆盖：`scripts/production_seed.py` 的安全栅栏、首次部署 / 升级 / 重置 / staging 4 种使用场景、docker-compose `seed` profile、与 §10.7 cron reset 的协作、故障排查。

---

## 1. 它是什么 / 不是什么

| | 是 | 不是 |
|---|---|---|
| 用途 | 让上线/演示环境**初始**有一个 demo 账号 + 5 个默认 Skill + §25.3 全套数据 | 数据迁移工具 |
| 调用对象 | 包装 `scripts/seed_prd10.py main(--reset)` | 替代 alembic / SQL migration |
| 触发时机 | 部署后 / staging 初始化 / 投资人演示前 | 每次启动（除非显式 opt-in） |
| 默认行为 | **No-op** —— 必须 env 显式开启 | 自动跑 |
| 影响范围 | 仅 demo user 自己的 [seed] 标签行；不动其他用户 | 真实生产用户数据 |

---

## 2. 4 道安全栅栏

启动时按顺序检查，任何一道**不通过**都会 exit 0（no-op）或 exit 2（拒绝）。整体为 **demo-only** 语义：`production_seed` 只重置 demo 账号名下带 `[seed]` 标记的数据，绝不触碰真实业务用户行。

| # | 栅栏 | 行为 |
|---|---|---|
| 1 | `AGENTOS_PROD_SEED_ON_BOOT` env | 不为 `on/1/true/yes/enabled` → 直接 exit 0（无副作用） |
| 2 | DSN 看起来像生产（host 含 `prod`/`production`） | 拒绝执行 → exit 2，除非 `AGENTOS_PROD_SEED_FORCE=1` |
| 3 | DB 内非 demo 用户 > 0 | 拒绝执行 → warning + exit 0，除非 `AGENTOS_PROD_SEED_FORCE=1` |
| 4 | 通过前 3 关后 | 调 `seed_prd10.main(--reset --email demo@whyme.local ...)`，只清自己 [seed] 标签的行 |

退出码：

| 码 | 含义 |
|---|---|
| 0 | 正确执行了 seed，或正确判断为不该跑 |
| 1 | 通用错误（DB 不通 / seed 脚本崩） |
| 2 | 拒绝执行（生产 DSN / 真实用户存在）；用 `--force` / env 覆盖 |

---

## 3. 4 种使用场景

### 3.1 首次部署（空库 → 初始化 demo）

最常见场景。配合 `docker-compose.prd10.yml --profile seed`：

```bash
cp .env.example .env
# 编辑：SECRET_KEY / JWT_SECRET_KEY / DEEPSEEK_API_KEY 等
echo "AGENTOS_PROD_SEED_ON_BOOT=on" >> .env

# 启动 app + db + redis
docker compose -f docker-compose.prd10.yml up -d

# 跑 oneshot seed
docker compose -f docker-compose.prd10.yml --profile seed run --rm seed
```

期望输出：

```text
[INFO] production_seed: starting (on_boot=True force=False dry_run=False seed_email=demo@whyme.local db=postgresql+asyncpg://agentos:****@postgres:5432/agentos_db)
[INFO] production_seed: calling seed_prd10.main (real_users=0, will --reset demo rows tagged [seed])
[INFO] seed_prd10: created folders=6 documents=20 cards=30 tasks=5 ...
[INFO] production_seed: production seed complete — demo account demo@whyme.local ready
```

退出码 0，任意时刻重跑都安全。

---

### 3.2 升级部署（保留真实用户）

当真实用户已经入驻（real_users > 0），脚本会**自动跳过**避免破坏数据：

```bash
docker compose -f docker-compose.prd10.yml --profile seed run --rm seed
```

输出：

```text
[WARNING] production_seed: found 12 real (non-demo) users in DB — skipping seed
to preserve existing data. Set AGENTOS_PROD_SEED_FORCE=1 / --force to override.
```

退出码 0。这是**期望行为**——升级时不应该重置 demo 数据。

---

### 3.3 Staging / 演示环境强制重置

例：每天 02:00 把 staging demo 账号刷新到一致状态：

```bash
AGENTOS_PROD_SEED_ON_BOOT=on AGENTOS_PROD_SEED_FORCE=1 \
  docker compose -f docker-compose.prd10.yml --profile seed run --rm seed
```

`FORCE=1` 同时跳过 DSN-look-like-prod + real-user 两道栅栏。**仅在 staging / demo 环境用**，生产环境永远不要。

> 与 §10.7 `scripts/demo-seed-reset.{ps1,sh}` 的关系：§10.7 是面向「投资人演示前快速 reset」的轻量包装（直接跑 seed_prd10），适合本地或人工触发；本脚本是面向「容器化生产部署」的安全栅栏版本，适合 docker / k8s。两者底层都调 `seed_prd10.main`。

---

### 3.4 干跑（dry-run）确认决策

调试时想确认脚本会不会跑、会调用什么参数，但**不真写**：

```bash
AGENTOS_PROD_SEED_ON_BOOT=on \
  docker compose -f docker-compose.prd10.yml --profile seed run --rm \
  seed python scripts/production_seed.py --dry-run -v
```

输出：

```text
[DEBUG] production_seed: starting (on_boot=True force=False dry_run=True seed_email=demo@whyme.local db=...)
[INFO] production_seed: DRY RUN — would call seed_prd10.main with email=demo@whyme.local, full_name=Demo User, reset=True (real_users=0)
```

退出码 0，无任何 DB 写入。

---

## 4. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `AGENTOS_PROD_SEED_ON_BOOT` | `off` | `on/1/true/yes/enabled` 才启用脚本（栅栏 1） |
| `AGENTOS_PROD_SEED_FORCE` | `(空)` | `1` 才能跳过 production-DSN + real-user 两道栅栏（栅栏 2/3） |
| `AGENTOS_PROD_SEED_EMAIL` | `demo@whyme.local` | demo 账号邮箱 |
| `AGENTOS_PROD_SEED_PASSWORD` | `demo-password-123` | demo 账号密码（**生产环境务必改**！） |
| `AGENTOS_PROD_SEED_FULLNAME` | `Demo User` | demo 账号显示名 |
| `DATABASE_URL` | (env) | 与 app service 共享；本脚本会自动从 compose env 注入 |

---

## 5. CLI 参数

```text
python scripts/production_seed.py [--force-run] [--force] [--dry-run] [-v]

  --force-run  bypass AGENTOS_PROD_SEED_ON_BOOT env check
  --force      bypass production-DSN + real-user fences (= AGENTOS_PROD_SEED_FORCE=1)
  --dry-run    compute decisions but don't call the seeder
  -v           verbose DEBUG logging
```

---

## 6. 与 §10.7 cron reset 的协作

| 场景 | 用 | 触发方式 |
|---|---|---|
| 容器化首次部署 | `production_seed.py`（本脚本） | docker compose `--profile seed` |
| 容器化升级（保留真实数据） | `production_seed.py` | 同上，自动跳过 |
| Staging 每日 02:00 重置 | `production_seed.py --force` | cron / k8s CronJob |
| 本地开发 / 投资人演示前 reset | `scripts/demo-seed-reset.{ps1,sh}` | 手动 / Windows Task Scheduler |
| 编辑后即时 reset 调试 | `python scripts/seed_prd10.py --reset` | 手动直接调 |

---

## 7. 故障排查

| 现象 | 排查 |
|---|---|
| 脚本退出 0，但 demo 账号没出现 | 检查环境变量是否真的传进去了：`docker compose --profile seed run --rm seed env \| grep AGENTOS_PROD_SEED`；最常见是 `.env` 没改 `AGENTOS_PROD_SEED_ON_BOOT=on` |
| 脚本退出 2 | 看日志 `DATABASE_URL looks like production` 或 `found N real users` —— 这是栅栏在工作。如果你**确定**要跑，加 `AGENTOS_PROD_SEED_FORCE=1` |
| `could not count users — DB unreachable` | postgres 还没起或网络不通；检查 `depends_on: postgres condition: service_healthy` 是否生效；本机跑：`docker compose ps postgres` 必须 `healthy` |
| seed 脚本本身报错 | 看 stderr 完整 trace；多半是 schema 不匹配（alembic / `init_db` 没跑），手动跑 `docker compose -f docker-compose.prd10.yml exec app python -c "import asyncio; from agent_os.db.base import init_db; asyncio.run(init_db())"` |
| 真实用户 + 想保留 + 又想刷新 demo | 用 `AGENTOS_PROD_SEED_FORCE=1`，因为 `seed_prd10.main(--reset)` 只删自己 `[seed]` 标签的行，**不会动其他用户**。栅栏只是默认保守。 |

---

## 8. 上线前自检

```bash
# 1. 确认默认状态：env 不开 → no-op
docker compose -f docker-compose.prd10.yml --profile seed run --rm seed
# 期望：[INFO] AGENTOS_PROD_SEED_ON_BOOT not set — skipping (no-op)

# 2. 干跑确认决策
AGENTOS_PROD_SEED_ON_BOOT=on docker compose -f docker-compose.prd10.yml \
  --profile seed run --rm seed python scripts/production_seed.py --dry-run -v
# 期望：[INFO] DRY RUN — would call seed_prd10.main ...

# 3. 真跑（首次部署，空库）
AGENTOS_PROD_SEED_ON_BOOT=on docker compose -f docker-compose.prd10.yml \
  --profile seed run --rm seed
# 期望：seed_prd10 输出 6/20/30/5/5/3/18/5/10/6 + 退出码 0

# 4. 验证 demo 可登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@whyme.local","password":"demo-password-123"}'
# 期望：{"success":true, "data":{"access_token":"..."}}

# 5. 验证幂等：再跑一次应该跳过（real_user=0 但 demo user 已存在 → reset 会清自己再插）
AGENTOS_PROD_SEED_ON_BOOT=on docker compose -f docker-compose.prd10.yml \
  --profile seed run --rm seed
# 期望：第二次执行 seed_prd10 仍然成功，账号数据 reset 到 known state
```

---

## 9. 相关 PRD10 章节

- §10.2 Demo 默认账号 seed
- §10.7 Demo seed 周期重置（cron）
- §11.9 本任务（生产 seed 自动化）
- §22 鉴权 / 文件安全 / 删除策略
- §25.3 Mock 数据要求（6/20/30/5/5/...）
