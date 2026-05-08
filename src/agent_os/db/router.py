"""Multi-tenant database router for organization-level data isolation.

This module provides database routing for multi-tenant architecture:
- Free/Personal users: Shared database with row-level isolation
- Enterprise customers: Separate databases for physical isolation
"""

import os
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_os.core.config import load_config


class DatabaseRouter:
    """Multi-tenant database router.

    Routes database connections to appropriate database based on organization:
    - Shared database for free/personal plans
    - Dedicated database for enterprise plans
    """

    def __init__(self):
        self.config = load_config("config.yaml")
        self.shared_engine = None
        self.shared_session_factory = None
        self.tenant_engines: dict[int, object] = {}
        self.tenant_session_factories: dict[int, object] = {}

    def _get_shared_engine(self):
        """Get or create shared database engine."""
        if self.shared_engine is None:
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://agentos:agentos@localhost/agentos_db"
            )

            self.shared_engine = create_async_engine(
                database_url,
                echo=False,  # Set to True for SQL query logging
                pool_size=20,
                max_overflow=40,
                pool_pre_ping=True,  # Verify connections before using
            )

            self.shared_session_factory = async_sessionmaker(
                self.shared_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

        return self.shared_engine

    def _get_tenant_engine(self, organization_id: int, db_config: dict):
        """Get or create tenant-specific database engine."""
        if organization_id not in self.tenant_engines:
            # Build database URL from tenant config
            database_url = (
                f"postgresql+asyncpg://{db_config['user']}:{db_config['password']}"
                f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            )

            # Create tenant-specific engine
            self.tenant_engines[organization_id] = create_async_engine(
                database_url,
                echo=False,
                pool_size=5,  # Smaller pool for dedicated databases
                max_overflow=10,
                pool_pre_ping=True,
            )

            self.tenant_session_factories[organization_id] = async_sessionmaker(
                self.tenant_engines[organization_id],
                class_=AsyncSession,
                expire_on_commit=False,
            )

        return self.tenant_engines[organization_id]

    async def get_session(self, organization_id: int | None = None) -> AsyncSession:
        """Get database session for organization.

        Args:
            organization_id: Organization ID. If None, uses shared database.

        Returns:
            AsyncSession for the appropriate database

        Example:
            ```python
            # Shared database (free users)
            session = await router.get_session()

            # Dedicated database (enterprise)
            session = await router.get_session(organization_id=123)
            ```
        """
        # Import here to avoid circular imports
        from agent_os.auth.crud import get_organization_by_id

        if organization_id is None:
            # Use shared database
            engine = self._get_shared_engine()
            session_factory = self.shared_session_factory
        else:
            # Check if organization has dedicated database
            org = await get_organization_by_id(organization_id)

            if org and org.db_host:
                # Enterprise customer - use dedicated database
                db_config = {
                    'host': org.db_host,
                    'port': org.db_port or 5432,
                    'database': org.db_name,
                    'user': org.db_user,
                    'password': org.db_password  # Should be encrypted
                }
                engine = self._get_tenant_engine(organization_id, db_config)
                session_factory = self.tenant_session_factories[organization_id]
            else:
                # Free/personal user - use shared database
                engine = self._get_shared_engine()
                session_factory = self.shared_session_factory

        return session_factory()

    async def close_all(self):
        """Close all database connections.

        Call this on application shutdown.
        """
        # Close shared engine
        if self.shared_engine:
            await self.shared_engine.dispose()

        # Close all tenant engines
        for engine in self.tenant_engines.values():
            await engine.dispose()

        self.tenant_engines.clear()
        self.tenant_session_factories.clear()


# Global router instance
db_router = DatabaseRouter()


async def get_db_session(organization_id: int | None = None) -> AsyncSession:
    """FastAPI dependency for getting database session.

    Args:
        organization_id: Organization ID for routing

    Returns:
        Database session

    Usage in FastAPI:
        ```python
        @router.get("/cards")
        async def list_cards(
            current_user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db_session)
        ):
            # Use db session
            result = await db.execute(select(Card).where(...))
            return result.scalars().all()
        ```
    """
    session = await db_router.get_session(organization_id)

    try:
        yield session
    finally:
        await session.close()


class RowLevelSecurity:
    """Row-Level Security (RLS) manager for PostgreSQL.

    Enforces data isolation at database level, preventing unauthorized access
    even if application code has bugs.
    """

    @staticmethod
    async def enable_rls_for_user(db: AsyncSession, user_id: int, organization_id: int):
        """Set RLS context for current database session.

        This should be called at the start of each request to ensure
        the database enforces row-level security.

        Args:
            db: Database session
            user_id: Current user ID
            organization_id: Current organization ID

        Example:
            ```python
            @router.get("/cards")
            async def list_cards(
                current_user: User = Depends(get_current_user),
                db: AsyncSession = Depends(get_db)
            ):
                # Set RLS context
                await RowLevelSecurity.enable_rls_for_user(
                    db, current_user.id, current_user.organization_id
                )

                # Now all queries are automatically filtered by organization
                result = await db.execute(select(Card))
                return result.scalars().all()
            ```
        """
        # Set PostgreSQL session variable for RLS
        await db.execute(
            f"SET LOCAL app.user_id = '{user_id}';"
        )
        await db.execute(
            f"SET LOCAL app.organization_id = '{organization_id}';"
        )

    @staticmethod
    async def create_rls_policies(db: AsyncSession):
        """Create RLS policies for all tables.

        This should be run once during database setup.

        Args:
            db: Database session
        """
        # Note: These policies are defined in the Alembic migration
        # This is a convenience method to recreate them if needed

        policies = [
            # Cards table
            """
            CREATE POLICY IF NOT EXISTS card_org_isolation
            ON cards FOR ALL
            TO public
            USING (
                organization_id = (
                    SELECT organization_id FROM users WHERE id = current_setting('app.user_id', true)::integer
                )
            );
            """,
            # Tasks table
            """
            CREATE POLICY IF NOT EXISTS task_org_isolation
            ON tasks FOR ALL
            TO public
            USING (
                organization_id = (
                    SELECT organization_id FROM users WHERE id = current_setting('app.user_id', true)::integer
                )
            );
            """,
            # Inbox items table
            """
            CREATE POLICY IF NOT EXISTS inbox_org_isolation
            ON inbox_items FOR ALL
            TO public
            USING (
                organization_id = (
                    SELECT organization_id FROM users WHERE id = current_setting('app.user_id', true)::integer
                )
            );
            """,
        ]

        for policy in policies:
            await db.execute(policy)

        # Enable RLS on all tables
        await db.execute("ALTER TABLE cards FORCE ROW LEVEL SECURITY;")
        await db.execute("ALTER TABLE tasks FORCE ROW LEVEL SECURITY;")
        await db.execute("ALTER TABLE inbox_items FORCE ROW LEVEL SECURITY;")

        await db.commit()
