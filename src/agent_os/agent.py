"""Simple Agent implementation for testing LLM integration."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agent_os.core.config import Config, load_config
from agent_os.core.interfaces import LLMProvider, CodingCapability, AgentCallbackHandler, MemoryProvider, ContextManager
from agent_os.core.types import RuntimeContext
from agent_os.llm.litellm_impl import LiteLLMProvider
from agent_os.tools import ToolRegistryImpl


class Agent:
    """Simple Agent for testing LLM capabilities."""

    def __init__(self, config: Config) -> None:
        """Initialize the agent with configuration."""
        self.config = config
        self.llm: LLMProvider | None = None
        self.coding: CodingCapability | None = None
        self.memory: MemoryProvider | None = None
        self.context: ContextManager | None = None
        self.tool_registry = ToolRegistryImpl()
        self.conversation_history: list[dict[str, Any]] = []

    @classmethod
    def from_config_file(cls, config_path: str = "config.yaml") -> Agent:
        """Create an agent from a configuration file."""
        config = load_config(config_path)
        return cls(config)

    async def initialize(self) -> None:
        """Initialize all components."""
        await self.initialize_llm()
        await self.initialize_coding()
        await self.initialize_memory()
        await self.initialize_context()
        
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
        self.conversation_history.append({
            "role": "user",
            "content": message,
        })
        
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
        self.conversation_history.append({
            "role": "assistant",
            "content": content,
        })

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
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result_str,
                })
        else:
            print(f"[DEBUG] No tool calls in response")

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
