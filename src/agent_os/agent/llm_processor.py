"""LLM-based content processing for summary and tags generation.

This module uses LiteLLM to call LLM APIs for intelligent content processing.
"""

import json
import logging
from typing import Any, Dict, List

from agent_os.llm.litellm_impl import LiteLLMProvider

logger = logging.getLogger(__name__)


# ============================================================================
# LLM Provider Configuration
# ============================================================================

def get_llm_provider() -> LiteLLMProvider:
    """Get the centrally configured LLM provider."""

    return LiteLLMProvider(
        temperature=0.3,
        max_tokens=1000,
    )


# ============================================================================
# Prompt Templates
# ============================================================================

SUMMARY_PROMPT = """You are a professional content summarizer. Please summarize the following content into a concise summary.

Requirements:
1. The summary should be 1-3 sentences
2. Capture the main idea and key information
3. Remove redundant details
4. Keep it clear and readable
5. Output ONLY the summary text, no additional explanation

Content to summarize:
{content}

Summary:"""

TAGS_PROMPT = """You are a professional content tagger. Please extract 3-8 keywords/tags from the following content.

Requirements:
1. Extract the most important keywords that represent the content
2. Include both general topics and specific details
3. Avoid common words and stopwords
4. Return tags as a JSON array of strings
5. Output ONLY the JSON array, no additional explanation

Content to tag:
{content}

Tags (JSON array):"""

COMBINED_PROMPT = """You are a professional content analyzer. Please analyze the following content and generate both a summary and tags.

Requirements:
1. Summary: 1-3 sentences capturing the main idea
2. Tags: 3-8 keywords that represent the content
3. Return result as JSON with "summary" and "tags" fields
4. Output ONLY the JSON, no additional explanation

Content to analyze:
{content}

Result (JSON):"""


# ============================================================================
# LLM-based Processing Functions
# ============================================================================

async def generate_summary_llm(content: str, max_length: int = 500) -> str:
    """Generate summary using LLM.

    Args:
        content: The content to summarize
        max_length: Maximum length of the summary

    Returns:
        Generated summary string
    """
    if not content or not content.strip():
        return ""

    try:
        llm = get_llm_provider()

        prompt = SUMMARY_PROMPT.format(content=content[:4000])  # Limit input length

        response = await llm.complete(
            messages=[
                {"role": "system", "content": "You are a professional content summarizer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200,
        )

        summary = response.get("content", "").strip()

        # Truncate if too long
        if len(summary) > max_length:
            summary = summary[:max_length - 3] + "..."

        logger.info(f"Generated LLM summary: {summary[:100]}...")
        return summary

    except Exception as e:
        logger.error(f"Error generating LLM summary: {e}")
        # Fallback to empty string, caller should handle fallback
        raise e


async def generate_tags_llm(content: str, max_tags: int = 8) -> list[str]:
    """Generate tags/keywords using LLM.

    Args:
        content: The content to extract tags from
        max_tags: Maximum number of tags

    Returns:
        List of tags
    """
    if not content or not content.strip():
        return []

    try:
        llm = get_llm_provider()

        prompt = TAGS_PROMPT.format(content=content[:4000])  # Limit input length

        response = await llm.complete(
            messages=[
                {"role": "system", "content": "You are a professional content tagger. Output JSON array only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200,
        )

        tags_text = response.get("content", "").strip()

        # Parse JSON array from response
        tags = parse_tags_from_response(tags_text, max_tags)

        logger.info(f"Generated LLM tags: {tags}")
        return tags

    except Exception as e:
        logger.error(f"Error generating LLM tags: {e}")
        # Fallback to empty list, caller should handle fallback
        raise e


async def generate_summary_and_tags_llm(content: str, max_length: int = 500, max_tags: int = 8) -> dict[str, Any]:
    """Generate both summary and tags using LLM in a single call.

    Args:
        content: The content to analyze
        max_length: Maximum length of the summary
        max_tags: Maximum number of tags

    Returns:
        Dictionary with 'summary' and 'tags' keys
    """
    if not content or not content.strip():
        return {"summary": "", "tags": []}

    try:
        llm = get_llm_provider()

        prompt = COMBINED_PROMPT.format(content=content[:4000])  # Limit input length

        response = await llm.complete(
            messages=[
                {"role": "system", "content": "You are a professional content analyzer. Output JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400,
        )

        result_text = response.get("content", "").strip()

        # Parse JSON response
        result = parse_combined_response(result_text, max_length, max_tags)

        logger.info(f"Generated LLM summary+tags: summary={result.get('summary', '')[:50]}..., tags={result.get('tags', [])}")
        return result

    except Exception as e:
        logger.error(f"Error generating LLM summary and tags: {e}")
        raise e


# ============================================================================
# Helper Functions
# ============================================================================

def parse_tags_from_response(response_text: str, max_tags: int = 8) -> list[str]:
    """Parse tags from LLM response text.

    Args:
        response_text: Raw response text from LLM
        max_tags: Maximum number of tags to return

    Returns:
        List of tags
    """
    # Try to extract JSON array from response
    import re

    # Try direct JSON parse first
    try:
        tags = json.loads(response_text)
        if isinstance(tags, list):
            return [str(t) for t in tags[:max_tags]]
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in text
    match = re.search(r'\[([^\]]+)\]', response_text)
    if match:
        array_text = match.group(0)
        try:
            tags = json.loads(array_text)
            if isinstance(tags, list):
                return [str(t) for t in tags[:max_tags]]
        except json.JSONDecodeError:
            pass

    # Fallback: split by common delimiters
    tags = re.split(r'[,\n]', response_text)
    tags = [t.strip().strip('"\'[]') for t in tags if t.strip()]
    return tags[:max_tags]


def parse_combined_response(response_text: str, max_length: int = 500, max_tags: int = 8) -> dict[str, Any]:
    """Parse combined summary+tags response from LLM.

    Args:
        response_text: Raw response text from LLM
        max_length: Maximum summary length
        max_tags: Maximum number of tags

    Returns:
        Dictionary with 'summary' and 'tags' keys
    """
    import re

    result = {"summary": "", "tags": []}

    # Try direct JSON parse first
    try:
        parsed = json.loads(response_text)
        if isinstance(parsed, dict):
            result["summary"] = str(parsed.get("summary", ""))[:max_length]
            result["tags"] = [str(t) for t in parsed.get("tags", [])[:max_tags]]
            return result
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
    if match:
        json_text = match.group(0)
        try:
            parsed = json.loads(json_text)
            if isinstance(parsed, dict):
                result["summary"] = str(parsed.get("summary", ""))[:max_length]
                result["tags"] = [str(t) for t in parsed.get("tags", [])[:max_tags]]
                return result
        except json.JSONDecodeError:
            pass

    return result


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "get_llm_provider",
    "generate_summary_llm",
    "generate_tags_llm",
    "generate_summary_and_tags_llm",
]
