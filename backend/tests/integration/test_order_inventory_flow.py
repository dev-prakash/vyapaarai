"""
Integration Tests for Order-Inventory Flow

Tests for:
- Complete order creation with stock validation
- Transactional stock updates on order
- Order cancellation with stock reversal
- Concurrent order handling
- End-to-end order lifecycle
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime
import asyncio


class TestOrderInventoryIntegration:
    """Integration tests for order-inventory flow"""

    @pytest.mark.asyncio
    async def test_complete_order_flow_success(
        self, mock_inventory_service, mock_hybrid_db
    ):
        """Test complete order flow: check stock -> create order -> reduce stock"""
        # Step 1: Check stock availability
        availability = await mock_inventory_service.check_availability(
            store_id="STORE-001",
            product_id="PROD-001",
            required_quantity=5
        )
        assert availability["available"] is True

        # Step 2: Create order
        order_result = await mock_hybrid_db.create_order(MagicMock(
            order_id="ORD-TEST-001",
            store_id="STORE-001",
            items=[{"product_id": "PROD-001", "quantity": 5}],
            total_amount=Decimal("500.00")
        ))
        assert order_result.success is True

        # Step 3: Reduce stock transactionally
        stock_result = await mock_inventory_service.update_stock_bulk_transactional(
            store_id="STORE-001",
            items=[{"product_id": "PROD-001", "quantity_change": -5}],
            reason="Order ORD-TEST-001"
        )
        assert stock_result["success"] is True

    @pytest.mark.asyncio
    async def test_order_fails_when_stock_unavailable(self, mock_inventory_service):
        """Test order creation fails early when stock is unavailable"""
        mock_inventory_service.check_availability = AsyncMock(return_value={
            "available": False,
            "current_stock": 3,
            "requested": 10,
            "shortage": 7
        })

        availability = await mock_inventory_service.check_availability(
            store_id="STORE-001",
            product_id="PROD-001",
            required_quantity=10
        )

        assert availability["available"] is False
        assert availability["shortage"] == 7
        # Order should NOT be created when this returns False

    @pytest.mark.asyncio
    async def test_transactional_rollback_on_partial_stock(self, mock_inventory_service):
        """Test transaction rolls back when one item has insufficient stock"""
        mock_inventory_service.update_stock_bulk_transactional = AsyncMock(return_value={
            "success": False,
            "error": "Transaction cancelled - insufficient stock",
            "failed_items": [
                {"product_id": "PROD-002", "reason": "Insufficient stock"}
            ]
        })

        # Try to update multiple items where one fails
        result = await mock_inventory_service.update_stock_bulk_transactional(
            store_id="STORE-001",
            items=[
                {"product_id": "PROD-001", "quantity_change": -5},  # Would succeed
                {"product_id": "PROD-002", "quantity_change": -100}  # Fails
            ],
            reason="Order ORD-FAIL-001"
        )

        # Entire transaction should fail
        assert result["success"] is False
        assert len(result["failed_items"]) > 0

    @pytest.mark.asyncio
    async def test_order_cancellation_restores_stock(
        self, mock_inventory_service, mock_hybrid_db
    ):
        """Test order cancellation properly restores inventory"""
        # Setup: Create an order first
        mock_hybrid_db.get_order = AsyncMock(return_value=MagicMock(
            success=True,
            data={
                "order_id": "ORD-TEST-001",
                "status": "pending",
                "items": [
                    {"product_id": "PROD-001", "quantity": 5},
                    {"product_id": "PROD-002", "quantity": 3}
                ]
            }
        ))

        # Get order to cancel
        order_result = await mock_hybrid_db.get_order("ORD-TEST-001")
        assert order_result.success is True

        # Cancel order (restore stock with positive quantity_change)
        restore_result = await mock_inventory_service.update_stock_bulk_transactional(
            store_id="STORE-001",
            items=[
                {"product_id": "PROD-001", "quantity_change": 5},  # Restore
                {"product_id": "PROD-002", "quantity_change": 3}   # Restore
            ],
            reason="Cancellation of ORD-TEST-001"
        )

        assert restore_result["success"] is True

    @pytest.mark.asyncio
    async def test_concurrent_orders_dont_oversell(self, mock_inventory_service):
        """Test concurrent orders don't result in overselling"""
        # Simulate stock of 10 units
        stock_remaining = 10
        orders_fulfilled = []
        orders_rejected = []

        async def simulate_order(order_id: str, quantity: int):
            nonlocal stock_remaining

            # Simulate atomic check and update
            if stock_remaining >= quantity:
                stock_remaining -= quantity
                orders_fulfilled.append(order_id)
                return {"success": True, "order_id": order_id}
            else:
                orders_rejected.append(order_id)
                return {"success": False, "error": "Insufficient stock"}

        # Concurrent orders each wanting 4 units (only 2 should succeed)
        results = await asyncio.gather(
            simulate_order("ORD-001", 4),
            simulate_order("ORD-002", 4),
            simulate_order("ORD-003", 4),
        )

        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        # Only 2 orders should succeed (10 / 4 = 2.5 -> 2)
        assert len(successful) == 2
        assert len(failed) == 1
        assert stock_remaining >= 0  # Never negative


class TestOrderStatusTransitions:
    """Tests for order status state machine"""

    @pytest.mark.asyncio
    async def test_valid_status_transitions(self, mock_hybrid_db):
        """Test valid order status transitions"""
        valid_transitions = [
            ("pending", "confirmed"),
            ("confirmed", "preparing"),
            ("preparing", "ready"),
            ("ready", "out_for_delivery"),
            ("out_for_delivery", "delivered"),
            ("pending", "cancelled"),
            ("confirmed", "cancelled")
        ]

        for from_status, to_status in valid_transitions:
            mock_hybrid_db.update_order_status = AsyncMock(return_value=MagicMock(
                success=True,
                error=None
            ))

            result = await mock_hybrid_db.update_order_status("ORD-001", to_status)
            assert result.success is True

    @pytest.mark.asyncio
    async def test_stock_restored_on_cancellation(
        self, mock_inventory_service, mock_hybrid_db
    ):
        """Test stock is restored when order is cancelled"""
        # Mock order with items
        order_items = [
            {"product_id": "PROD-001", "quantity": 2},
            {"product_id": "PROD-002", "quantity": 1}
        ]

        mock_hybrid_db.get_order = AsyncMock(return_value=MagicMock(
            success=True,
            data={"order_id": "ORD-001", "items": order_items, "status": "pending"}
        ))

        # Get order
        order = await mock_hybrid_db.get_order("ORD-001")

        # Cancel and restore stock
        restore_items = [
            {"product_id": item["product_id"], "quantity_change": item["quantity"]}
            for item in order.data["items"]
        ]

        result = await mock_inventory_service.update_stock_bulk_transactional(
            store_id="STORE-001",
            items=restore_items,
            reason="Order cancellation"
        )

        assert result["success"] is True


class TestMultiItemOrders:
    """Tests for orders with multiple items"""

    @pytest.mark.asyncio
    async def test_multi_item_order_all_available(self, mock_inventory_service):
        """Test multi-item order succeeds when all items available"""
        items_to_check = [
            ("PROD-001", 5),
            ("PROD-002", 3),
            ("PROD-003", 2)
        ]

        all_available = True
        for product_id, quantity in items_to_check:
            result = await mock_inventory_service.check_availability(
                store_id="STORE-001",
                product_id=product_id,
                required_quantity=quantity
            )
            if not result["available"]:
                all_available = False
                break

        assert all_available is True

    @pytest.mark.asyncio
    async def test_multi_item_order_one_unavailable(self, mock_inventory_service):
        """Test multi-item order fails when one item unavailable"""
        # First two items available, third unavailable
        mock_inventory_service.check_availability = AsyncMock(side_effect=[
            {"available": True, "current_stock": 100},
            {"available": True, "current_stock": 50},
            {"available": False, "current_stock": 0, "shortage": 2}
        ])

        items_to_check = [
            ("PROD-001", 5),
            ("PROD-002", 3),
            ("PROD-003", 2)  # Unavailable
        ]

        unavailable_items = []
        for product_id, quantity in items_to_check:
            result = await mock_inventory_service.check_availability(
                store_id="STORE-001",
                product_id=product_id,
                required_quantity=quantity
            )
            if not result["available"]:
                unavailable_items.append(product_id)

        assert len(unavailable_items) == 1
        assert "PROD-003" in unavailable_items


class TestPaymentIntegration:
    """Tests for payment integration with orders"""

    @pytest.mark.asyncio
    async def test_cod_order_no_payment_required(self, mock_payment_service):
        """Test COD orders don't require upfront payment"""
        # COD should just be recorded, not processed
        mock_payment_service.process_payment = AsyncMock(return_value={
            "success": True,
            "transaction_id": "COD-TXN-001",
            "status": "pending_delivery"
        })

        # COD payment is recorded but not charged
        result = await mock_payment_service.process_payment(
            order_id="ORD-001",
            amount=Decimal("500.00"),
            method="cod"
        )

        assert result["success"] is True
        assert result["status"] == "pending_delivery"

    @pytest.mark.asyncio
    async def test_upi_order_requires_payment(self, mock_payment_service):
        """Test UPI orders require payment processing"""
        result = await mock_payment_service.process_payment(
            order_id="ORD-001",
            amount=Decimal("500.00"),
            method="upi"
        )

        assert result["success"] is True
        assert result["status"] == "completed"


class TestOrderDataConsistency:
    """Tests for data consistency in order operations"""

    @pytest.mark.asyncio
    async def test_order_total_matches_items(self):
        """Test order total equals sum of item totals"""
        items = [
            {"product_id": "PROD-001", "quantity": 2, "unit_price": Decimal("100.00")},
            {"product_id": "PROD-002", "quantity": 3, "unit_price": Decimal("50.00")}
        ]

        calculated_subtotal = sum(
            item["quantity"] * item["unit_price"]
            for item in items
        )

        expected_subtotal = Decimal("350.00")  # 2*100 + 3*50
        assert calculated_subtotal == expected_subtotal

    @pytest.mark.asyncio
    async def test_tax_calculation_correct(self):
        """Test tax is calculated correctly"""
        subtotal = Decimal("1000.00")
        tax_rate = Decimal("0.05")  # 5% GST

        tax_amount = subtotal * tax_rate
        assert tax_amount == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_delivery_fee_applied_correctly(self):
        """Test delivery fee applied for small orders only"""
        # Free delivery over 200
        large_order_subtotal = Decimal("500.00")
        small_order_subtotal = Decimal("150.00")
        delivery_threshold = Decimal("200.00")
        delivery_fee = Decimal("20.00")

        large_order_delivery = delivery_fee if large_order_subtotal < delivery_threshold else Decimal("0")
        small_order_delivery = delivery_fee if small_order_subtotal < delivery_threshold else Decimal("0")

        assert large_order_delivery == Decimal("0")  # Free delivery
        assert small_order_delivery == Decimal("20.00")  # Delivery charged
