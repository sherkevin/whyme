# PRD6: 阿里企业邮箱配置与验证码邮件发送

**日期**: 2026-02-16
**状态**: 实施中
**优先级**: P0 (生产环境必需)

## 📋 需求概述

配置阿里云企业邮箱SMTP服务，实现用户注册/登录时的验证码邮件发送功能。

## 🎯 核心目标

- [x] 实现真实的验证码邮件发送
- [x] 支持所有用户邮箱类型（QQ、Gmail、163等）
- [x] 生产环境稳定可靠
- [x] 邮件送达率高，避免进入垃圾箱

## 📧 邮箱账号信息

**邮箱域名**: mydow.life
**管理员账号**: postmaster@mydow.life
**邮箱访问地址**: https://qiye.aliyun.com
**客户端专用密码**: rBWj0Mjvu6hrPU2r

## 🔧 技术配置方案

### 第一步：获取客户端专用密码 ✅

阿里云企业邮箱出于安全考虑，第三方程序（如Python代码）登录必须使用独立的授权码。

**授权码**: `rBWj0Mjvu6hrPU2r`
**说明**: 这不是网页登录密码，而是专门用于客户端应用的授权码。

### 第二步：SMTP配置参数

```yaml
# SMTP服务器配置
SMTP_HOST: smtp.qiye.aliyun.com
SMTP_PORT: 465  # 必须使用465 (SSL加密)
SMTP_USER: postmaster@mydow.life
SMTP_PASS: rBWj0Mjvu6hrPU2r
SMTP_FROM: postmaster@mydow.life
SENDER_NAME: MyDow 验证中心
SMTP_USE_TLS: true  # SSL加密
```

**关键说明**:
- **端口必须是465**: 阿里云ECS服务器封禁了25端口
- **使用SSL加密**: 确保邮件传输安全
- **不要改用25端口**: 本地可以，但服务器上会超时

### 第三步：Python邮件发送代码

```python
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from email.header import Header

# --- 配置区域 ---
SMTP_HOST = "smtp.qiye.aliyun.com"
SMTP_PORT = 465  # 必须使用 465 (SSL加密)
SENDER_EMAIL = "postmaster@mydow.life"
SENDER_PASSWORD = "rBWj0Mjvu6hrPU2r"  # 客户端专用密码
SENDER_NAME = "MyDow 验证中心"

def send_verification_email(receiver_email, code):
    """
    发送验证码邮件的主函数
    :param receiver_email: 用户接收邮箱 (如 user@qq.com)
    :param code: 验证码 (如 "123456")
    :return: True 成功, False 失败
    """
    try:
        # 1. 构建邮件内容 (HTML格式)
        subject = f"【MyDow】您的注册验证码：{code}"

        html_content = f"""
        <div style="background:#f7f7f7; padding: 20px;">
            <div style="background:#fff; border-radius:5px; padding:20px; max-width:500px; margin:0 auto;">
                <h3 style="color:#333;">邮箱验证</h3>
                <p>您好！感谢您注册 MyDow。</p>
                <p>您的验证码是：</p>
                <h2 style="color:#007BFF; letter-spacing: 2px;">{code}</h2>
                <p style="font-size:12px; color:#999;">验证码 5 分钟内有效，请勿泄露给他人。</p>
            </div>
        </div>
        """

        message = MIMEText(html_content, 'html', 'utf-8')
        message['From'] = formataddr((Header(SENDER_NAME, 'utf-8').encode(), SENDER_EMAIL))
        message['To'] = receiver_email
        message['Subject'] = Header(subject, 'utf-8')

        # 2. 连接服务器并发送
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [receiver_email], message.as_string())
        server.quit()

        print(f"✅ [成功] 验证码 {code} 已发送至 {receiver_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("❌ [认证失败] 请检查账号和客户端专用密码")
        return False
    except Exception as e:
        print(f"❌ [发送失败] 错误详情: {e}")
        return False
```

## 🚀 部署与上线注意事项

### 1. 端口配置

**必须使用465端口**:
- ✅ 使用 `SMTP_PORT = 465` (SSL加密)
- ❌ 不要使用 `25` 端口（会被阿里云ECS封禁）
- ❌ 不要使用 `587` 端口（可能不稳定）

**原因**: 阿里云所有云服务器（ECS）出于防垃圾邮件策略，默认封禁了TCP 25端口的出方向流量。

### 2. 发送频率控制（防封号）

**企业邮箱的限制**:
- 本质是"办公沟通"，不是"高并发通知系统"
- 短时间大量发信会触发风控，导致临时禁止发信

**建议配置**:
```python
# 已实现的频率限制
- 邮箱级别: 60秒内只能发送1次
- IP级别: 60秒内只能发送1次
- 验证码有效期: 5分钟（300秒）
- 失败次数限制: 最多5次，超过锁定30分钟
```

**防刷策略**:
- ✅ 前端按钮冷却时间（60秒）
- ✅ 后端Redis频率限制（已实现）
- ✅ 图形验证码（建议添加）

### 3. SPF记录配置（防垃圾箱）

**必须添加SPF记录**，防止邮件进入垃圾箱：

```
记录类型: TXT
主机记录: @
记录值: v=spf1 include:spf.qiye.aliyun.com -all
```

**配置位置**: 阿里云域名解析 → 添加记录

**重要性**:
- 没有SPF记录，发给Gmail/Outlook的邮件容易进垃圾箱
- SPF记录告诉收件服务器，这个IP有权代表mydow.life发邮件

### 4. 邮件模板优化

**当前模板特点**:
- ✅ HTML格式，美观专业
- ✅ 包含品牌标识 "MyDow"
- ✅ 验证码突出显示
- ✅ 安全提示（5分钟有效、请勿泄露）

**可改进项**:
- 添加Logo图片
- 添加取消订阅链接
- 添加客服联系方式
- 响应式设计（移动端优化）

## 📊 集成到现有系统

### 修改文件清单

1. **`.env` 配置文件**
   ```bash
   SMTP_HOST=smtp.qiye.aliyun.com
   SMTP_PORT=465
   SMTP_USER=postmaster@mydow.life
   SMTP_PASS=rBWj0Mjvu6hrPU2r
   SMTP_FROM=postmaster@mydow.life
   SMTP_USE_TLS=true
   ```

2. **`src/agent_os/auth/mailer.py`**
   - 更新SMTP连接逻辑
   - 使用465端口和SSL加密
   - 更新邮件模板

3. **测试验证**
   - 本地测试发送成功
   - 服务器部署测试
   - 不同邮箱类型测试（QQ、Gmail、163）

## ✅ 验收标准

### 功能验收

- [ ] 能够成功发送验证码到用户邮箱
- [ ] 邮件格式正确，显示品牌名称
- [ ] 验证码在5分钟内有效
- [ ] 频率限制正常工作（60秒冷却）
- [ ] 失败次数限制正常（5次锁定30分钟）

### 兼容性测试

- [ ] QQ邮箱能正常接收
- [ ] Gmail能正常接收
- [ ] 163邮箱能正常接收
- [ ] Outlook能正常接收

### 安全性检查

- [ ] 客户端专用密码不在代码中硬编码
- [ ] .env文件不提交到Git
- [ ] 邮件内容不包含敏感信息
- [ ] 验证码存储在Redis，有TTL

## 🔍 故障排查

### 常见错误及解决方案

**错误1: 认证失败**
```
smtplib.SMTPAuthenticationError
```
**解决**: 检查是否使用了客户端专用密码，而不是登录密码

**错误2: 连接超时**
```
timeout: timed out
```
**解决**: 确认使用465端口，不是25端口

**错误3: SSL错误**
```
SSL wrong version number
```
**解决**: 确认使用 `SMTP_SSL` 而不是 `SMTP`

**错误4: 邮件进垃圾箱**
```
邮件发送成功，但用户在垃圾箱中找到
```
**解决**: 添加SPF记录，检查发件人名称

## 📝 实施记录

### 2026-02-16 开始实施

- [x] 创建PRD文档
- [ ] 更新.env配置文件
- [ ] 测试邮件发送功能
- [ ] 验证不同邮箱类型
- [ ] 配置SPF记录（待DNS管理员操作）
- [ ] 生产环境部署测试

## 🎯 下一步计划

1. **立即执行**:
   - 更新.env配置
   - 测试邮件发送

2. **DNS配置**:
   - 添加SPF记录
   - 验证MX记录

3. **监控和优化**:
   - 监控邮件发送成功率
   - 优化邮件模板
   - 调整发送频率限制

---

**文档维护**: 本文档记录了阿里企业邮箱的完整配置过程，供后续维护和升级参考。
