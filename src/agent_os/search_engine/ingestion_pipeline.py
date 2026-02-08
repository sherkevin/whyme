"""Ingestion Pipeline - Orchestrates content ingestion workflow.

This module provides functionality for:
- Managing ingestion jobs
- Fetching content from URLs and PDFs
- Chunking text content
- Creating Cards/Notes and search indices
"""

import logging
import traceback
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.search_engine.models import IngestionJob
from agent_os.search_engine.content_fetcher import ContentFetcher
from agent_os.search_engine.text_chunker import TextChunker
from agent_os.search_engine.search_service import SearchService

# Import Card model (assuming it exists in cards module)
try:
    from agent_os.cards.models import Card
    CARD_AVAILABLE = True
except ImportError:
    CARD_AVAILABLE = False
    logging.warning("Card model not available, ingestion will create mock items")

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Pipeline for ingesting external content."""

    def __init__(
        self,
        db: AsyncSession,
        chunk_size: int = 1000,
        overlap: int = 200,
        fetch_timeout: int = 30
    ):
        """Initialize ingestion pipeline.

        Args:
            db: Database session
            chunk_size: Default chunk size for text splitting
            overlap: Default overlap between chunks
            fetch_timeout: Timeout for URL fetching
        """
        self.db = db
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.fetch_timeout = fetch_timeout

        # Initialize components
        self.fetcher = ContentFetcher(timeout=fetch_timeout)
        self.chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
        self.search_service = SearchService(db)

    async def run_job(self, job_id: str) -> IngestionJob:
        """Execute an ingestion job.

        Args:
            job_id: Job UUID

        Returns:
            Updated job

        Raises:
            ValueError: If job not found
            RuntimeError: If pipeline execution fails
        """
        # Get job
        from sqlalchemy import select
        stmt = select(IngestionJob).where(IngestionJob.id == uuid.UUID(job_id))
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Ingestion job not found: {job_id}")

        # Update status to running
        job.status = "running"
        job.started_at = datetime.utcnow()
        await self.db.commit()

        try:
            # Execute pipeline
            await self._execute_pipeline(job)

            # Update status to completed
            job.status = "completed"
            job.completed_at = datetime.utcnow()

            logger.info(f"Ingestion job {job_id} completed successfully")

        except Exception as e:
            # Update status to failed
            job.status = "failed"
            job.error_message = str(e)
            job.error_stack = traceback.format_exc()
            job.completed_at = datetime.utcnow()

            logger.error(f"Ingestion job {job_id} failed: {e}")

        await self.db.commit()
        await self.db.refresh(job)

        return job

    async def _execute_pipeline(self, job: IngestionJob):
        """Execute the ingestion pipeline.

        Args:
            job: Ingestion job

        Raises:
            RuntimeError: If pipeline step fails
        """
        # Step 1: Fetch content
        logger.info(f"Fetching content from {job.source_type}")
        content = await self._fetch_content(job)

        if not content or not content.strip():
            raise RuntimeError("No content could be fetched")

        # Step 2: Chunk content
        logger.info(f"Chunking content ({len(content)} chars)")
        chunks = self.chunker.chunk_text(
            content,
            chunk_size=job.chunk_size,
            overlap=job.overlap
        )

        if not chunks:
            raise RuntimeError("Content chunking produced no chunks")

        logger.info(f"Created {len(chunks)} chunks")

        # Step 3: Create items and indices
        item_ids = []
        for i, chunk in enumerate(chunks):
            item_id = await self._create_item_from_chunk(job, chunk, i + 1, len(chunks))
            item_ids.append(str(item_id))

            # Create search index
            await self._index_item(job, item_id, chunk, i + 1, len(chunks))

        # Update job with results
        job.items_created = len(item_ids)
        job.item_ids = item_ids

        logger.info(f"Created {len(item_ids)} items from ingestion job")

    async def _fetch_content(self, job: IngestionJob) -> str:
        """Fetch content based on source type.

        Args:
            job: Ingestion job

        Returns:
            Fetched content

        Raises:
            RuntimeError: If fetching fails
        """
        try:
            if job.source_type == "url":
                return await self.fetcher.fetch_url(job.source_url, timeout=self.fetch_timeout)
            elif job.source_type == "pdf":
                return await self.fetcher.fetch_pdf(job.source_file_path)
            elif job.source_type == "markdown":
                return await self.fetcher.fetch_markdown(job.source_file_path)
            else:
                raise RuntimeError(f"Unsupported source type: {job.source_type}")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch content: {e}")

    async def _create_item_from_chunk(
        self,
        job: IngestionJob,
        chunk: str,
        chunk_num: int,
        total_chunks: int
    ) -> uuid.UUID:
        """Create a Card or Note from content chunk.

        Args:
            job: Ingestion job
            chunk: Text chunk
            chunk_num: Chunk number
            total_chunks: Total number of chunks

        Returns:
            Created item ID
        """
        # Generate title
        if job.source_type == "url":
            base_title = job.source_url
        elif job.source_type == "pdf":
            base_title = job.source_file_path.split('/')[-1]
        else:
            base_title = f"Ingested Content {job.id}"

        title = f"{base_title} - Part {chunk_num}/{total_chunks}"

        if CARD_AVAILABLE:
            # Create Card
            card = Card(
                title=title,
                content=chunk,
                para_type="ingested",
                tags=["ingested", job.source_type],
                source_inbox_item_id=str(job.id)
            )
            self.db.add(card)
            await self.db.commit()
            await self.db.refresh(card)

            logger.debug(f"Created Card {card.id} for chunk {chunk_num}")
            return card.id
        else:
            # Create mock item (for testing without Card model)
            item_id = uuid.uuid4()
            logger.debug(f"Created mock item {item_id} for chunk {chunk_num}")
            return item_id

    async def _index_item(
        self,
        job: IngestionJob,
        item_id: uuid.UUID,
        chunk: str,
        chunk_num: int,
        total_chunks: int
    ):
        """Create search index for item.

        Args:
            job: Ingestion job
            item_id: Item ID
            chunk: Text chunk
            chunk_num: Chunk number
            total_chunks: Total chunks
        """
        # Generate title
        if job.source_type == "url":
            base_title = job.source_url
        elif job.source_type == "pdf":
            base_title = job.source_file_path.split('/')[-1]
        else:
            base_title = f"Ingested Content {job.id}"

        title = f"{base_title} - Part {chunk_num}/{total_chunks}"

        # Create index
        await self.search_service.index_item(
            item_type="card",
            item_id=str(item_id),
            title=title,
            content=chunk,
            tags=["ingested", job.source_type],
            search_metadata={
                "ingestion_job_id": str(job.id),
                "chunk_num": chunk_num,
                "total_chunks": total_chunks,
                "source_type": job.source_type
            }
        )

        logger.debug(f"Created search index for item {item_id}")


class IngestionService:
    """Service for managing ingestion jobs."""

    def __init__(self, db: AsyncSession):
        """Initialize ingestion service.

        Args:
            db: Database session
        """
        self.db = db
        self.pipeline = None  # Created per job with specific settings

    async def create_job(
        self,
        source_type: str,
        source_url: str = None,
        source_file_path: str = None,
        chunk_size: int = 1000,
        overlap: int = 200,
        created_by: str = None
    ) -> IngestionJob:
        """Create a new ingestion job.

        Args:
            source_type: Type of source (url, pdf, markdown)
            source_url: URL to fetch
            source_file_path: Path to local file
            chunk_size: Text chunk size
            overlap: Overlap between chunks
            created_by: User ID creating the job

        Returns:
            Created job

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate
        if source_type not in ["url", "pdf", "markdown"]:
            raise ValueError(f"Invalid source_type: {source_type}")

        if source_type == "url" and not source_url:
            raise ValueError("source_url is required for url source_type")

        if source_type in ["pdf", "markdown"] and not source_file_path:
            raise ValueError(f"source_file_path is required for {source_type} source_type")

        # Create job
        job = IngestionJob(
            source_type=source_type,
            source_url=source_url,
            source_file_path=source_file_path,
            chunk_size=chunk_size,
            overlap=overlap,
            created_by=created_by
        )

        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        logger.info(f"Created ingestion job {job.id} for {source_type}")
        return job

    async def start_job(self, job_id: str) -> IngestionJob:
        """Start an ingestion job.

        Args:
            job_id: Job UUID

        Returns:
            Updated job

        Raises:
            ValueError: If job not found
            RuntimeError: If job is not in pending state
        """
        # Get job
        from sqlalchemy import select
        stmt = select(IngestionJob).where(IngestionJob.id == uuid.UUID(job_id))
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Ingestion job not found: {job_id}")

        if job.status != "pending":
            raise RuntimeError(f"Job {job_id} is not in pending state (current: {job.status})")

        # Create pipeline with job settings
        self.pipeline = IngestionPipeline(
            db=self.db,
            chunk_size=job.chunk_size,
            overlap=job.overlap
        )

        # Run job (this will update status)
        return await self.pipeline.run_job(job_id)

    async def get_job_status(self, job_id: str) -> Dict:
        """Get job status and details.

        Args:
            job_id: Job UUID

        Returns:
            Job status dictionary

        Raises:
            ValueError: If job not found
        """
        from sqlalchemy import select
        stmt = select(IngestionJob).where(IngestionJob.id == uuid.UUID(job_id))
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Ingestion job not found: {job_id}")

        return {
            "id": str(job.id),
            "source_type": job.source_type,
            "source_url": job.source_url,
            "source_file_path": job.source_file_path,
            "status": job.status,
            "chunk_size": job.chunk_size,
            "overlap": job.overlap,
            "items_created": job.items_created,
            "item_ids": job.item_ids,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_by": job.created_by
        }

    async def list_jobs(
        self,
        status: str = None,
        created_by: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[IngestionJob]:
        """List ingestion jobs.

        Args:
            status: Filter by status
            created_by: Filter by creator
            limit: Max results
            offset: Pagination offset

        Returns:
            List of jobs
        """
        from sqlalchemy import select

        stmt = select(IngestionJob)

        if status:
            stmt = stmt.where(IngestionJob.status == status)

        if created_by:
            stmt = stmt.where(IngestionJob.created_by == created_by)

        stmt = stmt.order_by(IngestionJob.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return result.scalars().all()
