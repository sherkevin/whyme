"""Stage 4 - Search, Ingestion, and Insight capabilities.

This module adds:
- Unified Search across multiple data types
- Ingestion of external content (URL/PDF)
- Insight generation and aggregation
"""

from agent_os.stage4.models import SearchIndex, IngestionJob, InsightCluster

__all__ = ["SearchIndex", "IngestionJob", "InsightCluster"]
