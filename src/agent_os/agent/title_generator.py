"""Title generation module for Agent processing.

This module provides rule-based title generation from content.
Part of PA 1.0 Stage 2 implementation.
"""

import re
from typing import Optional


def generate_title(
    content: str,
    max_length: int = 200,
    existing_title: Optional[str] = None
) -> str:
    """从内容生成标题.

    规则:
    1. 如果已有有效标题，直接返回
    2. 尝试提取第一行作为标题
    3. 如果第一行为空，提取前 N 个字符
    4. 清理多余的空白和特殊字符
    5. 截断到最大长度

    Args:
        content: 原始内容文本
        max_length: 标题最大长度（默认200字符）
        existing_title: 已有标题（如果有）

    Returns:
        生成的标题字符串

    Examples:
        >>> generate_title("First line\\nSecond line")
        'First line'

        >>> generate_title("No newline content", max_length=10)
        'No newline'
    """
    # 如果已有有效标题，直接返回
    if existing_title and existing_title.strip():
        return existing_title.strip()[:max_length]

    # 内容为空处理
    if not content or not content.strip():
        return "(Untitled)"

    # 规则1: 尝试提取第一行
    lines = content.strip().split('\n')
    first_line = lines[0].strip()

    # 清理第一行：移除特殊标记（如 #, -, * 等）
    first_line = re.sub(r'^[\#\-\*\+]+ ', '', first_line)  # 移除开头的markdown标记
    first_line = first_line.strip()

    # 如果第一行有效且不为空，使用它
    if first_line and len(first_line) > 0:
        title = first_line
    else:
        # 规则2: 使用前 N 个字符
        # 寻找第一个句子结束（句号、问号、感叹号）
        content_clean = content.strip()
        sentence_end = re.search(r'[。.！!?？]', content_clean)

        if sentence_end and sentence_end.end() <= max_length:
            title = content_clean[:sentence_end.end()]
        else:
            # 在 max_length 处截断，避免在单词中间断开
            if len(content_clean) > max_length:
                # 尝试在空格处断开
                truncated = content_clean[:max_length]
                last_space = truncated.rfind(' ')
                if last_space > max_length * 0.7:  # 如果空格位置合理
                    title = truncated[:last_space]
                else:
                    title = truncated
            else:
                title = content_clean

    # 清理标题
    title = title.strip()
    # 移除多余的空白
    title = re.sub(r'\s+', ' ', title)
    # 截断到最大长度
    title = title[:max_length]
    # 再次清理可能的尾部空白
    title = title.strip()

    # 确保标题不为空
    if not title:
        title = "(Untitled)"

    return title


def generate_title_from_metadata(
    content: str,
    metadata: dict,
    max_length: int = 200
) -> str:
    """从元数据生成标题（优先使用元数据中的标题字段）.

    Args:
        content: 原始内容文本
        metadata: 元数据字典（可能包含 title, subject 等字段）
        max_length: 标题最大长度

    Returns:
        生成的标题字符串
    """
    # 尝试从元数据中提取标题
    title_fields = ['title', 'subject', 'name', 'heading']

    for field in title_fields:
        if field in metadata and metadata[field]:
            title = str(metadata[field]).strip()
            if title:
                return title[:max_length]

    # 如果元数据中没有标题，使用内容生成
    return generate_title(content, max_length)


def extract_keywords(content: str, max_keywords: int = 5) -> list[str]:
    """从内容中提取关键词作为备选标题.

    这是一个简单的规则实现，基于词频和常见词过滤.

    Args:
        content: 原始内容文本
        max_keywords: 最大关键词数量

    Returns:
        关键词列表
    """
    # 简单实现：分割单词并过滤常见词
    words = re.findall(r'\b\w+\b', content.lower())

    # 常见停用词（英文和中文）
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'over', 'under', 'this', 'that', 'these', 'those',
        '的', '了', '是', '在', '和', '与', '或', '但是', '然而', '因为', '所以'
    }

    # 过滤停用词和短词
    meaningful_words = [
        word for word in words
        if word not in stopwords and len(word) > 2
    ]

    # 统计词频
    word_freq = {}
    for word in meaningful_words:
        word_freq[word] = word_freq.get(word, 0) + 1

    # 按频率排序，返回前 N 个
    sorted_words = sorted(
        word_freq.items(),
        key=lambda x: x[1],
        reverse=True
    )

    keywords = [word for word, freq in sorted_words[:max_keywords]]
    return keywords
