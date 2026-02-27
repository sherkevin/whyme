#!/usr/bin/env python3
"""Test script for LLM-based summary and tags generation.

Usage:
    python test_llm_summary.py
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from agent_os.agent.llm_processor import (
    generate_summary_llm,
    generate_tags_llm,
    generate_summary_and_tags_llm,
)


async def test_summary():
    """Test LLM summary generation."""
    print("=" * 50)
    print("Testing LLM Summary Generation...")
    print("=" * 50)

    content = """
    今日团队会议讨论了以下几个重要事项：

    1. 项目进度更新：前端重构项目已经完成 80%，预计下周可以进入测试阶段。
       后端 API 接口已经全部完成，正在进行性能优化。

    2. 人员安排：张三将负责前端测试工作，李四将协助进行后端性能调优。
       王五将继续完善文档工作。

    3. 下周计划：完成剩余的前端页面开发，开始集成测试。
       准备产品上线前的各项准备工作，包括服务器配置、域名备案等。

    4. 技术债务：需要重构用户认证模块，当前的实现存在性能瓶颈。
       建议引入 Redis 缓存来提升会话管理效率。
    """

    try:
        summary = await generate_summary_llm(content)
        print(f"\nGenerated Summary:\n{summary}")
        print("\n✅ Summary generation successful!")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tags():
    """Test LLM tags generation."""
    print("\n" + "=" * 50)
    print("Testing LLM Tags Generation...")
    print("=" * 50)

    content = """
    Python 是一种高级编程语言，支持多种编程范式，
    包括面向对象、函数式编程等。Python 的设计哲学强调代码的可读性，
    使用缩进来表示代码块而不是大括号。

    主要特点包括：
    - 简洁清晰的语法
    - 动态类型系统
    - 自动内存管理（垃圾回收）
    - 丰富的标准库和第三方包
    """

    try:
        tags = await generate_tags_llm(content)
        print(f"\nGenerated Tags: {tags}")
        print("\n✅ Tags generation successful!")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_combined():
    """Test combined summary and tags generation."""
    print("\n" + "=" * 50)
    print("Testing Combined Summary + Tags Generation...")
    print("=" * 50)

    content = """
    关于 AI 技术发展的思考

    近年来，人工智能技术取得了飞速发展。从深度学习到大型语言模型，
    从图像识别到自然语言处理，AI 正在改变我们的工作和生活。

    关键趋势：
    1. 大模型能力不断增强，GPT-4、Claude 等模型展现出惊人的理解和推理能力
    2. 多模态成为主流，模型可以同时处理文本、图像、音频等多种输入
    3. 应用场景扩展，从客服、写作助手到编程辅助、医疗诊断
    4. 伦理和安全问题受到更多关注，包括偏见、隐私、就业影响等

    挑战与机遇并存。我们需要在技术创新和社会责任之间找到平衡。
    """

    try:
        result = await generate_summary_and_tags_llm(content, max_length=200, max_tags=5)
        print(f"\nGenerated Summary:\n{result.get('summary', '')}")
        print(f"\nGenerated Tags: {result.get('tags', [])}")
        print("\n✅ Combined generation successful!")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_llm_connection():
    """Test basic LLM connection."""
    print("=" * 50)
    print("Testing LLM Connection...")
    print("=" * 50)

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("BASE_URL")

    print(f"\nAPI Key: {api_key[:15]}...{api_key[-4:] if api_key else 'N/A'}")
    print(f"Base URL: {base_url}")

    try:
        from agent_os.agent.llm_processor import get_llm_provider

        llm = get_llm_provider()
        print(f"Model: {llm.model}")

        response = await llm.complete(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Reply 'OK' to confirm connection."},
            ],
        )

        print(f"\nLLM Response: {response.get('content', '')}")
        print("\n✅ LLM connection successful!")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n🚀 LLM Summary & Tags Generation Test Suite\n")

    # Check for API key
    if not os.getenv("DEEPSEEK_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("❌ ERROR: No API key found. Please set DEEPSEEK_API_KEY or OPENAI_API_KEY in .env file")
        return

    results = []

    # Run tests
    results.append(("LLM Connection", await test_llm_connection()))
    results.append(("Summary Generation", await test_summary()))
    results.append(("Tags Generation", await test_tags()))
    results.append(("Combined Generation", await test_combined()))

    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")

    all_passed = all(passed for _, passed in results)
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
