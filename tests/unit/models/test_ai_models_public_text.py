from agent_os.ai.models import AIConversation, AIMessage


def test_ai_conversation_dto_sanitizes_seed_preview():
    conv = AIConversation(
        title="（演示）PRD10 演示文档对话",
        mode="general",
        last_message_preview="（演示）下面是摘要。",
        message_count=2,
        context_scope={},
        extra={},
    )

    dto = conv.to_prd10_dict()

    assert dto["title"] == "PRD10 文档对话"
    assert dto["last_message_preview"] == "下面是摘要。"


def test_ai_message_dto_sanitizes_seed_content():
    msg = AIMessage(
        role="assistant",
        content="（演示）会议纪要总结：1) 已整理。",
        status="completed",
        citations=[],
        tool_calls=[],
        attachments=[],
    )

    dto = msg.to_prd10_dict()

    assert dto["content"] == "会议纪要总结：1) 已整理。"
