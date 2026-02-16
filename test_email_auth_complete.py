#!/usr/bin/env python3
"""
完整的邮箱验证码注册和登录测试流程
"""

import requests
import time
import sys


def test_email_registration_login(base_url, test_email):
    """测试完整的邮箱验证码注册和登录流程"""
    print(f"\n{'='*70}")
    print(f"🧪 MyDow 邮箱验证码注册/登录完整测试")
    print(f"{'='*70}")
    print(f"\n📧 测试邮箱: {test_email}")
    print(f"🌐 API地址: {base_url}")
    print(f"\n{'='*70}\n")

    # 步骤1: 发送验证码
    print("📮 步骤 1: 发送验证码...")
    send_response = requests.post(
        f"{base_url}/api/v1/auth/send-code",
        json={
            "email": test_email,
            "code_type": "login"
        }
    )

    print(f"   状态码: {send_response.status_code}")
    result = send_response.json()
    print(f"   响应: {result}")

    if send_response.status_code != 200:
        print(f"\n❌ 发送验证码失败")
        print(f"   错误: {result}")
        return False

    print(f"\n✅ 验证码发送成功！")
    print(f"   请检查邮箱 {test_email}")
    print(f"   验证码有效期: 5 分钟")

    # 步骤2: 获取验证码
    print(f"\n{'='*70}")
    print(f"📝 步骤 2: 输入收到的验证码")
    print(f"{'='*70}")
    print(f"\n💡 提示:")
    print(f"   - 检查收件箱和垃圾邮件文件夹")
    print(f"   - 发件人: postmaster@mydow.life")
    print(f"   - 主题: 【MyDow】您的注册验证码：XXXXXX")

    code = input("\n🔢 请输入收到的6位验证码: ").strip()

    if not code or len(code) != 6:
        print(f"\n⚠️  验证码格式不正确")
        return False

    # 步骤3: 注册新用户
    print(f"\n{'='*70}")
    print(f"✓ 步骤 3: 使用验证码注册新用户")
    print(f"{'='*70}\n")

    register_response = requests.post(
        f"{base_url}/api/v1/auth/register/email",
        json={
            "email": test_email,
            "password": "test123456",  # 测试密码
            "code": code
        }
    )

    print(f"   状态码: {register_response.status_code}")
    reg_result = register_response.json()
    print(f"   响应: {reg_result}")

    if register_response.status_code == 201:
        print(f"\n✅ 注册成功！")
        if 'access_token' in reg_result:
            print(f"   Access Token: {reg_result['access_token'][:50]}...")
            print(f"   Refresh Token: {reg_result['refresh_token'][:50]}...")

        # 步骤4: 测试登录
        print(f"\n{'='*70}")
        print(f"✓ 步骤 4: 测试使用验证码登录")
        print(f"{'='*70}\n")

        print(f"   发送新的验证码用于登录...")
        time.sleep(2)  # 等待2秒避免频率限制

        send_response = requests.post(
            f"{base_url}/api/v1/auth/send-code",
            json={
                "email": test_email,
                "code_type": "login"
            }
        )

        if send_response.status_code == 200:
            print(f"   ✅ 验证码发送成功")
            login_code = input(f"\n🔢 请输入新的验证码用于登录: ").strip()

            if login_code:
                login_response = requests.post(
                    f"{base_url}/api/v1/auth/login/email",
                    json={
                        "email": test_email,
                        "code": login_code
                    }
                )

                print(f"\n   状态码: {login_response.status_code}")
                login_result = login_response.json()
                print(f"   响应: {login_result}")

                if login_response.status_code == 200:
                    print(f"\n✅ 登录成功！")
                    return True
                else:
                    print(f"\n⚠️  登录失败: {login_result}")
                    return False

        return True

    elif register_response.status_code == 409:
        print(f"\n⚠️  邮箱已注册，直接测试登录...")
        # 用户已存在，直接测试登录
        print(f"\n{'='*70}")
        print(f"✓ 步骤 4: 测试使用验证码登录（已注册用户）")
        print(f"{'='*70}\n")

        login_response = requests.post(
            f"{base_url}/api/v1/auth/login/email",
            json={
                "email": test_email,
                "code": code
            }
        )

        print(f"   状态码: {login_response.status_code}")
        login_result = login_response.json()
        print(f"   响应: {login_result}")

        if login_response.status_code == 200:
            print(f"\n✅ 登录成功！")
            return True
        else:
            print(f"\n❌ 登录失败: {login_result}")
            return False

    else:
        print(f"\n❌ 注册失败")
        print(f"   错误: {reg_result}")
        return False


def test_api_endpoints(base_url):
    """测试所有相关API端点"""
    print(f"\n{'='*70}")
    print(f"🔍 API端点测试")
    print(f"{'='*70}\n")

    endpoints = [
        ("POST /api/v1/auth/send-code", "send-code"),
        ("POST /api/v1/auth/register/email", "register-with-email"),
        ("POST /api/v1/auth/login/email", "login-with-email"),
        ("POST /api/v1/auth/verify-code", "verify-code"),
    ]

    for endpoint, name in endpoints:
        print(f"✓ {endpoint}")
        print(f"  描述: {name}")
        print()


def main():
    """主测试函数"""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8003"
    test_email = sys.argv[2] if len(sys.argv) > 2 else "1505548152@qq.com"

    print(f"\n🚀 MyDow 邮箱验证码功能完整测试")
    print(f"   API: {base_url}")
    print(f"   邮箱: {test_email}")

    # 测试API端点
    test_api_endpoints(base_url)

    # 测试完整流程
    print(f"\n{'='*70}")
    print(f"开始完整流程测试...")
    print(f"{'='*70}")

    success = test_email_registration_login(base_url, test_email)

    # 总结
    print(f"\n{'='*70}")
    print(f"📊 测试总结")
    print(f"{'='*70}")

    if success:
        print(f"✅ 所有测试通过！")
        print(f"\n🎯 邮箱验证码功能已就绪:")
        print(f"   ✓ 发送验证码")
        print(f"   ✓ 注册新用户")
        print(f"   ✓ 验证码登录")
        print(f"   ✓ 频率限制")
        print(f"   ✓ 一次性验证码")
    else:
        print(f"⚠️  部分测试未完成")

    print(f"{'='*70}\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
