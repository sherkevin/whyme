# Codex Prompt For Running Mydow Locally

Copy this prompt into Codex on another computer after that computer has cloned
this repository. The other Codex instance should execute the local full-stack
runbook and verify the result.

```text
你现在在 Mydow 仓库根目录。请按下面流程启动完整真实本地服务，不要使用 mock、不要开启 demo mode、不要伪造 LLM 结果。

目标：
1. 阅读 `docs/11-deployment/one-click-docker.md`。
2. 确认 Docker 正在运行。
3. 使用仓库的一键脚本启动完整前后端栈：nginx + FastAPI app + Postgres + Redis。
4. 启动时如果脚本要求输入 LLM API URL，请填我提供的 URL；如果没有提供，则使用 `https://api.deepseek.com`。
5. 启动时如果脚本要求输入 LLM API KEY，请让我粘贴，或者读取本机已有环境变量/`.env.local`，但不要把 API KEY 写进 git。
6. 启动完成后验证：
   - `http://localhost:8080/health` 返回 healthy。
   - `http://localhost:8080/ready` 可访问。
   - `http://localhost:8080/` 会进入 `/mydow/biz_v14/` 产品界面。
   - Docker 容器 `app`、`postgres`、`redis`、`nginx` 正常运行。
7. 如果失败，读取 Docker 日志，修复可修问题后重试；不要切到 SQLite，不要打开 `AGENTOS_DEMO_MODE`，不要打开 `AGENTOS_AI_OFFLINE_PLACEHOLDER`。
8. 最后告诉我访问地址、健康检查结果、容器状态，以及是否还缺 LLM API KEY 或 SMTP 配置。

Windows 运行命令：
`run-mydow.cmd`

macOS/Linux 运行命令：
`chmod +x run-mydow.sh scripts/run_mydow_docker.sh && ./run-mydow.sh`
```
