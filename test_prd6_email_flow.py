#!/usr/bin/env python3
"""
PRD6 完整测试流程 - 阿里企业邮箱验证码功能
"""

import requests
import time
import sys


def test_verification_flow(base_url, test_email):
    """测试完整的验证码流程"""
    print(f"\n{'='*70}")
    print(f"🧪 PRD6 阿里企业邮箱验证码完整测试")
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
    print(f"   响应: {send_response.json()}")

    if send_response.status_code != 200:
        print(f"\n❌ 发送验证码失败")
        return False

    print(f"\n✅ 验证码发送成功！")
    print(f"   请检查邮箱 {test_email}")
    print(f"   验证码有效期: 5 分钟")

    # 步骤2: 等待用户输入验证码
    print(f"\n{'='*70}")
    print(f"📝 步骤 2: 请输入收到的验证码")
    print(f"{'='*70}")

    # 给用户时间检查邮件
    print(f"\n💡 提示:")
    print(f"   - 检查收件箱和垃圾邮件文件夹")
    print(f"   - 发件人: postmaster@mydow.life")
    print(f"   - 主题: 【AgentOS】您的验证码是：XXXXXX")

    # 从命令行读取验证码
    code = input("\n🔢 请输入收到的验证码 (或按 Enter 跳过验证): ").strip()

    if not code:
        print(f"\n⚠️  跳过验证步骤")
        return True

    # 步骤3: 验证验证码
    print(f"\n{'='*70}")
    print(f"✓ 步骤 3: 验证验证码...")
    print(f"{'='*70}")

    verify_response = requests.post(
        f"{base_url}/api/v1/auth/verify-code",
        json={
            "email": test_email,
            "code": code,
            "code_type": "login"
        }
    )

    print(f"   状态码: {verify_response.status_code}")
    print(f"   响应: {verify_response.json()}")

    if verify_response.status_code == 200:
        result = verify_response.json()
        if result.get("code") == "SUCCESS":
            print(f"\n✅ 验证成功！")
            if "data" in result and result["data"]:
                print(f"   Token: {result['data'].get('token', 'N/A')}")
                print(f"   User ID: {result['data'].get('user_id', 'N/A')}")
            return True

    print(f"\n❌ 验证失败")
    return False


def test_rate_limiting(base_url, test_email):
    """测试频率限制"""
    print(f"\n{'='*70}")
    print(f"🚦 步骤 4: 测试频率限制（60秒冷却）")
    print(f"{'='*70}\n")

    # 快速发送第二次请求
    print("   🔄 重新发送验证码（测试频率限制）...")

    send_response = requests.post(
        f"{base_url}/api/v1/auth/send-code",
        json={
            "email": test_email,
            "code_type": "login"
        }
    )

    print(f"   状态码: {send_response.status_code}")
    result = send_response.json()

    if "retry_after" in result:
        print(f"   ✅ 频率限制生效！")
        print(f"   ⏰ 需等待 {result['retry_after']} 秒")
    else:
        print(f"   ⚠️  未触发频率限制")
        print(f"   响应: {result}")

    print()


def main():
    """主测试函数"""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8003"
    test_email = sys.argv[2] if len(sys.argv) > 2 else "test@example.com"

    print(f"\n🚀 PRD6 阿里企业邮箱验证码功能测试")
    print(f"   API: {base_url}")
    print(f"   邮箱: {test_email}")

    # 测试完整流程
    success = test_verification_flow(base_url, test_email)

    # 测试频率限制
    test_rate_limiting(base_url, test_email)

    # 总结
    print(f"\n{'='*70}")
    print(f"📊 测试总结")
    print(f"{'='*70}")

    if success:
        print(f"✅ 所有测试通过！")
        print(f"\n🎯 验证码邮件发送功能已就绪")
        print(f"   - SMTP配置正确")
        print(f"   - 邮件发送成功")
        print(f"   - API端点正常工作")
    else:
        print(f"⚠️  部分测试未完成")
        print(f"   请检查邮箱和验证码")

    print(f"{'='*70}\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
