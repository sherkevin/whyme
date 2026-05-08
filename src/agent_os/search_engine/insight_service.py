"""Insight Service - Generate insights from indexed data.

This module provides aggregation and analysis capabilities:
- Summary generation
- Trend detection
- Topic extraction
- Pattern discovery
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select

from agent_os.search_engine.models import InsightCluster, SearchIndex


class InsightService:
    """Insight generation service.

    Provides methods to analyze aggregated data and generate
    structured insights (summaries, trends, topics, patterns).
    """

    def __init__(self, db: AsyncSession):
        """Initialize insight service.

        Args:
            db: Async database session
        """
        self.db = db

    async def generate_summary(
        self,
        item_type: str,
        item_ids: list[str] = None,
        date_range: dict[str, str] = None,
        name: str = None,
        generated_by: str = None
    ) -> InsightCluster:
        """Generate summary insight.

        Analyzes a collection of items and generates a summary
        with key topics and statistics.

        Args:
            item_type: Type of items to analyze ('card', 'task', 'note', etc.)
            item_ids: Optional list of specific item IDs to analyze
            date_range: Optional date range filter {"start": "...", "end": "..."}
            name: Optional name for the insight cluster
            generated_by: Optional user UUID who requested the insight

        Returns:
            InsightCluster: Generated summary insight
        """
        # Build query
        stmt = select(SearchIndex).where(SearchIndex.item_type == item_type)

        # Filter by item IDs if provided
        if item_ids:
            # Convert string IDs to UUID if needed
            uuid_ids = []
            for item_id in item_ids:
                try:
                    uuid_ids.append(uuid.UUID(item_id))
                except (ValueError, AttributeError):
                    pass
            if uuid_ids:
                stmt = stmt.where(SearchIndex.item_id.in_(uuid_ids))

        # Filter by date range if provided
        if date_range:
            if date_range.get("start"):
                start_date = self._parse_datetime(date_range["start"])
                if start_date:
                    stmt = stmt.where(SearchIndex.created_at >= start_date)
            if date_range.get("end"):
                end_date = self._parse_datetime(date_range["end"])
                if end_date:
                    stmt = stmt.where(SearchIndex.created_at <= end_date)

        # Limit to 100 items for performance
        stmt = stmt.limit(100)

        # Execute query
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        if not items:
            raise ValueError(f"No {item_type} items found matching the criteria")

        # Generate summary statistics
        total_items = len(items)
        unique_tags = set()
        total_content_length = 0

        for item in items:
            if item.tags:
                unique_tags.update(item.tags)
            if item.content:
                total_content_length += len(item.content)

        # Extract key topics from tags
        key_topics = list(unique_tags)[:10]  # Top 10 tags

        # Generate summary text
        summary_text = self._generate_summary_text(items)

        # Create insight data
        insight_data = {
            "total_items": total_items,
            "summary_text": summary_text,
            "key_topics": key_topics,
            "unique_tags_count": len(unique_tags),
            "avg_content_length": total_content_length // total_items if total_items > 0 else 0,
            "date_range": {
                "earliest": min(item.created_at for item in items).isoformat() if items else None,
                "latest": max(item.created_at for item in items).isoformat() if items else None
            }
        }

        # Create InsightCluster
        cluster = InsightCluster(
            cluster_type="summary",
            name=name or f"{item_type} summary",
            description=f"Summary of {total_items} {item_type} items",
            source_item_type=item_type,
            source_item_ids=[str(item.item_id) for item in items],
            date_range=date_range,
            insight_data=insight_data,
            confidence=0.8,
            sample_count=total_items,
            parameters={
                "item_ids": item_ids,
                "date_range": date_range
            },
            generated_by=generated_by
        )

        self.db.add(cluster)
        await self.db.commit()
        await self.db.refresh(cluster)

        return cluster

    async def generate_trend(
        self,
        item_type: str,
        metric: str = "count",
        date_range: dict[str, str] = None,
        group_by: str = "day",
        name: str = None,
        generated_by: str = None
    ) -> InsightCluster:
        """Generate trend insight.

        Analyzes items over time to detect trends and patterns.

        Args:
            item_type: Type of items to analyze
            metric: Metric to analyze ('count', 'avg_content_length', 'tag_frequency')
            date_range: Date range for analysis
            group_by: Time grouping ('day', 'week', 'month')
            name: Optional name for the insight cluster
            generated_by: Optional user UUID

        Returns:
            InsightCluster: Generated trend insight
        """
        # Default date range: last 30 days
        if not date_range:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            date_range = {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }

        start_date = self._parse_datetime(date_range.get("start"))
        end_date = self._parse_datetime(date_range.get("end"))

        if not start_date or not end_date:
            raise ValueError("Invalid date_range format")

        # Build query based on group_by
        # Note: Using SQLite-compatible date functions
        if group_by == "day":
            date_trunc = func.date(SearchIndex.created_at)
        elif group_by == "week":
            # SQLite doesn't have date_trunc, use strftime for week grouping
            # Format: YYYY-WW (year-week number)
            date_trunc = func.strftime('%Y-W%W', SearchIndex.created_at)
        elif group_by == "month":
            # SQLite: format as YYYY-MM
            date_trunc = func.strftime('%Y-%m', SearchIndex.created_at)
        else:
            raise ValueError(f"Invalid group_by: {group_by}")

        # Execute aggregation query
        stmt = select(
            date_trunc.label('period'),
            func.count(SearchIndex.id).label('count')
        ).where(
            and_(
                SearchIndex.item_type == item_type,
                SearchIndex.created_at >= start_date,
                SearchIndex.created_at <= end_date
            )
        ).group_by('period').order_by('period')

        result = await self.db.execute(stmt)
        rows = result.all()

        if not rows:
            raise ValueError(f"No {item_type} items found in the specified date range")

        # Extract data
        labels = [str(row.period) for row in rows]
        values = [row.count for row in rows]

        # Calculate trend statistics
        trend_data = self._calculate_trend_statistics(values)

        # Create insight data
        insight_data = {
            "metric": metric,
            "group_by": group_by,
            "values": values,
            "labels": labels,
            "total_items": sum(values),
            "periods_analyzed": len(values),
            **trend_data
        }

        # Create InsightCluster
        cluster = InsightCluster(
            cluster_type="trend",
            name=name or f"{item_type} {metric} trend",
            description=f"Trend analysis of {item_type} items grouped by {group_by}",
            source_item_type=item_type,
            date_range=date_range,
            insight_data=insight_data,
            confidence=0.9,
            sample_count=sum(values),
            parameters={
                "metric": metric,
                "group_by": group_by,
                "date_range": date_range
            },
            generated_by=generated_by
        )

        self.db.add(cluster)
        await self.db.commit()
        await self.db.refresh(cluster)

        return cluster

    async def generate_topics(
        self,
        item_type: str,
        item_ids: list[str] = None,
        num_topics: int = 5,
        name: str = None,
        generated_by: str = None
    ) -> InsightCluster:
        """Generate topic clustering insight.

        Analyzes items to extract and cluster topics.

        Args:
            item_type: Type of items to analyze
            item_ids: Optional list of specific item IDs
            num_topics: Number of topics to extract
            name: Optional name for the insight cluster
            generated_by: Optional user UUID

        Returns:
            InsightCluster: Generated topic insight
        """
        # Build query
        stmt = select(SearchIndex).where(SearchIndex.item_type == item_type)

        if item_ids:
            uuid_ids = []
            for item_id in item_ids:
                try:
                    uuid_ids.append(uuid.UUID(item_id))
                except (ValueError, AttributeError):
                    pass
            if uuid_ids:
                stmt = stmt.where(SearchIndex.item_id.in_(uuid_ids))

        stmt = stmt.limit(200)

        # Execute query
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        if not items:
            raise ValueError(f"No {item_type} items found matching the criteria")

        # Extract topics from tags and titles
        topic_analysis = self._extract_topics(items, num_topics)

        # Create insight data
        insight_data = {
            "num_topics": num_topics,
            "topics": topic_analysis["topics"],
            "total_items_analyzed": len(items),
            "coverage": topic_analysis["coverage"]
        }

        # Create InsightCluster
        cluster = InsightCluster(
            cluster_type="topic",
            name=name or f"{item_type} topic analysis",
            description=f"Topic clustering of {len(items)} {item_type} items",
            source_item_type=item_type,
            source_item_ids=[str(item.item_id) for item in items],
            insight_data=insight_data,
            confidence=0.75,
            sample_count=len(items),
            parameters={
                "item_ids": item_ids,
                "num_topics": num_topics
            },
            generated_by=generated_by
        )

        self.db.add(cluster)
        await self.db.commit()
        await self.db.refresh(cluster)

        return cluster

    async def generate_pattern(
        self,
        item_type: str,
        pattern_type: str = "creation_time",
        date_range: dict[str, str] = None,
        name: str = None,
        generated_by: str = None
    ) -> InsightCluster:
        """Generate pattern discovery insight.

        Detects patterns in data (e.g., creation times, content patterns).

        Args:
            item_type: Type of items to analyze
            pattern_type: Type of pattern to detect
            date_range: Optional date range filter
            name: Optional name for the insight cluster
            generated_by: Optional user UUID

        Returns:
            InsightCluster: Generated pattern insight
        """
        # Build query
        stmt = select(SearchIndex).where(SearchIndex.item_type == item_type)

        if date_range:
            if date_range.get("start"):
                start_date = self._parse_datetime(date_range["start"])
                if start_date:
                    stmt = stmt.where(SearchIndex.created_at >= start_date)
            if date_range.get("end"):
                end_date = self._parse_datetime(date_range["end"])
                if end_date:
                    stmt = stmt.where(SearchIndex.created_at <= end_date)

        stmt = stmt.limit(500)

        # Execute query
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        if not items:
            raise ValueError(f"No {item_type} items found for pattern analysis")

        # Detect patterns
        pattern_data = self._detect_patterns(items, pattern_type)

        # Create insight data
        insight_data = {
            "pattern_type": pattern_type,
            "patterns": pattern_data["patterns"],
            "total_items_analyzed": len(items),
            "confidence_explanation": pattern_data["explanation"]
        }

        # Create InsightCluster
        cluster = InsightCluster(
            cluster_type="pattern",
            name=name or f"{item_type} {pattern_type} pattern",
            description=f"Pattern detection in {item_type} items",
            source_item_type=item_type,
            source_item_ids=[str(item.item_id) for item in items],
            date_range=date_range,
            insight_data=insight_data,
            confidence=0.7,
            sample_count=len(items),
            parameters={
                "pattern_type": pattern_type,
                "date_range": date_range
            },
            generated_by=generated_by
        )

        self.db.add(cluster)
        await self.db.commit()
        await self.db.refresh(cluster)

        return cluster

    async def get_insight(
        self,
        insight_id: str
    ) -> InsightCluster | None:
        """Get an insight cluster by ID.

        Args:
            insight_id: UUID of the insight cluster

        Returns:
            InsightCluster or None
        """
        try:
            insight_uuid = uuid.UUID(insight_id)
        except (ValueError, AttributeError):
            return None

        stmt = select(InsightCluster).where(InsightCluster.id == insight_uuid)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_insights(
        self,
        cluster_type: str = None,
        source_item_type: str = None,
        limit: int = 20,
        include_expired: bool = False
    ) -> list[InsightCluster]:
        """List insight clusters.

        Args:
            cluster_type: Optional filter by cluster type
            source_item_type: Optional filter by source item type
            limit: Maximum number of results
            include_expired: Whether to include expired insights

        Returns:
            List of InsightCluster
        """
        stmt = select(InsightCluster).order_by(InsightCluster.generated_at.desc())

        if cluster_type:
            stmt = stmt.where(InsightCluster.cluster_type == cluster_type)

        if source_item_type:
            stmt = stmt.where(InsightCluster.source_item_type == source_item_type)

        if not include_expired:
            stmt = stmt.where(
                or_(
                    InsightCluster.expires_at.is_(None),
                    InsightCluster.expires_at > datetime.utcnow()
                )
            )

        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_insight(
        self,
        insight_id: str
    ) -> bool:
        """Delete an insight cluster.

        Args:
            insight_id: UUID of the insight cluster

        Returns:
            True if deleted, False if not found
        """
        try:
            insight_uuid = uuid.UUID(insight_id)
        except (ValueError, AttributeError):
            return False

        stmt = select(InsightCluster).where(InsightCluster.id == insight_uuid)
        result = await self.db.execute(stmt)
        insight = result.scalar_one_or_none()

        if not insight:
            return False

        await self.db.delete(insight)
        await self.db.commit()

        return True

    # ========================================================================
    # Private helper methods
    # ========================================================================

    def _parse_datetime(self, dt_str: str) -> datetime | None:
        """Parse datetime string.

        Supports ISO format and common variants.
        """
        if not dt_str:
            return None

        try:
            # Try ISO format
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            # Try common formats
            for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
            return None

    def _generate_summary_text(self, items: list[SearchIndex]) -> str:
        """Generate summary text from items."""
        if not items:
            return "No items to summarize."

        total = len(items)
        with_content = sum(1 for item in items if item.content)
        with_tags = sum(1 for item in items if item.tags)

        # Get most common tags
        all_tags = []
        for item in items:
            if item.tags:
                all_tags.extend(item.tags)

        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        summary_parts = [
            f"Analyzed {total} items.",
            f"{with_content} items contain content ({with_content*100//total}%).",
            f"{with_tags} items have tags ({with_tags*100//total}%)."
        ]

        if top_tags:
            tag_names = [tag for tag, count in top_tags]
            summary_parts.append(f"Top tags: {', '.join(tag_names)}.")

        return " ".join(summary_parts)

    def _calculate_trend_statistics(self, values: list[int]) -> dict[str, Any]:
        """Calculate trend statistics from time series values."""
        if len(values) < 2:
            return {
                "trend_direction": "unknown",
                "change_percent": 0,
                "average": sum(values) / len(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0
            }

        # Calculate trend direction
        first_avg = sum(values[:len(values)//2]) / (len(values)//2)
        second_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)

        if second_avg > first_avg * 1.1:
            trend_direction = "up"
        elif second_avg < first_avg * 0.9:
            trend_direction = "down"
        else:
            trend_direction = "stable"

        # Calculate change percentage
        change_percent = ((values[-1] - values[0]) / values[0] * 100) if values[0] > 0 else 0

        return {
            "trend_direction": trend_direction,
            "change_percent": round(change_percent, 2),
            "average": round(sum(values) / len(values), 2),
            "min": min(values),
            "max": max(values),
            "first_period_value": values[0],
            "last_period_value": values[-1]
        }

    def _extract_topics(self, items: list[SearchIndex], num_topics: int) -> dict[str, Any]:
        """Extract topics from items using tag analysis."""
        # Aggregate tags
        tag_counts = {}
        tag_items = {}  # tag -> list of item IDs

        for item in items:
            if item.tags:
                for tag in item.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                    if tag not in tag_items:
                        tag_items[tag] = []
                    tag_items[tag].append(str(item.item_id))

        # Sort by frequency
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

        # Take top N topics
        topics = []
        total_items = len(items)
        covered_items = set()

        for tag, count in sorted_tags[:num_topics]:
            topic_items = tag_items.get(tag, [])
            topics.append({
                "topic_name": tag,
                "frequency": count,
                "percentage": round(count / total_items * 100, 2),
                "sample_item_ids": topic_items[:5]  # Sample items with this tag
            })
            covered_items.update(topic_items)

        # Calculate coverage
        coverage = round(len(covered_items) / total_items * 100, 2) if total_items > 0 else 0

        return {
            "topics": topics,
            "coverage": coverage
        }

    def _detect_patterns(self, items: list[SearchIndex], pattern_type: str) -> dict[str, Any]:
        """Detect patterns in items."""
        patterns = []

        if pattern_type == "creation_time":
            # Analyze creation hour patterns
            hour_counts = {}
            for item in items:
                if item.created_at:
                    hour = item.created_at.hour
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1

            if hour_counts:
                peak_hour = max(hour_counts.items(), key=lambda x: x[1])
                patterns.append({
                    "pattern_name": "peak_creation_hour",
                    "description": f"Most items created at hour {peak_hour[0]}:00",
                    "value": peak_hour[0],
                    "count": peak_hour[1]
                })

        elif pattern_type == "tag_co_occurrence":
            # Find commonly co-occurring tags
            tag_pairs = {}
            for item in items:
                if item.tags and len(item.tags) > 1:
                    sorted_tags = sorted(item.tags)
                    for i in range(len(sorted_tags)):
                        for j in range(i + 1, len(sorted_tags)):
                            pair = (sorted_tags[i], sorted_tags[j])
                            tag_pairs[pair] = tag_pairs.get(pair, 0) + 1

            if tag_pairs:
                top_pair = max(tag_pairs.items(), key=lambda x: x[1])
                patterns.append({
                    "pattern_name": "frequent_tag_pair",
                    "description": f"Tags '{top_pair[0][0]}' and '{top_pair[0][1]}' often appear together",
                    "tags": list(top_pair[0]),
                    "co_occurrence_count": top_pair[1]
                })

        elif pattern_type == "content_length":
            # Analyze content length distribution
            lengths = [len(item.content) for item in items if item.content]

            if lengths:
                avg_length = sum(lengths) / len(lengths)
                patterns.append({
                    "pattern_name": "average_content_length",
                    "description": f"Average content length is {avg_length:.0f} characters",
                    "value": round(avg_length, 2),
                    "min": min(lengths),
                    "max": max(lengths)
                })

        return {
            "patterns": patterns,
            "explanation": f"Detected {len(patterns)} patterns of type '{pattern_type}'"
        }
