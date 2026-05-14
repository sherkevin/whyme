"""ReAct agent must not fabricate answers when real LLM is disabled."""

from __future__ import annotations

import pytest

from agent_os.agent.react_agent import run_react_agent
from agent_os.ai import llm_provider


@pytest.mark.asyncio
async def test_react_agent_llm_disabled_surfaces_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTOS_AI_LLM", "off")
    monkeypatch.delenv("AGENTOS_AI_OFFLINE_PLACEHOLDER", raising=False)
    llm_provider.set_test_provider(None)
    llm_provider.reset_provider_for_test()

    events = [
        event
        async for event in run_react_agent(
            db=None,  # type: ignore[arg-type]
            user=None,  # type: ignore[arg-type]
            user_message="hello",
        )
    ]

    assert events == [
        {
            "event": "error",
            "data": {
                "message": "真实 LLM 未启用，无法执行 ReAct 工具调用。请设置 AGENTOS_AI_LLM=on 并配置 DeepSeek API Key。"
            },
        }
    ]


@pytest.mark.asyncio
async def test_react_agent_offline_placeholder_requires_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTOS_AI_LLM", "off")
    monkeypatch.setenv("AGENTOS_AI_OFFLINE_PLACEHOLDER", "on")
    llm_provider.set_test_provider(None)
    llm_provider.reset_provider_for_test()

    events = [
        event
        async for event in run_react_agent(
            db=None,  # type: ignore[arg-type]
            user=None,  # type: ignore[arg-type]
            user_message="hello",
        )
    ]

    assert events[0]["event"] == "final_answer"
    assert "离线占位模式" in events[0]["data"]["answer"]
