"""Search Demo - Demonstrates the Search functionality.

This demo shows:
1. Creating search indices for various items
2. Executing different types of searches
3. Filtering by type and tags
4. Result ranking and pagination
5. Updating and deleting indices
"""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_os.db.base import Base
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


async def demo_search():
    """Run search demonstration."""

    # Initialize database
    await init_db()

    print("=" * 70)
    print("Stage 4 Search Demo")
    print("=" * 70)

    async with async_session() as db:
        service = SearchService(db)
        engine = SearchEngine(db)

        # =========================================================================
        # 1. Create Sample Data
        # =========================================================================

        print("\n[1] Creating sample search indices...")

        sample_data = [
            {
                "item_type": "card",
                "title": "FastAPI Performance Optimization",
                "content": "Learn how to optimize FastAPI applications for high performance. "
                         "Topics include async operations, database query optimization, "
                         "caching strategies, and deployment best practices.",
                "tags": ["backend", "python", "performance"]
            },
            {
                "item_type": "card",
                "title": "React State Management Guide",
                "content": "Comprehensive guide to state management in React applications. "
                         "Covering Redux, Context API, Zustand, and Recoil. "
                         "Learn when to use each approach.",
                "tags": ["frontend", "react", "javascript"]
            },
            {
                "item_type": "card",
                "title": "Docker Container Security",
                "content": "Best practices for securing Docker containers in production. "
                         "Including image scanning, vulnerability management, "
                         "runtime security, and network isolation.",
                "tags": ["devops", "docker", "security"]
            },
            {
                "item_type": "task",
                "title": "Implement User Authentication",
                "content": "Add JWT-based authentication to the application. "
                         "Include login, logout, token refresh, and password reset functionality.",
                "tags": ["backend", "security", "todo"]
            },
            {
                "item_type": "task",
                "title": "Design Database Schema",
                "content": "Create normalized database schema for the new feature. "
                         "Include proper indexes, foreign keys, and constraints.",
                "tags": ["backend", "database", "todo"]
            },
            {
                "item_type": "note",
                "title": "Meeting Notes - Architecture Review",
                "content": "Discussed microservices architecture for the new platform. "
                         "Key decisions: use event-driven communication, implement circuit breakers, "
                         "adopt API gateway pattern.",
                "tags": ["architecture", "meeting"]
            },
            {
                "item_type": "note",
                "title": "Python Async Patterns",
                "content": "Notes on async/await in Python: asyncio vs trio vs curio. "
                         "Best practices for async code, avoiding common pitfalls.",
                "tags": ["python", "async", "learning"]
            }
        ]

        for item in sample_data:
            item_id = uuid.uuid4()
            await service.index_item(
                item_type=item["item_type"],
                item_id=str(item_id),
                title=item["title"],
                content=item["content"],
                tags=item["tags"],
                search_metadata={"indexed_at": datetime.utcnow().isoformat()}
            )
            print(f"  ✓ Indexed: {item['item_type']} - {item['title']}")

        # =========================================================================
        # 2. Simple Text Search
        # =========================================================================

        print("\n[2] Simple text search for 'Python'...")
        query = SearchQuery(query="Python")
        result = await engine.search(query)

        print(f"  Found {result.total} results:")
        for r in result.results:
            print(f"    - [{r.item_type}] {r.title} (score: {r.score:.2f})")

        # =========================================================================
        # 3. Search with Type Filter
        # =========================================================================

        print("\n[3] Search for 'API' in cards only...")
        query = SearchQuery(
            query="API",
            item_types=["card"]
        )
        result = await engine.search(query)

        print(f"  Found {result.total} card results:")
        for r in result.results:
            print(f"    - {r.title}")

        # =========================================================================
        # 4. Search with Tag Filter
        # =========================================================================

        print("\n[4] Search for 'security' with tag filter...")
        query = SearchQuery(
            query="security",
            tags=["security"]
        )
        result = await engine.search(query)

        print(f"  Found {result.total} results with 'security' tag:")
        for r in result.results:
            tags_str = ", ".join(r.tags)
            print(f"    - {r.title} [{tags_str}]")

        # =========================================================================
        # 5. Search with Sorting
        # =========================================================================

        print("\n[5] Search results sorted by date (newest first)...")
        query = SearchQuery(
            query="",
            sort_by="-date",
            page_size=10
        )
        result = await engine.search(query)

        print(f"  Showing {len(result.results)} most recent items:")
        for i, r in enumerate(result.results, 1):
            date_str = r.created_at.strftime("%Y-%m-%d %H:%M")
            print(f"    {i}. [{r.item_type}] {r.title} ({date_str})")

        # =========================================================================
        # 6. Pagination
        # =========================================================================

        print("\n[6] Paginated search (page 1, page_size=3)...")
        query = SearchQuery(
            query="",
            page=1,
            page_size=3
        )
        result = await engine.search(query)

        print(f"  Total: {result.total} | Page: {result.page}/{(result.total + result.page_size - 1) // result.page_size}")
        for i, r in enumerate(result.results, 1):
            print(f"    {i}. {r.title}")

        # =========================================================================
        # 7. Content Snippet Generation
        # =========================================================================

        print("\n[7] Search with content snippets...")
        query = SearchQuery(query="best practices")
        result = await engine.search(query)

        print(f"  Found {result.total} results with snippets:")
        for r in result.results:
            snippet = r.content_snippet[:100] + "..." if len(r.content_snippet) > 100 else r.content_snippet
            print(f"    - {r.title}")
            print(f"      {snippet}")

        # =========================================================================
        # 8. Update Index
        # =========================================================================

        print("\n[8] Updating a search index...")

        # Get a card to update
        indices = await service.list_indices(item_type="card", limit=1)
        if indices:
            index = indices[0]
            old_title = index.title
            new_title = f"[UPDATED] {old_title}"

            await service.index_item(
                item_type=index.item_type,
                item_id=str(index.item_id),
                title=new_title,
                content=index.content
            )
            print(f"  ✓ Updated: {old_title} -> {new_title}")

            # Verify update
            updated = await service.get_index(index.item_type, str(index.item_id))
            print(f"  ✓ Verified: {updated.title}")

        # =========================================================================
        # 9. Statistics
        # =========================================================================

        print("\n[9] Search index statistics...")
        stats = await service.get_index_stats()
        print(f"  Total indices: {stats['total']}")
        print("  By type:")
        for item_type, count in stats['by_type'].items():
            print(f"    - {item_type}: {count}")

        # =========================================================================
        # 10. Delete Index
        # =========================================================================

        print("\n[10] Deleting a search index...")

        # Create a temporary item to delete
        temp_id = uuid.uuid4()
        await service.index_item(
            item_type="card",
            item_id=str(temp_id),
            title="Temporary Card to Delete",
            content="This will be deleted"
        )
        print(f"  ✓ Created temporary card: {temp_id}")

        # Delete it
        deleted = await service.delete_index("card", str(temp_id))
        print(f"  ✓ Deleted: {deleted}")

        # Verify deletion
        exists = await service.get_index("card", str(temp_id))
        print(f"  ✓ Verified deletion: {exists is None}")

        # =========================================================================
        # Summary
        # =========================================================================

        print("\n" + "=" * 70)
        print("Search Demo Complete!")
        print("=" * 70)
        print("\nKey Features Demonstrated:")
        print("  ✓ Full-text search with LIKE pattern matching")
        print("  ✓ Multi-type item indexing (card, task, note)")
        print("  ✓ Tag-based filtering")
        print("  ✓ Type-based filtering")
        print("  ✓ Date sorting and pagination")
        print("  ✓ Content snippet generation")
        print("  ✓ Relevance scoring")
        print("  ✓ Index CRUD operations")
        print("  ✓ Statistics and metadata")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Stage 4 Search Module Demo")
    print("Demonstrates unified search across multiple data types")
    print("=" * 70)

    asyncio.run(demo_search())
