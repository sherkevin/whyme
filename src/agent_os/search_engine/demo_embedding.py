"""Embedding Demo - Demonstrates semantic search capabilities.

This demo shows:
1. Embedding generation for text
2. Vector similarity calculations
3. Hybrid search (text + semantic)
4. Performance comparison
"""

import asyncio
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_os.db.base import Base
from agent_os.search_engine.embedding_service import EmbeddingService
from agent_os.search_engine.models import SearchIndex
from agent_os.search_engine.search_engine import SearchEngine, SearchQuery
from agent_os.search_engine.search_service import SearchService

# Create async engine for demo
DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """Initialize database with tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def demo_embedding():
    """Run embedding demonstration."""

    # Initialize database
    await init_db()

    print("=" * 70)
    print("Stage 4 Embedding Demo")
    print("Demonstrates semantic search with local embeddings")
    print("=" * 70)

    async with async_session() as db:
        # =========================================================================
        # 1. Embedding Generation Demo
        # =========================================================================

        print("\n[1] Embedding Generation")

        embedding_service = EmbeddingService()

        texts = [
            "Python is a programming language",
            "JavaScript is used for web development",
            "Machine learning processes large data",
            "FastAPI is a Python web framework"
        ]

        print("\n  Generating embeddings for sample texts...")
        start = time.time()
        embeddings = await embedding_service.generate_embeddings_batch(texts)
        elapsed = time.time() - start

        print(f"    Generated {len(embeddings)} embeddings in {elapsed*1000:.2f}ms")
        print(f"    Embedding dimension: {len(embeddings[0])}")

        for i, (text, emb) in enumerate(zip(texts, embeddings), 1):
            print(f"      {i}. '{text[:40]}...'")
            print(f"         Vector: [{emb[0]:.4f}, {emb[1]:.4f}, ..., {emb[-1]:.4f}]")

        # =========================================================================
        # 2. Similarity Calculation Demo
        # =========================================================================

        print("\n[2] Similarity Calculations")

        # Similar texts
        vec1 = embeddings[0]  # "Python is a programming language"
        vec2 = embeddings[3]  # "FastAPI is a Python web framework"

        similarity = embedding_service.cosine_similarity(vec1, vec2)
        print("\n  Comparing:")
        print(f"    Text 1: '{texts[0]}'")
        print(f"    Text 2: '{texts[3]}'")
        print(f"    Cosine Similarity: {similarity:.4f}")
        print(f"    Interpretation: {'High similarity (both about Python)' if similarity > 0.5 else 'Low similarity'}")

        # Different texts
        vec3 = embeddings[1]  # "JavaScript..."
        similarity2 = embedding_service.cosine_similarity(vec1, vec3)
        print("\n  Comparing:")
        print(f"    Text 1: '{texts[0]}'")
        print(f"    Text 3: '{texts[1]}'")
        print(f"    Cosine Similarity: {similarity2:.4f}")
        print(f"    Interpretation: {'Low similarity (different topics)' if similarity2 < 0.3 else 'Some similarity'}")

        # =========================================================================
        # 3. Create Indexed Data with Embeddings
        # =========================================================================

        print("\n[3] Creating Search Indices with Embeddings")

        # Enable auto-embedding
        search_service = SearchService(db, auto_embed=True)

        sample_docs = [
            ("Python Programming Basics", "Learn Python from scratch with hands-on examples"),
            ("Advanced JavaScript", "Master JavaScript ES6+ features and modern web development"),
            ("Machine Learning Fundamentals", "Introduction to ML algorithms and data processing"),
            ("FastAPI Web Framework", "Build RESTful APIs with Python's FastAPI framework"),
            ("Data Science with Python", "Explore data analysis using Pandas, NumPy, and Matplotlib"),
            ("Web Development Guide", "Complete guide to HTML, CSS, and JavaScript for modern web"),
        ]

        print("\n  Creating indices with auto-generated embeddings...")
        for title, content in sample_docs:
            item_id = uuid.uuid4()
            await search_service.index_item(
                item_type="card",
                item_id=str(item_id),
                title=title,
                content=content,
                tags=["sample", "tutorial"]
            )
            print(f"    ✓ Indexed: '{title}'")

        # =========================================================================
        # 4. Text-Only Search (Baseline)
        # =========================================================================

        print("\n[4] Text-Only Search (Baseline)")

        engine_text_only = SearchEngine(db, enable_vector_search=False)

        queries = ["Python programming", "web development"]

        for query_text in queries:
            query = SearchQuery(query=query_text)
            start = time.time()
            result = await engine_text_only.search(query)
            elapsed = (time.time() - start) * 1000

            print(f"\n  Query: '{query_text}'")
            print(f"    Results: {result.total} in {elapsed:.2f}ms")
            for r in result.results[:3]:
                print(f"      - {r.title} (score: {r.score:.2f})")

        # =========================================================================
        # 5. Hybrid Search (Text + Semantic)
        # =========================================================================

        print("\n[5] Hybrid Search (Text + Semantic)")

        engine_hybrid = SearchEngine(db, enable_vector_search=True)

        for query_text in queries:
            query = SearchQuery(query=query_text)
            start = time.time()
            result = await engine_hybrid.search(query)
            elapsed = (time.time() - start) * 1000

            print(f"\n  Query: '{query_text}'")
            print(f"    Results: {result.total} in {elapsed:.2f}ms")
            for r in result.results[:3]:
                print(f"      - {r.title} (score: {r.score:.2f})")

        # =========================================================================
        # 6. Semantic Search Demonstration
        # =========================================================================

        print("\n[6] Semantic Search Demonstration")

        # Query that might not match exact keywords
        query_text = "coding tutorials"
        query = SearchQuery(query=query_text)
        result = await engine_hybrid.search(query)

        print(f"\n  Query: '{query_text}' (semantic search)")
        print(f"  Results: {result.total}")
        for r in result.results[:3]:
            print(f"    - {r.title}")
            print(f"      Content snippet: {r.content_snippet[:60]}...")

        # =========================================================================
        # 7. Performance Comparison
        # =========================================================================

        print("\n[7] Performance Comparison")

        query = SearchQuery(query="Python")

        # Text-only search
        start = time.time()
        result_text = await engine_text_only.search(query)
        time_text = (time.time() - start) * 1000

        # Hybrid search
        start = time.time()
        result_hybrid = await engine_hybrid.search(query)
        time_hybrid = (time.time() - start) * 1000

        print(f"\n  Query: '{query.query}'")
        print(f"    Text-only search: {time_text:.2f}ms ({result_text.total} results)")
        print(f"    Hybrid search:    {time_hybrid:.2f}ms ({result_hybrid.total} results)")
        print(f"    Overhead:         {time_hybrid - time_text:.2f}ms")

        # =========================================================================
        # 8. Statistics
        # =========================================================================

        print("\n[8] Statistics")

        # Get index stats
        stats = await search_service.get_index_stats()
        print("\n  Search Index Statistics:")
        print(f"    Total indices: {stats['total']}")
        print(f"    By type: {stats['by_type']}")

        # Count indices with embeddings
        from sqlalchemy import func, select
        stmt = select(func.count(SearchIndex.id)).where(SearchIndex.embedding.isnot(None))
        result = await db.execute(stmt)
        with_embeddings = result.scalar() or 0

        print(f"    Indices with embeddings: {with_embeddings}/{stats['total']}")
        print(f"    Coverage: {with_embeddings/stats['total']*100:.1f}%")

        # =========================================================================
        # Summary
        # =========================================================================

        print("\n" + "=" * 70)
        print("Embedding Demo Complete!")
        print("=" * 70)
        print("\nKey Features Demonstrated:")
        print("  ✓ Local TF-IDF embedding generation")
        print("  ✓ Fast embedding (< 10ms per document)")
        print("  ✓ Cosine similarity calculation")
        print("  ✓ Text-only search (baseline)")
        print("  ✓ Hybrid search (text + semantic)")
        print("  ✓ Semantic search for related concepts")
        print("  ✓ Performance comparison")
        print("\nArchitecture Notes:")
        print("  • Local TF-IDF: No network calls, fast and reliable")
        print("  • 384-dimensional vectors (matching all-MiniLM-L6-v2)")
        print("  • L2 normalized embeddings for cosine similarity")
        print("  • Hybrid scoring: 60% text + 40% semantic")
        print("  • Disabled by default, enable with enable_vector_search=True")
        print("\nFuture Enhancements:")
        print("  • Upgrade to sentence-transformers for better semantics")
        print("  • Add OpenAI/Cohere API options")
        print("  • Implement caching for frequently queried texts")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Stage 4 Embedding Module Demo")
    print("Demonstrates semantic search with local TF-IDF embeddings")
    print("=" * 70)

    asyncio.run(demo_embedding())
