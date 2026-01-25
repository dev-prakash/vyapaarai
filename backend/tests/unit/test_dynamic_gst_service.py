"""
Unit Tests for Dynamic GST Service
Tests for cache, repository, and dynamic service with database and static fallback

Author: DevPrakash
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


# ============================================================================
# CACHE TESTS
# ============================================================================

class TestGSTCache:
    """Tests for GSTCache class"""

    @pytest.mark.unit
    def test_cache_is_stale_when_empty(self):
        """Cache should report stale when no data loaded"""
        from app.services.gst_cache import GSTCache

        cache = GSTCache(ttl_seconds=300)
        assert cache.is_categories_stale() is True
        assert cache.is_hsn_stale() is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_returns_none_when_stale(self):
        """get_categories should return None when cache is stale"""
        from app.services.gst_cache import GSTCache

        cache = GSTCache(ttl_seconds=300)
        result = await cache.get_categories()
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_returns_data_when_fresh(self):
        """get_categories should return data when cache is fresh"""
        from app.services.gst_cache import GSTCache

        cache = GSTCache(ttl_seconds=300)
        test_data = {"BISCUITS": {"gst_rate": Decimal("18")}}

        await cache.set_categories(test_data)
        result = await cache.get_categories()

        assert result is not None
        assert "BISCUITS" in result
        assert result["BISCUITS"]["gst_rate"] == Decimal("18")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_marks_stale_after_ttl(self):
        """Cache should be stale after TTL expires"""
        from app.services.gst_cache import GSTCache

        # Use very short TTL for testing
        cache = GSTCache(ttl_seconds=0)

        await cache.set_categories({"TEST": {}})

        # Immediately stale due to 0 TTL
        assert cache.is_categories_stale() is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_clears_cache(self):
        """invalidate_all should clear all cached data"""
        from app.services.gst_cache import GSTCache

        cache = GSTCache(ttl_seconds=300)

        await cache.set_categories({"BISCUITS": {}})
        await cache.set_hsn_mappings({"1905": {}})

        # Verify data is cached
        assert await cache.get_categories() is not None
        assert await cache.get_hsn_mappings() is not None

        # Invalidate
        await cache.invalidate_all()

        # Verify cache is empty
        assert await cache.get_categories() is None
        assert await cache.get_hsn_mappings() is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hsn_mapping_prefix_lookup(self):
        """get_hsn_mapping should try 4-digit prefix if exact match not found"""
        from app.services.gst_cache import GSTCache

        cache = GSTCache(ttl_seconds=300)

        # Store mapping with 4-digit code
        await cache.set_hsn_mappings({"1905": {"category_code": "BISCUITS"}})

        # Lookup with 6-digit code should match prefix
        result = await cache.get_hsn_mapping("190510")
        assert result is not None
        assert result["category_code"] == "BISCUITS"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_stats_tracking(self):
        """Cache should track hits and misses"""
        from app.services.gst_cache import GSTCache

        cache = GSTCache(ttl_seconds=300)

        # Initial miss (cache empty)
        await cache.get_categories()

        # Set data
        await cache.set_categories({"TEST": {}})

        # Now a hit
        await cache.get_categories()

        stats = await cache.get_stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["hit_rate_percent"] == 50.0


# ============================================================================
# DYNAMIC GST SERVICE TESTS
# ============================================================================

class TestDynamicGSTService:
    """Tests for DynamicGSTService class"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_categories_uses_cache(self, dynamodb_mock, seeded_gst_tables):
        """Service should return cached categories when fresh"""
        from app.services.dynamic_gst_service import DynamicGSTService

        # Reset environment for test
        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        service = DynamicGSTService()

        # First call populates cache from DB
        categories1 = await service.get_all_categories()
        assert len(categories1) > 0

        # Second call should use cache (check via stats)
        categories2 = await service.get_all_categories()
        assert categories1 == categories2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_categories_falls_back_to_static_on_db_error(self):
        """Service should fall back to static config when DB fails"""
        from app.services.dynamic_gst_service import DynamicGSTService
        from app.core.gst_config import GST_CATEGORIES

        service = DynamicGSTService()

        # Invalidate cache first to force DB lookup
        await service.cache.invalidate_all()

        # Mock repository to raise exception
        service.repository.get_all_categories = AsyncMock(side_effect=Exception("DB Error"))

        # Should fall back to static config
        categories = await service.get_all_categories()

        assert len(categories) > 0
        assert service._static_fallback_used is True
        # Static config should have BISCUITS
        assert "BISCUITS" in categories or "FRESH_VEGETABLES" in categories

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hsn_lookup_returns_correct_rate(self, dynamodb_mock, seeded_gst_tables):
        """get_gst_rate_from_hsn should return correct rate for known HSN"""
        from app.services.dynamic_gst_service import DynamicGSTService

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        service = DynamicGSTService()

        # HSN 1905 -> BISCUITS -> 18%
        rate = await service.get_gst_rate_from_hsn("1905")
        assert rate == Decimal("18")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hsn_lookup_returns_none_for_unknown(self, dynamodb_mock):
        """get_gst_rate_from_hsn should return None for unknown HSN"""
        from app.services.dynamic_gst_service import DynamicGSTService

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        service = DynamicGSTService()

        # Unknown HSN code
        rate = await service.get_gst_rate_from_hsn("9999")
        assert rate is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_category_suggestion_matches_keywords(self, dynamodb_mock, seeded_gst_tables):
        """suggest_category_from_product_name should match category keywords"""
        from app.services.dynamic_gst_service import DynamicGSTService

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        service = DynamicGSTService()

        # Populate cache first
        await service.get_all_categories()

        # "Parle biscuit" should match BISCUITS category (keyword: biscuit, parle)
        category = await service.suggest_category_from_product_name("Parle Biscuit")
        assert category is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_refresh_cache_clears_and_reloads(self, dynamodb_mock, seeded_gst_tables):
        """refresh_cache should invalidate and reload data"""
        from app.services.dynamic_gst_service import DynamicGSTService

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        service = DynamicGSTService()

        # Populate cache
        await service.get_all_categories()

        # Refresh
        result = await service.refresh_cache()

        assert result["categories_loaded"] >= 0
        assert result["hsn_mappings_loaded"] >= 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_hsn_code_format(self, dynamodb_mock):
        """validate_hsn_code should check format and lookup"""
        from app.services.dynamic_gst_service import DynamicGSTService

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        service = DynamicGSTService()

        # Invalid: not numeric
        result = await service.validate_hsn_code("ABC")
        assert result["valid"] is False
        assert "numeric" in result["error"]

        # Invalid: wrong length
        result = await service.validate_hsn_code("123")
        assert result["valid"] is False
        assert "4, 6, or 8" in result["error"]

        # Valid format but no mapping
        result = await service.validate_hsn_code("9999")
        assert result["valid"] is True
        assert result["category_code"] is None


# ============================================================================
# GST RATE CHANGE TESTS
# ============================================================================

@pytest.mark.regression
class TestGSTRateChanges:
    """Regression tests for GST rate changes flowing through the system"""

    @pytest.mark.asyncio
    async def test_rate_change_reflects_in_category_lookup(self, dynamodb_mock, seeded_gst_tables, gst_rates_table):
        """When admin changes GST rate, new rate should be returned after cache refresh"""
        from app.services.dynamic_gst_service import DynamicGSTService
        from app.repositories.gst_repository import GSTRepository

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        # Create service and inject repository that uses mocked tables
        service = DynamicGSTService()
        service.repository = GSTRepository()
        service.repository.rates_table = gst_rates_table

        # Invalidate cache to start fresh
        await service.cache.invalidate_all()

        # Get initial rate for BISCUITS (from seeded data = 18%)
        categories = await service.get_all_categories()
        assert "BISCUITS" in categories
        initial_rate = Decimal(str(categories["BISCUITS"]["gst_rate"]))
        assert initial_rate == Decimal("18")

        # Simulate admin changing rate in DB
        gst_rates_table.update_item(
            Key={"category_code": "BISCUITS"},
            UpdateExpression="SET gst_rate = :rate",
            ExpressionAttributeValues={":rate": Decimal("12")}
        )

        # Before cache refresh, old rate should still be returned (from cache)
        categories_cached = await service.get_all_categories()
        assert Decimal(str(categories_cached["BISCUITS"]["gst_rate"])) == initial_rate

        # After cache refresh, new rate should be returned
        await service.cache.invalidate_all()
        categories_new = await service.get_all_categories()
        assert Decimal(str(categories_new["BISCUITS"]["gst_rate"])) == Decimal("12")

    @pytest.mark.asyncio
    async def test_new_category_available_after_cache_refresh(self, dynamodb_mock, seeded_gst_tables, gst_rates_table):
        """Newly added category should be available after cache refresh"""
        from app.services.dynamic_gst_service import DynamicGSTService
        from app.repositories.gst_repository import GSTRepository
        from datetime import datetime

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        # Create service and inject repository that uses mocked tables
        service = DynamicGSTService()
        service.repository = GSTRepository()
        service.repository.rates_table = gst_rates_table

        # Invalidate cache to start fresh
        await service.cache.invalidate_all()

        # Initial load
        categories = await service.get_all_categories()
        assert "NEW_CATEGORY" not in categories

        # Admin adds new category
        now = datetime.utcnow().isoformat()
        gst_rates_table.put_item(Item={
            "category_code": "NEW_CATEGORY",
            "category_name": "New Test Category",
            "gst_rate": Decimal("5"),
            "hsn_prefix": "9999",
            "cess_rate": Decimal("0"),
            "description": "Test category",
            "keywords": ["test"],
            "is_active": True,
            "effective_from": "2026-01-01",
            "created_at": now,
            "updated_at": now,
            "updated_by": "ADMIN_TEST"
        })

        # Still not visible due to cache
        categories_cached = await service.get_all_categories()
        assert "NEW_CATEGORY" not in categories_cached

        # After cache invalidation, should be visible
        await service.cache.invalidate_all()
        categories_new = await service.get_all_categories()
        assert "NEW_CATEGORY" in categories_new
        assert Decimal(str(categories_new["NEW_CATEGORY"]["gst_rate"])) == Decimal("5")


# ============================================================================
# REPOSITORY TESTS
# ============================================================================

class TestGSTRepository:
    """Tests for GSTRepository class"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_all_categories_returns_active_only(self, dynamodb_mock, gst_rates_table, sample_gst_categories):
        """get_all_categories(active_only=True) should exclude inactive categories"""
        from app.repositories.gst_repository import GSTRepository

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        repo = GSTRepository()

        # Seed with active categories
        for cat in sample_gst_categories:
            gst_rates_table.put_item(Item=cat)

        # Add an inactive category
        gst_rates_table.put_item(Item={
            "category_code": "INACTIVE_CAT",
            "category_name": "Inactive Category",
            "gst_rate": Decimal("18"),
            "is_active": False,
            "updated_by": "TEST"
        })

        # Get active only
        categories = await repo.get_all_categories(active_only=True)
        category_codes = [c["category_code"] for c in categories]

        assert "INACTIVE_CAT" not in category_codes
        assert len(categories) == len(sample_gst_categories)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_category_sets_audit_fields(self, dynamodb_mock, gst_rates_table):
        """create_category should set created_at, updated_at, updated_by"""
        from app.repositories.gst_repository import GSTRepository

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        repo = GSTRepository()

        cat = await repo.create_category(
            category_code="TEST_CAT",
            category_name="Test Category",
            gst_rate=Decimal("18"),
            hsn_prefix="9999",
            admin_id="ADMIN_001"
        )

        assert cat["created_at"] is not None
        assert cat["updated_at"] is not None
        assert cat["updated_by"] == "ADMIN_001"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_category_updates_audit_fields(self, dynamodb_mock, seeded_gst_tables, gst_rates_table):
        """update_category should update updated_at and updated_by"""
        from app.repositories.gst_repository import GSTRepository

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        repo = GSTRepository()

        # Update BISCUITS category
        updated = await repo.update_category(
            category_code="BISCUITS",
            updates={"gst_rate": Decimal("12")},
            admin_id="ADMIN_002"
        )

        assert updated is not None
        assert updated["updated_by"] == "ADMIN_002"
        assert Decimal(str(updated["gst_rate"])) == Decimal("12")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_category_soft_deletes(self, dynamodb_mock, seeded_gst_tables, gst_rates_table):
        """delete_category should set is_active=False, not remove item"""
        from app.repositories.gst_repository import GSTRepository

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        repo = GSTRepository()

        # Delete SALT category
        success = await repo.delete_category("SALT", "ADMIN_003")
        assert success is True

        # Item should still exist but inactive
        response = gst_rates_table.get_item(Key={"category_code": "SALT"})
        assert "Item" in response
        assert response["Item"]["is_active"] is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_bulk_upsert_categories(self, dynamodb_mock, gst_rates_table):
        """bulk_upsert_categories should insert multiple categories"""
        from app.repositories.gst_repository import GSTRepository

        import os
        os.environ["VYAPAARAI_ENV"] = "test"

        repo = GSTRepository()

        categories = [
            {"category_code": "BULK1", "category_name": "Bulk Cat 1", "gst_rate": 5},
            {"category_code": "BULK2", "category_name": "Bulk Cat 2", "gst_rate": 12},
            {"category_code": "BULK3", "category_name": "Bulk Cat 3", "gst_rate": 18},
        ]

        count = await repo.bulk_upsert_categories(categories, "ADMIN_BULK")
        assert count == 3

        # Verify all inserted
        response = gst_rates_table.scan()
        assert len(response["Items"]) == 3
