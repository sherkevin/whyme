"""Ingestion Demo - Demonstrates the Ingestion functionality.

This demo shows:
1. Creating ingestion jobs for URLs and PDFs
2. Fetching and parsing content
3. Text chunking with overlap
4. Creating items and search indices
5. Managing job status
"""

import asyncio
import uuid
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from agent_os.search_engine.content_fetcher import ContentFetcher
from agent_os.search_engine.text_chunker import TextChunker
from agent_os.search_engine.ingestion_pipeline import IngestionService
from agent_os.search_engine.search_service import SearchService
from agent_os.search_engine.search_engine import SearchEngine, SearchQuery
from agent_os.db.base import Base


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


async def demo_ingestion():
    """Run ingestion demonstration."""

    # Initialize database
    await init_db()

    print("=" * 70)
    print("Stage 4 Ingestion Demo")
    print("=" * 70)

    async with async_session() as db:
        # =========================================================================
        # 1. Content Fetcher Demo
        # =========================================================================

        print("\n[1] Content Fetcher Demo")

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

        # Test HTML extraction
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
        print(f"    Extracted: {text[:100]}...")

        # Test Markdown file
        print("\n  Markdown File:")
        # Create temporary markdown file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test Document\n\nThis is a **markdown** file with *formatting*.\n\n## Section\n\nContent here.")
            md_path = f.name

        try:
            md_content = await fetcher.fetch_markdown(md_path)
            print(f"    Loaded: {md_content[:50]}...")
        finally:
            Path(md_path).unlink()

        # =========================================================================
        # 2. Text Chunker Demo
        # =========================================================================

        print("\n[2] Text Chunker Demo")

        chunker = TextChunker(chunk_size=200, overlap=50)

        # Test basic chunking
        print("\n  Basic Text Chunking:")
        long_text = "This is a test. " * 50  # ~300 chars
        chunks = chunker.chunk_text(long_text)
        print(f"    Original: {len(long_text)} chars")
        print(f"    Chunks: {len(chunks)}")
        for i, chunk in enumerate(chunks, 1):
            print(f"      Chunk {i}: {len(chunk)} chars - '{chunk[:50]}...'")

        # Test markdown chunking
        print("\n  Markdown Chunking:")
        md_text = """
# Introduction

This is the introduction paragraph with enough content to trigger chunking.

## Main Content

This section contains the main content of the document. It has multiple paragraphs and should be split appropriately.

## Conclusion

Final thoughts and summary of the document.
"""
        md_chunks = chunker.chunk_markdown(md_text, chunk_size=150)
        print(f"    Markdown chunks: {len(md_chunks)}")
        for i, chunk in enumerate(md_chunks, 1):
            print(f"      Chunk {i}: {len(chunk)} chars, starts with '{chunk[:20]}...'")

        # Test chunk metadata
        print("\n  Chunk Metadata:")
        if chunks:
            metadata = chunker.get_chunk_metadata(chunks[0], 0, len(chunks))
            print(f"    Metadata: {metadata}")

        # =========================================================================
        # 3. IngestionService Demo
        # =========================================================================

        print("\n[3] IngestionService Demo")

        service = IngestionService(db)

        # Create URL job
        print("\n  Creating URL ingestion job...")
        url_job = await service.create_job(
            source_type="url",
            source_url="https://example.com/article",
            chunk_size=500,
            overlap=100,
            created_by=str(uuid.uuid4())
        )
        print(f"    ✓ Created job: {url_job.id}")
        print(f"      Type: {url_job.source_type}")
        print(f"      URL: {url_job.source_url}")
        print(f"      Status: {url_job.status}")

        # Create PDF job
        print("\n  Creating PDF ingestion job...")
        pdf_job = await service.create_job(
            source_type="pdf",
            source_file_path="/data/document.pdf",
            chunk_size=1000,
            overlap=200
        )
        print(f"    ✓ Created job: {pdf_job.id}")

        # Get job status
        print("\n  Getting job status...")
        status = await service.get_job_status(str(url_job.id))
        print(f"    Job {str(url_job.id)[:8]}...")
        print(f"      Status: {status['status']}")
        print(f"      Chunk size: {status['chunk_size']}")
        print(f"      Overlap: {status['overlap']}")

        # List jobs
        print("\n  Listing all jobs...")
        jobs = await service.list_jobs()
        print(f"    Total jobs: {len(jobs)}")
        for job in jobs:
            print(f"      - {job.source_type}: {job.status}")

        # List pending jobs
        print("\n  Listing pending jobs...")
        pending_jobs = await service.list_jobs(status="pending")
        print(f"    Pending jobs: {len(pending_jobs)}")

        # =========================================================================
        # 4. Full Ingestion Pipeline Simulation
        # =========================================================================

        print("\n[4] Full Ingestion Pipeline Simulation")

        # Simulate content fetch
        print("\n  Step 1: Fetch content")
        sample_content = """
        AgentOS is an AI-powered development environment that combines the power of
        large language models with traditional software engineering tools. It provides
        a unified interface for code generation, debugging, testing, and deployment.

        The system is built with a modular architecture, allowing developers to easily
        extend and customize functionality. Key components include the Agent Engine,
        Knowledge Base, Task Management, and Search capabilities.

        With AgentOS, developers can focus on high-level problem-solving while the AI
        handles routine coding tasks, suggests optimizations, and helps maintain code
        quality throughout the development lifecycle.
        """ * 3  # Repeat for longer content

        print(f"    Fetched {len(sample_content)} characters of content")

        # Simulate chunking
        print("\n  Step 2: Chunk content")
        pipeline_chunker = TextChunker(chunk_size=300, overlap=50)
        chunks = pipeline_chunker.chunk_text(sample_content)
        print(f"    Created {len(chunks)} chunks")

        # Simulate creating items and indices
        print("\n  Step 3: Create items and search indices")
        search_service = SearchService(db)
        created_ids = []

        for i, chunk in enumerate(chunks, 1):
            # Create mock item (simulating Card creation)
            item_id = uuid.uuid4()
            created_ids.append(str(item_id))

            # Create search index
            await search_service.index_item(
                item_type="card",
                item_id=str(item_id),
                title=f"AgentOS Documentation - Part {i}",
                content=chunk,
                tags=["ingested", "documentation"],
                search_metadata={
                    "source": "ingestion_demo",
                    "chunk_num": i,
                    "total_chunks": len(chunks)
                }
            )

            print(f"    ✓ Created item {i}: {len(chunk)} chars")

        # =========================================================================
        # 5. Search Ingested Content
        # =========================================================================

        print("\n[5] Search Ingested Content")

        engine = SearchEngine(db)

        # Search for ingested content
        print("\n  Searching for 'AgentOS'...")
        query = SearchQuery(query="AgentOS")
        result = await engine.search(query)

        print(f"    Found {result.total} results")
        for r in result.results:
            print(f"      - {r.title}")
            if "ingested" in r.tags:
                print(f"        Tags: {r.tags}")
                print(f"        Metadata: {r.search_metadata}")

        # Search by tags
        print("\n  Searching with tag filter 'ingested'...")
        query = SearchQuery(
            query="",
            tags=["ingested"]
        )
        result = await engine.search(query)

        print(f"    Found {result.total} results with 'ingested' tag")
        for r in result.results[:3]:
            print(f"      - {r.title}")

        # =========================================================================
        # 6. Statistics
        # =========================================================================

        print("\n[6] Statistics")

        # Search index stats
        stats = await search_service.get_index_stats()
        print(f"\n  Search Index Statistics:")
        print(f"    Total indices: {stats['total']}")
        print(f"    By type:")
        for item_type, count in stats['by_type'].items():
            print(f"      - {item_type}: {count}")

        # Chunk statistics
        if chunks:
            chunk_result = chunker.chunk_text(sample_content)
            print(f"\n  Chunking Statistics:")
            print(f"    Original length: {len(sample_content)} chars")
            print(f"    Number of chunks: {len(chunk_result)}")
            avg_size = sum(len(c) for c in chunk_result) / len(chunk_result)
            print(f"    Average chunk size: {avg_size:.1f} chars")

        # =========================================================================
        # Summary
        # =========================================================================

        print("\n" + "=" * 70)
        print("Ingestion Demo Complete!")
        print("=" * 70)
        print("\nKey Features Demonstrated:")
        print("  ✓ ContentFetcher - URL validation and HTML parsing")
        print("  ✓ ContentFetcher - Markdown file loading")
        print("  ✓ TextChunker - Basic text chunking with overlap")
        print("  ✓ TextChunker - Markdown-aware chunking")
        print("  ✓ TextChunker - Chunk metadata generation")
        print("  ✓ IngestionService - Job creation and management")
        print("  ✓ IngestionService - Job status tracking")
        print("  ✓ IngestionService - Job listing and filtering")
        print("  ✓ Full pipeline - Fetch → Chunk → Index workflow")
        print("  ✓ Search integration - Finding ingested content")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Stage 4 Ingestion Module Demo")
    print("Demonstrates content ingestion from external sources")
    print("=" * 70)

    asyncio.run(demo_ingestion())
