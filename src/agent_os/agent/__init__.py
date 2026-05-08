"""Agent processing module for PA 1.0 Stage 2.

This module contains Agent-related functionality including:
- Title generation
- Summarization
- Content classification
- Core processing logic
"""

from agent_os.agent.classifier import (
    ClassificationConfidence,
    ItemType,
    classify_content,
    infer_subtype,
)
from agent_os.agent.processor import (
    ProcessingResult,
    agent_tick,
    get_raw_items,
    process_inbox_item,
    process_multiple_items,
)
from agent_os.agent.summarizer import (
    calculate_summary_quality,
    clean_text,
    extract_key_points,
    extract_sentences,
    generate_summary,
    truncate_text,
)
from agent_os.agent.title_generator import (
    extract_keywords,
    generate_title,
    generate_title_from_metadata,
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
    "Agent",
]

# Legacy Agent import.
# Keep `from agent_os.agent import Agent` working while the PRD10 API moves
# toward feature-specific services. The concrete class still lives in the
# legacy module; importing from this package previously recursed into itself.
try:
    from agent_os.agent_legacy import Agent
except ImportError:
    Agent = None  # type: ignore[assignment]
