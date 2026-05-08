## ─── Mydow shared location blocks ────────────────────────────────────────
##
## 由 mydow.conf 的 :80 / :443 server 块共同 include。所有路由分流、
## 缓存策略、安全头、限流都在这里统一定义，避免 HTTP/HTTPS 版本漂移。
##
## todo-tasks.md §11.3（Owner: Agent / my-mcp-20）
## ──────────────────────────────────────────────────────────────────────────

# ─── 通用安全头（全 server / 全路径） ──────────────────────────────────
# X-Frame-Options：禁止 iframe 嵌入（点击劫持防护）
# X-Content-Type-Options：禁止浏览器 MIME 嗅探
# Referrer-Policy：跨站只发 origin，不带 path
# Permissions-Policy：关闭不需要的浏览器特性
# Content-Security-Policy：只允许 self + inline（biz/index.html 用了内联脚本）
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options        "SAMEORIGIN" always;
add_header Referrer-Policy        "strict-origin-when-cross-origin" always;
add_header Permissions-Policy     "camera=(), microphone=(self), geolocation=(), interest-cohort=()" always;
add_header Cross-Origin-Opener-Policy   "same-origin" always;
add_header Cross-Origin-Resource-Policy "same-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' fonts.googleapis.com; font-src 'self' fonts.gstatic.com data:; img-src 'self' data: blob: https:; connect-src 'self' https: wss:; frame-ancestors 'self';" always;

# gzip
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_proxied any;
gzip_comp_level 5;
gzip_types
    text/plain
    text/css
    text/javascript
    text/xml
    application/javascript
    application/json
    application/xml
    application/xml+rss
    application/manifest+json
    image/svg+xml;

# 上传大小（capture/file/commit 文件可能较大；S3 直传时这里只跑 commit metadata）
client_max_body_size 50M;

# ─── 静态资源：路径分级缓存 ──────────────────────────────────────────
# /(mydow|static)/*.{ext} 命中文件名带 hash → immutable 1 年
#                          否则 → 30 天 + must-revalidate
location ~* ^/(mydow|static)/.*\.(js|css|png|jpg|jpeg|gif|svg|webp|ico|woff2?|ttf|map)$ {
    proxy_pass http://mydow_app;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Request-ID $request_id;

    if ($is_hashed_asset = 1) {
        # 带 hash 的版本化资源：1 年 immutable
        add_header Cache-Control "public, max-age=31536000, immutable" always;
    }
    if ($is_hashed_asset = 0) {
        # 未带 hash 的资源：30 天 + revalidate
        add_header Cache-Control "public, max-age=2592000, must-revalidate" always;
    }

    # CORS for fonts (some browsers require this on cross-origin font loads)
    add_header Access-Control-Allow-Origin "*" always;
}

# ─── HTML 文档（index.html / biz/index.html / spa）：no-cache ─────────
# 防止 demo 期间 HTML 被 CDN 缓存导致旧版 SPA 残留
location ~* \.(html?|json)$ {
    proxy_pass http://mydow_app;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Request-ID $request_id;

    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
}

# ─── SSE：禁 buffering + 24h read timeout ─────────────────────────────
# /api/v1/notifications/stream  PRD10 §15
# /api/v1/ai/conversations/{id}/messages/stream  PRD10 §11
# /api/v1/ai/messages/{id}/stream  PRD10 §11
location ~ ^/api/v1/(notifications/stream|ai/(conversations/[^/]+/)?messages?/[^/]+/stream|ai/messages/[^/]+/stream)$ {
    proxy_pass http://mydow_app;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Request-ID $request_id;

    # SSE-critical settings
    proxy_buffering    off;
    proxy_cache        off;
    proxy_read_timeout 24h;
    proxy_send_timeout 24h;
    chunked_transfer_encoding on;
    add_header X-Accel-Buffering "no" always;
}

# ─── WebSocket（IDE 老路径 + 未来扩展）──────────────────────────────
location ~ ^/(ws|api/sessions/[^/]+/ws)$ {
    proxy_pass http://mydow_app;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 1h;
    proxy_send_timeout 1h;
}

# ─── 限流：auth / AI / search（PRD10 §29） ──────────────────────────
location ~ ^/api/v1/(auth/login|auth/register|demo/login)$ {
    limit_req zone=auth_zone burst=5 nodelay;
    limit_req_status 429;

    proxy_pass http://mydow_app;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Request-ID $request_id;
}

location ~ ^/api/v1/ai/conversations/[^/]+/messages(/stream)?$ {
    limit_req zone=ai_zone burst=10 nodelay;
    limit_req_status 429;

    proxy_pass http://mydow_app;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Request-ID $request_id;

    # AI 请求可能流式 / 长响应：放宽 buffering（仅对 stream 路径，普通 POST 走默认）
    proxy_buffering    off;
    proxy_read_timeout 24h;
}

location ~ ^/api/v1/search {
    limit_req zone=search_zone burst=30 nodelay;
    limit_req_status 429;

    proxy_pass http://mydow_app;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Request-ID $request_id;
}

# ─── 健康检查 / ready 检查（不带 access_log，便于 LB 直接接） ────────
location = /health {
    access_log off;
    proxy_pass http://mydow_app/health;
    proxy_set_header Host $host;
}

location = /ready {
    access_log off;
    proxy_pass http://mydow_app/ready;
    proxy_set_header Host $host;
}

# ─── 默认：转发到 FastAPI ─────────────────────────────────────────────
location / {
    proxy_pass http://mydow_app;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Request-ID $request_id;

    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_read_timeout 60s;
    proxy_send_timeout 60s;
}
