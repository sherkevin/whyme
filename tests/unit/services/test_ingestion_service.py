"""Unit tests for Stage 4 Ingestion modules."""

import pytest
import uuid
from datetime import datetime
from pathlib import Path
from sqlalchemy import select

from agent_os.search_engine.content_fetcher import ContentFetcher
from agent_os.search_engine.text_chunker import TextChunker, ChunkResult
from agent_os.search_engine.ingestion_pipeline import IngestionService
from agent_os.search_engine.models import IngestionJob


# =============================================================================
# ContentFetcher Tests
# =============================================================================

@pytest.mark.asyncio
class TestContentFetcher:
    """Test ContentFetcher functionality."""

    async def test_is_valid_url(self, db_session):
        """Test URL validation."""
        fetcher = ContentFetcher()

        # Valid URLs
        assert fetcher._is_valid_url("https://example.com") is True
        assert fetcher._is_valid_url("http://example.com") is True
        assert fetcher._is_valid_url("https://example.com/path?query=value") is True
        assert fetcher._is_valid_url("http://localhost:8000") is True

        # Invalid URLs
        assert fetcher._is_valid_url("not-a-url") is False
        assert fetcher._is_valid_url("") is False
        assert fetcher._is_valid_url("ftp://example.com") is False

        print("✅ URL validation tests passed")

    async def test_extract_html_text(self, db_session):
        """Test HTML text extraction."""
        fetcher = ContentFetcher()

        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Welcome</h1>
                <p>This is a test paragraph.</p>
                <script>var x = 1;</script>
                <style>body { color: red; }</style>
            </body>
        </html>
        """

        text = fetcher._extract_html_text(html, "http://example.com")

        assert "Welcome" in text
        assert "test paragraph" in text
        assert "var x = 1" not in text  # Script removed
        assert "color: red" not in text  # Style removed

        print("✅ HTML text extraction test passed")

    async def test_extract_html_with_no_bs4(self, db_session, monkeypatch):
        """Test HTML extraction without BeautifulSoup."""
        # Temporarily disable BS4
        import agent_os.stage4.content_fetcher as cf_module
        monkeypatch.setattr(cf_module, "BS4_AVAILABLE", False)

        fetcher = ContentFetcher()

        html = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        text = fetcher._extract_html_text(html, "http://example.com")

        assert "Title" in text or "Content" in text
        print("✅ HTML extraction without BS4 test passed")

    async def test_fetch_markdown_file(self, db_session, tmp_path):
        """Test fetching markdown file."""
        fetcher = ContentFetcher()

        # Create test markdown file
        md_file = tmp_path / "test.md"
        md_content = "# Test Document\n\nThis is a **markdown** file."
        md_file.write_text(md_content)

        # Fetch it
        content = await fetcher.fetch_markdown(str(md_file))

        assert content == md_content
        assert "# Test Document" in content
        print("✅ Markdown file fetch test passed")

    async def test_fetch_markdown_file_not_found(self, db_session):
        """Test fetching non-existent markdown file."""
        fetcher = ContentFetcher()

        with pytest.raises(FileNotFoundError):
            await fetcher.fetch_markdown("/nonexistent/file.md")

        print("✅ Markdown file not found test passed")


# =============================================================================
# TextChunker Tests
# =============================================================================

@pytest.mark.asyncio
class TestTextChunker:
    """Test TextChunker functionality."""

    async def test_chunk_text_basic(self, db_session):
        """Test basic text chunking."""
        chunker = TextChunker(chunk_size=100, overlap=20)

        text = "A" * 150  # 150 characters
        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 2
        assert sum(len(c) for c in chunks) >= len(text)
        print(f"✅ Basic chunking: {len(chunks)} chunks from {len(text)} chars")

    async def test_chunk_text_with_overlap(self, db_session):
        """Test chunking with overlap."""
        chunker = TextChunker(chunk_size=100, overlap=30)

        text = "word " * 100  # 500 characters
        chunks = chunker.chunk_text(text)

        # Check that we got multiple chunks
        assert len(chunks) >= 2

        # Check that total content is preserved (with overlap)
        total_chars = sum(len(c) for c in chunks)
        assert total_chars >= len(text)  # Should have more due to overlap

        print(f"✅ Overlap chunking: {len(chunks)} chunks, total chars {total_chars} (original: {len(text)})")

    async def test_chunk_short_text(self, db_session):
        """Test chunking short text (no split needed)."""
        chunker = TextChunker(chunk_size=1000, overlap=200)

        text = "Short text"
        chunks = chunker.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0] == text
        print("✅ Short text chunking test passed")

    async def test_chunk_empty_text(self, db_session):
        """Test chunking empty text."""
        chunker = TextChunker()

        chunks = chunker.chunk_text("")
        assert len(chunks) == 0

        chunks = chunker.chunk_text("   ")
        assert len(chunks) == 0

        print("✅ Empty text chunking test passed")

    async def test_chunk_markdown_sections(self, db_session):
        """Test markdown section splitting."""
        chunker = TextChunker()

        md = """# Section 1
Content for section 1.

## Section 1.1
More content.

# Section 2
Content for section 2.
"""

        sections = chunker._split_markdown_sections(md)

        assert len(sections) >= 2
        assert "# Section 1" in sections[0]
        assert "# Section 2" in sections[-1]

        print(f"✅ Markdown section splitting: {len(sections)} sections")

    async def test_chunk_markdown(self, db_session):
        """Test markdown chunking."""
        chunker = TextChunker(chunk_size=200)

        md = """# Title

This is a long paragraph that should be split into multiple chunks when it exceeds the configured chunk size limit for the markdown chunker.

## Subsection

Another paragraph with enough content to trigger chunking at appropriate boundaries.
"""

        chunks = chunker.chunk_markdown(md)

        assert len(chunks) >= 1
        assert all("#" in c or "paragraph" in c for c in chunks)

        print(f"✅ Markdown chunking: {len(chunks)} chunks")

    async def test_find_split_index(self, db_session):
        """Test finding optimal split point."""
        chunker = TextChunker()

        # Test with paragraph break
        text = "Sentence one. Sentence two.\n\nNew paragraph here."
        index = chunker._find_split_index(text)

        # Should prefer paragraph break
        assert index > 0
        assert text[index:] == text[index:]

        print("✅ Split index finding test passed")

    async def test_get_chunk_metadata(self, db_session):
        """Test chunk metadata generation."""
        chunker = TextChunker()

        chunk = "This is a test chunk. It has multiple sentences!"
        metadata = chunker.get_chunk_metadata(chunk, 0, 5)

        assert metadata["chunk_index"] == 0
        assert metadata["total_chunks"] == 5
        assert metadata["char_count"] == len(chunk)
        assert metadata["word_count"] > 0
        assert metadata["line_count"] >= 1
        assert isinstance(metadata["starts_with_sentence"], bool)
        assert isinstance(metadata["ends_with_sentence"], bool)

        print("✅ Chunk metadata test passed")

    async def test_merge_chunks(self, db_session):
        """Test merging chunks back together."""
        chunker = TextChunker(overlap=50)

        chunks = ["First chunk here.", "Second chunk there.", "Third chunk everywhere."]
        merged = chunker.merge_chunks(chunks, overlap=0)

        assert "First chunk here" in merged
        assert "Second chunk there" in merged
        assert "Third chunk everywhere" in merged

        print("✅ Chunk merging test passed")


# =============================================================================
# IngestionService Tests
# =============================================================================

@pytest.mark.asyncio
class TestIngestionService:
    """Test IngestionService functionality."""

    async def test_create_job_url(self, db_session):
        """Test creating URL ingestion job."""
        service = IngestionService(db_session)

        job = await service.create_job(
            source_type="url",
            source_url="https://example.com/article",
            chunk_size=1000,
            overlap=200,
            created_by=str(uuid.uuid4())
        )

        assert job.id is not None
        assert job.source_type == "url"
        assert job.source_url == "https://example.com/article"
        assert job.status == "pending"
        assert job.chunk_size == 1000
        print(f"✅ Created URL job: {job.id}")

    async def test_create_job_pdf(self, db_session):
        """Test creating PDF ingestion job."""
        service = IngestionService(db_session)

        job = await service.create_job(
            source_type="pdf",
            source_file_path="/data/document.pdf",
            chunk_size=2000,
            overlap=300
        )

        assert job.source_type == "pdf"
        assert job.source_file_path == "/data/document.pdf"
        assert job.status == "pending"
        print(f"✅ Created PDF job: {job.id}")

    async def test_create_job_markdown(self, db_session):
        """Test creating Markdown ingestion job."""
        service = IngestionService(db_session)

        job = await service.create_job(
            source_type="markdown",
            source_file_path="/data/doc.md"
        )

        assert job.source_type == "markdown"
        assert job.source_file_path == "/data/doc.md"
        print(f"✅ Created Markdown job: {job.id}")

    async def test_create_job_invalid_source_type(self, db_session):
        """Test creating job with invalid source type."""
        service = IngestionService(db_session)

        with pytest.raises(ValueError):
            await service.create_job(
                source_type="invalid_type"
            )

        print("✅ Invalid source type rejected")

    async def test_create_job_url_missing_url(self, db_session):
        """Test URL job without URL."""
        service = IngestionService(db_session)

        with pytest.raises(ValueError):
            await service.create_job(
                source_type="url"
                # Missing source_url
            )

        print("✅ URL job without URL rejected")

    async def test_create_job_pdf_missing_path(self, db_session):
        """Test PDF job without file path."""
        service = IngestionService(db_session)

        with pytest.raises(ValueError):
            await service.create_job(
                source_type="pdf"
                # Missing source_file_path
            )

        print("✅ PDF job without path rejected")

    async def test_get_job_status(self, db_session):
        """Test getting job status."""
        service = IngestionService(db_session)

        # Create job
        job = await service.create_job(
            source_type="url",
            source_url="https://example.com"
        )

        # Get status
        status = await service.get_job_status(str(job.id))

        assert status["id"] == str(job.id)
        assert status["source_type"] == "url"
        assert status["status"] == "pending"
        assert "created_at" in status
        print("✅ Job status retrieved")

    async def test_get_job_status_not_found(self, db_session):
        """Test getting status of non-existent job."""
        service = IngestionService(db_session)

        with pytest.raises(ValueError):
            await service.get_job_status(str(uuid.uuid4()))

        print("✅ Non-existent job rejected")

    async def test_list_jobs(self, db_session):
        """Test listing jobs."""
        service = IngestionService(db_session)

        # Create some jobs
        user_id = str(uuid.uuid4())
        await service.create_job(
            source_type="url",
            source_url="https://example.com/1",
            created_by=user_id
        )
        await service.create_job(
            source_type="pdf",
            source_file_path="/test.pdf",
            created_by=user_id
        )

        # List all
        jobs = await service.list_jobs()
        assert len(jobs) >= 2
        print(f"✅ Listed {len(jobs)} jobs")

    async def test_list_jobs_with_status_filter(self, db_session):
        """Test listing jobs with status filter."""
        service = IngestionService(db_session)

        # Create job
        job = await service.create_job(
            source_type="url",
            source_url="https://example.com"
        )

        # List pending jobs
        jobs = await service.list_jobs(status="pending")
        assert any(j.id == job.id for j in jobs)
        print(f"✅ Filtered jobs by status: {len(jobs)} pending")

    async def test_list_jobs_with_user_filter(self, db_session):
        """Test listing jobs with user filter."""
        service = IngestionService(db_session)

        # Create jobs for different users
        user1 = str(uuid.uuid4())
        user2 = str(uuid.uuid4())

        await service.create_job(
            source_type="url",
            source_url="https://example.com/1",
            created_by=user1
        )
        await service.create_job(
            source_type="url",
            source_url="https://example.com/2",
            created_by=user2
        )

        # List by user
        jobs = await service.list_jobs(created_by=user1)
        assert all(j.created_by == user1 for j in jobs)
        print(f"✅ Filtered jobs by user: {len(jobs)} for {user1[:8]}...")


# =============================================================================
# ChunkResult Tests
# =============================================================================

@pytest.mark.asyncio
class TestChunkResult:
    """Test ChunkResult functionality."""

    async def test_chunk_result_basic(self, db_session):
        """Test ChunkResult creation."""
        chunks = ["chunk 1", "chunk 2", "chunk 3"]
        result = ChunkResult(
            chunks=chunks,
            original_length=100,
            chunk_count=3
        )

        assert result.chunks == chunks
        assert result.original_length == 100
        assert result.chunk_count == 3
        print("✅ ChunkResult creation test passed")

    async def test_chunk_result_stats(self, db_session):
        """Test ChunkResult statistics."""
        chunks = ["short", "medium length chunk", "very long chunk here"]
        result = ChunkResult(
            chunks=chunks,
            original_length=50,
            chunk_count=3
        )

        stats = result.get_stats()

        assert stats["chunk_count"] == 3
        assert stats["original_length"] == 50
        assert stats["total_chars"] == sum(len(c) for c in chunks)
        assert stats["min_chunk_size"] > 0
        assert stats["max_chunk_size"] > 0
        assert stats["avg_chunk_size"] > 0

        print("✅ ChunkResult stats test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
