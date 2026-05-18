# mydow.club 服务器预检记录

> 检查时间：2026-05-17 17:00-17:10 (UTC+8)
>
> 范围：仅验证 SSH 连通性、服务器基础规格、Docker/Compose、端口占用、DNS 与部署前置条件；未部署项目、未读取或输出私钥内容。

## 连接信息

```text
域名：mydow.club
公网 IP：82.156.119.135
SSH 用户：ubuntu
SSH key：D:/chromedown/mydow.pem
```

验证结果：

- `root@mydow.club`：登录失败，远端拒绝 root key 登录。
- `ubuntu@mydow.club`：登录成功。
- `ubuntu@82.156.119.135`：登录成功。
- 本地私钥初始 ACL 过宽，OpenSSH 报 `UNPROTECTED PRIVATE KEY FILE`；已在本机将 `D:/chromedown/mydow.pem` 收紧为当前 Windows 用户只读。

## DNS

结果：

- 服务器 metadata 显示公网 IP 为 `82.156.119.135`。
- 服务器内 `resolvectl query mydow.club` 返回 `82.156.119.135`。
- 2026-05-17 17:11 复核：服务器内 `resolvectl query www.mydow.club` 返回 `82.156.119.135`。
- 本机 DoH 查询：
  - Cloudflare DoH 返回 `82.156.119.135`。
  - Google DoH 返回 `82.156.119.135`。
- 2026-05-17 17:11 复核：本机 Cloudflare / Google DoH 查询 `mydow.club` 与 `www.mydow.club` 均返回 `82.156.119.135`。
- 本机普通 UDP DNS 查询曾返回 `198.18.0.251` / `198.18.1.0`，疑似本地 DNS / 网络代理环境差异；以 DNSPod 权威解析、DoH 与服务器侧解析结果为准。

部署建议：

- 继续使用 `82.156.119.135` 做 SSH 和部署目标。
- DNSPod 中确认 `mydow.club` 和后续 `app.mydow.club` 的 A 记录均指向 `82.156.119.135`。
- 部署完成后用公网浏览器和 DoH 再验证解析。

当前用户截图显示已添加：

```text
@    A    82.156.119.135
www  A    82.156.119.135
```

该配置满足根域名与 `www` 域名访问要求。若后续需要更清晰的产品入口，也可额外添加：

```text
app  A    82.156.119.135
```

## 服务器规格

```text
云厂商/地域：腾讯云 ap-beijing
主机名：VM-0-15-ubuntu
系统：Ubuntu 24.04 LTS
内核：Linux 6.8.0-49-generic x86_64
CPU：2 vCPU
内存：3.6 GiB
Swap：1.9 GiB
系统盘：100G，总可用约 89G
```

结论：

- 满足当前第一版 Docker Compose 部署最低要求。
- 2C4G 可用于早期内测和小流量上线。
- 如果后续并发、文档上传、AI/RAG、后台任务明显增加，建议升级到 4C8G。

## 权限和工具

```text
登录用户：ubuntu
sudo：免密可用
git：2.43.0
curl：8.5.0
Docker：27.5.1
Docker Compose：v2.32.4
Docker 服务：active
Docker storage driver：overlay2
```

结论：

- 已具备部署当前 `docker-compose.prd10.yml` 的基础条件。
- `ubuntu` 当前不在 docker 组，直接执行 `docker ps` 会 permission denied；使用 `sudo docker ...` 正常。部署脚本可以用 `sudo docker compose`，或后续把 `ubuntu` 加入 docker 组并重新登录。

## 端口与占用

云侧连通性：

```text
22：可连通
80：可连通
443：可连通
```

服务器内监听：

```text
22：sshd 正在监听
80：未被业务进程占用
443：未被业务进程占用
```

当前容器：

```text
docker ps：无运行容器
```

结论：

- 80/443 未被 nginx、宝塔、WordPress 等占用，适合直接部署项目 nginx 容器。
- `ufw` 当前 inactive，主要依赖腾讯云防火墙 / 安全组控制公网端口。

## 备案要求

服务器地域为北京，属于中国境内地域。根据腾讯云 ICP 备案文档，使用中国境内云资源对外提供网站 / APP 服务前，需要先完成 ICP 备案并取得备案号；轻量应用服务器备案需中国境内轻量实例、包年包月、购买 3 个月及以上且备案期间剩余有效期大于等于 1 个月。

域名后缀方面，腾讯云域名注册商信息文档列出的工信部公示可注册后缀包含 `.club`，但实际备案可用性仍需以腾讯云备案小程序 / 控制台域名校验结果为准。

## 结论

服务器本身符合当前项目第一版部署要求：

- SSH key 登录已验证；
- Ubuntu / Docker / Compose 均可用；
- CPU、内存、磁盘满足最低部署规格；
- 80/443 没有本机服务占用；
- 可直接作为 `docker compose` 单机部署目标。

继续部署前还需要：

1. 确认腾讯云防火墙 / 安全组只开放 22、80、443。
2. 确认 `mydow.club` / `app.mydow.club` 在 DNSPod 指向 `82.156.119.135`。
3. 完成或启动 ICP 备案流程；备案完成前不要把北京服务器上的站点正式对公众开放。
4. 准备生产 `.env` 必需密钥：`JWT_SECRET_KEY`、`SECRET_KEY`、`POSTGRES_PASSWORD`、`REDIS_PASSWORD`、`DEEPSEEK_API_KEY`、SMTP 配置等。
5. 决定正式访问路径：建议 `https://app.mydow.club/mydow/`。

## 2026-05-17 17:11 完整部署条件判断

当前已经具备完整 Docker Compose 技术部署的基础设施条件：

- 域名解析：`mydow.club` / `www.mydow.club` 通过 DoH 与服务器侧解析均指向 `82.156.119.135`。
- 服务器：SSH、Docker、Compose、磁盘、80/443 端口均满足。
- 部署目标：可以使用 `ubuntu@82.156.119.135` 执行部署。

若目标是“无 mock / 无假数据 / AI 与注册邮件完整可用”的生产服务，还需要生产密钥：

- DeepSeek API Key：缺少时 AI 真实 LLM 链路不能算完整。
- SMTP 邮箱配置：缺少时注册验证码、邮件通知等邮件链路不能算完整。
- 生产随机密钥：`SECRET_KEY`、`JWT_SECRET_KEY`、`POSTGRES_PASSWORD`、`REDIS_PASSWORD` 可由 Codex 在服务器上生成。

根域名直达效果：

- 当前代码根路径 `/` 可能展示 landing page，而 `/mydow/` 会跳转到 v14 产品界面。
- 若要求访问 `https://mydow.club/` 直接进入产品，应在部署前把根路径重定向到 `/mydow/biz_v14/`，或在 nginx 层添加根路径跳转。
