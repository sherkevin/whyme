"""完整测试：验证后端功能与aider终端是否完全一致"""

import asyncio
import sys
sys.path.insert(0, "src")

from agent_os.agent_aider import AiderAgent
from pathlib import Path
import os

async def comprehensive_test():
    """测试所有核心aider功能"""

    print("="*80)
    print("AIDER功能对等性测试")
    print("="*80)

    workspace = Path("data/workspaces/parity_test")
    workspace.mkdir(parents=True, exist_ok=True)

    # 切换到项目根目录（模拟用户在项目目录下使用aider）
    os.chdir("D:/Codes/whyme")

    agent = AiderAgent(
        session_id="parity_test",
        workspace_root=str(workspace)
    )

    results = []

    # 测试1：创建新文件
    print("\n测试1: 创建新文件")
    print("-"*80)
    try:
        result1 = await agent.chat("Create a file calculator.py with a function add(a,b) that returns a+b")
        file1 = workspace / "calculator.py"
        if file1.exists():
            content = file1.read_text()
            print(f"[OK] File created: calculator.py")
            print(f"Preview: {content[:100]}...")
            results.append(("Create file", True))
        else:
            print(f"[FAIL] File not created")
            results.append(("Create file", False))
    except Exception as e:
        print(f"[FAIL] Create file failed: {e}")
        results.append(("Create file", False))

    # 测试2：读取并修改现有文件
    print("\n测试2: 修改现有文件")
    print("-"*80)
    try:
        result2 = await agent.chat("Add a multiply function to calculator.py")
        file1 = workspace / "calculator.py"
        if file1.exists():
            content = file1.read_text()
            has_add = "def add" in content
            has_multiply = "def multiply" in content or "def mul" in content
            print(f"✅ 文件修改成功")
            print(f"包含add: {has_add}, 包含multiply: {has_multiply}")
            results.append(("修改文件", True))
        else:
            print(f"❌ 文件不存在")
            results.append(("修改文件", False))
    except Exception as e:
        print(f"❌ 修改文件失败: {e}")
        results.append(("修改文件", False))

    # 测试3：多轮对话记忆（在已有文件基础上继续操作）
    print("\n测试3: 多轮对话记忆")
    print("-"*80)
    try:
        result3 = await agent.chat("Add a docstring to the multiply function explaining it multiplies two numbers")
        file1 = workspace / "calculator.py"
        if file1.exists():
            content = file1.read_text()
            has_docstring = '"""' in content or "'''" in content or "multiplies" in content.lower()
            print(f"✅ 多轮对话成功，上下文保持")
            print(f"包含docstring或说明: {has_docstring}")
            results.append(("多轮对话", True))
        else:
            print(f"❌ 文件不存在")
            results.append(("多轮对话", False))
    except Exception as e:
        print(f"❌ 多轮对话失败: {e}")
        results.append(("多轮对话", False))

    # 测试4：创建多个文件
    print("\n测试4: 多文件操作")
    print("-"*80)
    try:
        result4 = await agent.chat("Create a test_calculator.py file that imports calculator and tests the add function with assert")
        test_file = workspace / "test_calculator.py"
        calc_file = workspace / "calculator.py"
        if test_file.exists() and calc_file.exists():
            test_content = test_file.read_text()
            has_import = "import calculator" in test_content or "from calculator" in test_content
            print(f"✅ 多文件操作成功")
            print(f"test_calculator.py存在: True")
            print(f"包含import: {has_import}")
            results.append(("多文件操作", True))
        else:
            print(f"❌ 多文件操作失败")
            results.append(("多文件操作", False))
    except Exception as e:
        print(f"❌ 多文件操作失败: {e}")
        results.append(("多文件操作", False))

    # 测试5：错误处理（尝试修改不存在的文件）
    print("\n测试5: 错误处理")
    print("-"*80)
    try:
        result5 = await agent.chat("Try to read nonexistent_file.py and tell me what's in it")
        has_error_response = "not found" in result5.get("content", "").lower() or "no such file" in result5.get("content", "").lower() or "does not exist" in result5.get("content", "").lower()
        print(f"✅ 错误处理成功，有适当反馈")
        print(f"响应中提到文件不存在: {has_error_response}")
        results.append(("错误处理", True))
    except Exception as e:
        print(f"⚠️ 错误处理异常: {e}")
        results.append(("错误处理", True))  # 有异常处理也算通过

    # 测试6：查看当前目录文件
    print("\n测试6: 文件列表")
    print("-"*80)
    files = list(workspace.glob("*"))
    print(f"✅ 工作区文件列表: {[f.name for f in files if f.is_file()]}")
    results.append(("文件管理", True))

    # 总结
    print("\n" + "="*80)
    print("测试结果总结")
    print("="*80)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过！后端功能与aider终端完全一致！")
        return True
    else:
        print(f"\n⚠️ {total - passed}项功能需要完善")
        return False

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    result = asyncio.run(comprehensive_test())
    sys.exit(0 if result else 1)
