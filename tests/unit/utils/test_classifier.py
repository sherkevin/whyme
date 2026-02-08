"""Tests for content classification module (Stage 2).

Tests for the classifier.py module that classifies content by type.
"""

import pytest
from agent_os.agent.classifier import (
    ItemType,
    ClassificationConfidence,
    classify_content,
    infer_subtype
)


class TestClassifyContent:
    """测试 classify_content 函数"""

    def test_classify_task_with_todo_keyword(self):
        """验证识别 TODO 任务"""
        content = "TODO: Finish the quarterly report"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.TASK
        assert confidence == ClassificationConfidence.HIGH
        print("✅ TODO keyword classified as TASK")

    def test_classify_task_with_action_verb(self):
        """验证识别动作动词任务"""
        content = "Implement the new authentication system"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.TASK
        assert confidence in [ClassificationConfidence.HIGH, ClassificationConfidence.MEDIUM]
        print("✅ Action verb classified as TASK")

    def test_classify_task_with_time_expression(self):
        """验证识别包含时间的任务"""
        content = "Fix the bug by tomorrow"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.TASK
        print("✅ Time expression classified as TASK")

    def test_classify_task_chinese(self):
        """验证识别中文任务"""
        content = "完成用户认证模块的开发"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.TASK
        print("✅ Chinese task classified")

    def test_classify_reference_with_url(self):
        """验证识别 URL 参考"""
        content = "Check out this article: https://example.com/article"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.REFERENCE
        assert confidence == ClassificationConfidence.HIGH
        print("✅ URL classified as REFERENCE")

    def test_classify_reference_with_metadata(self):
        """验证从元数据识别参考"""
        content = "Some content"
        metadata = {"url": "https://example.com"}
        item_type, confidence = classify_content(content, metadata=metadata)

        assert item_type == ItemType.REFERENCE
        assert confidence == ClassificationConfidence.HIGH
        print("✅ Metadata URL classified as REFERENCE")

    def test_classify_reference_with_prefix(self):
        """验证识别参考前缀"""
        content = "Reference: Important documentation"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.REFERENCE
        print("✅ Reference prefix classified")

    def test_classify_note_with_keywords(self):
        """验证识别笔记关键词"""
        content = "Meeting notes about the project progress"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.NOTE
        assert confidence in [ClassificationConfidence.HIGH, ClassificationConfidence.MEDIUM]
        print("✅ Note keyword classified as NOTE")

    def test_classify_note_with_question(self):
        """验证识别问句为笔记"""
        content = "Why is the system behaving this way? Need to investigate."
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.NOTE
        print("✅ Question classified as NOTE")

    def test_classify_note_chinese(self):
        """验证识别中文笔记"""
        content = "会议记录：讨论了项目进度和下一步计划"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.NOTE
        print("✅ Chinese note classified")

    def test_classify_unknown_when_unclear(self):
        """验证无法明确分类时返回 UNKNOWN"""
        content = "Some random text that doesn't clearly indicate type or action"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.UNKNOWN
        assert confidence == ClassificationConfidence.LOW
        print("✅ Unclear content classified as UNKNOWN")

    def test_classify_with_title(self):
        """验证结合标题分类"""
        title = "Fix authentication bug"
        content = "The login system is not working properly."
        item_type, confidence = classify_content(content, title=title)

        assert item_type == ItemType.TASK
        print("✅ Title used in classification")

    def test_classify_empty_content(self):
        """验证空内容处理"""
        item_type, confidence = classify_content("")

        assert item_type == ItemType.UNKNOWN
        print("✅ Empty content classified as UNKNOWN")


class TestTaskScoring:
    """测试任务评分逻辑"""

    def test_bug_fix_task(self):
        """验证 Bug 修复任务"""
        content = "Fix the login bug"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.TASK
        assert confidence == ClassificationConfidence.HIGH
        print("✅ Bug fix task recognized")

    def test_feature_task(self):
        """验证功能开发任务"""
        content = "Implement new user registration feature"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.TASK
        assert confidence == ClassificationConfidence.HIGH
        print("✅ Feature task recognized")

    def test_review_task(self):
        """验证审查任务"""
        content = "Review the pull request for authentication module"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.TASK
        print("✅ Review task recognized")

    def test_deployment_task(self):
        """验证部署任务"""
        content = "Deploy the latest version to production"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.TASK
        print("✅ Deployment task recognized")


class TestNoteScoring:
    """测试笔记评分逻辑"""

    def test_meeting_note(self):
        """验证会议笔记"""
        content = "Meeting with the design team to discuss new UI components"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.NOTE
        print("✅ Meeting note recognized")

    def test_idea_note(self):
        """验证想法笔记"""
        content = "Idea: We could improve the user experience by adding shortcuts"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.NOTE
        print("✅ Idea note recognized")

    def test_learning_note(self):
        """验证学习笔记"""
        content = "Learned about async programming patterns in Python today"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.NOTE
        print("✅ Learning note recognized")

    def test_summary_note(self):
        """验证摘要笔记"""
        content = "Summary: The project is on track to meet the deadline"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.NOTE
        print("✅ Summary note recognized")


class TestReferenceScoring:
    """测试参考评分逻辑"""

    def test_url_reference(self):
        """验证 URL 参考"""
        content = "https://docs.python.org/3/library/asyncio.html"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.REFERENCE
        assert confidence == ClassificationConfidence.HIGH
        print("✅ URL reference recognized")

    def test_multiple_urls(self):
        """验证多个 URL"""
        content = "Check these links: https://example1.com and https://example2.com"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.REFERENCE
        print("✅ Multiple URLs recognized")

    def test_chinese_reference(self):
        """验证中文参考标记"""
        content = "参考：Python 异步编程最佳实践"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.REFERENCE
        print("✅ Chinese reference recognized")


class TestInferSubtype:
    """测试子类型推断"""

    def test_task_subtypes(self):
        """验证任务子类型"""
        assert infer_subtype("Fix the bug", ItemType.TASK) == "bugfix"
        assert infer_subtype("Implement feature", ItemType.TASK) == "feature"
        assert infer_subtype("Review code", ItemType.TASK) == "review"
        assert infer_subtype("Test the system", ItemType.TASK) == "testing"
        assert infer_subtype("Deploy to prod", ItemType.TASK) == "deployment"
        assert infer_subtype("Generic task", ItemType.TASK) == "general"
        print("✅ Task subtypes inferred correctly")

    def test_note_subtypes(self):
        """验证笔记子类型"""
        assert infer_subtype("Meeting notes", ItemType.NOTE) == "meeting"
        assert infer_subtype("New idea", ItemType.NOTE) == "idea"
        assert infer_subtype("Learning Python", ItemType.NOTE) == "learning"
        assert infer_subtype("Summary of work", ItemType.NOTE) == "summary"
        assert infer_subtype("Generic note", ItemType.NOTE) == "general"
        print("✅ Note subtypes inferred correctly")

    def test_reference_subtypes(self):
        """验证参考子类型"""
        assert infer_subtype("https://example.com", ItemType.REFERENCE) == "url"
        assert infer_subtype("document.pdf", ItemType.REFERENCE) == "document"
        assert infer_subtype("/path/to/file", ItemType.REFERENCE) == "path"
        assert infer_subtype("Generic reference", ItemType.REFERENCE) == "general"
        print("✅ Reference subtypes inferred correctly")

    def test_unknown_subtype(self):
        """验证未知类型无子类型"""
        subtype = infer_subtype("Some content", ItemType.UNKNOWN)
        assert subtype is None
        print("✅ UNKNOWN type returns None subtype")


class TestConfidenceLevels:
    """测试置信度级别"""

    def test_high_confidence_tasks(self):
        """验证高置信度任务"""
        high_confidence_tasks = [
            "TODO: Implement authentication",
            "Fix the login bug today",
            "Complete the feature by tomorrow",
        ]

        for task in high_confidence_tasks:
            item_type, confidence = classify_content(task)
            assert item_type == ItemType.TASK
            assert confidence == ClassificationConfidence.HIGH
            print(f"✅ High confidence: {task}")

    def test_medium_confidence_tasks(self):
        """验证中等置信度任务"""
        medium_confidence_tasks = [
            "Need to check the code",
            "Should implement caching",
        ]

        for task in medium_confidence_tasks:
            item_type, confidence = classify_content(task)
            assert item_type == ItemType.TASK
            # 至少应该是中等置信度
            assert confidence in [ClassificationConfidence.HIGH, ClassificationConfidence.MEDIUM]
            print(f"✅ Medium+ confidence: {task}")

    def test_low_confidence_unknown(self):
        """验证低置信度未知"""
        unclear_contents = [
            "Some random text here",
            "Just writing something",
            "Not sure what this is",
        ]

        for content in unclear_contents:
            item_type, confidence = classify_content(content)
            assert item_type == ItemType.UNKNOWN
            assert confidence == ClassificationConfidence.LOW
            print(f"✅ Low confidence UNKNOWN: {content}")


class TestEdgeCases:
    """测试边界情况"""

    def test_very_short_content(self):
        """验证非常短的内容"""
        item_type, confidence = classify_content("Fix bug")

        # 短内容更可能是任务
        assert item_type == ItemType.TASK
        print("✅ Very short content classified as TASK")

    def test_very_long_content(self):
        """验证非常长的内容"""
        long_content = "This is a very long note that contains a lot of descriptive text " * 20
        item_type, confidence = classify_content(long_content)

        # 长内容更可能是笔记
        assert item_type == ItemType.NOTE
        print("✅ Very long content classified as NOTE")

    def test_mixed_signals(self):
        """验证混合信号（任务词 + 笔记词）"""
        content = "TODO: Learn about the new framework features"
        item_type, confidence = classify_content(content)

        # TODO 权重更高，应该是任务
        assert item_type == ItemType.TASK
        print("✅ Mixed signals prioritized to TASK")

    def test_special_characters(self):
        """验证特殊字符处理"""
        content = "Fix bug: System crashes when input is @#$%"
        item_type, confidence = classify_content(content)

        assert item_type == ItemType.TASK
        print("✅ Special characters handled")

    def test_multilingual_content(self):
        """验证多语言内容"""
        content = "Meeting 会议 today 今天"
        item_type, confidence = classify_content(content)

        # 应该能识别为笔记（meeting）
        assert item_type == ItemType.NOTE
        print("✅ Multilingual content handled")


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Content Classification for Stage 2")
    print("=" * 60)
    print()

    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
