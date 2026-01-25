"""
GST Cache - In-Memory Cache for GST Reference Data
Provides fast access to GST categories and HSN mappings with TTL-based expiration.

Author: DevPrakash
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)


class GSTCache:
    """
    Thread-safe in-memory cache for GST reference data.
    Implements TTL-based expiration and atomic operations.
    """

    DEFAULT_TTL_SECONDS = 300  # 5 minutes

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        """
        Initialize the cache.

        Args:
            ttl_seconds: Time-to-live for cached data in seconds
        """
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()

        # Categories cache
        self._categories: Dict[str, Any] = {}
        self._categories_loaded_at: Optional[datetime] = None

        # HSN mappings cache
        self._hsn_mappings: Dict[str, Any] = {}
        self._hsn_loaded_at: Optional[datetime] = None

        # Stats
        self._cache_hits = 0
        self._cache_misses = 0

    # =========================================================================
    # CATEGORIES CACHE
    # =========================================================================

    def is_categories_stale(self) -> bool:
        """
        Check if categories cache is stale (expired).

        Returns:
            True if cache is stale or empty, False if fresh
        """
        if not self._categories or self._categories_loaded_at is None:
            return True

        age = datetime.utcnow() - self._categories_loaded_at
        return age > self._ttl

    async def get_categories(self) -> Optional[Dict[str, Any]]:
        """
        Get cached categories if fresh.

        Returns:
            Dictionary of categories if cache is fresh, None if stale
        """
        async with self._lock:
            if self.is_categories_stale():
                self._cache_misses += 1
                return None

            self._cache_hits += 1
            return self._categories.copy()

    async def set_categories(self, categories: Dict[str, Any]) -> None:
        """
        Set categories in cache.

        Args:
            categories: Dictionary of category_code -> category data
        """
        async with self._lock:
            self._categories = categories.copy()
            self._categories_loaded_at = datetime.utcnow()
            logger.debug(f"Cached {len(categories)} GST categories")

    async def get_category(self, category_code: str) -> Optional[Dict[str, Any]]:
        """
        Get a single category from cache.

        Args:
            category_code: Category code to lookup

        Returns:
            Category dict if found and fresh, None otherwise
        """
        async with self._lock:
            if self.is_categories_stale():
                self._cache_misses += 1
                return None

            result = self._categories.get(category_code)
            if result:
                self._cache_hits += 1
            else:
                self._cache_misses += 1
            return result

    # =========================================================================
    # HSN MAPPINGS CACHE
    # =========================================================================

    def is_hsn_stale(self) -> bool:
        """
        Check if HSN mappings cache is stale.

        Returns:
            True if cache is stale or empty, False if fresh
        """
        if not self._hsn_mappings or self._hsn_loaded_at is None:
            return True

        age = datetime.utcnow() - self._hsn_loaded_at
        return age > self._ttl

    async def get_hsn_mappings(self) -> Optional[Dict[str, Any]]:
        """
        Get all cached HSN mappings if fresh.

        Returns:
            Dictionary of hsn_code -> mapping data if fresh, None if stale
        """
        async with self._lock:
            if self.is_hsn_stale():
                self._cache_misses += 1
                return None

            self._cache_hits += 1
            return self._hsn_mappings.copy()

    async def set_hsn_mappings(self, mappings: Dict[str, Any]) -> None:
        """
        Set HSN mappings in cache.

        Args:
            mappings: Dictionary of hsn_code -> mapping data
        """
        async with self._lock:
            self._hsn_mappings = mappings.copy()
            self._hsn_loaded_at = datetime.utcnow()
            logger.debug(f"Cached {len(mappings)} HSN mappings")

    async def get_hsn_mapping(self, hsn_code: str) -> Optional[Dict[str, Any]]:
        """
        Get a single HSN mapping from cache.

        Args:
            hsn_code: HSN code to lookup

        Returns:
            Mapping dict if found and fresh, None otherwise
        """
        async with self._lock:
            if self.is_hsn_stale():
                self._cache_misses += 1
                return None

            # Try exact match
            result = self._hsn_mappings.get(hsn_code)
            if result:
                self._cache_hits += 1
                return result

            # Try 4-digit prefix match
            if len(hsn_code) > 4:
                prefix = hsn_code[:4]
                result = self._hsn_mappings.get(prefix)
                if result:
                    self._cache_hits += 1
                    return result

            self._cache_misses += 1
            return None

    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================

    async def invalidate_all(self) -> None:
        """
        Invalidate all cached data.
        Call this after admin updates to force refresh.
        """
        async with self._lock:
            self._categories = {}
            self._categories_loaded_at = None
            self._hsn_mappings = {}
            self._hsn_loaded_at = None
            logger.info("GST cache invalidated")

    async def invalidate_categories(self) -> None:
        """Invalidate only categories cache."""
        async with self._lock:
            self._categories = {}
            self._categories_loaded_at = None
            logger.debug("GST categories cache invalidated")

    async def invalidate_hsn(self) -> None:
        """Invalidate only HSN mappings cache."""
        async with self._lock:
            self._hsn_mappings = {}
            self._hsn_loaded_at = None
            logger.debug("HSN mappings cache invalidated")

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        async with self._lock:
            total_requests = self._cache_hits + self._cache_misses
            hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "categories_count": len(self._categories),
                "hsn_mappings_count": len(self._hsn_mappings),
                "categories_stale": self.is_categories_stale(),
                "hsn_stale": self.is_hsn_stale(),
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "hit_rate_percent": round(hit_rate, 2),
                "ttl_seconds": self._ttl.total_seconds(),
                "categories_loaded_at": (
                    self._categories_loaded_at.isoformat()
                    if self._categories_loaded_at else None
                ),
                "hsn_loaded_at": (
                    self._hsn_loaded_at.isoformat()
                    if self._hsn_loaded_at else None
                )
            }

    async def reset_stats(self) -> None:
        """Reset cache statistics."""
        async with self._lock:
            self._cache_hits = 0
            self._cache_misses = 0


# Singleton instance
gst_cache = GSTCache()
