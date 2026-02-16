# 📧 前端开发指南 - 邮箱验证码注册/登录

**版本**: v1.0
**更新日期**: 2026-02-16
**目标读者**: 前端开发人员

---

## 🎯 快速开始

### 新功能概述

我们新增了**邮箱验证码注册和登录**功能，用户可以使用邮箱接收验证码来完成注册和登录，无需记忆复杂的密码。

### 核心优势

- ✅ **用户体验更好**: 无需记忆密码
- ✅ **安全性更高**: 验证码一次性使用
- ✅ **支持所有邮箱**: QQ、Gmail、163等所有邮箱
- ✅ **即时到达**: 2秒内收到验证码

---

## 📡 API端点

### 1. 发送验证码

```http
POST /api/v1/auth/send-code
Content-Type: application/json

{
  "email": "user@example.com",
  "code_type": "login"
}
```

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

**频率限制响应** (429):
```json
{
  "code": "RATE_LIMITED",
  "message": "发送过于频繁，请 45 秒后重试",
  "retry_after": 45
}
```

**前端处理建议**:
- 发送后立即禁用"发送验证码"按钮
- 显示60秒倒计时
- 倒计时结束后重新启用按钮

---

### 2. 邮箱验证码注册 ⭐

```http
POST /api/v1/auth/register/email
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "code": "123456"
}
```

**成功响应** (201):
```json
{
  "access_token": "eyJ0eXAiOiJ...",
  "refresh_token": "eyJ0eXAiOiJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**错误响应**:

邮箱已存在 (409):
```json
{
  "detail": "Email already registered"
}
```
→ 前端提示："该邮箱已注册，请直接登录"

验证码无效 (422):
```json
{
  "detail": "Invalid or expired verification code"
}
```
→ 前端提示："验证码无效或已过期，请重新获取"

---

### 3. 邮箱验证码登录 ⭐

```http
POST /api/v1/auth/login/email
Content-Type: application/json

{
  "email": "user@example.com",
  "code": "123456"
}
```

**成功响应** (200):
```json
{
  "access_token": "eyJ0eXAiOiJ...",
  "refresh_token": "eyJ0eXAiOiJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**错误响应**:

用户不存在 (401):
```json
{
  "detail": "User not found. Please register first."
}
```
→ 前端提示："用户不存在，请先注册"

验证码无效 (401):
```json
{
  "detail": "Invalid or expired verification code"
}
```
→ 前端提示："验证码错误，请重新输入"

账户已锁定 (423):
```json
{
  "detail": "Account temporarily locked. Please try again later"
}
```
→ 前端提示："账户已锁定，请30分钟后再试"

---

## 🎨 前端实现示例

### 注册页面

```jsx
import { useState } from 'react';

function RegisterPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  // 发送验证码
  const sendCode = async () => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setMessage('请输入有效的邮箱地址');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('http://localhost:8003/api/v1/auth/send-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          code_type: 'login'
        })
      });

      const data = await response.json();

      if (response.ok) {
        setMessage('验证码已发送！请检查邮箱');
        // 开始60秒倒计时
        setCountdown(60);
        const timer = setInterval(() => {
          setCountdown(prev => {
            if (prev <= 1) {
              clearInterval(timer);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      } else if (response.status === 429) {
        setMessage(`发送过于频繁，请 ${data.retry_after} 秒后重试`);
      } else {
        setMessage(data.detail || '发送失败');
      }
    } catch (error) {
      setMessage('网络错误，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 注册
  const register = async () => {
    if (!email || !password || !code) {
      setMessage('请填写所有必填项');
      return;
    }

    if (code.length !== 6) {
      setMessage('验证码必须是6位数字');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('http://localhost:8003/api/v1/auth/register/email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          password: password,
          code: code
        })
      });

      const data = await response.json();

      if (response.ok) {
        setMessage('🎉 注册成功！正在登录...');
        // 保存token
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);

        // 跳转到首页
        setTimeout(() => {
          window.location.href = '/dashboard';
        }, 1000);
      } else if (response.status === 409) {
        setMessage('该邮箱已注册，请直接登录');
      } else {
        setMessage(data.detail || '注册失败');
      }
    } catch (error) {
      setMessage('网络错误，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="register-page">
      <h1>注册账号</h1>

      {/* 邮箱输入 */}
      <div className="form-group">
        <label>邮箱地址</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="请输入邮箱"
          disabled={loading}
        />
      </div>

      {/* 密码输入 */}
      <div className="form-group">
        <label>设置密码</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="至少6位字符"
          disabled={loading}
        />
      </div>

      {/* 验证码输入 */}
      <div className="form-group">
        <label>验证码</label>
        <div className="code-input">
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="6位验证码"
            maxLength={6}
            disabled={loading}
          />
          <button
            onClick={sendCode}
            disabled={loading || countdown > 0}
          >
            {countdown > 0 ? `重新发送 (${countdown}s)` : '发送验证码'}
          </button>
        </div>
      </div>

      {/* 提交按钮 */}
      <button
        onClick={register}
        disabled={loading}
        className="submit-btn"
      >
        {loading ? '注册中...' : '注册账号'}
      </button>

      {/* 提示信息 */}
      {message && (
        <div className={`alert ${message.includes('成功') ? 'success' : 'error'}`}>
          {message}
        </div>
      )}

      {/* 切换到登录 */}
      <p className="switch-link">
        已有账号？<a href="/login">使用验证码登录</a>
      </p>
    </div>
  );
}
```

---

### 登录页面

```jsx
import { useState } from 'react';

function LoginPage() {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  // 发送验证码
  const sendCode = async () => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setMessage('请输入有效的邮箱地址');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('http://localhost:8003/api/v1/auth/send-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          code_type: 'login'
        })
      });

      const data = await response.json();

      if (response.ok) {
        setMessage('验证码已发送！请检查邮箱');
        setCountdown(60);
        // 开始倒计时...
      } else if (response.status === 429) {
        setMessage(`发送过于频繁，请 ${data.retry_after} 秒后重试`);
      } else {
        setMessage(data.detail || '发送失败');
      }
    } catch (error) {
      setMessage('网络错误，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 登录
  const login = async () => {
    if (!email || !code) {
      setMessage('请填写邮箱和验证码');
      return;
    }

    if (code.length !== 6) {
      setMessage('验证码必须是6位数字');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('http://localhost:8003/api/v1/auth/login/email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          code: code
        })
      });

      const data = await response.json();

      if (response.ok) {
        setMessage('🎉 登录成功！');

        // 保存token
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);

        // 跳转到首页
        setTimeout(() => {
          window.location.href = '/dashboard';
        }, 500);
      } else {
        setMessage(data.detail || '登录失败');
      }
    } catch (error) {
      setMessage('网络错误，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <h1>邮箱验证码登录</h1>

      {/* 邮箱输入 */}
      <div className="form-group">
        <label>邮箱地址</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="请输入邮箱"
          disabled={loading}
        />
      </div>

      {/* 验证码输入 */}
      <div className="form-group">
        <label>验证码</label>
        <div className="code-input">
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="6位验证码"
            maxLength={6}
            disabled={loading}
          />
          <button
            onClick={sendCode}
            disabled={loading || countdown > 0}
          >
            {countdown > 0 ? `重新发送 (${countdown}s)` : '发送验证码'}
          </button>
        </div>
      </div>

      {/* 提交按钮 */}
      <button
        onClick={login}
        disabled={loading}
        className="submit-btn"
      >
        {loading ? '登录中...' : '登录'}
      </button>

      {/* 提示信息 */}
      {message && (
        <div className={`alert ${message.includes('成功') ? 'success' : 'error'}`}>
          {message}
        </div>
      )}

      {/* 切换到注册 */}
      <p className="switch-link">
        还没有账号？<a href="/register">注册账号</a>
      </p>
    </div>
  );
}
```

---

## 🎯 UI/UX 最佳实践

### 1. 表单验证

**邮箱验证**:
```javascript
const isValidEmail = (email) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};
```

**验证码验证**:
```javascript
const isValidCode = (code) => {
  return /^\d{6}$/.test(code);
};
```

### 2. 倒计时显示

```javascript
const CountdownTimer = ({ seconds, onComplete }) => {
  const [remaining, setRemaining] = useState(seconds);

  useEffect(() => {
    if (remaining > 0) {
      const timer = setInterval(() => {
        setRemaining(prev => {
          if (prev <= 1) {
            clearInterval(timer);
            onComplete();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [remaining, onComplete]);

  return (
    <span className="countdown">
      重新发送 ({remaining}s)
    </span>
  );
};
```

### 3. 错误处理

```javascript
const handleError = (error) => {
  switch (error.status) {
    case 400:
      return '请求参数错误';
    case 409:
      return '该邮箱已注册';
    case 422:
      return '验证码无效或已过期';
    case 429:
      return '发送过于频繁，请稍后重试';
    case 423:
      return '账户已锁定，请30分钟后再试';
    default:
      return '网络错误，请稍后重试';
  }
};
```

### 4. Token管理

```javascript
// 保存认证令
const saveTokens = (accessToken, refreshToken) => {
  localStorage.setItem('access_token', accessToken);
  localStorage.setItem('refresh_token', refreshToken);
};

// 获取访问令牌
const getAccessToken = () => {
  return localStorage.getItem('access_token');
};

// 刷新令牌
const refreshAccessToken = async () => {
  const refreshToken = localStorage.getItem('refresh_token');

  const response = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });

  const data = await response.json();

  if (response.ok) {
    saveTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } else {
    // Token刷新失败，清除本地存储并跳转登录
    localStorage.clear();
    window.location.href = '/login';
  }
};

// Axios拦截器（自动添加token）
axios.interceptors.request.use(config => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

axios.interceptors.response.use(
  response => response,
  async (error) => {
    if (error.response?.status === 401) {
      // 401错误，尝试刷新token
      try {
        const newToken = await refreshAccessToken();
        error.config.headers.Authorization = `Bearer ${newToken}`;
        return axios.request(error.config);
      } catch {
        // 刷新失败，跳转登录
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
```

---

## 📱 组件示例

### 发送验证码按钮

```jsx
function SendCodeButton({ email, codeType = 'login' }) {
  const [countdown, setCountdown] = useState(0);
  const [sending, setSending] = useState(false);

  const handleSend = async () => {
    setSending(true);

    try {
      const response = await fetch('/api/v1/auth/send-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code_type: codeType })
      });

      const data = await response.json();

      if (response.ok) {
        // 成功发送，开始倒计时
        setCountdown(60);
        startCountdown();
      } else if (response.status === 429) {
        alert(`发送过于频繁，请 ${data.retry_after} 秒后重试`);
      } else {
        alert(data.detail || '发送失败');
      }
    } catch (error) {
      alert('网络错误，请稍后重试');
    } finally {
      setSending(false);
    }
  };

  const startCountdown = () => {
    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  return (
    <button
      onClick={handleSend}
      disabled={sending || countdown > 0}
      className="send-code-btn"
    >
      {sending ? '发送中...' :
       countdown > 0 ? `重新发送 (${countdown}s)` :
       '发送验证码'}
    </button>
  );
}
```

---

## 🔐 安全建议

### 1. Token存储

**推荐**: 使用HttpOnly Cookie
```javascript
// 后端设置Cookie
response.set_cookie(
    'access_token',
    token,
    httponly=True,
    secure=True,  // HTTPS only
    samesite='strict'
);
```

### 2. 验证码显示

```javascript
// 安全显示：自动填充样式
<code
  className="verification-code"
  style={{
    letterSpacing: '4px',
    fontFamily: 'monospace',
    fontSize: '24px',
    fontWeight: 'bold'
  }}
>
  {code}
</code>
```

### 3. 输入限制

```javascript
// 验证码输入框
<input
  type="text"
  inputMode="numeric"
  pattern="\d*"
  maxLength={6}
  placeholder="123456"
  required
/>
```

---

## 📊 响应示例

### 成功场景

**1. 发送验证码成功**:
```json
{
  "code": "SUCCESS",
  "message": "If the email exists, a verification code has been sent",
  "data": {
    "expires_in": 300
  }
}
```
→ 前端显示："验证码已发送，请查收邮箱"

**2. 注册成功**:
```json
{
  "access_token": "eyJ0eXAiOiJ...",
  "refresh_token": "eyJ0eXAiOiJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```
→ 前端显示："注册成功！"，保存token，跳转首页

**3. 登录成功**:
```json
{
  "access_token": "eyJ0eXAiOiJ...",
  "refresh_token": "eyJ0eXAiOiJ...",
  "token_type": "bearer",
  "expires_in": 1800}
```
→ 前端显示："登录成功！"，保存token，跳转首页

### 错误场景

**1. 邮箱已存在**:
```json
{
  "detail": "Email already registered"
}
```
→ 前端显示："该邮箱已注册，请使用邮箱登录"

**2. 验证码过期**:
```json
{
  "detail": "Verification code has expired. Please request a new one."
}
```
→ 前端显示："验证码已过期，请重新获取"

**3. 频率限制**:
```json
{
  "code": "RATE_LIMITED",
  "message": "发送过于频繁，请 45 秒后重试",
  "retry_after": 45
}
```
→ 前端显示："发送过于频繁，请 45 秒后重试"，倒计时45秒

**4. 验证码错误**:
```json
{
  "detail": "Invalid code, 4 attempts remaining"
}
```
→ 前端显示："验证码错误，还有4次机会"

**5. 账户锁定**:
```json
{
  "detail": "Account temporarily locked. Please try again later"
}
```
→ 前端显示："账户已锁定，请30分钟后再试"

---

## 🎨 设计建议

### 1. 页面布局

```
┌─────────────────────────────┐
│                                 │
│        邮箱验证码登录          │
│                                 │
│  ┌───────────────────────────┐ │
│  │ 📧 邮箱                  │ │
│  │ [输入框]                 │ │
│  └───────────────────────────┘ │
│                                 │
│  ┌───────────────────────────┐ │
│  │ 🔢 验证码  [发送验证码]    │ │
│  │ [输入框]  [倒计时 60s]     │ │
│  └───────────────────────────┘ │
│                                 │
│  [           登录               ] │
│                                 │
│  还没有账号？[注册账号]        │
└─────────────────────────────┘
```

### 2. 交互流程

**注册流程**:
```
输入邮箱 → 输入密码 →
点击"发送验证码" →
(倒计时60秒) →
查收邮件输入验证码 →
点击"注册" →
成功！
```

**登录流程**:
```
输入邮箱 →
点击"发送验证码" →
(倒计时60秒) →
查收邮件输入验证码 →
点击"登录" →
成功！
```

### 3. 状态管理

```javascript
// 状态定义
const [email, setEmail] = useState('');
const [password, setPassword] = useState('');
const [code, setCode] = useState('');
const [countdown, setCountdown] = useState(0);
const [loading, setLoading] = useState(false);
const [error, setError] = useState('');
const [success, setSuccess] = useState(false);

// 验证邮箱格式
const validateEmail = (email) => {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
};

// 验证码格式
const validateCode = (code) => {
  return /^\d{6}$/.test(code);
};
```

---

## 📚 相关文档

- [完整API文档](./COMPLETE_API_REFERENCE.md)
- [邮箱配置文档](../01-prd/PRD6-ALIYUN-EMAIL-CONFIG.md)
- [实施总结](../01-prd/PRD6-IMPLEMENTATION-SUMMARY.md)

---

## 🆘 获取帮助

### 技术支持

- **API问题**: 查看 API 文档
- **配置问题**: 查看配置文档
- **集成问题**: 查看代码示例

### 测试工具

- **Web测试**: http://localhost:8003/static/email-auth.html
- **Python测试**: `python test_email_auth_complete.py`

---

**更新日期**: 2026-02-16
**维护者**: AgentOS Team
**版本**: v1.0
