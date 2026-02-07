"""PostgreSQL Full-Text Search configuration for Stage 4.

This module provides migration scripts and utilities for setting up
full-text search capabilities in PostgreSQL.
"""

import logging

logger = logging.getLogger(__name__)


# SQL statements for PostgreSQL full-text search setup
POSTGRES_FULLTEXT_SETUP = """

-- =============================================================================
-- PostgreSQL Full-Text Search Configuration
-- =============================================================================

-- Install required extensions (PostgreSQL 15+)
CREATE EXTENSION IF NOT EXISTS pgvector;  -- Optional, for vector search

-- Create custom text search configuration for English and Chinese
CREATE TEXT SEARCH CONFIGURATION IF NOT EXISTS search_config (COPY = pg_catalog.simple);

-- Add support for Chinese (if zhparser is available)
-- CREATE EXTENSION IF NOT EXISTS zhparser;
-- ALTER TEXT SEARCH CONFIGURATION search_config
--     PARSER = zhparser;

-- =============================================================================
-- Search Indexes
-- =============================================================================

-- Add columns for full-text search vectors (using raw SQL to add them)
ALTER TABLE search_indices
ADD COLUMN IF NOT EXISTS title_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(title, ''))) STORED;

ALTER TABLE search_indices
ADD COLUMN IF NOT EXISTS content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;

-- Create GIN indexes for full-text search
CREATE INDEX IF NOT EXISTS ix_search_indices_title_tsv
ON search_indices USING gin(title_tsv);

CREATE INDEX IF NOT EXISTS ix_search_indices_content_tsv
ON search_indices USING gin(content_tsv);

-- Create composite index for type + date queries
CREATE INDEX IF NOT EXISTS ix_search_indices_type_date
ON search_indices(item_type, created_at DESC);

-- =============================================================================
-- Sample Queries
-- =============================================================================

-- Simple text search:
-- SELECT id, item_type, item_id, title,
--        ts_rank(title_tsv, query) AS rank
-- FROM search_indices,
--      to_tsquery('english', 'search & query') AS query
-- WHERE title_tsv @@ query
-- ORDER BY rank DESC
-- LIMIT 20;

-- Combined title and content search:
-- SELECT id, item_type, item_id, title,
--        ts_rank(title_tsv + content_tsv, query) AS rank
-- FROM search_indices,
--      to_tsquery('english', 'search & query') AS query
-- WHERE title_tsv @@ query OR content_tsv @@ query
-- ORDER BY rank DESC
-- LIMIT 20;

-- Search with filtering:
-- SELECT id, item_type, item_id, title
-- FROM search_indices
-- WHERE item_type = 'card'
--   AND (title_tsv @@ to_tsquery('english', 'search'))
-- ORDER BY created_at DESC
-- LIMIT 20;

"""


class SearchConfig:
    """Search configuration and utilities."""

    @staticmethod
    def get_search_query(
        search_text: str,
        item_types: list = None,
        use_content: bool = True
    ) -> str:
        """Generate SQL for full-text search query.

        Args:
            search_text: Search query text
            item_types: Optional list of item types to filter
            use_content: Whether to search content field

        Returns:
            SQL query string
        """
        # Convert search text to tsquery format
        # Simple implementation: join words with AND
        words = search_text.strip().split()
        ts_query = " & ".join(words)

        # Build WHERE clause
        where_clauses = ["title_tsv @@ to_tsquery('english', ?)"]
        params = [ts_query]

        if use_content:
            where_clauses.append("content_tsv @@ to_tsquery('english', ?)")

        if item_types:
            placeholders = ", ".join(["%s"] * len(item_types))
            where_clauses.append(f"item_type IN ({placeholders})")
            params.extend(item_types)

        sql = f"""
            SELECT id, item_type, item_id, title,
                   ts_rank(title_tsv, query) AS title_rank,
                   ts_rank(COALESCE(content_tsv, to_tsvector('')), query) AS content_rank
            FROM search_indices,
                 to_tsquery('english', $1) AS query
            WHERE {" AND ".join(where_clauses)}
            ORDER BY COALESCE(content_rank, 0) + title_rank DESC
            LIMIT 20
        """

        return sql, params

    @staticmethod
    def get_sample_search_queries() -> dict:
        """Get sample search queries for different use cases."""
        return {
            "simple_title_search": """
                SELECT id, item_type, item_id, title
                FROM search_indices
                WHERE title_tsv @@ to_tsquery('english', 'search & query')
                ORDER BY ts_rank(title_tsv, to_tsquery('english', 'search & query')) DESC
                LIMIT 20;
            """,

            "full_text_search": """
                SELECT id, item_type, item_id, title,
                       ts_rank(title_tsv + content_tsv, query) AS rank
                FROM search_indices,
                     to_tsquery('english', 'search & query') AS query
                WHERE title_tsv @@ query OR content_tsv @@ query
                ORDER BY rank DESC
                LIMIT 20;
            """,

            "filtered_search": """
                SELECT id, item_type, item_id, title
                FROM search_indices
                WHERE item_type = 'card'
                  AND title_tsv @@ to_tsquery('english', 'search')
                ORDER BY created_at DESC
                LIMIT 20;
            """
        }


# =============================================================================
# Migration Helper
# =============================================================================

def create_migration_script() -> str:
    """Generate a migration script for adding full-text search.

    Returns:
        SQL migration script
    """
    return f"""

-- Migration: Add full-text search support for Stage 4
-- Date: 2026-02-07
-- Description: Add tsvector columns and GIN indexes for full-text search

-- Add tsvector columns
ALTER TABLE search_indices
ADD COLUMN IF NOT EXISTS title_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(title, ''))) STORED;

ALTER TABLE search_indices
ADD COLUMN IF NOT EXISTS content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;

-- Create GIN indexes
CREATE INDEX IF NOT EXISTS ix_search_indices_title_tsv
ON search_indices USING gin(title_tsv);

CREATE INDEX IF NOT EXISTS ix_search_indices_content_tsv
ON search_indices USING gin(content_tsv);

-- Create composite index for type + date
CREATE INDEX IF NOT EXISTS ix_search_indices_type_date
ON search_indices(item_type, created_at DESC);

-- Grant permissions (adjust as needed)
-- GRANT SELECT ON search_indices TO app_user;
"""


def get_search_setup_commands() -> list:
    """Get list of SQL commands for setting up search.

    Returns:
        List of SQL commands
    """
    return [
        "CREATE EXTENSION IF NOT EXISTS pgvector;",
        "CREATE TEXT SEARCH CONFIGURATION IF NOT EXISTS search_config (COPY = pg_catalog.simple);",
        "ALTER TABLE search_indices ADD COLUMN IF NOT EXISTS title_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(title, ''))) STORED;",
        "ALTER TABLE search_indices ADD COLUMN IF NOT EXISTS content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;",
        "CREATE INDEX IF NOT EXISTS ix_search_indices_title_tsv ON search_indices USING gin(title_tsv);",
        "CREATE INDEX IF NOT EXISTS ix_search_indices_content_tsv ON search_indices USING gin(content_tsv);",
        "CREATE INDEX IF NOT EXISTS ix_search_indices_type_date ON search_indices(item_type, created_at DESC);",
    ]


if __name__ == "__main__":
    print("Search Configuration Module")
    print("=" * 60)
    print("\nThis module provides PostgreSQL full-text search configuration.")
    print("\nKey components:")
    print("- SearchConfig: Query generation utilities")
    print("- create_migration_script(): Generate SQL migrations")
    print("- get_search_setup_commands(): List of setup commands")
    print("\nFor production PostgreSQL deployment:")
    print("1. Run the SQL commands in POSTGRES_FULLTEXT_SETUP")
    print("2. Or use create_migration_script() as a migration")
    print("\nNote: For SQLite (testing), full-text search uses")
    print("      the LIKE operator with % wildcards.")
