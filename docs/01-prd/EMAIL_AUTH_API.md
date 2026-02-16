# 邮箱验证码注册/登录 API 文档

## 概述

本文档描述了基于邮箱验证码的注册和登录功能。用户可以通过邮箱接收验证码来完成注册和登录，无需记忆复杂的密码。

## 新增端点

### 1. 发送验证码

**端点**: `POST /api/v1/auth/send-code`

**描述**: 向指定邮箱发送6位数字验证码

**请求体**:
```json
{
  "email": "user@example.com",
  "code_type": "login"
}
```

**参数说明**:
- `email`: 用户邮箱地址（必填）
- `code_type`: 验证码类型，可选值: `login`, `bind`, `reset`（必填）

**响应**:
```json
{
  "code": "SUCCESS",
  "message": "If the email exists, a verification code has been sent",
  "data": {
    "expires_in": 300
  }
}
```

**错误响应**:
```json
{
  "code": "RATE_LIMITED",
  "message": "发送过于频繁，请 45 秒后重试",
  "retry_after": 45
}
```

**功能特性**:
- ✅ 频率限制：同一邮箱60秒内只能发送1次
- ✅ 验证码有效期：5分钟（300秒）
- ✅ 安全设计：不透露邮箱是否存在

---

### 2. 邮箱验证码注册

**端点**: `POST /api/v1/auth/register/email`

**描述**: 使用邮箱和验证码注册新账号

**请求体**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "code": "123456"
}
```

**参数说明**:
- `email`: 用户邮箱地址（必填）
- `password`: 设置密码（必填，至少6位）
- `code`: 邮箱收到的6位验证码（必填）

**成功响应** (201 Created):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**错误响应**:
- `400 Bad Request`: 请求参数无效
- `409 Conflict`: 邮箱已注册
- `422 Unprocessable Entity`: 验证码无效或已过期

**功能特性**:
- ✅ 自动生成用户名（从邮箱地址提取）
- ✅ 自动验证邮箱有效性
- ✅ 一次性使用验证码（验证后失效）
- ✅ 返回JWT令牌用于后续API调用

---

### 3. 邮箱验证码登录

**端点**: `POST /api/v1/auth/login/email`

**描述**: 使用邮箱和验证码登录（无需密码）

**请求体**:
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**参数说明**:
- `email`: 用户邮箱地址（必填）
- `code`: 邮箱收到的6位验证码（必填）

**成功响应** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**错误响应**:
- `401 Unauthorized`: 验证码无效或用户不存在
- `422 Unprocessable Entity`: 验证码已过期
- `423 Locked`: 账户已锁定（多次失败）

**功能特性**:
- ✅ 无密码登录（更安全）
- ✅ 自动更新最后登录时间
- ✅ 失败次数限制（5次后锁定30分钟）

---

### 4. 验证码校验

**端点**: `POST /api/v1/auth/verify-code`

**描述**: 验证邮箱验证码是否正确

**请求体**:
```json
{
  "email": "user@example.com",
  "code": "123456",
  "code_type": "login"
}
```

**成功响应**:
```json
{
  "code": "SUCCESS",
  "message": "Verification successful",
  "data": {
    "token": "...",
    "user_id": "..."
  }
}
```

**错误响应**:
- `400 Bad Request`: 验证码无效
- `410 Gone`: 验证码已过期
- `429 Too Many Requests`: 尝试次数过多

---

## 使用流程

### 注册流程

```bash
# 1. 发送验证码
curl -X POST http://localhost:8003/api/v1/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","code_type":"login"}'

# 2. 用户收到验证码（如：123456）

# 3. 使用验证码注册
curl -X POST http://localhost:8003/api/v1/auth/register/email \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","password":"mypassword123","code":"123456"}'
```

### 登录流程

```bash
# 1. 发送验证码
curl -X POST http://localhost:8003/api/v1/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"existinguser@example.com","code_type":"login"}'

# 2. 用户收到验证码（如：654321）

# 3. 使用验证码登录
curl -X POST http://localhost:8003/api/v1/auth/login/email \
  -H "Content-Type: application/json" \
  -d '{"email":"existinguser@example.com","code":"654321"}'
```

---

## 安全机制

### 频率限制

- **邮箱级别**: 同一邮箱60秒内只能发送1次
- **IP级别**: 同一IP 60秒内只能发送1次
- **验证限制**: 每个验证码只能使用1次

### 失败处理

- **最多尝试次数**: 5次
- **锁定时间**: 30分钟
- **错误提示**: 显示剩余尝试次数

### 验证码特性

- **长度**: 6位数字
- **有效期**: 5分钟（300秒）
- **存储**: Redis（带TTL）
- **类型**: 随机生成（10^6 种组合）

---

## 错误码说明

| HTTP状态码 | 错误类型 | 说明 |
|-----------|---------|------|
| 200 | SUCCESS | 操作成功 |
| 201 | CREATED | 注册成功 |
| 400 | BAD_REQUEST | 请求参数错误 |
| 401 | UNAUTHORIZED | 认证失败 |
| 409 | CONFLICT | 邮箱已存在 |
| 422 | UNPROCESSABLE_ENTITY | 验证码无效 |
| 423 | LOCKED | 账户已锁定 |
| 429 | RATE_LIMITED | 频率限制 |
| 500 | INTERNAL_ERROR | 服务器错误 |

---

## 测试工具

### 1. Web界面测试

访问: `http://localhost:8003/static/email-auth.html`

功能:
- 可视化注册/登录界面
- 实时显示API响应
- 自动倒计时功能
- 错误提示

### 2. Python测试脚本

```bash
# 完整流程测试
python test_email_auth_complete.py http://localhost:8003 your-email@example.com
```

### 3. cURL测试

```bash
# 发送验证码
curl -X POST http://localhost:8003/api/v1/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","code_type":"login"}'
```

---

## 邮件模板

### 验证码邮件示例

**主题**: 【MyDow】您的注册验证码：123456

**正文**:
```html
<div style="background:#f7f7f7; padding: 20px;">
    <div style="background:#fff; border-radius:5px; padding:20px; max-width:500px; margin:0 auto;">
        <h3 style="color:#333;">邮箱验证</h3>
        <p>您好！感谢您注册 MyDow。</p>
        <p>您的验证码是：</p>
        <h2 style="color:#007BFF; letter-spacing: 2px;">123456</h2>
        <p style="font-size:12px; color:#999;">验证码 5 分钟内有效，请勿泄露给他人。</p>
    </div>
</div>
```

**发件人**: `postmaster@mydow.life` (MyDow 验证中心)

---

## 技术实现

### 邮件服务
- **SMTP服务器**: smtp.qiye.aliyun.com
- **端口**: 465 (SSL加密)
- **认证**: 客户端专用密码

### 存储
- **验证码存储**: Redis
- **TTL**: 300秒（5分钟）
- **键格式**: `verify_code:{email}:{type}`

### 安全性
- **传输加密**: SSL/TLS
- **密码加密**: bcrypt
- **令牌**: JWT (HS256)
- **频率限制**: Redis + TTL

---

## 常见问题

### Q1: 没有收到验证码邮件？

**A**: 请检查：
1. 垃圾邮件文件夹
2. 邮箱地址是否正确
3. 是否被频率限制（等待60秒）
4. SMTP服务是否正常

### Q2: 验证码提示已过期？

**A**: 验证码有效期为5分钟，过期后需要重新获取。

### Q3: 验证码输错多次被锁定？

**A**: 账户会在5次失败后锁定30分钟。等待30分钟后自动解锁。

### Q4: 如何更换绑定的邮箱？

**A**: 目前需要联系管理员。后续版本会支持邮箱换绑功能。

---

## 更新日志

### v1.0 (2026-02-16)
- ✅ 新增邮箱验证码注册功能
- ✅ 新增邮箱验证码登录功能
- ✅ 新增发送验证码API
- ✅ 新增验证码校验API
- ✅ 集成阿里企业邮箱SMTP
- ✅ 添加频率限制和安全机制
- ✅ 创建Web测试界面
- ✅ 完善API文档

---

## 相关文档

- [PRD5 验证码功能设计](./PRD5-AUTH-SMTP-VERIFICATION.md)
- [PRD6 阿里企业邮箱配置](./PRD6-ALIYUN-EMAIL-CONFIG.md)
- [API完整参考](../09-api/COMPLETE_API_REFERENCE.md)

---

**维护者**: AgentOS Team
**最后更新**: 2026-02-16
