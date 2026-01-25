"""
Custom Products Feature - Test Suite

Tests for store owner custom product functionality:
1. Creating custom products (store-specific)
2. Visibility rules (only visible to creating store)
3. CRUD operations for custom products
4. Promotion workflow to global catalog

Run with: pytest backend/tests/test_custom_products.py -v
"""

import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.inventory_service import (
    InventoryService,
    PRODUCT_SOURCE_CUSTOM,
    PRODUCT_SOURCE_GLOBAL,
    VISIBILITY_STORE_ONLY,
    VISIBILITY_GLOBAL,
    PROMOTION_STATUS_NONE,
    PROMOTION_STATUS_PENDING
)


class TestCustomProductCreation:
    """Test suite for custom product creation"""

    @pytest.fixture
    def inventory_service(self):
        """Create inventory service with mocked DynamoDB"""
        with patch('boto3.resource') as mock_resource:
            # Mock DynamoDB tables
            mock_dynamodb = MagicMock()
            mock_resource.return_value = mock_dynamodb

            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table

            service = InventoryService()
            service.use_mock = False
            service.store_inventory_table = mock_table
            service.global_products_table = mock_table

            return service

    @pytest.mark.asyncio
    async def test_create_custom_product_success(self, inventory_service):
        """Test successful custom product creation"""
        # Setup mock
        inventory_service.store_inventory_table.put_item = MagicMock()

        # Test data
        store_id = "STORE-TEST-001"
        user_id = "USER-TEST-001"
        product_data = {
            "product_name": "Test Custom Product",
            "selling_price": 99.99,
            "category": "Test Category",
            "current_stock": 50,
            "unit": "piece"
        }

        # Execute
        result = await inventory_service.create_custom_product(
            store_id=store_id,
            user_id=user_id,
            product_data=product_data
        )

        # Verify
        assert result.get('success') == True
        assert 'CUST_' in result.get('product_id', '')
        assert 'SKU-' in result.get('sku', '')

        # Verify put_item was called with correct data
        call_args = inventory_service.store_inventory_table.put_item.call_args
        created_item = call_args.kwargs.get('Item', call_args[1].get('Item'))

        assert created_item['product_source'] == PRODUCT_SOURCE_CUSTOM
        assert created_item['source_store_id'] == store_id
        assert created_item['visibility'] == VISIBILITY_STORE_ONLY
        assert created_item['created_by_user_id'] == user_id

    @pytest.mark.asyncio
    async def test_create_custom_product_missing_name(self, inventory_service):
        """Test custom product creation fails without name"""
        result = await inventory_service.create_custom_product(
            store_id="STORE-TEST-001",
            user_id="USER-TEST-001",
            product_data={
                "selling_price": 99.99
            }
        )

        assert result.get('success') == False
        assert 'name' in result.get('error', '').lower()

    @pytest.mark.asyncio
    async def test_create_custom_product_missing_price(self, inventory_service):
        """Test custom product creation fails without valid price"""
        result = await inventory_service.create_custom_product(
            store_id="STORE-TEST-001",
            user_id="USER-TEST-001",
            product_data={
                "product_name": "Test Product",
                "selling_price": 0
            }
        )

        assert result.get('success') == False
        assert 'price' in result.get('error', '').lower()


class TestCustomProductVisibility:
    """Test suite for custom product visibility rules"""

    def test_filter_visible_products_global_visible_to_all(self):
        """Global catalog products should be visible to all stores"""
        service = InventoryService.__new__(InventoryService)

        products = [
            {"product_id": "GP001", "product_source": PRODUCT_SOURCE_GLOBAL},
            {"product_id": "GP002", "product_source": PRODUCT_SOURCE_GLOBAL}
        ]

        # Test visibility for Store A
        visible = service.filter_visible_products(products, "STORE-A", "store_owner")
        assert len(visible) == 2

        # Test visibility for Store B
        visible = service.filter_visible_products(products, "STORE-B", "store_owner")
        assert len(visible) == 2

    def test_filter_visible_products_custom_only_to_source_store(self):
        """Custom products should only be visible to the source store"""
        service = InventoryService.__new__(InventoryService)

        products = [
            {
                "product_id": "CUST001",
                "product_source": PRODUCT_SOURCE_CUSTOM,
                "source_store_id": "STORE-A"
            },
            {
                "product_id": "CUST002",
                "product_source": PRODUCT_SOURCE_CUSTOM,
                "source_store_id": "STORE-B"
            },
            {"product_id": "GP001", "product_source": PRODUCT_SOURCE_GLOBAL}
        ]

        # Store A should see their custom product + global
        visible_a = service.filter_visible_products(products, "STORE-A", "store_owner")
        assert len(visible_a) == 2
        product_ids = [p['product_id'] for p in visible_a]
        assert "CUST001" in product_ids  # Store A's custom product
        assert "CUST002" not in product_ids  # Store B's custom product - NOT visible
        assert "GP001" in product_ids  # Global product - visible

        # Store B should see their custom product + global
        visible_b = service.filter_visible_products(products, "STORE-B", "store_owner")
        assert len(visible_b) == 2
        product_ids = [p['product_id'] for p in visible_b]
        assert "CUST001" not in product_ids  # Store A's custom product - NOT visible
        assert "CUST002" in product_ids  # Store B's custom product
        assert "GP001" in product_ids  # Global product - visible

    def test_filter_visible_products_admin_sees_all(self):
        """Admin should see all products including other stores' custom products"""
        service = InventoryService.__new__(InventoryService)

        products = [
            {
                "product_id": "CUST001",
                "product_source": PRODUCT_SOURCE_CUSTOM,
                "source_store_id": "STORE-A"
            },
            {
                "product_id": "CUST002",
                "product_source": PRODUCT_SOURCE_CUSTOM,
                "source_store_id": "STORE-B"
            },
            {"product_id": "GP001", "product_source": PRODUCT_SOURCE_GLOBAL}
        ]

        # Admin should see all 3 products
        visible = service.filter_visible_products(products, "STORE-A", "admin")
        assert len(visible) == 3

    def test_filter_visible_products_mixed_scenario(self):
        """Test complex scenario with mixed product sources"""
        service = InventoryService.__new__(InventoryService)

        products = [
            # Store A's custom products
            {"product_id": "CUST-A1", "product_source": PRODUCT_SOURCE_CUSTOM, "source_store_id": "STORE-A"},
            {"product_id": "CUST-A2", "product_source": PRODUCT_SOURCE_CUSTOM, "source_store_id": "STORE-A"},
            # Store B's custom products
            {"product_id": "CUST-B1", "product_source": PRODUCT_SOURCE_CUSTOM, "source_store_id": "STORE-B"},
            # Store C's custom products
            {"product_id": "CUST-C1", "product_source": PRODUCT_SOURCE_CUSTOM, "source_store_id": "STORE-C"},
            # Global products
            {"product_id": "GP001", "product_source": PRODUCT_SOURCE_GLOBAL},
            {"product_id": "GP002", "product_source": PRODUCT_SOURCE_GLOBAL},
            {"product_id": "GP003", "product_source": PRODUCT_SOURCE_GLOBAL},
        ]

        # Store A sees 2 custom + 3 global = 5 products
        visible_a = service.filter_visible_products(products, "STORE-A", "store_owner")
        assert len(visible_a) == 5

        # Store B sees 1 custom + 3 global = 4 products
        visible_b = service.filter_visible_products(products, "STORE-B", "store_owner")
        assert len(visible_b) == 4

        # Store D (no custom products) sees only 3 global
        visible_d = service.filter_visible_products(products, "STORE-D", "store_owner")
        assert len(visible_d) == 3


class TestCustomProductUpdate:
    """Test suite for custom product updates"""

    @pytest.fixture
    def inventory_service(self):
        """Create inventory service with mocked DynamoDB"""
        with patch('boto3.resource') as mock_resource:
            mock_dynamodb = MagicMock()
            mock_resource.return_value = mock_dynamodb

            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table

            service = InventoryService()
            service.use_mock = False
            service.store_inventory_table = mock_table
            service.global_products_table = mock_table

            return service

    @pytest.mark.asyncio
    async def test_update_custom_product_success(self, inventory_service):
        """Test successful custom product update"""
        # Mock get_product to return a custom product
        existing_product = {
            "product_id": "CUST-TEST-001",
            "product_source": PRODUCT_SOURCE_CUSTOM,
            "source_store_id": "STORE-A",
            "promotion_status": PROMOTION_STATUS_NONE
        }

        with patch.object(inventory_service, 'get_product', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_product
            inventory_service.store_inventory_table.update_item = MagicMock(
                return_value={'Attributes': {**existing_product, 'product_name': 'Updated Name'}}
            )

            result = await inventory_service.update_custom_product(
                store_id="STORE-A",
                product_id="CUST-TEST-001",
                user_id="USER-001",
                updates={"product_name": "Updated Name"}
            )

            assert result.get('success') == True

    @pytest.mark.asyncio
    async def test_update_custom_product_not_authorized(self, inventory_service):
        """Test that store B cannot update store A's custom product"""
        existing_product = {
            "product_id": "CUST-TEST-001",
            "product_source": PRODUCT_SOURCE_CUSTOM,
            "source_store_id": "STORE-A",  # Owned by Store A
        }

        with patch.object(inventory_service, 'get_product', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_product

            # Store B trying to update Store A's product
            result = await inventory_service.update_custom_product(
                store_id="STORE-B",  # Different store
                product_id="CUST-TEST-001",
                user_id="USER-002",
                updates={"product_name": "Hacked Name"}
            )

            assert result.get('success') == False
            assert 'Not authorized' in result.get('error', '')

    @pytest.mark.asyncio
    async def test_cannot_update_global_product(self, inventory_service):
        """Test that global catalog products cannot be updated via custom product endpoint"""
        existing_product = {
            "product_id": "GP-001",
            "product_source": PRODUCT_SOURCE_GLOBAL,  # Global product
        }

        with patch.object(inventory_service, 'get_product', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_product

            result = await inventory_service.update_custom_product(
                store_id="STORE-A",
                product_id="GP-001",
                user_id="USER-001",
                updates={"product_name": "Can't Update This"}
            )

            assert result.get('success') == False
            assert 'global catalog' in result.get('error', '').lower()


class TestCustomProductDelete:
    """Test suite for custom product deletion"""

    @pytest.fixture
    def inventory_service(self):
        with patch('boto3.resource') as mock_resource:
            mock_dynamodb = MagicMock()
            mock_resource.return_value = mock_dynamodb

            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table

            service = InventoryService()
            service.use_mock = False
            service.store_inventory_table = mock_table
            service.global_products_table = mock_table

            return service

    @pytest.mark.asyncio
    async def test_soft_delete_custom_product(self, inventory_service):
        """Test soft delete (deactivation) of custom product"""
        existing_product = {
            "product_id": "CUST-TEST-001",
            "product_source": PRODUCT_SOURCE_CUSTOM,
            "source_store_id": "STORE-A",
        }

        with patch.object(inventory_service, 'get_product', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_product
            inventory_service.store_inventory_table.update_item = MagicMock()

            result = await inventory_service.delete_custom_product(
                store_id="STORE-A",
                product_id="CUST-TEST-001",
                user_id="USER-001",
                hard_delete=False  # Soft delete
            )

            assert result.get('success') == True
            assert result.get('hard_delete') == False

            # Verify update_item was called (not delete_item)
            inventory_service.store_inventory_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_hard_delete_custom_product(self, inventory_service):
        """Test hard delete (permanent removal) of custom product"""
        existing_product = {
            "product_id": "CUST-TEST-001",
            "product_source": PRODUCT_SOURCE_CUSTOM,
            "source_store_id": "STORE-A",
        }

        with patch.object(inventory_service, 'get_product', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_product
            inventory_service.store_inventory_table.delete_item = MagicMock()

            result = await inventory_service.delete_custom_product(
                store_id="STORE-A",
                product_id="CUST-TEST-001",
                user_id="USER-001",
                hard_delete=True  # Hard delete
            )

            assert result.get('success') == True
            assert result.get('hard_delete') == True

            # Verify delete_item was called
            inventory_service.store_inventory_table.delete_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_delete_other_store_product(self, inventory_service):
        """Test that store B cannot delete store A's custom product"""
        existing_product = {
            "product_id": "CUST-TEST-001",
            "product_source": PRODUCT_SOURCE_CUSTOM,
            "source_store_id": "STORE-A",  # Owned by Store A
        }

        with patch.object(inventory_service, 'get_product', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_product

            # Store B trying to delete Store A's product
            result = await inventory_service.delete_custom_product(
                store_id="STORE-B",
                product_id="CUST-TEST-001",
                user_id="USER-002",
                hard_delete=True
            )

            assert result.get('success') == False
            assert 'Not authorized' in result.get('error', '')


class TestPromotionWorkflow:
    """Test suite for custom product promotion to global catalog"""

    def test_quality_score_calculation(self):
        """Test quality score calculation for promotion eligibility"""
        service = InventoryService.__new__(InventoryService)

        # Complete product (should be eligible)
        complete_product = {
            "product_name": "Test Product",
            "description": "This is a detailed product description that meets the minimum length requirement.",
            "category": "Electronics",
            "selling_price": 999.99,
            "image": "https://example.com/image.jpg",
            "barcode": "1234567890123",
            "brand": "TestBrand",
            "unit": "piece"
        }

        result = service._calculate_quality_score(complete_product)
        assert result['score'] == 100.0
        assert result['eligible'] == True
        assert len(result['missing']) == 0

        # Incomplete product (should not be eligible)
        incomplete_product = {
            "product_name": "Test",
            "selling_price": 10.0
        }

        result = service._calculate_quality_score(incomplete_product)
        assert result['score'] < 60  # Below threshold
        assert result['eligible'] == False
        assert len(result['missing']) > 0


# Integration Test Scenarios (require actual DynamoDB connection)
class TestIntegrationScenarios:
    """
    Integration test scenarios - these describe the expected behavior
    for manual testing against a live environment.
    """

    def test_scenario_custom_product_isolation(self):
        """
        SCENARIO: Store A creates a custom product, Store B cannot see it

        STEPS:
        1. Store A authenticates and creates a custom product "My Special Item"
        2. Verify the product is created with:
           - product_source = 'store_custom'
           - source_store_id = Store A's ID
           - visibility = 'store_only'
        3. Store A lists their products - should see the custom product
        4. Store B lists their products - should NOT see Store A's custom product
        5. Store B tries to access Store A's custom product directly - should be filtered out

        EXPECTED:
        - Custom products are isolated to their creating store
        - Global catalog products remain visible to all stores
        - Admin can see all products regardless of ownership
        """
        # This is a documentation test - actual implementation would require
        # DynamoDB connection and authentication
        assert True  # Placeholder for documentation

    def test_scenario_promotion_workflow(self):
        """
        SCENARIO: Store owner requests promotion of custom product to global catalog

        STEPS:
        1. Store A creates a high-quality custom product with all required fields
        2. Store A requests promotion via POST /inventory/products/{id}/request-promotion
        3. Verify quality score meets threshold (60%+)
        4. Product status changes to 'pending_review'
        5. Admin reviews and approves the product
        6. Product is copied to global catalog
        7. Original custom product marked as 'promoted'
        8. Product is now visible to all stores as a global catalog item

        EXPECTED:
        - Only high-quality products can be promoted
        - Promotion requires admin approval
        - Promoted products become global catalog items
        """
        assert True  # Placeholder for documentation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
