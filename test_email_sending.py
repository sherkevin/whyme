#!/usr/bin/env python3
"""阿里企业邮箱邮件发送测试脚本"""

import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from email.header import Header

# 添加项目路径
sys.path.insert(0, '/root/whyme/src')

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
                <hr style="margin:20px 0; border:none; border-top:1px solid #eee;">
                <p style="font-size:12px; color:#999;">
                    如果这不是您的操作，请忽略此邮件。<br>
                    本邮件由系统自动发送，请勿回复。
                </p>
            </div>
        </div>
        """

        message = MIMEText(html_content, 'html', 'utf-8')
        # 格式化发件人头，显示中文名
        message['From'] = formataddr((Header(SENDER_NAME, 'utf-8').encode(), SENDER_EMAIL))
        message['To'] = receiver_email
        message['Subject'] = Header(subject, 'utf-8')

        # 2. 连接服务器并发送
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context)

        # 登录
        server.login(SENDER_EMAIL, SENDER_PASSWORD)

        # 发送
        server.sendmail(SENDER_EMAIL, [receiver_email], message.as_string())

        # 退出
        server.quit()

        print(f"✅ [成功] 验证码 {code} 已发送至 {receiver_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("❌ [认证失败] 请检查：1.账号是否正确 2.是否使用了'客户端专用密码'而不是登录密码")
        return False
    except Exception as e:
        print(f"❌ [发送失败] 错误详情: {e}")
        return False


def test_email_sending(test_email):
    """测试邮件发送功能"""
    print(f"\n{'='*60}")
    print(f"🧪 阿里企业邮箱邮件发送测试")
    print(f"{'='*60}")
    print(f"\n📧 测试邮箱: {test_email}")
    print(f"📮 SMTP服务器: {SMTP_HOST}:{SMTP_PORT}")
    print(f"👤 发件账号: {SENDER_EMAIL}")
    print(f"\n{'='*60}\n")

    # 生成测试验证码
    import random
    test_code = "".join([str(random.randint(0, 9)) for _ in range(6)])

    print(f"🔢 生成的测试验证码: {test_code}")
    print(f"\n正在发送...")

    # 发送邮件
    success = send_verification_email(test_email, test_code)

    print(f"\n{'='*60}")
    if success:
        print(f"✅ 测试成功！请检查邮箱 {test_email}")
        print(f"📝 验证码是: {test_code}")
        print(f"\n💡 提示:")
        print(f"   - 如果没有收到，请检查垃圾邮件文件夹")
        print(f"   - 验证码 5 分钟内有效")
        print(f"   - 来自: {SENDER_EMAIL}")
    else:
        print(f"❌ 测试失败，请检查配置")
    print(f"{'='*60}\n")

    return success


if __name__ == "__main__":
    # 测试邮箱 - 请改为你的实际邮箱地址
    test_email = "your-email@example.com"  # ⚠️ 修改为你的测试邮箱

    if len(sys.argv) > 1:
        test_email = sys.argv[1]

    if test_email == "your-email@example.com":
        print("⚠️  请先修改脚本中的 test_email 为你的实际邮箱地址")
        print("   或者在命令行指定: python test_email_sending.py your-email@qq.com")
        sys.exit(1)

    success = test_email_sending(test_email)
    sys.exit(0 if success else 1)
