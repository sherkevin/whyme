"""Tests for title generation module (Stage 2).

Tests for the title_generator.py module that generates titles from content.
"""

import pytest

from agent_os.agent.title_generator import (
    extract_keywords,
    generate_title,
    generate_title_from_metadata,
)


class TestGenerateTitle:
    """测试 generate_title 函数"""

    def test_generate_title_from_first_line(self):
        """验证从第一行生成标题"""
        content = "First line\nSecond line\nThird line"
        title = generate_title(content)

        assert title == "First line"
        print("✅ Title generated from first line")

    def test_generate_title_from_first_line_with_markdown(self):
        """验证清理 Markdown 标记"""
        content = "# Heading\nSome content"
        title = generate_title(content)

        assert title == "Heading"
        print("✅ Markdown heading markers cleaned")

    def test_generate_title_from_first_line_with_dash(self):
        """验证清理短横线标记"""
        content = "- Task item\nDescription here"
        title = generate_title(content)

        assert title == "Task item"
        print("✅ Dash markers cleaned")

    def test_generate_title_with_max_length(self):
        """验证标题长度限制"""
        content = "This is a very long first line that should be truncated"
        title = generate_title(content, max_length=20)

        assert len(title) <= 20
        print(f"✅ Title truncated to max length: {title}")

    def test_generate_title_truncates_at_word_boundary(self):
        """验证在单词边界处截断"""
        content = "This is a long line with many words that should be broken at a word boundary"
        title = generate_title(content, max_length=30)

        # 应该在空格处断开，而不是在单词中间
        assert not title.endswith(' ')
        assert len(title) <= 30
        print(f"✅ Truncated at word boundary: {title}")

    def test_generate_title_from_content_if_no_newline(self):
        """验证无换行符时使用内容前部"""
        content = "Single line content without newlines"
        title = generate_title(content)

        assert title == "Single line content without newlines"
        print("✅ Title from single line content")

    def test_generate_title_empty_content(self):
        """验证空内容处理"""
        title = generate_title("")

        assert title == "(Untitled)"
        print("✅ Empty content returns (Untitled)")

    def test_generate_title_whitespace_only(self):
        """验证仅空白字符内容处理"""
        title = generate_title("   \n\t  \n  ")

        assert title == "(Untitled)"
        print("✅ Whitespace-only content returns (Untitled)")

    def test_generate_title_with_existing_title(self):
        """验证使用已有标题"""
        content = "New content\nWith multiple lines"
        existing = "Existing Title"

        title = generate_title(content, existing_title=existing)

        assert title == "Existing Title"
        print("✅ Existing title is used when provided")

    def test_generate_title_with_empty_existing_title(self):
        """验证空已有标题时生成新标题"""
        content = "Real content\nMore content"
        existing = "   "

        title = generate_title(content, existing_title=existing)

        assert title == "Real content"
        print("✅ Empty existing title ignored, new one generated")

    def test_generate_title_strips_extra_whitespace(self):
        """验证清理多余空白"""
        content = "  Title    with    extra   spaces  \nNext line"
        title = generate_title(content)

        assert title == "Title with extra spaces"
        # 多个空格被压缩为单个空格
        assert "    " not in title
        print("✅ Extra whitespace cleaned")

    def test_generate_title_extract_first_sentence(self):
        """验证提取第一个句子"""
        content = "This is sentence one. This is sentence two! And sentence three?"
        title = generate_title(content, max_length=100)

        # 应该在第一个句号处结束
        assert "This is sentence one." in title or title.startswith("This is sentence one")
        print("✅ First sentence extracted")

    def test_generate_title_chinese_content(self):
        """验证中文内容处理"""
        content = "这是第一行标题\n这是第二行内容"
        title = generate_title(content)

        assert title == "这是第一行标题"
        print("✅ Chinese content handled correctly")

    def test_generate_title_mixed_language(self):
        """验证中英文混合内容"""
        content = "Mixed 混合 Title 标题"
        title = generate_title(content)

        assert "Mixed" in title or "混合" in title
        print("✅ Mixed language content handled")


class TestGenerateTitleFromMetadata:
    """测试 generate_title_from_metadata 函数"""

    def test_title_from_metadata_title_field(self):
        """验证从元数据 title 字段提取"""
        content = "Some content"
        metadata = {"title": "Metadata Title"}

        title = generate_title_from_metadata(content, metadata)

        assert title == "Metadata Title"
        print("✅ Title extracted from metadata.title")

    def test_title_from_metadata_subject_field(self):
        """验证从元数据 subject 字段提取"""
        content = "Some content"
        metadata = {"subject": "Email Subject"}

        title = generate_title_from_metadata(content, metadata)

        assert title == "Email Subject"
        print("✅ Title extracted from metadata.subject")

    def test_title_from_metadata_name_field(self):
        """验证从元数据 name 字段提取"""
        content = "Some content"
        metadata = {"name": "Document Name"}

        title = generate_title_from_metadata(content, metadata)

        assert title == "Document Name"
        print("✅ Title extracted from metadata.name")

    def test_falls_back_to_content_generation(self):
        """验证元数据无标题时使用内容生成"""
        content = "First line\nSecond line"
        metadata = {"url": "https://example.com", "date": "2026-02-07"}

        title = generate_title_from_metadata(content, metadata)

        assert title == "First line"
        print("✅ Falls back to content generation when no title in metadata")

    def test_empty_metadata(self):
        """验证空元数据时使用内容生成"""
        content = "Content line"
        metadata = {}

        title = generate_title_from_metadata(content, metadata)

        assert title == "Content line"
        print("✅ Empty metadata falls back to content generation")

    def test_metadata_title_with_max_length(self):
        """验证元数据标题长度限制"""
        content = "Content"
        metadata = {"title": "This is a very long metadata title that should be truncated"}

        title = generate_title_from_metadata(content, metadata, max_length=20)

        assert len(title) <= 20
        print(f"✅ Metadata title truncated: {title}")


class TestExtractKeywords:
    """测试 extract_keywords 函数"""

    def test_extract_keywords_simple(self):
        """验证基本关键词提取"""
        content = "Python is great. Python programming is fun. Learn Python."

        keywords = extract_keywords(content, max_keywords=3)

        # "python" 应该是最高频词
        assert "python" in keywords
        assert len(keywords) <= 3
        print(f"✅ Keywords extracted: {keywords}")

    def test_extract_keywords_removes_stopwords(self):
        """验证移除停用词"""
        content = "The quick brown fox jumps over the lazy dog"

        keywords = extract_keywords(content)

        # 常见停用词应该被过滤
        assert "the" not in keywords
        assert "over" not in keywords
        print(f"✅ Stopwords removed: {keywords}")

    def test_extract_keywords_empty_content(self):
        """验证空内容的关键词提取"""
        keywords = extract_keywords("")

        assert keywords == []
        print("✅ Empty content returns empty keywords")

    def test_extract_keywords_max_limit(self):
        """验证关键词数量限制"""
        content = "word1 word2 word3 word4 word5 word6 word7 word8"

        keywords = extract_keywords(content, max_keywords=5)

        assert len(keywords) <= 5
        print(f"✅ Keywords limited to max: {keywords}")

    def test_extract_keywords_case_insensitive(self):
        """验证大小写不敏感"""
        content = "Python python PYTHON Java java"

        keywords = extract_keywords(content)

        # 相同词的不同大小写应该被合并
        assert keywords.count("python") <= 1
        print(f"✅ Case insensitive: {keywords}")

    def test_extract_keywords_chinese_content(self):
        """验证中文内容关键词"""
        content = "人工智能很重要。机器学习是人工智能的一部分。深度学习很强大。"

        keywords = extract_keywords(content)

        # 应该能提取中文关键词
        assert len(keywords) > 0
        print(f"✅ Chinese keywords: {keywords}")


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Title Generation for Stage 2")
    print("=" * 60)
    print()

    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
