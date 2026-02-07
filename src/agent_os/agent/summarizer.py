"""Summarization module for Agent processing.

This module provides rule-based content summarization.
Part of PA 1.0 Stage 2 implementation.
"""

import re
from typing import Optional


def generate_summary(
    content: str,
    max_length: int = 500,
    sentences_count: int = 3
) -> str:
    """从内容生成摘要.

    规则:
    1. 提取前 N 个句子
    2. 或提取前 N 个字符
    3. 清理格式标记
    4. 保留关键信息

    Args:
        content: 原始内容文本
        max_length: 摘要最大长度（默认500字符）
        sentences_count: 提取句子数量（默认3句）

    Returns:
        生成的摘要字符串

    Examples:
        >>> generate_summary("First sentence. Second sentence. Third sentence.")
        'First sentence. Second sentence. Third sentence.'

        >>> generate_summary("Long content...", max_length=50)
        'Long content...'
    """
    # 内容为空处理
    if not content or not content.strip():
        return ""

    # 清理内容
    content_clean = content.strip()

    # 尝试提取句子
    sentences = extract_sentences(content_clean)

    # 如果有足够的句子，使用前 N 个
    if len(sentences) > sentences_count:
        selected_sentences = sentences[:sentences_count]
    else:
        selected_sentences = sentences

    # 组合句子
    summary = ' '.join(selected_sentences)

    # 如果摘要仍然太长，截断
    if len(summary) > max_length:
        summary = truncate_text(summary, max_length)

    # 清理摘要
    summary = clean_text(summary)

    return summary


def extract_sentences(text: str) -> list[str]:
    """提取文本中的句子.

    Args:
        text: 输入文本

    Returns:
        句子列表
    """
    # 使用正则表达式分割句子
    # 支持中英文标点：。.!！?？
    # 使用正向后顾断言在标点后分割，保留标点
    sentences = re.split(
        r'([。.！!?？]+)',
        text
    )

    # 重新组合句子和标点
    result = []
    for i in range(0, len(sentences) - 1, 2):
        sentence = sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else '')
        sentence = sentence.strip()
        if sentence:
            result.append(sentence)

    # 处理最后一个元素（如果没有标点结尾）
    if len(sentences) % 2 == 1 and sentences[-1].strip():
        result.append(sentences[-1].strip())

    return result


def truncate_text(text: str, max_length: int) -> str:
    """在合适的位置截断文本.

    Args:
        text: 输入文本
        max_length: 最大长度

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text

    # 尝试在句子结束处截断
    truncated = text[:max_length]

    # 寻找最后一个句号
    last_period = truncated.rfind('.')
    last_question = truncated.rfind('?')
    last_exclamation = truncated.rfind('!')
    last_chinese_period = truncated.rfind('。')

    # 找到最后一个句子结束标记
    last_end = max(last_period, last_question, last_exclamation, last_chinese_period)

    if last_end > max_length * 0.7:  # 如果结束位置合理
        return truncated[:last_end + 1]

    # 否则，尝试在空格处断开
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.7:
        return truncated[:last_space]

    # 最后，直接截断并添加省略号
    return truncated + "..."


def clean_text(text: str) -> str:
    """清理文本格式.

    Args:
        text: 输入文本

    Returns:
        清理后的文本
    """
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)

    # 移除每行开头的 markdown 标记
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # 移除行首的 markdown 标记
        line = re.sub(r'^[\#\-\*\+]+\s*', '', line)
        cleaned_lines.append(line)

    text = ' '.join(cleaned_lines)

    # 移除多余的空白
    text = re.sub(r'\s+', ' ', text)

    # 清理首尾空白
    text = text.strip()

    return text


def extract_key_points(content: str, max_points: int = 5) -> list[str]:
    """从内容中提取关键点.

    这是一个简单的规则实现，基于列表项提取.

    Args:
        content: 原始内容文本
        max_points: 最大关键点数量

    Returns:
        关键点列表
    """
    key_points = []

    # 尝试提取 markdown 列表项
    lines = content.split('\n')

    for line in lines:
        line = line.strip()

        # 检查是否是列表项
        if line.startswith(('-', '*', '+')) or re.match(r'^\d+\.', line):
            # 移除列表标记
            point = re.sub(r'^[\-\*\+\d\.]+ ', '', line)
            point = point.strip()

            if point:
                key_points.append(point)

                if len(key_points) >= max_points:
                    break

    # 如果没有找到列表项，提取句子作为关键点
    if not key_points:
        sentences = extract_sentences(content)
        key_points = sentences[:max_points]

    return key_points


def generate_summary_from_key_points(content: str, max_points: int = 5) -> str:
    """基于关键点生成摘要.

    Args:
        content: 原始内容文本
        max_points: 最大关键点数量

    Returns:
        生成的摘要字符串
    """
    key_points = extract_key_points(content, max_points)

    if not key_points:
        return generate_summary(content)

    # 组合关键点为摘要
    summary = ' | '.join(key_points)

    return summary


def calculate_summary_quality(summary: str, original_length: int) -> dict:
    """计算摘要质量指标.

    Args:
        summary: 摘要文本
        original_length: 原始内容长度

    Returns:
        质量指标字典
    """
    summary_length = len(summary)

    if original_length == 0:
        compression_ratio = 0
    else:
        compression_ratio = summary_length / original_length

    # 提取句子数量
    sentences = extract_sentences(summary)

    return {
        "summary_length": summary_length,
        "original_length": original_length,
        "compression_ratio": compression_ratio,
        "sentence_count": len(sentences),
        "is_quality": 0.1 < compression_ratio < 0.5,  # 合理的压缩比是 10%-50%
    }
