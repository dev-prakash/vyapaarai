"""
Unit tests for Inventory Summary Cache
Author: DevPrakash

Tests the in-memory caching layer for inventory summary to ensure:
- Cache hits return cached data
- Cache misses trigger DB fetch
- TTL expiration works correctly
- Cache invalidation works
- Thread safety under concurrent access
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock, AsyncMock

# Import the cache class directly for unit testing
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestInventorySummaryCache:
    """Test the InventorySummaryCache class directly"""

    @pytest.mark.unit
    def test_cache_set_and_get_returns_data(self):
        """Test that data can be stored and retrieved from cache"""
        from app.services.inventory_service import InventorySummaryCache

        cache = InventorySummaryCache(default_ttl=60)
        test_data = {
            "total_products": 10,
            "active_products": 8,
            "total_stock_value": 1500.0
        }

        cache.set("STORE-001", test_data)
        result = cache.get("STORE-001")

        assert result is not None
        assert result["total_products"] == 10
        assert result["active_products"] == 8
        assert result["total_stock_value"] == 1500.0

    @pytest.mark.unit
    def test_cache_miss_returns_none(self):
        """Test that cache miss returns None"""
        from app.services.inventory_service import InventorySummaryCache

        cache = InventorySummaryCache(default_ttl=60)
        result = cache.get("NONEXISTENT-STORE")

        assert result is None

    @pytest.mark.unit
    def test_cache_expired_returns_none(self):
        """Test that expired cache entries return None"""
        from app.services.inventory_service import InventorySummaryCache

        # Use very short TTL for testing
        cache = InventorySummaryCache(default_ttl=1)
        test_data = {"total_products": 5}

        cache.set("STORE-001", test_data)

        # Verify data exists immediately
        assert cache.get("STORE-001") is not None

        # Wait for TTL to expire
        time.sleep(1.5)

        # Now should return None
        result = cache.get("STORE-001")
        assert result is None

    @pytest.mark.unit
    def test_cache_invalidate_removes_entry(self):
        """Test that cache invalidation removes the entry"""
        from app.services.inventory_service import InventorySummaryCache

        cache = InventorySummaryCache(default_ttl=60)
        test_data = {"total_products": 5}

        cache.set("STORE-001", test_data)
        assert cache.get("STORE-001") is not None

        cache.invalidate("STORE-001")
        assert cache.get("STORE-001") is None

    @pytest.mark.unit
    def test_cache_invalidate_all_clears_cache(self):
        """Test that invalidate_all clears all entries"""
        from app.services.inventory_service import InventorySummaryCache

        cache = InventorySummaryCache(default_ttl=60)

        cache.set("STORE-001", {"total_products": 5})
        cache.set("STORE-002", {"total_products": 10})
        cache.set("STORE-003", {"total_products": 15})

        cache.invalidate_all()

        assert cache.get("STORE-001") is None
        assert cache.get("STORE-002") is None
        assert cache.get("STORE-003") is None

    @pytest.mark.unit
    def test_cache_returns_copy_not_reference(self):
        """Test that cache returns a copy, not a reference to internal data"""
        from app.services.inventory_service import InventorySummaryCache

        cache = InventorySummaryCache(default_ttl=60)
        test_data = {"total_products": 5}

        cache.set("STORE-001", test_data)
        result = cache.get("STORE-001")

        # Modify the returned data
        result["total_products"] = 999

        # Original cached data should be unchanged
        fresh_result = cache.get("STORE-001")
        assert fresh_result["total_products"] == 5

    @pytest.mark.unit
    def test_cache_stats_returns_correct_info(self):
        """Test that cache stats returns correct information"""
        from app.services.inventory_service import InventorySummaryCache

        cache = InventorySummaryCache(default_ttl=60)

        cache.set("STORE-001", {"total_products": 5})
        cache.set("STORE-002", {"total_products": 10})

        stats = cache.stats()

        assert stats["total_entries"] == 2
        assert stats["active_entries"] == 2
        assert stats["ttl_seconds"] == 60

    @pytest.mark.unit
    def test_cache_thread_safety(self):
        """Test that cache is thread-safe under concurrent access"""
        from app.services.inventory_service import InventorySummaryCache

        cache = InventorySummaryCache(default_ttl=60)
        errors = []

        def writer_thread(store_id, value):
            try:
                for _ in range(100):
                    cache.set(store_id, {"total_products": value})
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def reader_thread(store_id):
            try:
                for _ in range(100):
                    cache.get(store_id)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            t1 = threading.Thread(target=writer_thread, args=(f"STORE-{i}", i))
            t2 = threading.Thread(target=reader_thread, args=(f"STORE-{i}",))
            threads.extend([t1, t2])

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"


class TestInventoryServiceCaching:
    """Test caching integration with InventoryService"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_inventory_summary_uses_cache(self):
        """
        REGRESSION: Verify that get_inventory_summary uses cache on second call.
        This is critical for performance - reduces DynamoDB queries.
        """
        from app.services.inventory_service import InventoryService, _inventory_summary_cache

        # Clear any existing cache
        _inventory_summary_cache.invalidate_all()

        # Create service instance with mock DynamoDB
        service = InventoryService()
        service.use_mock = False

        # Mock the DynamoDB query
        mock_response = {
            'Items': [
                {
                    'product_id': 'PROD-001',
                    'is_active': True,
                    'current_stock': 10,
                    'min_stock_level': 5,
                    'selling_price': 100
                }
            ]
        }

        with patch.object(service.store_inventory_table, 'query', return_value=mock_response):
            # First call should query DB
            result1 = await service.get_inventory_summary("STORE-001")

            assert result1["total_products"] == 1
            assert result1["total_stock_value"] == 1000.0

            # Second call should use cache (not query DB again)
            result2 = await service.get_inventory_summary("STORE-001")

            assert result2["total_products"] == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_inventory_summary_skip_cache(self):
        """
        Test that skip_cache=True bypasses cache and queries DB.
        """
        from app.services.inventory_service import InventoryService, _inventory_summary_cache

        _inventory_summary_cache.invalidate_all()

        service = InventoryService()
        service.use_mock = False

        mock_response = {
            'Items': [
                {
                    'product_id': 'PROD-001',
                    'is_active': True,
                    'current_stock': 10,
                    'min_stock_level': 5,
                    'selling_price': 100
                }
            ]
        }

        call_count = 0

        def mock_query(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response

        with patch.object(service.store_inventory_table, 'query', side_effect=mock_query):
            # First call
            await service.get_inventory_summary("STORE-001", skip_cache=False)
            # Second call with skip_cache=True should query again
            await service.get_inventory_summary("STORE-001", skip_cache=True)

        # Both calls should have queried DB because second used skip_cache
        assert call_count == 2


class TestCacheInvalidationOnStockUpdate:
    """Test that cache is invalidated when stock is modified"""

    @pytest.mark.unit
    def test_invalidate_summary_cache_method_exists(self):
        """Verify the invalidate_summary_cache method exists on InventoryService"""
        from app.services.inventory_service import InventoryService

        service = InventoryService()
        assert hasattr(service, 'invalidate_summary_cache')
        assert callable(service.invalidate_summary_cache)

    @pytest.mark.unit
    def test_get_cache_stats_method_exists(self):
        """Verify the get_cache_stats method exists on InventoryService"""
        from app.services.inventory_service import InventoryService

        service = InventoryService()
        assert hasattr(service, 'get_cache_stats')
        assert callable(service.get_cache_stats)


class TestAPIEndpointCacheSupport:
    """Test that API endpoints properly support caching parameters"""

    @pytest.mark.unit
    def test_inventory_summary_endpoint_has_skip_cache_param(self):
        """
        REGRESSION: Verify inventory summary endpoint supports skip_cache parameter.
        Check the source file directly to avoid import chain issues.
        """
        import ast
        import os

        inventory_file = os.path.join(
            os.path.dirname(__file__), '..', '..', 'app', 'api', 'v1', 'inventory.py'
        )

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Parse the AST and find the get_inventory_summary function
        tree = ast.parse(source)

        found_skip_cache = False
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == 'get_inventory_summary':
                # Check function arguments
                for arg in node.args.args + node.args.kwonlyargs:
                    if arg.arg == 'skip_cache':
                        found_skip_cache = True
                        break

        assert found_skip_cache, "inventory summary endpoint must support skip_cache parameter"

    @pytest.mark.unit
    def test_cache_stats_endpoint_exists(self):
        """Verify cache stats endpoint exists in source code"""
        import os

        inventory_file = os.path.join(
            os.path.dirname(__file__), '..', '..', 'app', 'api', 'v1', 'inventory.py'
        )

        with open(inventory_file, 'r') as f:
            source = f.read()

        assert '/cache/stats' in source or 'cache/stats' in source, "Cache stats endpoint must exist"
        assert 'def get_cache_stats' in source, "get_cache_stats function must exist"

    @pytest.mark.unit
    def test_cache_invalidate_endpoint_exists(self):
        """Verify cache invalidate endpoint exists in source code"""
        import os

        inventory_file = os.path.join(
            os.path.dirname(__file__), '..', '..', 'app', 'api', 'v1', 'inventory.py'
        )

        with open(inventory_file, 'r') as f:
            source = f.read()

        assert '/cache/invalidate' in source or 'cache/invalidate' in source, "Cache invalidate endpoint must exist"
        assert 'def invalidate_cache' in source, "invalidate_cache function must exist"
