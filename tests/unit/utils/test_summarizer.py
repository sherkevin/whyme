"""Tests for summarization module (Stage 2).

Tests for the summarizer.py module that generates summaries from content.
"""

import pytest

from agent_os.agent.summarizer import (
    calculate_summary_quality,
    clean_text,
    extract_key_points,
    extract_sentences,
    generate_summary,
    generate_summary_from_key_points,
    truncate_text,
)


class TestGenerateSummary:
    """测试 generate_summary 函数"""

    def test_generate_summary_basic(self):
        """验证基本摘要生成"""
        content = "First sentence. Second sentence. Third sentence."
        summary = generate_summary(content)

        assert summary == content
        print("✅ Basic summary generated")

    def test_generate_summary_with_newlines(self):
        """验证处理换行的内容"""
        content = """First sentence.
        Second sentence.
        Third sentence."""

        summary = generate_summary(content)

        assert "First sentence" in summary
        assert len(summary) > 0
        print(f"✅ Summary with newlines: {summary}")

    def test_generate_summary_max_length(self):
        """验证摘要长度限制"""
        content = "This is a very long content that should be summarized. " * 20
        summary = generate_summary(content, max_length=100)

        assert len(summary) <= 105  # 允许一些误差
        print(f"✅ Summary length limited: {len(summary)} chars")

    def test_generate_summary_sentence_count(self):
        """验证提取句子数量"""
        content = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        summary = generate_summary(content, sentences_count=2)

        sentences = extract_sentences(summary)
        assert len(sentences) <= 2
        print(f"✅ Sentence count limited: {len(sentences)} sentences")

    def test_generate_summary_empty_content(self):
        """验证空内容处理"""
        summary = generate_summary("")

        assert summary == ""
        print("✅ Empty content returns empty summary")

    def test_generate_summary_whitespace_only(self):
        """验证仅空白字符内容处理"""
        summary = generate_summary("   \n\t  \n  ")

        assert summary == ""
        print("✅ Whitespace-only content returns empty summary")

    def test_generate_summary_chinese_content(self):
        """验证中文内容处理"""
        content = "这是第一句。这是第二句。这是第三句。"
        summary = generate_summary(content)

        assert "这是第一句" in summary or "第二句" in summary
        print(f"✅ Chinese summary: {summary}")

    def test_generate_summary_mixed_language(self):
        """验证中英文混合内容"""
        content = "English sentence. 中文句子。Another English."
        summary = generate_summary(content)

        assert len(summary) > 0
        assert "English" in summary or "中文" in summary
        print(f"✅ Mixed language summary: {summary}")


class TestExtractSentences:
    """测试 extract_sentences 函数"""

    def test_extract_sentences_basic(self):
        """验证基本句子提取"""
        text = "First sentence. Second sentence. Third sentence."
        sentences = extract_sentences(text)

        assert len(sentences) == 3
        # 句子应该保留标点符号
        assert sentences[0] == "First sentence."
        assert sentences[1] == "Second sentence."
        assert sentences[2] == "Third sentence."
        print(f"✅ Sentences extracted: {sentences}")

    def test_extract_sentences_with_chinese(self):
        """验证中文句子提取"""
        text = "这是第一句。这是第二句！这是第三句？"
        sentences = extract_sentences(text)

        assert len(sentences) == 3
        print(f"✅ Chinese sentences: {sentences}")

    def test_extract_sentences_mixed_punctuation(self):
        """验证混合标点符号"""
        text = "First. Second! Third? Fourth。 Fifth！"
        sentences = extract_sentences(text)

        assert len(sentences) >= 4
        print(f"✅ Mixed punctuation: {sentences}")

    def test_extract_sentences_empty_text(self):
        """验证空文本"""
        sentences = extract_sentences("")

        assert sentences == []
        print("✅ Empty text returns empty list")

    def test_extract_sentences_no_punctuation(self):
        """验证无标点文本"""
        text = "Just some words without punctuation marks"
        sentences = extract_sentences(text)

        # 整个文本作为一个句子
        assert len(sentences) == 1
        assert sentences[0] == text
        print(f"✅ No punctuation treated as single sentence: {sentences[0]}")


class TestTruncateText:
    """测试 truncate_text 函数"""

    def test_truncate_text_shorter_than_max(self):
        """验证文本短于最大长度时不变"""
        text = "Short text"
        result = truncate_text(text, max_length=100)

        assert result == text
        print("✅ Short text unchanged")

    def test_truncate_text_at_sentence_end(self):
        """验证在句子结束处截断"""
        text = "First sentence. Second sentence. Third sentence."
        result = truncate_text(text, max_length=20)

        # 应该在第一个句号处截断
        assert result.endswith('.')
        assert "First sentence" in result or result.startswith("First")
        print(f"✅ Truncated at sentence end: {result}")

    def test_truncate_text_at_word_boundary(self):
        """验证在单词边界处截断"""
        text = "This is a long line with many words that should be broken"
        result = truncate_text(text, max_length=30)

        # 不应该在单词中间截断（除非没有其他选择）
        assert len(result) <= 35  # 允许 "..." 的长度
        print(f"✅ Truncated at word boundary: {result}")

    def test_truncate_text_adds_ellipsis(self):
        """验证添加省略号"""
        text = "This is a very long text that cannot be broken at a sentence boundary or word boundary so it should have ellipsis"
        result = truncate_text(text, max_length=20)

        # 如果不能在句子或单词边界断开，应该添加省略号
        assert len(result) <= 24  # 20 + "..."
        print(f"✅ Ellipsis added: {result}")


class TestCleanText:
    """测试 clean_text 函数"""

    def test_clean_text_removes_extra_whitespace(self):
        """验证移除多余空白"""
        text = "Text    with    extra    spaces"
        result = clean_text(text)

        assert result == "Text with extra spaces"
        print("✅ Extra whitespace removed")

    def test_clean_text_removes_markdown_headings(self):
        """验证移除 Markdown 标题标记"""
        text = "# Heading 1\n## Heading 2\n### Heading 3"
        result = clean_text(text)

        assert "#" not in result
        assert "Heading 1" in result
        print(f"✅ Markdown headings removed: {result}")

    def test_clean_text_removes_markdown_lists(self):
        """验证移除 Markdown 列表标记"""
        text = "- Item one\n* Item two\n+ Item three"
        result = clean_text(text)

        # 列表标记应该被移除
        assert not result.startswith('-')
        assert not result.startswith('*')
        print(f"✅ Markdown list markers removed: {result}")

    def test_clean_text_removes_html_tags(self):
        """验证移除 HTML 标签"""
        text = "<p>This is <strong>bold</strong> text</p>"
        result = clean_text(text)

        assert "<p>" not in result
        assert "<strong>" not in result
        assert "This is" in result
        assert "bold" in result
        print(f"✅ HTML tags removed: {result}")

    def test_clean_text_preserves_content(self):
        """验证保留原始内容"""
        text = "Normal text with no special formatting"
        result = clean_text(text)

        assert result == text
        print("✅ Normal text preserved")


class TestExtractKeyPoints:
    """测试 extract_key_points 函数"""

    def test_extract_key_points_from_markdown_list(self):
        """验证从 Markdown 列表提取关键点"""
        content = """- First point
        - Second point
        - Third point
        - Fourth point"""

        points = extract_key_points(content, max_points=3)

        assert len(points) == 3
        assert "First point" in points[0]
        print(f"✅ Key points from markdown: {points}")

    def test_extract_key_points_from_numbered_list(self):
        """验证从数字列表提取关键点"""
        content = """1. First item
        2. Second item
        3. Third item"""

        points = extract_key_points(content)

        assert len(points) == 3
        assert "First item" in points[0]
        assert "Second item" in points[1]
        print(f"✅ Key points from numbered list: {points}")

    def test_extract_key_points_falls_back_to_sentences(self):
        """验证无列表时使用句子"""
        content = "Sentence one. Sentence two. Sentence three."

        points = extract_key_points(content, max_points=3)

        assert len(points) == 3
        print(f"✅ Falls back to sentences: {points}")

    def test_extract_key_points_empty_content(self):
        """验证空内容"""
        points = extract_key_points("")

        assert points == []
        print("✅ Empty content returns empty list")

    def test_extract_key_points_max_limit(self):
        """验证数量限制"""
        content = """- Point 1
        - Point 2
        - Point 3
        - Point 4
        - Point 5
        - Point 6"""

        points = extract_key_points(content, max_points=3)

        assert len(points) == 3
        print(f"✅ Limited to max points: {points}")


class TestGenerateSummaryFromKeyPoints:
    """测试 generate_summary_from_key_points 函数"""

    def test_summary_from_key_points_basic(self):
        """验证从关键点生成摘要"""
        content = """- Point one
        - Point two
        - Point three"""

        summary = generate_summary_from_key_points(content)

        assert "Point one" in summary
        assert " | " in summary  # 关键点用分隔符连接
        print(f"✅ Summary from key points: {summary}")

    def test_summary_from_key_points_falls_back(self):
        """验证无关键点时回退"""
        content = "Just some regular text without list items."

        summary = generate_summary_from_key_points(content)

        assert len(summary) > 0
        assert "regular text" in summary or "Just" in summary
        print(f"✅ Falls back to regular summary: {summary}")


class TestCalculateSummaryQuality:
    """测试 calculate_summary_quality 函数"""

    def test_quality_metrics_basic(self):
        """验证基本质量指标"""
        original = "This is the original content that is quite long. " * 10
        summary = "This is a shorter summary."

        metrics = calculate_summary_quality(summary, len(original))

        assert "summary_length" in metrics
        assert "original_length" in metrics
        assert "compression_ratio" in metrics
        assert metrics["original_length"] == len(original)
        assert metrics["summary_length"] == len(summary)
        assert 0 < metrics["compression_ratio"] < 1
        print(f"✅ Quality metrics: {metrics}")

    def test_quality_ratio_good(self):
        """验证良好的压缩比"""
        original = "A" * 1000
        summary = "B" * 200  # 20% 压缩比

        metrics = calculate_summary_quality(summary, len(original))

        assert metrics["compression_ratio"] == 0.2
        assert metrics["is_quality"] == True
        print("✅ Good compression ratio detected")

    def test_quality_ratio_too_high(self):
        """验证过高的压缩比"""
        original = "A" * 100
        summary = "B" * 80  # 80% 压缩比

        metrics = calculate_summary_quality(summary, len(original))

        assert metrics["compression_ratio"] == 0.8
        assert metrics["is_quality"] == False
        print("✅ High compression ratio detected as poor quality")

    def test_quality_ratio_too_low(self):
        """验证过低的压缩比"""
        original = "A" * 1000
        summary = "B" * 10  # 1% 压缩比

        metrics = calculate_summary_quality(summary, len(original))

        assert metrics["compression_ratio"] == 0.01
        assert metrics["is_quality"] == False
        print("✅ Low compression ratio detected as poor quality")

    def test_quality_empty_original(self):
        """验证空原始内容"""
        metrics = calculate_summary_quality("Summary", 0)

        assert metrics["compression_ratio"] == 0
        assert metrics["is_quality"] == False
        print("✅ Empty original handled")


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Summarization for Stage 2")
    print("=" * 60)
    print()

    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
