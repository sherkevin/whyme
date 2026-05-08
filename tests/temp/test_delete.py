"""Test deleting file with Aider"""
import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from agent_os.agent_aider import AiderAgent
from agent_os.core.config import AgentConfig, Config, ContextConfig, LLMConfig, MemoryConfig


async def test():
    config = Config(
        agent=AgentConfig(name="AgentOS"),
        llm=LLMConfig(
            provider="agent_os.llm.litellm_impl.LiteLLMProvider",
            config={}
        ),
        memory=MemoryConfig(
            provider="agent_os.memory.simple_memory.SimpleMemory",
            config={}
        ),
        context=ContextConfig(
            provider="agent_os.context.simple_context.SimpleContextManager",
            config={}
        )
    )

    agent = AiderAgent(
        session_id="test_session",
        workspace_root="./data/workspaces/my_first_project_b9bffa2c",
        config=config
    )

    result = await agent.chat(
        message="删除hello.txt文件",
        session_id="test_session"
    )

    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test())
