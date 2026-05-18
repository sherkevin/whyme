from agent_os.common.public_text import sanitize_public_text


def test_sanitize_public_text_removes_internal_seed_markers():
    assert (
        sanitize_public_text("联调对接清单与状态码 的精炼摘要——演示用。 [seed]")
        == "联调对接清单与状态码 的精炼摘要。"
    )
    assert sanitize_public_text("（演示）会议纪要总结：1) A") == "会议纪要总结：1) A"


def test_sanitize_public_text_keeps_real_user_text():
    text = "真实网页剪藏摘要：Example Domain 可用于文档示例。"
    assert sanitize_public_text(text) == text
