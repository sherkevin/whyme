"""Ingestion Demo - Simple version without network operations.

This demo shows:
1. ContentFetcher URL validation and HTML parsing
2. TextChunker chunking functionality
3. IngestionService job creation
4. Search integration
"""

import asyncio
import tempfile
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_os.db.base import Base
from agent_os.search_engine.content_fetcher import ContentFetcher
from agent_os.search_engine.ingestion_pipeline import IngestionService
from agent_os.search_engine.search_engine import SearchEngine, SearchQuery
from agent_os.search_engine.search_service import SearchService
from agent_os.search_engine.text_chunker import TextChunker

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


async def demo_ingestion_simple():
    """Run simplified ingestion demonstration."""

    # Initialize database
    await init_db()

    print("=" * 70)
    print("Stage 4 Ingestion Demo (Simple)")
    print("=" * 70)

    # =========================================================================
    # 1. Content Fetcher Demo (no network calls)
    # =========================================================================

    print("\n[1] Content Fetcher Demo (No Network)")

    fetcher = ContentFetcher()

    # Test URL validation
    print("\n  URL Validation:")
    test_urls = [
        "https://example.com",
        "http://localhost:8000",
        "invalid-url",
        ""
    ]
    for url in test_urls:
        valid = fetcher._is_valid_url(url)
        print(f"    {url}: {'✓ Valid' if valid else '✗ Invalid'}")

    # Test HTML extraction (offline)
    print("\n  HTML Text Extraction:")
    html = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Welcome to AgentOS</h1>
            <p>This is a <strong>test</strong> paragraph.</p>
            <script>console.log('test');</script>
        </body>
    </html>
    """
    text = fetcher._extract_html_text(html, "http://example.com")
    print(f"    Extracted: {text[:80]}...")

    # Test Markdown file (local)
    print("\n  Markdown File Loading:")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Test Document\n\nThis is a **markdown** file.")
        md_path = f.name

    try:
        md_content = await fetcher.fetch_markdown(md_path)
        print(f"    Loaded: {md_content}")
    finally:
        Path(md_path).unlink()

    # =========================================================================
    # 2. Text Chunker Demo
    # =========================================================================

    print("\n[2] Text Chunker Demo")

    chunker = TextChunker(chunk_size=200, overlap=50)

    # Test basic chunking
    print("\n  Basic Text Chunking:")
    long_text = "This is a test sentence. " * 50  # ~400 chars
    chunks = chunker.chunk_text(long_text)
    print(f"    Original: {len(long_text)} chars")
    print(f"    Created: {len(chunks)} chunks")

    for i, chunk in enumerate(chunks[:3], 1):
        print(f"      Chunk {i}: {len(chunk)} chars - '{chunk[:50]}...'")

    # Test markdown chunking
    print("\n  Markdown-Aware Chunking:")
    md_text = """
# Introduction

This is the introduction paragraph with enough content to trigger chunking when processing markdown documents.

## Main Content

This section contains the main content of the document. It has multiple paragraphs.

## Conclusion

Final thoughts and summary.
"""
    md_chunks = chunker.chunk_markdown(md_text, chunk_size=150)
    print(f"    Markdown chunks: {len(md_chunks)}")

    # Test chunk metadata
    print("\n  Chunk Metadata:")
    if chunks:
        metadata = chunker.get_chunk_metadata(chunks[0], 0, len(chunks))
        print(f"    Chars: {metadata['char_count']}, Words: {metadata['word_count']}")

    # =========================================================================
    # 3. IngestionService Demo
    # =========================================================================

    print("\n[3] IngestionService Demo")

    async with async_session() as db:
        service = IngestionService(db)

        # Create URL job (without running it)
        print("\n  Creating ingestion jobs:")
        url_job = await service.create_job(
            source_type="url",
            source_url="https://example.com/article",
            chunk_size=500,
            overlap=100
        )
        print(f"    ✓ URL job: {url_job.id}")

        pdf_job = await service.create_job(
            source_type="pdf",
            source_file_path="/data/document.pdf",
            chunk_size=1000
        )
        print(f"    ✓ PDF job: {pdf_job.id}")

        # Get job status
        print("\n  Job status:")
        status = await service.get_job_status(str(url_job.id))
        print(f"    Status: {status['status']}")
        print(f"    Chunk size: {status['chunk_size']}")

        # List jobs
        jobs = await service.list_jobs()
        print(f"\n  Total jobs: {len(jobs)}")

        # =========================================================================
        # 4. Search Integration Demo
        # =========================================================================

        print("\n[4] Search Integration Demo")

        # Create some sample indices (simulating ingestion)
        search_service = SearchService(db)

        sample_docs = [
            ("AgentOS is an AI-powered development environment", "doc1"),
            ("Python is a popular programming language", "doc2"),
            ("FastAPI is a modern web framework for Python", "doc3"),
        ]

        print("\n  Creating search indices:")
        for content, doc_id in sample_docs:
            await search_service.index_item(
                item_type="card",
                item_id=str(uuid.uuid4()),
                title=f"Document {doc_id}",
                content=content,
                tags=["sample", "ingested"]
            )
            print(f"    ✓ Indexed: {content[:40]}...")

        # Search for content
        print("\n  Searching for 'Python'...")
        search_engine = SearchEngine(db)
        query = SearchQuery(query="Python")
        result = await search_engine.search(query)

        print(f"    Found {result.total} results:")
        for r in result.results:
            print(f"      - {r.title}")

        # =========================================================================
        # 5. Statistics
        # =========================================================================

        print("\n[5] Statistics")

        stats = await search_service.get_index_stats()
        print(f"  Total indices: {stats['total']}")
        print(f"  By type: {stats['by_type']}")

        # =========================================================================
        # Summary
        # =========================================================================

        print("\n" + "=" * 70)
        print("Ingestion Demo Complete!")
        print("=" * 70)
        print("\nKey Features Demonstrated:")
        print("  ✓ ContentFetcher - URL validation and HTML parsing")
        print("  ✓ ContentFetcher - Local markdown file loading")
        print("  ✓ TextChunker - Text chunking with overlap")
        print("  ✓ TextChunker - Markdown-aware chunking")
        print("  ✓ TextChunker - Chunk metadata")
        print("  ✓ IngestionService - Job creation")
        print("  ✓ IngestionService - Job status tracking")
        print("  ✓ Search integration - Finding ingested content")
        print("\nNote: This demo avoids network calls for reliability.")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Stage 4 Ingestion Module Demo (Simple)")
    print("Demonstrates ingestion without network operations")
    print("=" * 70)

    asyncio.run(demo_ingestion_simple())
