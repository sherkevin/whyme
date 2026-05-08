"""Stage 4 - Search, Ingestion, and Insight capabilities.

This module adds:
- Unified Search across multiple data types
- Semantic search with embeddings
- Ingestion of external content (URL/PDF)
- Insight generation and aggregation
"""

from agent_os.search_engine.content_fetcher import ContentFetcher
from agent_os.search_engine.embedding_service import EmbeddingService, get_embedding_service
from agent_os.search_engine.ingestion_pipeline import IngestionPipeline, IngestionService
from agent_os.search_engine.insight_service import InsightService
from agent_os.search_engine.models import IngestionJob, InsightCluster, SearchIndex
from agent_os.search_engine.search_engine import SearchEngine
from agent_os.search_engine.search_service import SearchService
from agent_os.search_engine.text_chunker import TextChunker

__all__ = [
    "SearchIndex",
    "IngestionJob",
    "InsightCluster",
    "SearchService",
    "SearchEngine",
    "ContentFetcher",
    "TextChunker",
    "IngestionPipeline",
    "IngestionService",
    "EmbeddingService",
    "get_embedding_service",
    "InsightService"
]
