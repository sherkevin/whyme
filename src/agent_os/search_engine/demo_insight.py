"""Insight Demo - Demonstrates insight generation capabilities.

This demo shows:
1. Summary generation
2. Trend analysis
3. Topic clustering
4. Pattern detection
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_os.db.base import Base
from agent_os.search_engine.insight_service import InsightService
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


async def setup_sample_data(db: AsyncSession):
    """Create sample data for insight generation."""
    print("\n[Setup] Creating sample data...")

    search_service = SearchService(db, auto_embed=False)

    # Sample cards with different themes
    sample_data = [
        # Python programming
        ("Python Basics", "Learn Python fundamentals including variables, loops, and functions", ["python", "programming", "tutorial"]),
        ("Advanced Python", "Master decorators, generators, and metaclasses in Python", ["python", "advanced", "programming"]),
        ("Python for Data Science", "Use pandas, numpy, and matplotlib for data analysis", ["python", "data", "science"]),

        # JavaScript programming
        ("JavaScript Essentials", "Learn modern ES6+ JavaScript syntax and features", ["javascript", "programming", "web"]),
        ("React Framework", "Build modern web applications with React", ["javascript", "react", "web"]),
        ("Node.js Backend", "Create server-side applications with Node.js", ["javascript", "backend", "nodejs"]),

        # Web development
        ("HTML5 Guide", "Master semantic HTML5 markup", ["html", "web", "frontend"]),
        ("CSS3 Styling", "Create beautiful responsive layouts with CSS3", ["css", "web", "design"]),
        ("TypeScript Basics", "Add type safety to your JavaScript code", ["typescript", "javascript", "web"]),

        # Data science
        ("Machine Learning Intro", "Introduction to ML algorithms and concepts", ["ml", "data", "science"]),
        ("Deep Learning", "Neural networks and deep learning frameworks", ["dl", "ml", "ai"]),
        ("Data Visualization", "Create compelling charts and graphs", ["visualization", "data", "science"]),
    ]

    for i, (title, content, tags) in enumerate(sample_data):
        await search_service.index_item(
            item_type="card",
            item_id=uuid.uuid4(),
            title=title,
            content=content,
            tags=tags
        )

    print(f"    Created {len(sample_data)} sample cards")


async def demo_insight():
    """Run insight demonstration."""

    # Initialize database
    await init_db()

    print("=" * 70)
    print("Stage 4 Insight Demo")
    print("Demonstrates insight generation and analysis")
    print("=" * 70)

    async with async_session() as db:
        # Setup sample data
        await setup_sample_data(db)

        # =========================================================================
        # 1. Summary Insight
        # =========================================================================

        print("\n[1] Summary Insight")

        insight_service = InsightService(db)

        start = time.time()
        summary = await insight_service.generate_summary(
            item_type="card",
            name="Card Summary"
        )
        elapsed = (time.time() - start) * 1000

        print(f"\n  Generated summary in {elapsed:.2f}ms")
        print(f"    Name: {summary.name}")
        print(f"    Items analyzed: {summary.sample_count}")
        print(f"    Confidence: {summary.confidence}")
        print("\n  Summary Statistics:")
        print(f"    Total items: {summary.insight_data['total_items']}")
        print(f"    Unique tags: {summary.insight_data['unique_tags_count']}")
        print(f"    Avg content length: {summary.insight_data['avg_content_length']} chars")
        print("\n  Key Topics:")
        for topic in summary.insight_data['key_topics'][:5]:
            print(f"    - {topic}")
        print("\n  Summary Text:")
        print(f"    {summary.insight_data['summary_text']}")

        # =========================================================================
        # 2. Trend Insight
        # =========================================================================

        print("\n[2] Trend Insight")

        # Generate date range (last 30 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        date_range = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }

        start = time.time()
        trend = await insight_service.generate_trend(
            item_type="card",
            metric="count",
            date_range=date_range,
            group_by="day",
            name="Creation Trend"
        )
        elapsed = (time.time() - start) * 1000

        print(f"\n  Generated trend in {elapsed:.2f}ms")
        print(f"    Name: {trend.name}")
        print(f"    Items analyzed: {trend.sample_count}")
        print(f"    Trend direction: {trend.insight_data['trend_direction']}")
        print(f"    Change: {trend.insight_data['change_percent']:.1f}%")
        print("\n  Statistics:")
        print(f"    Average: {trend.insight_data['average']:.1f} items/period")
        print(f"    Min: {trend.insight_data['min']}, Max: {trend.insight_data['max']}")
        print(f"    Periods analyzed: {trend.insight_data['periods_analyzed']}")

        # =========================================================================
        # 3. Topic Insight
        # =========================================================================

        print("\n[3] Topic Clustering Insight")

        start = time.time()
        topics = await insight_service.generate_topics(
            item_type="card",
            num_topics=5,
            name="Topic Analysis"
        )
        elapsed = (time.time() - start) * 1000

        print(f"\n  Generated topics in {elapsed:.2f}ms")
        print(f"    Name: {topics.name}")
        print(f"    Items analyzed: {topics.sample_count}")
        print(f"    Coverage: {topics.insight_data['coverage']}%")
        print(f"\n  Top {len(topics.insight_data['topics'])} Topics:")
        for topic in topics.insight_data['topics']:
            print(f"    - {topic['topic_name']}")
            print(f"      Frequency: {topic['frequency']} ({topic['percentage']:.1f}%)")

        # =========================================================================
        # 4. Pattern Insight
        # =========================================================================

        print("\n[4] Pattern Detection Insight")

        # Creation time pattern
        start = time.time()
        pattern = await insight_service.generate_pattern(
            item_type="card",
            pattern_type="creation_time",
            name="Creation Time Pattern"
        )
        elapsed = (time.time() - start) * 1000

        print(f"\n  Generated pattern in {elapsed:.2f}ms")
        print(f"    Name: {pattern.name}")
        print(f"    Pattern type: {pattern.insight_data['pattern_type']}")
        print(f"    Patterns found: {len(pattern.insight_data['patterns'])}")
        print("\n  Detected Patterns:")
        for p in pattern.insight_data['patterns']:
            print(f"    - {p['pattern_name']}: {p['description']}")

        # Content length pattern
        pattern2 = await insight_service.generate_pattern(
            item_type="card",
            pattern_type="content_length",
            name="Content Length Pattern"
        )

        print("\n  Content Length Pattern:")
        for p in pattern2.insight_data['patterns']:
            if p['pattern_name'] == 'average_content_length':
                print(f"    Average: {p['value']:.0f} characters")
                print(f"    Range: {p['min']} - {p['max']} characters")

        # =========================================================================
        # 5. Query Insights
        # =========================================================================

        print("\n[5] Query Insights")

        # List all insights
        all_insights = await insight_service.list_insights(limit=10)

        print(f"\n  Total insights: {len(all_insights)}")
        for insight in all_insights:
            print(f"    - {insight.cluster_type}: {insight.name}")
            print(f"      Confidence: {insight.confidence}, Sample count: {insight.sample_count}")

        # List by type
        summaries = await insight_service.list_insights(cluster_type="summary", limit=5)
        print(f"\n  Summary insights: {len(summaries)}")

        trends = await insight_service.list_insights(cluster_type="trend", limit=5)
        print(f"  Trend insights: {len(trends)}")

        topic_clusters = await insight_service.list_insights(cluster_type="topic", limit=5)
        print(f"  Topic insights: {len(topic_clusters)}")

        patterns = await insight_service.list_insights(cluster_type="pattern", limit=5)
        print(f"  Pattern insights: {len(patterns)}")

        # =========================================================================
        # 6. Get Specific Insight
        # =========================================================================

        print("\n[6] Retrieve Specific Insight")

        # Get the summary we created earlier
        retrieved = await insight_service.get_insight(str(summary.id))

        if retrieved:
            print(f"\n  Retrieved: {retrieved.name}")
            print(f"  Type: {retrieved.cluster_type}")
            print(f"  Created at: {retrieved.generated_at}")
            print(f"  Source items: {len(retrieved.source_item_ids)}")

        # =========================================================================
        # 7. Performance Metrics
        # =========================================================================

        print("\n[7] Performance Metrics")

        # Generate multiple insights to measure performance
        iterations = 5
        times = []

        for i in range(iterations):
            start = time.time()
            await insight_service.generate_summary(
                item_type="card",
                name=f"Performance Test {i}"
            )
            times.append((time.time() - start) * 1000)

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n  Summary generation over {iterations} iterations:")
        print(f"    Average: {avg_time:.2f}ms")
        print(f"    Min: {min_time:.2f}ms")
        print(f"    Max: {max_time:.2f}ms")

        # =========================================================================
        # Summary
        # =========================================================================

        print("\n" + "=" * 70)
        print("Insight Demo Complete!")
        print("=" * 70)
        print("\nKey Features Demonstrated:")
        print("  ✓ Summary generation with statistics")
        print("  ✓ Trend analysis with direction detection")
        print("  ✓ Topic clustering with frequency analysis")
        print("  ✓ Pattern detection (creation time, content length)")
        print("  ✓ Insight querying and filtering")
        print("  ✓ Performance measurement")
        print("\nArchitecture Notes:")
        print("  • SQLite-compatible date functions")
        print("  • Tag-based topic extraction")
        print("  • Statistical trend analysis")
        print("  • Configurable confidence scores")
        print("  • Fast in-memory processing (< 100ms)")
        print("\nFuture Enhancements:")
        print("  • LLM-powered summarization")
        print("  • K-means clustering for topics")
        print("  • Advanced pattern detection")
        print("  • Time-series forecasting")
        print("  • Insight caching and refresh")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Stage 4 Insight Module Demo")
    print("Demonstrates insight generation and analysis capabilities")
    print("=" * 70)

    asyncio.run(demo_insight())
