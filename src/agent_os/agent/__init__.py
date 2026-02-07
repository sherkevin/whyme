"""Agent processing module for PA 1.0 Stage 2.

This module contains Agent-related functionality including:
- Title generation
- Summarization
- Content classification
- Core processing logic
"""

from agent_os.agent.title_generator import (
    generate_title,
    generate_title_from_metadata,
    extract_keywords
)

from agent_os.agent.summarizer import (
    generate_summary,
    extract_sentences,
    truncate_text,
    clean_text,
    extract_key_points,
    calculate_summary_quality
)

from agent_os.agent.classifier import (
    ItemType,
    ClassificationConfidence,
    classify_content,
    infer_subtype
)

from agent_os.agent.processor import (
    ProcessingResult,
    process_inbox_item,
    process_multiple_items,
    get_raw_items,
    agent_tick
)

__all__ = [
    # Title generation
    "generate_title",
    "generate_title_from_metadata",
    "extract_keywords",

    # Summarization
    "generate_summary",
    "extract_sentences",
    "truncate_text",
    "clean_text",
    "extract_key_points",
    "calculate_summary_quality",

    # Classification
    "ItemType",
    "ClassificationConfidence",
    "classify_content",
    "infer_subtype",

    # Processing
    "ProcessingResult",
    "process_inbox_item",
    "process_multiple_items",
    "get_raw_items",
    "agent_tick",
]
