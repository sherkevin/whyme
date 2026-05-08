from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .types import PruningReport, RuntimeContext


class MemoryProvider(ABC):
    @abstractmethod
    async def add(
        self, ctx: RuntimeContext, content: str, metadata: dict[str, Any] | None = None
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def search(
        self, ctx: RuntimeContext, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class ContextManager(ABC):
    @abstractmethod
    async def process(
        self, messages: list[dict[str, Any]], max_tokens: int
    ) -> tuple[list[dict[str, Any]], PruningReport]:
        raise NotImplementedError


class ExecutionEnvironment(ABC):
    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def run_command(self, cmd: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def read_file(self, path: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def list_files(self, path: str = ".") -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError


class ToolRegistry(ABC):
    @abstractmethod
    async def register_mcp(self, name: str, command: str, args: list[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_definitions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError


class CodingCapability(ABC):
    @abstractmethod
    async def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return a list of tool definitions provided by this capability."""
        raise NotImplementedError

    @abstractmethod
    async def apply_edit(self, ctx: RuntimeContext, instructions: str) -> str:
        raise NotImplementedError


class LLMProvider(ABC):
    """Interface for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a completion from the LLM.

        Args:
            messages: Chat messages in OpenAI format
            tools: Optional tool definitions in OpenAI format
            **kwargs: Additional model parameters (temperature, max_tokens, etc.)

        Returns:
            Response dict with 'content', 'tool_calls', 'usage', etc.
        """
        raise NotImplementedError

    @abstractmethod
    async def stream_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ):
        """Stream completions from the LLM.

        Yields chunks as they arrive.
        """
        raise NotImplementedError


class AgentCallbackHandler:
    """Callback handler for agent events."""

    async def on_log(self, message: str) -> None:
        """Called when the agent wants to log a message."""
        pass

    async def on_tool_start(self, tool_name: str, args: dict[str, Any]) -> None:
        """Called when a tool is about to run."""
        pass

    async def on_tool_end(self, tool_name: str, result: str) -> None:
        """Called when a tool has finished running."""
        pass

    async def on_agent_response(self, content: str) -> None:
        """Called when the agent produces a text response."""
        pass
