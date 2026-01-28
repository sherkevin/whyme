"""End-to-end flow test."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_os.agent import Agent
from agent_os.core.config import AgentConfig, CodingConfig, Config, ContextConfig, IOConfig, MemoryConfig, SandboxConfig, LLMConfig
from agent_os.core.types import RuntimeContext


class TestE2EFlow:
    """End-to-end tests for the agent flow."""

    @pytest.fixture
    def mock_llm_provider(self) -> MagicMock:
        """Mock LLM provider."""
        provider = AsyncMock()
        # First call returns a tool call
        # Second call returns final response
        provider.complete.side_effect = [
            {
                "content": "",
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": '{"path": "main.py", "content": "hello"}'
                        }
                    }
                ]
            },
            {
                "content": "Done.",
                "role": "assistant"
            }
        ]
        return provider

    @pytest.mark.asyncio
    async def test_agent_coding_flow(self, mock_llm_provider: MagicMock) -> None:
        """Test agent executing a coding task."""
        
        # Setup config
        config = Config(
            agent=AgentConfig(name="TestBot"),
            memory=MemoryConfig(provider="agent_os.memory.local_json.LocalJSONProvider", config={}),
            context=ContextConfig(provider="agent_os.context.sliding_window.SlidingWindowContext", config={}),
            coding=CodingConfig(provider="agent_os.capabilities.coding.aider_adapter.AiderAdapter"),
            # We mock LLM anyway, but config needs to be valid-ish
            llm=LLMConfig(provider="agent_os.llm.litellm_impl.LiteLLMProvider", config={}),
        )

        agent = Agent(config)
        
        # Inject mocks
        agent.llm = mock_llm_provider
        await agent.initialize_coding()
        
        # Mock SessionManager/Sandbox
        mock_sandbox = AsyncMock()
        mock_sandbox.write_file.return_value = None
        
        with patch("agent_os.server.app._session_manager") as mock_mgr:
            mock_mgr.get_or_create_sandbox = AsyncMock(return_value=mock_sandbox)
            
            # Run chat
            response = await agent.chat("Create main.py")
            
            # Verify LLM was called
            agent.llm.complete.assert_called()
            
            # Verify Sandbox was called through the adapter
            mock_sandbox.write_file.assert_called_with("main.py", "hello")
            
            # Verify response
            assert response["content"] == "Done."
            assert "tool_calls" in response
