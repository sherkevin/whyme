"""Performance test configuration and fixtures."""

import pytest
import asyncio
import time
import statistics
from typing import List, Dict, Any
from datetime import datetime
from statistics import StatisticsError

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_os.search_engine.search_engine import SearchEngine, SearchQuery
from agent_os.search_engine.search_service import SearchService
from agent_os.search_engine.models import SearchIndex, Base


# ============================================================================
# Performance Benchmarks
# ============================================================================

# PRD4 Performance Requirements
PERF_BENCHMARKS = {
    "agent_response_p75": 10.0,  # seconds (P75, max 30s)
    "agent_response_max": 30.0,   # seconds (absolute max)
    "input_response": 0.05,      # seconds (50ms)
    "search_response_200": 0.1,  # seconds (100ms for 200 items)
    "concurrent_search_4": 0.5,  # seconds (4 concurrent searches)
}


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
async def perf_db():
    """Create in-memory database for performance testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # Seed test data
        await seed_test_data(session, num_items=200)
        yield session

    await engine.dispose()


@pytest.fixture
def perf_thresholds():
    """Get performance thresholds for validation."""
    return PERF_BENCHMARKS


# ============================================================================
# Test Data Seeding
# ============================================================================

async def seed_test_data(db: AsyncSession, num_items: int = 200):
    """Seed test data for performance testing.

    Args:
        db: Database session
        num_items: Number of test items to create
    """
    import uuid

    item_types = ["card", "task", "note", "resource"]
    tags_list = [
        ["important", "urgent"],
        ["work", "project-a"],
        ["personal", "ideas"],
        ["reference", "documentation"],
        ["bug", "fix-required"]
    ]

    for i in range(num_items):
        item_type = item_types[i % len(item_types)]
        tags = tags_list[i % len(tags_list)]

        index = SearchIndex(
            item_type=item_type,
            item_id=uuid.uuid4(),
            title=f"Test Item {i}: {item_type.capitalize()}",
            content=f"This is test content for item {i}. " * 10,
            tags=tags,
            search_metadata={
                "priority": i % 3,
                "status": "active"
            }
        )

        db.add(index)

    await db.commit()
    print(f"✓ Seeded {num_items} test items")


# ============================================================================
# Performance Utilities
# ============================================================================

class PerformanceMetrics:
    """Track and analyze performance metrics."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def add_result(self, name: str, duration: float, success: bool = True, metadata: Dict = None):
        """Add a performance result."""
        self.results.append({
            "name": name,
            "duration": duration,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        })

    def get_statistics(self, name: str = None) -> Dict[str, Any]:
        """Get statistics for results.

        Args:
            name: Optional filter by test name

        Returns:
            Statistics dictionary
        """
        if name:
            data = [r for r in self.results if r["name"] == name]
        else:
            data = self.results

        if not data:
            return {}

        durations = [r["duration"] for r in data if r["success"]]
        success_rate = sum(1 for r in data if r["success"]) / len(data)

        stats = {
            "count": len(data),
            "success_rate": success_rate,
            "min": min(durations) if durations else 0,
            "max": max(durations) if durations else 0,
            "mean": statistics.mean(durations) if durations else 0,
            "median": statistics.median(durations) if durations else 0,
            "stdev": statistics.stdev(durations) if len(durations) > 1 else 0,
        }

        # Add percentiles if we have enough data
        if len(durations) >= 2:
            try:
                stats["p50"] = statistics.quantiles(durations, n=2)[1]
            except (IndexError, StatisticsError):
                stats["p50"] = stats["median"]

            try:
                stats["p75"] = statistics.quantiles(durations, n=4)[3]
            except (IndexError, StatisticsError):
                stats["p75"] = durations[-1] if durations else 0

            try:
                stats["p95"] = statistics.quantiles(durations, n=20)[19] if len(durations) >= 20 else durations[-1]
            except (IndexError, StatisticsError):
                stats["p95"] = durations[-1] if durations else 0

            try:
                stats["p99"] = statistics.quantiles(durations, n=100)[99] if len(durations) >= 100 else durations[-1]
            except (IndexError, StatisticsError):
                stats["p99"] = durations[-1] if durations else 0
        else:
            stats["p50"] = durations[0] if durations else 0
            stats["p75"] = durations[0] if durations else 0
            stats["p95"] = durations[0] if durations else 0
            stats["p99"] = durations[0] if durations else 0

        return stats

    def print_summary(self):
        """Print performance summary."""
        print("\n" + "="*60)
        print("PERFORMANCE TEST SUMMARY")
        print("="*60)

        for name in set(r["name"] for r in self.results):
            stats = self.get_statistics(name)
            if stats:
                print(f"\n{name}:")
                print(f"  Samples: {stats['count']}")
                print(f"  Success Rate: {stats['success_rate']*100:.1f}%")
                print(f"  Mean: {stats['mean']*1000:.2f}ms")
                print(f"  Median (P50): {stats['p50']*1000:.2f}ms")
                print(f"  P75: {stats['p75']*1000:.2f}ms")
                print(f"  P95: {stats['p95']*1000:.2f}ms")
                print(f"  P99: {stats['p99']*1000:.2f}ms")
                print(f"  Min: {stats['min']*1000:.2f}ms")
                print(f"  Max: {stats['max']*1000:.2f}ms")

        print("\n" + "="*60)


@pytest.fixture
def perf_metrics():
    """Create performance metrics tracker."""
    return PerformanceMetrics()


# ============================================================================
# Benchmark Decorator
# ============================================================================

def benchmark(name: str, thresholds: Dict[str, float] = None):
    """Decorator for benchmarking async functions.

    Args:
        name: Benchmark name
        thresholds: Optional performance thresholds

    Usage:
        @benchmark("search_100_items", {"p95": 0.1})
        async def test_search_performance(perf_db, perf_metrics):
            # ... test code
    """
    def decorator(func):
        async def wrapper(*args, perf_metrics: PerformanceMetrics, **kwargs):
            # Warmup
            for _ in range(3):
                await func(*args, **kwargs)

            # Actual benchmark runs
            durations = []
            for _ in range(10):
                start = time.perf_counter()
                try:
                    await func(*args, **kwargs)
                    success = True
                except Exception as e:
                    success = False
                    print(f"Error: {e}")
                finally:
                    duration = time.perf_counter() - start
                    durations.append(duration)
                    perf_metrics.add_result(name, duration, success)

            # Validate against thresholds
            if thresholds:
                stats = perf_metrics.get_statistics(name)
                for metric, limit in thresholds.items():
                    actual = stats.get(metric, 0)
                    if actual > limit:
                        pytest.fail(
                            f"{name}: {metric} ({actual:.3f}s) exceeds threshold ({limit:.3f}s)"
                        )

        return wrapper
    return decorator
