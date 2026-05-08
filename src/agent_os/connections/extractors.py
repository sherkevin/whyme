"""NLP Extractors for Connection Engine - Keywords and Entities."""

import logging
import re
from typing import List

logger = logging.getLogger(__name__)


class KeywordExtractor:
    """
    关键词提取器 - 基于简化的TF-IDF算法

    Stage 3实现: 使用词频和停用词过滤
    未来可升级: 使用sklearn的TfidfVectorizer或jieba的TF-IDF
    """

    # 停用词 (英文 + 中文)
    STOPWORDS = {
        # 英文停用词
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
        'for', 'of', 'with', 'by', 'from', 'as', 'is', 'it', 'that',
        'this', 'these', 'those', 'be', 'are', 'was', 'were', 'been',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'can', 'about',

        # 中文停用词
        '的', '了', '和', '是', '在', '有', '我', '不', '人', '都',
        '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
        '会', '着', '没有', '看', '好', '自己', '这', '那', '里', '就',
        '吗', '吧', '呢', '啊', '哦', '呀', '哪', '怎么', '为什么',
    }

    # 最小词长
    MIN_WORD_LENGTH = 2

    # 最小频率
    MIN_FREQUENCY = 2

    def __init__(self):
        """初始化关键词提取器"""
        pass

    def extract(self, text: str, top_k: int = 10) -> list[str]:
        """
        提取文本中的关键词

        Args:
            text: 输入文本
            top_k: 返回前K个关键词

        Returns:
            关键词列表 (按重要性降序)
        """
        if not text:
            return []

        try:
            # 1. 分词
            words = self._tokenize(text)

            # 2. 过滤停用词和短词
            words = [
                w for w in words
                if w not in self.STOPWORDS and len(w) >= self.MIN_WORD_LENGTH
            ]

            if not words:
                return []

            # 3. 计算词频
            freq = {}
            for word in words:
                freq[word] = freq.get(word, 0) + 1

            # 4. 过滤低频词
            freq = {
                word: count
                for word, count in freq.items()
                if count >= self.MIN_FREQUENCY
            }

            if not freq:
                return []

            # 5. 排序并返回top_k
            sorted_words = sorted(
                freq.items(),
                key=lambda x: x[1],
                reverse=True
            )

            keywords = [word for word, _ in sorted_words[:top_k]]

            logger.debug(f"Extracted {len(keywords)} keywords from {len(words)} words")

            return keywords

        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []

    def _tokenize(self, text: str) -> list[str]:
        """
        分词 - 简化版本

        英文: 按空格和标点分割
        中文: 按空格分割 (未来可使用jieba)

        Args:
            text: 输入文本

        Returns:
            词语列表
        """
        # 转小写
        text = text.lower()

        # 保留中文字符、字母、数字和空格
        # \u4e00-\u9fa5 是中文字符范围
        text = re.sub(r'[^\w\s\u4e00-\u9fa5]', ' ', text)

        # 按空格分割
        words = text.split()

        return words


class EntityExtractor:
    """
    实体提取器 - 基于规则的NER

    Stage 3实现: 使用正则表达式提取人名、地名、组织名
    未来可升级: 使用spaCy、Hugging Face NER模型
    """

    # 实体模式 (正则表达式)
    PATTERNS = {
        # Email (作为人名标识)
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',

        # URL (作为组织标识)
        'url': r'\bhttps?://[^\s]+\b',

        # 中文人名模式 (姓氏 + 1-2个字)
        'cn_name': r'[\u4e00-\u9fa5]{2,4}',

        # 英文人名模式 (Title case)
        'en_name': r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',

        # 组织名 (包含 Inc., Ltd., Co., 等)
        'organization': r'\b[\w\s]+(?:Inc|Ltd|LLC|Co|Corp|Company)\b\.?',

        # 日期 (作为实体标识)
        'date': r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b',
    }

    # 常见组织关键词
    ORGANIZATION_KEYWORDS = {
        'team', 'department', 'company', 'organization', 'group',
        'lab', 'studio', 'agency', 'bureau', 'office',
        '团队', '部门', '公司', '组织', '小组', '实验室',
    }

    def __init__(self):
        """初始化实体提取器"""
        # 编译正则表达式
        self.compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PATTERNS.items()
        }

    def extract(self, text: str) -> list[str]:
        """
        提取文本中的实体

        Args:
            text: 输入文本

        Returns:
            实体列表
        """
        if not text:
            return []

        try:
            entities = set()

            # 1. 使用正则表达式提取
            for pattern_name, pattern in self.compiled_patterns.items():
                matches = pattern.findall(text)
                for match in matches:
                    # 清理匹配结果
                    entity = match.strip()
                    if len(entity) >= 2:  # 最小长度
                        entities.add(entity)

            # 2. 提取组织关键词
            words = text.lower().split()
            for word in words:
                if word in self.ORGANIZATION_KEYWORDS:
                    entities.add(word)

            # 3. 过滤掉太短的实体
            entities = {
                e for e in entities
                if len(e) >= 2
            }

            result = list(entities)

            logger.debug(f"Extracted {len(result)} entities")

            return result

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []

    def extract_persons(self, text: str) -> list[str]:
        """
        提取人名

        Args:
            text: 输入文本

        Returns:
            人名列表
        """
        persons = set()

        # 提取中文人名
        cn_matches = self.compiled_patterns['cn_name'].findall(text)
        for match in cn_matches:
            if len(match) >= 2:
                persons.add(match)

        # 提取英文人名
        en_matches = self.compiled_patterns['en_name'].findall(text)
        for match in en_matches:
            persons.add(match)

        return list(persons)

    def extract_organizations(self, text: str) -> list[str]:
        """
        提取组织名

        Args:
            text: 输入文本

        Returns:
            组织名列表
        """
        orgs = set()

        # 提取组织名 (包含Inc, Ltd等)
        matches = self.compiled_patterns['organization'].findall(text)
        for match in matches:
            orgs.add(match.strip())

        # 提取组织关键词
        words = text.lower().split()
        for word in words:
            if word in self.ORGANIZATION_KEYWORDS:
                orgs.add(word)

        return list(orgs)

    def extract_emails(self, text: str) -> list[str]:
        """
        提取邮箱地址

        Args:
            text: 输入文本

        Returns:
            邮箱列表
        """
        matches = self.compiled_patterns['email'].findall(text)
        return list(set(matches))


# =============================================================================
# 辅助函数
# =============================================================================

def extract_keywords_and_entities(
    text: str,
    top_k: int = 10
) -> tuple[list[str], list[str]]:
    """
    同时提取关键词和实体

    Args:
        text: 输入文本
        top_k: 关键词数量

    Returns:
        (关键词列表, 实体列表)
    """
    keyword_extractor = KeywordExtractor()
    entity_extractor = EntityExtractor()

    keywords = keyword_extractor.extract(text, top_k=top_k)
    entities = entity_extractor.extract(text)

    return keywords, entities
