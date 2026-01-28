"""Real Aider Coder integration - wraps the actual aider Coder class."""

import sys
import os
from pathlib import Path
from typing import Any, List, Dict
from agent_os.core.interfaces import CodingCapability
from agent_os.core.types import RuntimeContext

# Add aider to path
aider_path = Path(__file__).parent.parent.parent.parent / "aider" / "aider"
if str(aider_path) not in sys.path:
    sys.path.insert(0, str(aider_path))

from aider.coders import Coder
from aider.models import Model
from aider.io import InputOutput
from aider.repo import GitRepo
from aider.args import get_parser


class AiderCoderIntegration(CodingCapability):
    """Real integration with aider's Coder class."""

    def __init__(self, workspace_root: str, model_name: str = "openai/DeepSeek-V3.1",
                 output_queue=None, event_loop=None):
        self.workspace_root = Path(workspace_root).resolve()
        self.model_name = model_name
        self.coder = None
        self.io = None
        self._output_queue = output_queue
        self._event_loop = event_loop
        self._ws_io = None  # WebSocketIO instance for confirm_ask

    async def initialize(self):
        """Initialize the aider Coder instance."""
        import os
        import shutil

        # Change to workspace directory BEFORE creating Coder
        self.original_cwd = os.getcwd()
        os.chdir(str(self.workspace_root))
        print(f"[DEBUG] Changed to workspace for Coder creation: {os.getcwd()}")

        # Initialize WebSocketIO if queue and loop are provided
        if self._output_queue and self._event_loop:
            from agent_os.server.websocket_io import WebSocketIO
            self._ws_io = WebSocketIO(
                output_queue=self._output_queue,
                loop=self._event_loop,
                pretty=True
            )
            print(f"[DEBUG] WebSocketIO initialized for Aider")

        # Initialize toolkit for this workspace
        await self._setup_toolkit()

        # Create a minimal IO object for non-interactive use
        import io

        class WebIO:
            """Custom IO for web use."""

            def __init__(self, parent_integration):
                self.output_buffer = []
                self.tool_errors_list = []  # Renamed to avoid conflict with method
                self.user_input_history = []
                self.pretty = True  # Required by aider
                self.placeholder = None
                self.encoding = "utf-8"  # Required by aider
                self._parent = parent_integration  # Reference to parent AiderCoderIntegration

            def tool_output(self, msg="", bold=False):
                if msg:  # Only append if there's a message
                    self.output_buffer.append(("tool", msg))

            def tool_error(self, msg="", bold=False):
                if msg:
                    self.tool_errors_list.append(msg)
                    self.output_buffer.append(("error", msg))

            def tool_warning(self, msg="", bold=False):
                if msg:
                    self.output_buffer.append(("warning", msg))

            def get_input(self, *args, **kwargs):
                # This should not be called in web mode
                return ""

            def user_input(self, inp, log_only=False):
                self.user_input_history.append(inp)

            def add_to_input_history(self, inp):
                """Add input to history."""
                self.user_input_history.append(inp)

            def confirm_ask(self, question, default="y", subject="", explicit_yes=False):
                """Ask user for confirmation via WebSocket."""
                # If we have a WebSocketIO instance, use it
                if self._parent._ws_io:
                    return self._parent._ws_io.confirm_ask(
                        question=question,
                        default=default,
                        subject=subject,
                        explicit_yes=explicit_yes
                    )
                # Otherwise, auto-confirm for backward compatibility
                return default == "y" or default == "yes"

            def offer_url(self, *args, **kwargs):
                pass

            # Required methods for aider Coder
            def llm_started(self):
                """Called when LLM starts processing."""
                pass

            def llm_response(self, **kwargs):
                """Called with LLM response."""
                pass

            def get_file_content(self, filename):
                """Get file content - simplified version."""
                try:
                    with open(filename, "r", encoding=self.encoding) as f:
                        return f.read()
                except Exception as e:
                    return f"Error reading file: {e}"

            def read_text(self, filename):
                """Read text file content."""
                return self.get_file_content(filename)

            def write_text(self, filename, content):
                """Write text file content."""
                try:
                    with open(filename, "w", encoding=self.encoding) as f:
                        f.write(content)
                    return True
                except Exception as e:
                    self.tool_error(f"Error writing file {filename}: {e}")
                    return False

            def rule(self):
                """Print a separator line."""
                pass

            def autocomplete(self, *args, **kwargs):
                """Autocomplete handler."""
                return []

            # LLM history methods
            def log_llm_history(self, role, content):
                """Log LLM history."""
                pass

            def get_llm_history_messages(self):
                """Get LLM history messages."""
                return []

            # Chat history methods
            def write_chat_history(self, text):
                """Write to chat history."""
                pass

            # User input methods
            def read_image(self, filename):
                """Read image file."""
                return None

            def is_dumb_terminal(self):
                """Check if terminal is dumb."""
                return True

            # Output display methods (needed by aider)
            def assistant_output(self, content, pretty=None):
                """Display assistant output."""
                if content:
                    self.output_buffer.append(("assistant", content))

            def ai_output(self, content):
                """Display AI output."""
                if content:
                    self.output_buffer.append(("ai", content))

        self.io = WebIO(self)

        # Initialize git repo if not exists
        git_dname = None
        try:
            repo = GitRepo(
                self.io,
                [],
                git_dname,
                fnames=str(self.workspace_root)
            )
        except Exception as e:
            # No git repo, that's ok
            print(f"[DEBUG] No git repo: {e}")
            repo = None

        # Create model with environment variables for API key and base URL
        import os

        # Set OpenAI environment variables for aider
        api_key = os.getenv("API_KEY")
        base_url = os.getenv("BASE_URL")

        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            print(f"[DEBUG] Set OPENAI_API_KEY from environment")
        if base_url:
            os.environ["OPENAI_API_BASE"] = base_url
            print(f"[DEBUG] Set OPENAI_API_BASE from environment: {base_url}")

        main_model = Model(self.model_name)

        # Create coder
        try:
            # Chinese system prompt for better language alignment
            chinese_system_prompt = """你是一个专业的编程助手。请遵循以下规则：

1. **语言要求**：必须使用中文与用户交流，包括所有回复、说明和注释。

2. **删除文件的方法**：
   当用户要求删除文件时，必须使用以下Python代码来删除：
   ```python
   import os
   files_to_delete = ["test.txt", "websocket_test.txt"]  # 根据用户要求修改
   for f in files_to_delete:
       if os.path.exists(f):
           os.remove(f)
   ```
   **重要**：不要让用户手动执行命令，直接创建并执行删除文件的Python代码。

3. **其他文件操作**：
   - 创建文件：直接使用文件编辑功能创建
   - 修改文件：直接编辑文件内容
   - 所有操作都要自动执行，不要询问确认

4. **回复风格**：
   - 简洁明了
   - 重点说明做了什么，结果如何
   - 避免冗长的技术细节
   - 例如："已删除2个测试文件：test.txt 和 websocket_test.txt"

## 🛠️ 工具箱 (Toolkit) 使用指南

你拥有一个强大的工具箱，位于 `toolkit/` 目录。

### 1. 如何发现工具
在开始任务前，如果需要外部数据或特殊功能，请先运行以下命令查看可用工具：
```
/run python toolkit/manager.py list
```

或者查看工具摘要：
```
/read toolkit/tools_summary.md
```

### 2. 如何调用工具
- **本地 Skill**: 直接运行 `/run python toolkit/bins/<script_name>.py <args>`
  例如：`/run python toolkit/bins/weather.py Beijing`

- **MCP 工具**: 运行 `/run python toolkit/bridge.py <server_name> call <tool_name> '<json_args>'`
  例如：`/run python toolkit/bridge.py filesystem call read_file '{{"path": "test.txt"}}'`

### 3. 如何扩展工具 (CRUD)
- **创建新工具**:
  1. 运行 `/run python toolkit/manager.py new <skill_name>` 创建模板
  2. 编辑 `toolkit/bins/<skill_name>.py` 实现功能
  3. 运行 `/run python toolkit/manager.py refresh` 注册工具

- **修改工具**: 直接编辑 `toolkit/bins/` 下的代码，修改即时生效（热插拔）

- **删除工具**: 删除 `toolkit/bins/xxx.py`，然后运行 `/run python toolkit/manager.py refresh`

### 4. 工具使用原则
⚠️ **重要**：所有的外部数据获取、复杂计算、网络请求，请优先检查是否有现成工具，或者编写新工具来实现，而不是依靠你自己的训练数据猜测。

例如：
- 需要天气信息？使用 `weather.py` 工具
- 需要数学计算？使用 `calculator.py` 工具
- 需要文件操作？检查是否有 MCP filesystem 工具
- 需要网络搜索？检查是否配置了搜索工具

如果没有合适的工具，你可以快速创建一个！"""

            self.coder = Coder.create(
                main_model=main_model,
                io=self.io,
                repo=repo,
                fnames=[],
                edit_format=None,  # Let model decide
                auto_commits=False,
                show_diffs=False,
                verbose=False,
                stream=False,
                use_git=False,  # Don't require git
            )

            # Set custom system message
            if hasattr(self.coder, 'system_prompt'):
                self.coder.system_prompt = chinese_system_prompt
            elif hasattr(self.coder, 'gpt_prompts'):
                if hasattr(self.coder.gpt_prompts, 'main_system'):
                    self.coder.gpt_prompts.main_system = chinese_system_prompt

            # Set Chinese as preferred language in coder attributes
            if hasattr(self.coder, 'commit_prompt'):
                self.coder.commit_prompt = chinese_system_prompt
            print(f"[DEBUG] Aider Coder initialized for {self.workspace_root}")

            # Initialize aider_edited_files if not present
            if not hasattr(self.coder, 'aider_edited_files') or self.coder.aider_edited_files is None:
                self.coder.aider_edited_files = set()
                print(f"[DEBUG] Initialized aider_edited_files as empty set")

            # Initialize reflected_message if not present
            if not hasattr(self.coder, 'reflected_message'):
                self.coder.reflected_message = None
                print(f"[DEBUG] Initialized reflected_message as None")

            # Initialize other missing attributes
            if not hasattr(self.coder, 'num_migrations'):
                self.coder.num_migrations = 0

            if not hasattr(self.coder, 'num_reflections'):
                self.coder.num_reflections = 0
        except Exception as e:
            print(f"[ERROR] Failed to initialize Coder: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Aider doesn't use tool definitions in the traditional sense."""
        # Return empty list - aider handles everything internally
        return []

    async def apply_edit(self, ctx: RuntimeContext, instructions: str) -> str:
        """Not used - we use run_message instead."""
        return await self.run_message(ctx, instructions)

    async def execute_tool(self, ctx: RuntimeContext, name: str, args: Dict[str, Any]) -> str:
        """Not used - we use run_message instead."""
        return await self.run_message(ctx, args.get("instructions", ""))

    async def run_message(self, ctx: RuntimeContext, message: str) -> str:
        """Run a message through the aider Coder.

        This is the main entry point - instead of using individual tools,
        we pass the user's message to aider's Coder which will:
        1. Understand the request
        2. Read relevant files
        3. Make modifications
        4. Show diffs
        5. Return results
        """
        if not self.coder:
            await self.initialize()

        # Clear previous output
        self.io.output_buffer = []

        try:
            # Run the message through aider
            import os
            print(f"[DEBUG] Running message through aider: {message[:50]}...")
            print(f"[DEBUG] Coder type: {type(self.coder)}")
            print(f"[DEBUG] Current directory: {os.getcwd()}")

            # Coder was already created in workspace directory, so we don't need to change

            try:
                # Try to use send_message directly (more reliable than run_one)
                print("[DEBUG] Calling send_message directly...")
                try:
                    msg_count = 0
                    for msg in self.coder.send_message(message):
                        msg_count += 1
                        if msg_count % 10 == 0:
                            print(f"[DEBUG] Processed {msg_count} messages...")
                    print(f"[DEBUG] send_message completed with {msg_count} messages")
                except Exception as e:
                    print(f"[DEBUG] send_message error: {e}")
                    import traceback
                    traceback.print_exc()
                    raise

                print(f"[DEBUG] Message processing completed")
            except Exception as e:
                print(f"[DEBUG] Message processing error: {e}")
                raise

            # Collect output
            output_parts = []
            for msg_type, msg in self.io.output_buffer:
                if msg_type == "tool":
                    output_parts.append(msg)
                elif msg_type == "error":
                    output_parts.append(f"Error: {msg}")
                elif msg_type == "warning":
                    output_parts.append(f"Warning: {msg}")
                elif msg_type == "assistant":
                    output_parts.append(msg)
                elif msg_type == "ai":
                    output_parts.append(msg)

            # Add coder's response
            if hasattr(self.coder, 'partial_response_content'):
                response = self.coder.partial_response_content or ""
                if response:
                    output_parts.append(response)

            result = "\n".join(output_parts)

            print(f"[DEBUG] Aider response length: {len(result)}")
            return result or "Command completed"

        except Exception as e:
            error_msg = f"Error running aider: {e}"
            print(f"[ERROR] {error_msg}")
            import traceback
            tb = traceback.format_exc()
            print(f"[ERROR] Full traceback:\n{tb}")
            # Write to file for debugging
            with open("aider_error.log", "a", encoding="utf-8") as f:
                f.write(f"\n\n{error_msg}\n{tb}\n")
            return error_msg

    def get_file_changes(self) -> List[Dict[str, Any]]:
        """Get list of files that were modified."""
        changes = []

        if self.coder and hasattr(self.coder, 'abs_fnames'):
            for fname in self.coder.abs_fnames:
                changes.append({
                    "path": fname,
                    "action": "modified"
                })

        return changes

    def add_file(self, filepath: str):
        """Add a file to the coder context."""
        if self.coder:
            abs_path = str(Path(filepath).resolve())
            if abs_path not in self.coder.abs_fnames:
                self.coder.abs_fnames.add(abs_path)

    def get_chat_history(self) -> List[Dict[str, Any]]:
        """Get the chat history."""
        if not self.coder:
            return []

        history = []

        # Done messages (completed turns)
        for msg in self.coder.done_messages:
            history.append({
                "role": msg.get("role"),
                "content": msg.get("content", "")
            })

        # Current messages (incomplete turn)
        for msg in self.coder.cur_messages:
            history.append({
                "role": msg.get("role"),
                "content": msg.get("content", "")
            })

        return history

    async def _setup_toolkit(self):
        """Setup toolkit directory for this workspace"""
        import shutil
        import os

        toolkit_dir = self.workspace_root / "toolkit"
        # 修正路径：global_toolkit 在项目根目录，不在 src 目录
        global_toolkit = Path(__file__).parent.parent.parent.parent.parent / "global_toolkit"

        # Check if global_toolkit exists
        if not global_toolkit.exists():
            print(f"[WARNING] Global toolkit not found at {global_toolkit}")
            return

        # If toolkit doesn't exist in workspace, copy from global
        if not toolkit_dir.exists():
            print(f"[DEBUG] Copying toolkit from {global_toolkit} to {toolkit_dir}")
            shutil.copytree(global_toolkit, toolkit_dir)
            print(f"[DEBUG] Toolkit initialized at {toolkit_dir}")
        else:
            print(f"[DEBUG] Toolkit already exists at {toolkit_dir}")

        # Run refresh to generate registry and summary
        try:
            manager_path = toolkit_dir / "manager.py"
            if manager_path.exists():
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(manager_path), "refresh"],
                    cwd=str(toolkit_dir),
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print(f"[DEBUG] Toolkit registry refreshed")
                else:
                    print(f"[WARNING] Failed to refresh toolkit: {result.stderr}")
        except Exception as e:
            print(f"[WARNING] Failed to refresh toolkit: {e}")


__all__ = ["AiderCoderIntegration"]
