"""Content classification module for Agent processing.

This module provides rule-based content type classification.
Part of PA 1.0 Stage 2 implementation.
"""

import re
from enum import Enum
from typing import Optional


class ItemType(str, Enum):
    """内容类型枚举 - 阶段二"""
    TASK = "task"           # 任务: 需要执行的动作
    NOTE = "note"           # 笔记: 记录的信息
    REFERENCE = "reference" # 参考: 资料和链接
    UNKNOWN = "unknown"     # 未知: 无法明确分类


class ClassificationConfidence(str, Enum):
    """分类置信度"""
    HIGH = "high"       # 高置信度: 明确匹配规则
    MEDIUM = "medium"   # 中等置信度: 部分匹配
    LOW = "low"         # 低置信度: 不确定


def classify_content(
    content: str,
    title: Optional[str] = None,
    metadata: Optional[dict] = None
) -> tuple[ItemType, ClassificationConfidence]:
    """分类内容类型.

    规则:
    1. 任务: 包含动词、时间、行动指示
    2. 笔记: 描述性内容、知识记录
    3. 参考: 链接、引用、参考资料
    4. 未知: 无法明确判断

    Args:
        content: 原始内容文本
        title: 标题（可选）
        metadata: 元数据（可选，可能包含 url 等信息）

    Returns:
        (类型, 置信度) 元组

    Examples:
        >>> classify_content("TODO: Finish the report")
        (ItemType.TASK, ClassificationConfidence.HIGH)

        >>> classify_content("https://example.com")
        (ItemType.REFERENCE, ClassificationConfidence.HIGH)
    """
    metadata = metadata or {}
    text = (content or "").lower()
    title_text = (title or "").lower()

    # 规则 1: 检查是否是参考（链接）
    if _is_reference(content, metadata):
        return ItemType.REFERENCE, ClassificationConfidence.HIGH

    # 计算得分
    task_score = _calculate_task_score(content, title, metadata)
    note_score = _calculate_note_score(content, title, metadata)

    # 规则 2: 强笔记标记优先（idea, learn, thought 等在开头）
    strong_note_starters = ['idea', '想法', 'thought', '思考', 'learn', 'learned', '学习']
    for starter in strong_note_starters:
        if text.startswith(starter + ' ') or text.startswith(starter + ':'):
            return ItemType.NOTE, ClassificationConfidence.HIGH

    # 规则 3: 强任务标记优先（todo, fix 等）
    strong_task_starters = ['todo', 'task', '任务', '待办', 'fix', '修复']
    for starter in strong_task_starters:
        if text.startswith(starter + ' ') or text.startswith(starter + ':'):
            return ItemType.TASK, ClassificationConfidence.HIGH

    # 规则 4: 基于得分判断
    if task_score >= 3:
        return ItemType.TASK, ClassificationConfidence.HIGH
    elif note_score >= 4:
        return ItemType.NOTE, ClassificationConfidence.HIGH

    # 规则 5: 中等置信度
    if task_score >= 2 and task_score > note_score:
        return ItemType.TASK, ClassificationConfidence.MEDIUM
    elif note_score >= 3:
        return ItemType.NOTE, ClassificationConfidence.HIGH
    elif note_score >= 2:
        return ItemType.NOTE, ClassificationConfidence.MEDIUM
    elif task_score >= 2:
        return ItemType.TASK, ClassificationConfidence.MEDIUM

    # 默认: 未知
    return ItemType.UNKNOWN, ClassificationConfidence.LOW


def _is_reference(content: str, metadata: dict) -> bool:
    """检查是否是参考类型."""
    # 检查元数据中是否有 URL
    if metadata.get('url') or metadata.get('link'):
        return True

    # 检查内容是否包含链接
    url_pattern = r'https?://[^\s]+'
    if re.search(url_pattern, content):
        return True

    # 检查是否以"参考"、"reference"等开头
    reference_prefixes = ['参考', 'reference', 'ref', '链接', 'link', '资源', 'resource']
    content_lower = content.lower().strip()
    for prefix in reference_prefixes:
        if content_lower.startswith(prefix):
            return True

    return False


def _calculate_task_score(content: str, title: Optional[str], metadata: dict) -> int:
    """计算任务得分.

    得分规则:
    - 包含任务关键词: +2（提高权重）
    - 包含动作动词: +1
    - 包含时间表达: +1
    - 简短且明确: +1
    """
    score = 0
    text = (content + " " + (title or "")).lower()

    # 任务关键词（提高权重以获得高置信度）
    task_keywords = [
        'todo', 'task', '任务', '待办',
        '完成', 'finish', '完成', 'implement', '实现', 'complete', '完成',
        'fix', '修复', 'bug', '错误',
        'review', '审查', 'check', '检查',
        'send', '发送', 'write', '写', 'create', '创建',
        'update', '更新', 'delete', '删除', 'add', '添加'
    ]

    # 检查是否以任务关键词开头（更强的信号）
    starts_with_task = False
    for keyword in task_keywords:
        if text.startswith(keyword + ' ') or text.startswith(keyword + ':'):
            score += 3  # 开头关键词给更高权重
            starts_with_task = True
            break

    if not starts_with_task:
        # 检查是否包含任务关键词（较弱信号）
        for keyword in task_keywords:
            if keyword in text:
                score += 2
                break

    # 动作词（动词开头）
    action_verbs = [
        'implement', 'create', 'add', 'remove', 'update', 'delete',
        'fix', 'debug', 'test', 'deploy', 'release',
        '实现', '创建', '添加', '删除', '修复', '测试', '部署', '发布'
    ]

    for verb in action_verbs:
        if text.startswith(verb) or f' {verb}' in text:
            score += 1
            break

    # 时间表达
    time_patterns = [
        r'\b(today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(今天|明天|昨天|周一|周二|周三|周四|周五|周六|周日)\b',
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # 日期
        r'\b(at \d{1,2}(:\d{2})?\s*(am|pm)?)\b',  # 时间
        r'\b(在\d{1,2}点|下午|上午|晚上)\b',
    ]

    for pattern in time_patterns:
        if re.search(pattern, text):
            score += 1
            break

    # 简短内容（更可能是任务）
    if len(content.strip()) < 200:
        score += 1

    return score


def _calculate_note_score(content: str, title: Optional[str], metadata: dict) -> int:
    """计算笔记得分.

    得分规则:
    - 包含笔记关键词: +2（提高权重）
    - 描述性内容: +1
    - 中等到长长度: +1
    - 包含解释性词汇: +1
    """
    score = 0
    text = (content + " " + (title or "")).lower()

    # 笔记关键词（提高权重）
    # 将强笔记关键词放在前面，给予更高优先级
    strong_note_keywords = [
        'idea', '想法', 'thought', '思考',
        'learn', 'learned', '学习',
        'note', 'notes', '笔记', '记录',
        'summary', '摘要', 'concept', '概念',
        'research', '研究',
        'meeting', '会议', 'discussion', '讨论'
    ]

    for keyword in strong_note_keywords:
        if keyword in text:
            score += 3  # 强关键词给3分
            break

    # 描述性词汇
    descriptive_words = [
        'about', 'regarding', 'concerning', 'related to',
        '关于', '相关', '涉及', '是指', '意思是'
    ]

    for word in descriptive_words:
        if word in text:
            score += 1
            break

    # 长内容（更可能是笔记）
    content_length = len(content.strip())
    if content_length > 500:
        score += 2  # 长内容更可能是笔记
    elif 100 <= content_length <= 500:
        score += 1

    # 包含问句（说明在思考或探索）- 提高权重
    if '?' in content or '？' in content or 'why' in text or '如何' in text or '为什么' in text:
        score += 2

    return score


def infer_subtype(content: str, item_type: ItemType) -> Optional[str]:
    """推断内容子类型.

    Args:
        content: 原始内容
        item_type: 主类型

    Returns:
        子类型字符串，如果无法推断则返回 None
    """
    if item_type == ItemType.TASK:
        return _infer_task_subtype(content)
    elif item_type == ItemType.NOTE:
        return _infer_note_subtype(content)
    elif item_type == ItemType.REFERENCE:
        return _infer_reference_subtype(content)

    return None


def _infer_task_subtype(content: str) -> Optional[str]:
    """推断任务子类型."""
    content_lower = content.lower()

    if any(word in content_lower for word in ['bug', 'fix', 'error', '修复', '错误']):
        return "bugfix"
    elif any(word in content_lower for word in ['feature', 'implement', '实现', '新增']):
        return "feature"
    elif any(word in content_lower for word in ['review', 'check', '审查', '检查']):
        return "review"
    elif any(word in content_lower for word in ['test', '测试']):
        return "testing"
    elif any(word in content_lower for word in ['deploy', 'release', '部署', '发布']):
        return "deployment"

    return "general"


def _infer_note_subtype(content: str) -> Optional[str]:
    """推断笔记子类型."""
    content_lower = content.lower()

    if any(word in content_lower for word in ['meeting', '会议', 'discussion', '讨论']):
        return "meeting"
    elif any(word in content_lower for word in ['idea', '想法', 'thought', '思考']):
        return "idea"
    elif any(word in content_lower for word in ['learn', '学习', 'study', '研究']):
        return "learning"
    elif any(word in content_lower for word in ['summary', '摘要', 'conclusion', '结论']):
        return "summary"

    return "general"


def _infer_reference_subtype(content: str) -> Optional[str]:
    """推断参考子类型."""
    if 'http://' in content or 'https://' in content:
        return "url"
    elif content.endswith('.pdf') or content.endswith('.doc') or content.endswith('.docx'):
        return "document"
    elif content.startswith('/'):
        return "path"

    return "general"
