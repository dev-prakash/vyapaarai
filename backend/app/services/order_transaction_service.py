"""
Order Transaction Service - Saga Pattern Implementation

Provides transactional safety for order-inventory operations using
the Saga pattern with compensating transactions.

The flow ensures:
1. Stock is reserved (reduced) FIRST - atomically
2. Order is created only if stock reduction succeeds
3. If order creation fails, stock is restored (compensating transaction)

This prevents:
- Overselling due to race conditions
- Orphaned orders without inventory deduction
- Lost inventory (reduced but order not created)
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class OrderItem:
    """Order item structure"""
    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    unit: str = "pieces"


@dataclass
class OrderTransactionResult:
    """Result of order transaction"""
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    failed_items: Optional[List[Dict]] = None
    processing_time_ms: float = 0.0


class OrderTransactionService:
    """
    Transactional Order Service using Saga Pattern

    Ensures atomic order creation with inventory management:
    1. Reserve stock (atomic deduction with conditional expressions)
    2. Create order in database
    3. On failure: Execute compensating transaction (restore stock)
    """

    def __init__(self, inventory_service, database):
        """
        Initialize with dependencies

        Args:
            inventory_service: InventoryService instance for stock operations
            database: HybridDatabase instance for order storage
        """
        self.inventory_service = inventory_service
        self.database = database

    async def create_order_with_stock_reservation(
        self,
        store_id: str,
        items: List[OrderItem],
        order_data: Dict[str, Any]
    ) -> OrderTransactionResult:
        """
        Create order with transactional stock reservation

        This method implements the Saga pattern:
        1. Try to reserve (deduct) stock atomically for ALL items
        2. If successful, create the order
        3. If order creation fails, rollback stock (compensating transaction)

        Args:
            store_id: Store identifier
            items: List of order items
            order_data: Complete order data for database storage

        Returns:
            OrderTransactionResult with success status and details
        """
        start_time = datetime.utcnow()
        # Support both dict and dataclass for order_data
        order_id = order_data.order_id if hasattr(order_data, 'order_id') else order_data.get('order_id')

        logger.info(f"Starting transactional order creation: {order_id} for store {store_id}")

        # Step 1: Reserve stock (atomic deduction for all items)
        stock_reservation = await self._reserve_stock(store_id, items, order_id)

        if not stock_reservation['success']:
            # Stock reservation failed - no need to rollback, nothing was changed
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.warning(
                f"Stock reservation failed for order {order_id}: "
                f"{stock_reservation.get('error')}"
            )

            return OrderTransactionResult(
                success=False,
                order_id=order_id,
                error=stock_reservation.get('error', 'Stock reservation failed'),
                error_code='INSUFFICIENT_STOCK',
                failed_items=stock_reservation.get('failed_items', []),
                processing_time_ms=processing_time
            )

        logger.info(f"Stock reserved successfully for order {order_id}")

        # Step 2: Create order in database
        try:
            db_result = await self.database.create_order(order_data)

            if not db_result.success:
                # Order creation failed - execute compensating transaction
                logger.error(
                    f"Order creation failed for {order_id}, executing compensation: "
                    f"{db_result.error}"
                )

                await self._rollback_stock_reservation(store_id, items, order_id)

                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                return OrderTransactionResult(
                    success=False,
                    order_id=order_id,
                    error=f"Order creation failed: {db_result.error}",
                    error_code='ORDER_CREATION_FAILED',
                    processing_time_ms=processing_time
                )

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(
                f"Order {order_id} created successfully with stock reservation "
                f"in {processing_time:.2f}ms"
            )

            return OrderTransactionResult(
                success=True,
                order_id=order_id,
                processing_time_ms=processing_time
            )

        except Exception as e:
            # Unexpected error - execute compensating transaction
            logger.error(
                f"Unexpected error creating order {order_id}, executing compensation: {e}"
            )

            await self._rollback_stock_reservation(store_id, items, order_id)

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return OrderTransactionResult(
                success=False,
                order_id=order_id,
                error=f"Unexpected error: {str(e)}",
                error_code='UNEXPECTED_ERROR',
                processing_time_ms=processing_time
            )

    async def _reserve_stock(
        self,
        store_id: str,
        items: List[OrderItem],
        order_id: str
    ) -> Dict[str, Any]:
        """
        Reserve stock by deducting quantities atomically

        Uses DynamoDB TransactWriteItems to ensure ALL items are
        deducted together or NONE are deducted (atomic transaction).

        Args:
            store_id: Store identifier
            items: List of items to reserve
            order_id: Order ID for logging/tracking

        Returns:
            Dict with success status and details
        """
        stock_items = [
            {
                "product_id": item.product_id,
                "quantity_change": -item.quantity
            }
            for item in items
        ]

        result = await self.inventory_service.update_stock_bulk_transactional(
            store_id=store_id,
            items=stock_items,
            reason=f"Reserve for order {order_id}"
        )

        return result

    async def _rollback_stock_reservation(
        self,
        store_id: str,
        items: List[OrderItem],
        order_id: str
    ) -> Dict[str, Any]:
        """
        Rollback stock reservation (compensating transaction)

        Adds back the quantities that were previously deducted.

        Args:
            store_id: Store identifier
            items: List of items to restore
            order_id: Order ID for logging/tracking

        Returns:
            Dict with success status and details
        """
        logger.info(f"Executing stock rollback for order {order_id}")

        stock_items = [
            {
                "product_id": item.product_id,
                "quantity_change": item.quantity  # Positive to add back
            }
            for item in items
        ]

        result = await self.inventory_service.update_stock_bulk_transactional(
            store_id=store_id,
            items=stock_items,
            reason=f"Rollback for failed order {order_id}"
        )

        if result.get('success'):
            logger.info(f"Stock rollback successful for order {order_id}")
        else:
            # Critical: Rollback failed - needs manual intervention
            logger.critical(
                f"CRITICAL: Stock rollback FAILED for order {order_id}! "
                f"Manual intervention required. Items: {stock_items}, "
                f"Error: {result.get('error')}"
            )

            # TODO: In production, this should:
            # 1. Send alert to ops team
            # 2. Add to dead letter queue for retry
            # 3. Log to audit trail

        return result

    async def cancel_order_with_stock_restoration(
        self,
        order_id: str,
        store_id: str,
        items: List[OrderItem],
        reason: str = "Order cancelled"
    ) -> OrderTransactionResult:
        """
        Cancel order and restore stock

        Args:
            order_id: Order to cancel
            store_id: Store identifier
            items: Items to restore stock for
            reason: Cancellation reason

        Returns:
            OrderTransactionResult with status
        """
        start_time = datetime.utcnow()

        logger.info(f"Cancelling order {order_id} and restoring stock")

        # Step 1: Update order status to cancelled
        try:
            update_result = await self.database.update_order_status(order_id, "cancelled")

            if not update_result.success:
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                return OrderTransactionResult(
                    success=False,
                    order_id=order_id,
                    error=f"Failed to cancel order: {update_result.error}",
                    error_code='CANCEL_FAILED',
                    processing_time_ms=processing_time
                )
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return OrderTransactionResult(
                success=False,
                order_id=order_id,
                error=f"Error cancelling order: {str(e)}",
                error_code='CANCEL_ERROR',
                processing_time_ms=processing_time
            )

        # Step 2: Restore stock
        stock_items = [
            {
                "product_id": item.product_id,
                "quantity_change": item.quantity  # Positive to restore
            }
            for item in items
        ]

        stock_result = await self.inventory_service.update_stock_bulk_transactional(
            store_id=store_id,
            items=stock_items,
            reason=f"Cancelled order {order_id}: {reason}"
        )

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        if not stock_result.get('success'):
            # Order is cancelled but stock restoration failed
            # This is a critical inconsistency
            logger.critical(
                f"CRITICAL: Order {order_id} cancelled but stock restoration failed! "
                f"Items: {stock_items}, Error: {stock_result.get('error')}"
            )

            return OrderTransactionResult(
                success=True,  # Order was cancelled
                order_id=order_id,
                error="Stock restoration failed - requires manual review",
                error_code='STOCK_RESTORE_FAILED',
                processing_time_ms=processing_time
            )

        logger.info(
            f"Order {order_id} cancelled and stock restored in {processing_time:.2f}ms"
        )

        return OrderTransactionResult(
            success=True,
            order_id=order_id,
            processing_time_ms=processing_time
        )


# Factory function for dependency injection
def create_order_transaction_service():
    """
    Create OrderTransactionService with real dependencies

    Returns:
        OrderTransactionService instance
    """
    from app.services.inventory_service import inventory_service
    from app.database.hybrid_db import HybridDatabase

    db = HybridDatabase()
    return OrderTransactionService(inventory_service, db)


# Global instance (lazy initialization)
_order_transaction_service = None


def get_order_transaction_service() -> OrderTransactionService:
    """Get or create the global OrderTransactionService instance"""
    global _order_transaction_service
    if _order_transaction_service is None:
        _order_transaction_service = create_order_transaction_service()
    return _order_transaction_service
