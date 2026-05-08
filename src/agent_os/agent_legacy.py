"""Agent implementation with Skills system integration."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.conversations import ConversationRepository
from agent_os.core.config import Config, load_config
from agent_os.core.interfaces import (
    AgentCallbackHandler,
    CodingCapability,
    ContextManager,
    LLMProvider,
    MemoryProvider,
)
from agent_os.core.types import RuntimeContext
from agent_os.tools import ToolRegistryImpl


class Agent:
    """AI Agent with Skills system support.

    The Agent can dynamically switch roles by applying Skills,
    which modify the system prompt, available tools, and parameters.
    """

    def __init__(
        self,
        config: Config,
        db_session: AsyncSession | None = None,
    ) -> None:
        """Initialize the agent with configuration.

        Args:
            config: Agent configuration
            db_session: Optional database session for conversation persistence
        """
        self.config = config
        self.llm: LLMProvider | None = None
        self.coding: CodingCapability | None = None
        self.memory: MemoryProvider | None = None
        self.context: ContextManager | None = None
        self.tool_registry = ToolRegistryImpl()
        self.conversation_history: list[dict[str, Any]] = []
        self.db_session = db_session
        self.conversation_repo = ConversationRepository() if db_session else None

        # Skills system
        self.skill_manager: Any = None  # Will be initialized lazily
        self.active_skill: str | None = None
        self.agent_state: dict[str, Any] = {}

    @classmethod
    def from_config_file(
        cls,
        config_path: str = "config.yaml",
        db_session: AsyncSession | None = None,
    ) -> Agent:
        """Create an agent from a configuration file.

        Args:
            config_path: Path to configuration file
            db_session: Optional database session for conversation persistence

        Returns:
            Initialized Agent instance
        """
        config = load_config(config_path)
        return cls(config, db_session=db_session)

    async def initialize(self) -> None:
        """Initialize all components."""
        await self.initialize_llm()
        await self.initialize_coding()
        await self.initialize_memory()
        await self.initialize_context()

    async def load_conversation_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 50,
    ) -> None:
        """Load conversation history from database.

        Args:
            user_id: User identifier
            session_id: Session identifier
            limit: Maximum number of messages to load
        """
        if not self.db_session or not self.conversation_repo:
            return

        try:
            conversations = await self.conversation_repo.get_conversation_history(
                session=self.db_session,
                user_id=int(user_id),
                session_id=session_id,
                limit=limit,
            )

            # Clear current history and load from database
            self.conversation_history = []
            for conv in conversations:
                msg = {"role": conv.role, "content": conv.content}
                if conv.tool_calls:
                    msg["tool_calls"] = conv.tool_calls
                self.conversation_history.append(msg)

        except Exception as e:
            print(f"Failed to load conversation history: {e}")
            # Continue with empty history
        
    async def initialize_memory(self) -> None:
        """Initialize memory provider."""
        if self.config.memory:
            from agent_os.core.config import instantiate
            self.memory = instantiate(self.config.memory.provider, **self.config.memory.config)

    async def initialize_context(self) -> None:
        """Initialize context manager."""
        if self.config.context:
            from agent_os.core.config import instantiate
            self.context = instantiate(self.config.context.provider, **self.config.context.config)

    def initialize_skills(self, skills_directory: str | Path | None = None) -> None:
        """Initialize the skills manager.

        Args:
            skills_directory: Optional path to skills directory.
                            Defaults to src/agent_os/skills/library
        """
        from agent_os.skills import SkillManager

        if skills_directory is None:
            # Default to the built-in skills library
            skills_directory = Path(__file__).parent / "skills" / "library"

        self.skill_manager = SkillManager(skills_directory)
        print(f"Initialized {self.skill_manager.skill_count} skills")

    async def initialize_coding(self) -> None:
        """Initialize coding capability."""
        if self.config.coding:
            from agent_os.core.config import instantiate
            self.coding = instantiate(self.config.coding.provider)
            
            # Register coding tool
            async def edit_code(instructions: str) -> str:
                """Edit the code in the workspace based on instructions."""
                # We need context here. Using the last context or a global one is tricky.
                # Ideally context is passed to the tool.
                # For now, we will use a hack or assume context is managed globally/thread-local?
                # Or we bind the tool to the current request context when we create it.
                # Let's assume we pass a runtime context via closure if we register it per request.
                # But here we register once.
                # We'll need a way to access the active context.
                pass 
            
            # Note: We can't easily register a tool that needs 'ctx' if 'ctx' varies per request
            # without some context variable.
            # We'll skip auto-registration for now and handle it in chat loop.

    async def initialize_llm(self) -> None:
        """Initialize the LLM provider from config."""
        if self.config.llm is None:
            raise ValueError("LLM configuration is missing from config.yaml")

        from agent_os.core.config import instantiate

        # Get API key and base from environment or config
        api_key = self.config.llm.get_api_key()
        api_base = self.config.llm.get_api_base()

        # Merge config with environment values
        llm_config = dict(self.config.llm.config)
        if api_key:
            llm_config["api_key"] = api_key
        if api_base:
            llm_config["api_base"] = api_base

        self.llm = instantiate(
            self.config.llm.provider,
            **llm_config,
        )

    def register_tool(self, func: callable) -> None:
        """Register a Python function as a tool."""
        asyncio.create_task(self.tool_registry.register_python_tool(func))

    async def chat(
        self,
        message: str,
        user_id: str = "default_user",
        session_id: str | None = None,
        callbacks: list[AgentCallbackHandler] | None = None,
    ) -> dict[str, Any]:
        """Send a message and get a response from the LLM."""
        if self.llm is None:
            await self.initialize_llm()

        if session_id is None:
            session_id = str(uuid.uuid4())

        callbacks = callbacks or []

        # Debug: Check if coding is initialized
        with open("debug_agent.log", "a", encoding="utf-8") as f:
            f.write(f"\n[{__import__('datetime').datetime.now()}] Chat called\n")
            f.write(f"  self.coding is None: {self.coding is None}\n")
            f.write(f"  self.config.coding: {self.config.coding}\n")

        # Create runtime context
        ctx = RuntimeContext(
            session_id=session_id,
            user_id=user_id,
            trace_id=str(uuid.uuid4()),
        )

        # Add user message to history
        user_msg = {"role": "user", "content": message}
        self.conversation_history.append(user_msg)

        # Persist to database if session available
        if self.db_session and self.conversation_repo:
            try:
                await self.conversation_repo.add_message(
                    session=self.db_session,
                    user_id=int(user_id),
                    session_id=session_id,
                    role="user",
                    content=message,
                )
                await self.db_session.commit()
            except Exception as e:
                print(f"Failed to persist user message: {e}")
                await self.db_session.rollback()

        # Log thinking
        for cb in callbacks:
            await cb.on_log(f"Processing message: {message[:50]}...")

        # Search memory
        if self.memory:
            try:
                # Basic memory retrieval based on the latest message
                memories = await self.memory.search(ctx, message)
                if memories:
                    memory_content = "\n- ".join([m["content"] for m in memories])
                    # Add as a system message (transient, so we might want to track it differently 
                    # but for now adding to history is simplest, though it grows context)
                    # Alternatively, specific "system" block for memory
                    
                    # Check if we already have a memory block? No.
                    self.conversation_history.append({
                        "role": "system",
                        "content": f"Relevant past memories:\n- {memory_content}"
                    })
                    for cb in callbacks:
                        await cb.on_log(f"Retrieved {len(memories)} relevant memories.")
            except Exception as e:
                # Log usage warning but continue
                print(f"Memory retrieval failed: {e}")

        # Get tool definitions
        tool_definitions = await self.tool_registry.get_definitions()
        
        # Add coding capability tools if available
        if self.coding:
            try:
                coding_tools = await self.coding.get_tool_definitions()
                tool_definitions.extend(coding_tools)
            except NotImplementedError:
                # Fallback for old implementations
                tool_definitions.append({
                    "type": "function",
                    "function": {
                        "name": "edit_code",
                        "description": "Edit the code in the workspace based on instructions.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "instructions": {
                                    "type": "string",
                                    "description": "Instructions for editing the code."
                                }
                            },
                            "required": ["instructions"]
                        }
                    }
                })

        # Context Management
        messages_to_send = self.conversation_history

        # Add system prompt if tools are available
        if tool_definitions:
            # Check if there's already a system message at the beginning
            has_system_prompt = messages_to_send and messages_to_send[0].get("role") == "system"

            # Log to file for debugging
            with open("debug_agent.log", "a", encoding="utf-8") as f:
                f.write(f"\n[{__import__('datetime').datetime.now()}] Tool definitions available: {len(tool_definitions)}\n")
                f.write(f"Has system prompt: {has_system_prompt}\n")
                f.write(f"Conversation history length: {len(messages_to_send)}\n")

            if not has_system_prompt:
                # Insert system prompt at the beginning
                system_prompt = {
                    "role": "system",
                    "content": (
                        "You are a coding assistant with access to tools that can read files, write files, "
                        "run commands, and list directories. When the user asks you to create, modify, or view code, "
                        "you MUST use the available tools instead of just describing what you would do. "
                        "Always read existing files before modifying them to understand the current code. "
                        "IMPORTANT: Never claim to have modified, created, or done something without actually "
                        "calling the corresponding tool. Always use tools first, then report what you did. "
                        "Do not say 'I have modified' or 'I have created' unless you actually called the tool."
                    )
                }
                messages_to_send = [system_prompt] + messages_to_send

                with open("debug_agent.log", "a", encoding="utf-8") as f:
                    f.write(f"System prompt injected: {system_prompt['content'][:100]}...\n")

        if self.context:
            try:
                # Get max tokens from config or default
                max_tokens = self.config.context.config.get("max_tokens", 8000)
                messages_to_send, report = await self.context.process(messages_to_send, max_tokens)
                if report and report.pruned_count > 0:
                     for cb in callbacks:
                        await cb.on_log(f"Context pruned: removed {report.pruned_count} messages.")
            except Exception as e:
                print(f"Context processing failed: {e}")

        # Get completion from LLM
        print(f"[DEBUG] Calling LLM with {len(tool_definitions)} tools")
        response = await self.llm.complete(
            messages=messages_to_send,
            tools=tool_definitions if tool_definitions else None,
        )
        print(f"[DEBUG] LLM response keys: {list(response.keys())}")
        print(f"[DEBUG] LLM response content: {response.get('content', '')[:200]}")
        print(f"[DEBUG] Tool calls in response: {'tool_calls' in response}")

        # Add assistant response to history
        content = response.get("content", "")
        assistant_msg = {"role": "assistant", "content": content}
        self.conversation_history.append(assistant_msg)

        # Persist assistant message to database
        if self.db_session and self.conversation_repo:
            try:
                await self.conversation_repo.add_message(
                    session=self.db_session,
                    user_id=int(user_id),
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    tool_calls=response.get("tool_calls"),
                    model=response.get("model"),
                )
                await self.db_session.commit()
            except Exception as e:
                print(f"Failed to persist assistant message: {e}")
                await self.db_session.rollback()

        if content:
            for cb in callbacks:
                await cb.on_agent_response(content)

        # Handle tool calls if present
        if "tool_calls" in response and response["tool_calls"]:
            print(f"[DEBUG] Processing {len(response['tool_calls'])} tool calls")
            for tool_call in response["tool_calls"]:
                function_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]
                # Parse arguments (they come as JSON string)
                import json
                try:
                    args = json.loads(arguments) if isinstance(arguments, str) else arguments
                except json.JSONDecodeError:
                    args = {"raw": arguments}

                # Notify tool start
                for cb in callbacks:
                    await cb.on_tool_start(function_name, args)

                # Execute tool
                try:
                    if function_name == "edit_code" and self.coding:
                         # Legacy path
                        result = await self.coding.apply_edit(ctx, args["instructions"])
                    elif self.coding and hasattr(self.coding, "execute_tool") and function_name in ["write_file", "read_file", "run_command", "list_files"]:
                        # Standard coding tools
                        # Ideally we check if function_name is in coding_tools definitions
                        result = await self.coding.execute_tool(ctx, function_name, args)
                    else:
                        result = await self.tool_registry.execute(function_name, args)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    result = f"Error executing tool: {e}"

                # Notify tool end
                result_str = str(result)
                for cb in callbacks:
                    await cb.on_tool_end(function_name, result_str)

                # Add tool result to conversation
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result_str,
                }
                self.conversation_history.append(tool_msg)

                # Persist tool message to database
                if self.db_session and self.conversation_repo:
                    try:
                        await self.conversation_repo.add_message(
                            session=self.db_session,
                            user_id=int(user_id),
                            session_id=session_id,
                            role="tool",
                            content=result_str,
                            tool_calls=[{"id": tool_call["id"], "name": function_name, "args": args}],
                        )
                        await self.db_session.commit()
                    except Exception as e:
                        print(f"Failed to persist tool message: {e}")
                        await self.db_session.rollback()
        else:
            print("[DEBUG] No tool calls in response")

        # Get final response after tool execution (only if tools were called)
        if "tool_calls" in response and response["tool_calls"]:
            messages_to_send = self.conversation_history

            # Ensure system prompt is present for second call
            if tool_definitions:
                has_system_prompt = messages_to_send and messages_to_send[0].get("role") == "system"
                if not has_system_prompt:
                    system_prompt = {
                        "role": "system",
                        "content": (
                            "You are a coding assistant with access to tools that can read files, write files, "
                            "run commands, and list directories. When the user asks you to create, modify, or view code, "
                            "you MUST use the available tools instead of just describing what you would do. "
                            "Always read existing files before modifying them to understand the current code. "
                            "IMPORTANT: Never claim to have modified, created, or done something without actually "
                            "calling the corresponding tool. Always use tools first, then report what you did. "
                            "Do not say 'I have modified' or 'I have created' unless you actually called the tool."
                        )
                    }
                    messages_to_send = [system_prompt] + messages_to_send

            if self.context:
                max_tokens = self.config.context.config.get("max_tokens", 8000)
                messages_to_send, _ = await self.context.process(messages_to_send, max_tokens)

            final_response = await self.llm.complete(
                messages=messages_to_send,
            )

            final_content = final_response.get("content", "")
            self.conversation_history.append({
                "role": "assistant",
                "content": final_content,
            })
            
            if final_content:
                for cb in callbacks:
                    await cb.on_agent_response(final_content)
                
                # Save interaction to memory
                if self.memory:
                    try:
                        await self.memory.add(ctx, message, metadata={"role": "user"})
                        await self.memory.add(ctx, final_content, metadata={"role": "assistant"})
                    except Exception as e:
                        print(f"Memory save failed: {e}")

            return {
                "content": final_content,
                "tool_calls": response.get("tool_calls", []),
                "usage": response.get("usage", {}),
            }

        # Save simple response to memory
        content = response.get("content", "")
        if content and self.memory:
            try:
                await self.memory.add(ctx, message, metadata={"role": "user"})
                await self.memory.add(ctx, content, metadata={"role": "assistant"})
            except Exception as e:
                print(f"Memory save failed: {e}")

        return {
            "content": content,
            "usage": response.get("usage", {}),
        }

    # ===== Skills System Methods =====

    def apply_skill(self, skill_name: str) -> dict[str, Any]:
        """Apply a skill to change agent behavior.

        Args:
            skill_name: Name of the skill to apply

        Returns:
            Result dict with success status and modifications
        """
        if self.skill_manager is None:
            self.initialize_skills()

        if self.skill_manager is None:
            return {
                "success": False,
                "error": "Skill manager not initialized",
            }

        # Get available tools
        tool_definitions = asyncio.run(self.tool_registry.get_definitions())
        available_tools = [t.get("function", {}).get("name", "") for t in tool_definitions]

        # Apply the skill
        result = self.skill_manager.apply_skill(
            agent_state=self.agent_state,
            skill_name=skill_name,
            available_tools=available_tools,
        )

        if result.success:
            self.active_skill = skill_name
            # Reset conversation when switching skills
            self.conversation_history = []

        return {
            "success": result.success,
            "skill_name": result.skill_name,
            "modified_prompt": result.modified_prompt,
            "filtered_tools": result.filtered_tools,
            "error": result.error_message,
        }

    def clear_skill(self) -> None:
        """Clear the active skill and restore default behavior."""
        if self.skill_manager:
            self.skill_manager.clear_skill(self.agent_state)
        self.active_skill = None

    def list_skills(self, category: str | None = None, tag: str | None = None) -> list[dict[str, Any]]:
        """List available skills.

        Args:
            category: Optional category filter
            tag: Optional tag filter

        Returns:
            List of skill dicts
        """
        if self.skill_manager is None:
            self.initialize_skills()

        if self.skill_manager is None:
            return []

        from agent_os.skills.models import SkillCategory

        skill_category = SkillCategory(category) if category else None
        skills = self.skill_manager.list_skills(category=skill_category, tag=tag)

        return [
            {
                "name": s.name,
                "description": s.description,
                "category": s.category if isinstance(s.category, str) else s.category.value if s.category else None,
                "tags": s.tags,
                "version": s.version,
            }
            for s in skills
        ]

    def get_active_skill(self) -> str | None:
        """Get the currently active skill name.

        Returns:
            Active skill name or None
        """
        return self.active_skill

    def reset_conversation(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []

    async def stream_chat(
        self,
        message: str,
        user_id: str = "default_user",
    ):
        """Stream a chat response."""
        if self.llm is None:
            await self.initialize_llm()

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": message,
        })

        async for chunk in self.llm.stream_complete(messages=self.conversation_history):
            yield chunk

        # Note: For streaming, we'd need to rebuild the full response
        # This is simplified for demo purposes


__all__ = ["Agent"]
