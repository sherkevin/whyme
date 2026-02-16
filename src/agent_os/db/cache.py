"""Caching layer for improved query performance.

Provides Redis-based caching for frequently accessed data:
- User session data
- Organization settings
- Frequently accessed cards/tasks
- Query result caching
"""

import os
import json
import hashlib
from typing import Optional, Any, List
from datetime import timedelta
from functools import wraps

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class CacheManager:
    """Redis-based cache manager.

    Caches frequently accessed data to reduce database load.
    """

    def __init__(self):
        """Initialize Redis connection."""
        if not REDIS_AVAILABLE:
            print("Warning: Redis not available. Install with: pip install redis")
            self.redis = None
            return

        self.redis = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired

        Example:
            >>> value = await cache.get("user:123:cards")
        """
        if not self.redis:
            return None

        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds (default: 5 minutes)

        Returns:
            True if successful, False otherwise

        Example:
            >>> await cache.set("user:123:cards", cards, ttl=600)
        """
        if not self.redis:
            return False

        try:
            await self.redis.setex(
                key,
                ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            return False

        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            print(f"Cache delete error: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "user:123:*")

        Returns:
            Number of keys deleted

        Example:
            >>> # Delete all cache entries for user 123
            >>> count = await cache.delete_pattern("user:123:*")
        """
        if not self.redis:
            return 0

        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            print(f"Cache delete_pattern error: {e}")
            return 0

    async def invalidate_user_cache(self, user_id: int):
        """Invalidate all cache entries for a user.

        Args:
            user_id: User ID

        Example:
            >>> await cache.invalidate_user_cache(123)
        """
        await self.delete_pattern(f"user:{user_id}:*")

    async def invalidate_org_cache(self, organization_id: int):
        """Invalidate all cache entries for an organization.

        Args:
            organization_id: Organization ID

        Example:
            >>> await cache.invalidate_org_cache(456)
        """
        await self.delete_pattern(f"org:{organization_id}:*")

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()


# Global cache instance
cache_manager = CacheManager()


# ============================================================================
# Redis helper for verification service
# ============================================================================

def get_redis():
    """Get synchronous Redis client for verification codes.

    Returns:
        Redis client or None if Redis not available
    """
    if not REDIS_AVAILABLE:
        return None

    try:
        import redis
        return redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    except Exception as e:
        print(f"Failed to create Redis client: {e}")
        return None


# ============================================================================
# Cache decorators
# ============================================================================

def cached(ttl: int = 300, key_prefix: str = ""):
    """Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache key

    Usage:
        ```python
        @cached(ttl=600, key_prefix="cards")
        async def get_user_cards(user_id: int) -> List[Card]:
            # Expensive database query
            return await db.query(Card).filter_by(user_id=user_id).all()
        ```
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]

            # Add args to key
            for arg in args:
                if isinstance(arg, (int, str)):
                    key_parts.append(str(arg))

            # Add kwargs to key
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (int, str)):
                    key_parts.append(f"{k}:{v}")

            cache_key = ":".join(key_parts)

            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            await cache_manager.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


# ============================================================================
# Specific cache helpers
# ============================================================================

class UserCache:
    """Cache helpers for user-specific data."""

    @staticmethod
    async def get_cards(org_id: int, user_id: int) -> Optional[List]:
        """Get cached cards for user."""
        key = f"org:{org_id}:user:{user_id}:cards"
        return await cache_manager.get(key)

    @staticmethod
    async def set_cards(org_id: int, user_id: int, cards: List, ttl: int = 300):
        """Cache cards for user."""
        key = f"org:{org_id}:user:{user_id}:cards"
        await cache_manager.set(key, cards, ttl=ttl)

    @staticmethod
    async def get_tasks(org_id: int, user_id: int) -> Optional[List]:
        """Get cached tasks for user."""
        key = f"org:{org_id}:user:{user_id}:tasks"
        return await cache_manager.get(key)

    @staticmethod
    async def set_tasks(org_id: int, user_id: int, tasks: List, ttl: int = 300):
        """Cache tasks for user."""
        key = f"org:{org_id}:user:{user_id}:tasks"
        await cache_manager.set(key, tasks, ttl=ttl)

    @staticmethod
    async def invalidate(org_id: int, user_id: int):
        """Invalidate all cache for user."""
        await cache_manager.delete_pattern(f"org:{org_id}:user:{user_id}:*")


class OrganizationCache:
    """Cache helpers for organization-specific data."""

    @staticmethod
    async def get_settings(org_id: int) -> Optional[dict]:
        """Get cached organization settings."""
        key = f"org:{org_id}:settings"
        return await cache_manager.get(key)

    @staticmethod
    async def set_settings(org_id: int, settings: dict, ttl: int = 3600):
        """Cache organization settings (longer TTL)."""
        key = f"org:{org_id}:settings"
        await cache_manager.set(key, settings, ttl=ttl)

    @staticmethod
    async def invalidate(org_id: int):
        """Invalidate all cache for organization."""
        await cache_manager.delete_pattern(f"org:{org_id}:*")


# ============================================================================
# Cache warming
# ============================================================================

class CacheWarmer:
    """Cache warming for frequently accessed data."""

    async def warm_user_cache(self, db, org_id: int, user_id: int):
        """Warm cache for a user's frequently accessed data.

        Args:
            db: Database session
            org_id: Organization ID
            user_id: User ID
        """
        # Import here to avoid circular imports
        from agent_os.knowledge.crud import list_cards
        from agent_os.tasks.crud import list_tasks

        # Cache user's cards
        cards, _ = await list_cards(db, organization_id=org_id, user_id=user_id, limit=100)
        await UserCache.set_cards(org_id, user_id, cards, ttl=600)

        # Cache user's tasks
        tasks, _ = await list_tasks(db, organization_id=org_id, user_id=user_id, limit=100)
        await UserCache.set_tasks(org_id, user_id, tasks, ttl=600)

    async def warm_org_cache(self, db, org_id: int):
        """Warm cache for an organization's settings.

        Args:
            db: Database session
            org_id: Organization ID
        """
        # Import here to avoid circular imports
        from agent_os.auth.crud import get_organization_by_id

        # Cache organization settings
        org = await get_organization_by_id(org_id)
        if org:
            await OrganizationCache.set_settings(org_id, {
                'name': org.name,
                'plan': org.plan,
                'max_users': org.max_users,
                'max_storage_gb': org.max_storage_gb,
            }, ttl=3600)


# Global cache warmer
cache_warmer = CacheWarmer()
