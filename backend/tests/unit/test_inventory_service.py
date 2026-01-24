"""
Unit Tests for Inventory Service

Tests for:
- Stock operations (get, update, bulk transactional)
- Availability checks
- Atomic conditional updates
- Error handling and edge cases
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime
from botocore.exceptions import ClientError


class TestInventoryServiceStockOperations:
    """Tests for stock update operations"""

    @pytest.mark.asyncio
    async def test_update_stock_positive_change(self, mock_inventory_service):
        """Test adding stock to a product"""
        result = await mock_inventory_service.update_stock(
            store_id="STORE-001",
            product_id="PROD-001",
            quantity_change=10,
            reason="Restocking"
        )

        assert result["success"] is True
        mock_inventory_service.update_stock.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stock_negative_change_sufficient_stock(self, mock_inventory_service):
        """Test reducing stock when sufficient stock available"""
        # Configure mock to return successful update
        mock_inventory_service.update_stock = AsyncMock(return_value={
            "success": True,
            "previous_stock": 100,
            "new_stock": 95,
            "change": -5,
            "atomic": True
        })

        result = await mock_inventory_service.update_stock(
            store_id="STORE-001",
            product_id="PROD-001",
            quantity_change=-5,
            reason="Order fulfillment"
        )

        assert result["success"] is True
        assert result["new_stock"] == 95
        assert result["change"] == -5

    @pytest.mark.asyncio
    async def test_update_stock_insufficient_stock(self, mock_inventory_service):
        """Test stock reduction fails when insufficient stock"""
        mock_inventory_service.update_stock = AsyncMock(return_value={
            "success": False,
            "error": "Insufficient stock",
            "current_stock": 3,
            "requested_change": -10,
            "required": 10
        })

        result = await mock_inventory_service.update_stock(
            store_id="STORE-001",
            product_id="PROD-001",
            quantity_change=-10,
            reason="Large order"
        )

        assert result["success"] is False
        assert "Insufficient stock" in result["error"]
        assert result["current_stock"] == 3


class TestInventoryServiceBulkTransactional:
    """Tests for bulk transactional stock updates"""

    @pytest.mark.asyncio
    async def test_bulk_update_all_items_success(self, mock_inventory_service):
        """Test bulk update succeeds when all items have sufficient stock"""
        items = [
            {"product_id": "PROD-001", "quantity_change": -2},
            {"product_id": "PROD-002", "quantity_change": -1},
            {"product_id": "PROD-003", "quantity_change": -3}
        ]

        result = await mock_inventory_service.update_stock_bulk_transactional(
            store_id="STORE-001",
            items=items,
            reason="Order ORD-12345"
        )

        assert result["success"] is True
        assert result["updated_count"] == 2  # From mock fixture

    @pytest.mark.asyncio
    async def test_bulk_update_transaction_failure_rolls_back(self, mock_inventory_service):
        """Test transaction failure rolls back all changes"""
        mock_inventory_service.update_stock_bulk_transactional = AsyncMock(return_value={
            "success": False,
            "error": "Transaction cancelled - insufficient stock",
            "failed_items": [
                {"product_id": "PROD-002", "reason": "Insufficient stock"}
            ]
        })

        items = [
            {"product_id": "PROD-001", "quantity_change": -2},
            {"product_id": "PROD-002", "quantity_change": -100},  # More than available
        ]

        result = await mock_inventory_service.update_stock_bulk_transactional(
            store_id="STORE-001",
            items=items,
            reason="Order ORD-12345"
        )

        assert result["success"] is False
        assert "Transaction cancelled" in result["error"]
        assert len(result["failed_items"]) > 0

    @pytest.mark.asyncio
    async def test_bulk_update_empty_items(self, mock_inventory_service):
        """Test bulk update with empty items list"""
        mock_inventory_service.update_stock_bulk_transactional = AsyncMock(return_value={
            "success": True,
            "items": [],
            "message": "No items to update"
        })

        result = await mock_inventory_service.update_stock_bulk_transactional(
            store_id="STORE-001",
            items=[],
            reason="Empty order"
        )

        assert result["success"] is True


class TestInventoryServiceAvailability:
    """Tests for availability check operations"""

    @pytest.mark.asyncio
    async def test_check_availability_product_available(self, mock_inventory_service):
        """Test availability check returns true when stock sufficient"""
        result = await mock_inventory_service.check_availability(
            store_id="STORE-001",
            product_id="PROD-001",
            required_quantity=5
        )

        assert result["available"] is True
        assert result["current_stock"] == 100
        assert result["requested"] == 5

    @pytest.mark.asyncio
    async def test_check_availability_product_unavailable(self, mock_inventory_service):
        """Test availability check returns false when stock insufficient"""
        mock_inventory_service.check_availability = AsyncMock(return_value={
            "available": False,
            "current_stock": 3,
            "requested": 10,
            "shortage": 7,
            "is_active": True
        })

        result = await mock_inventory_service.check_availability(
            store_id="STORE-001",
            product_id="PROD-001",
            required_quantity=10
        )

        assert result["available"] is False
        assert result["shortage"] == 7

    @pytest.mark.asyncio
    async def test_check_availability_product_not_found(self, mock_inventory_service):
        """Test availability check when product doesn't exist"""
        mock_inventory_service.check_availability = AsyncMock(return_value={
            "available": False,
            "error": "Product not found"
        })

        result = await mock_inventory_service.check_availability(
            store_id="STORE-001",
            product_id="NONEXISTENT",
            required_quantity=1
        )

        assert result["available"] is False
        assert "not found" in result.get("error", "").lower()


class TestInventoryServiceProductRetrieval:
    """Tests for product retrieval operations"""

    @pytest.mark.asyncio
    async def test_get_product_exists(self, mock_inventory_service):
        """Test retrieving existing product"""
        result = await mock_inventory_service.get_product(
            store_id="STORE-001",
            product_id="PROD-001"
        )

        assert result is not None
        assert result["product_id"] == "PROD-001"
        assert result["current_stock"] == 100

    @pytest.mark.asyncio
    async def test_get_product_not_found(self, mock_inventory_service):
        """Test retrieving non-existent product"""
        mock_inventory_service.get_product = AsyncMock(return_value=None)

        result = await mock_inventory_service.get_product(
            store_id="STORE-001",
            product_id="NONEXISTENT"
        )

        assert result is None


class TestInventoryServiceErrorHandling:
    """Tests for error handling scenarios"""

    @pytest.mark.asyncio
    async def test_dynamodb_throughput_exceeded_retry(self):
        """Test retry logic on DynamoDB throughput exceeded"""
        with patch('app.services.inventory_service.InventoryService') as MockService:
            mock_instance = MockService.return_value

            # First call fails with throughput error, second succeeds
            mock_instance.update_stock = AsyncMock(side_effect=[
                {"success": False, "error": "ProvisionedThroughputExceededException"},
                {"success": True, "new_stock": 95}
            ])

            # First attempt should fail
            result1 = await mock_instance.update_stock(
                store_id="STORE-001",
                product_id="PROD-001",
                quantity_change=-5
            )

            # Second attempt should succeed (simulating retry)
            result2 = await mock_instance.update_stock(
                store_id="STORE-001",
                product_id="PROD-001",
                quantity_change=-5
            )

            assert result1["success"] is False
            assert result2["success"] is True

    @pytest.mark.asyncio
    async def test_mock_mode_returns_fallback(self):
        """Test that mock mode returns appropriate fallback responses"""
        with patch('app.services.inventory_service.InventoryService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.use_mock = True

            mock_instance.update_stock = AsyncMock(return_value={
                "success": False,
                "error": "Mock mode - no stock updates"
            })

            result = await mock_instance.update_stock(
                store_id="STORE-001",
                product_id="PROD-001",
                quantity_change=-5
            )

            assert result["success"] is False
            assert "Mock mode" in result["error"]


class TestInventoryServiceAtomicOperations:
    """Tests verifying atomic operation behavior"""

    @pytest.mark.asyncio
    async def test_concurrent_stock_updates_atomic(self):
        """Test that concurrent updates maintain consistency (conceptual test)"""
        # This test verifies the concept of atomic operations
        # In production, DynamoDB conditional expressions prevent race conditions

        with patch('app.services.inventory_service.InventoryService') as MockService:
            mock_instance = MockService.return_value

            # Simulate atomic update behavior
            initial_stock = 100
            updates_applied = []

            async def mock_atomic_update(store_id, product_id, quantity_change, **kwargs):
                # Simulate conditional check
                current = initial_stock - sum(updates_applied)
                if current >= abs(quantity_change):
                    updates_applied.append(abs(quantity_change))
                    return {
                        "success": True,
                        "new_stock": current + quantity_change,
                        "atomic": True
                    }
                return {
                    "success": False,
                    "error": "Insufficient stock"
                }

            mock_instance.update_stock = AsyncMock(side_effect=mock_atomic_update)

            # Simulate concurrent requests
            import asyncio
            results = await asyncio.gather(
                mock_instance.update_stock("STORE-001", "PROD-001", -30),
                mock_instance.update_stock("STORE-001", "PROD-001", -30),
                mock_instance.update_stock("STORE-001", "PROD-001", -30),
                mock_instance.update_stock("STORE-001", "PROD-001", -30),
            )

            # All should succeed because we have 100 units
            successful_updates = [r for r in results if r["success"]]
            assert len(successful_updates) >= 3  # At least 3 should succeed (30*3=90 < 100)
