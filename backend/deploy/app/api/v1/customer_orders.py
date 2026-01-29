"""
Customer-facing Order API endpoints for VyaparAI
These endpoints are used by the customer PWA for order management

IMPORTANT: Order creation now atomically clears the cart after successful order creation.
This follows the enterprise best practice of pessimistic updates where:
1. Order is created first (with stock reservation)
2. Cart is cleared ONLY after order is confirmed
3. Frontend syncs local state from backend (empty cart)
"""

import logging
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from pydantic import BaseModel, Field
import boto3

from app.api.v1.customer_auth import verify_customer_token
from app.database.hybrid_db import HybridDatabase, OrderData
from app.services.order_transaction_service import (
    OrderTransactionService, OrderItem as TransactionOrderItem,
    get_order_transaction_service
)
from app.models.order import OrderStatus

logger = logging.getLogger(__name__)

# Create router with prefix matching frontend expectations
router = APIRouter(prefix="/customers/orders", tags=["customer-orders"])

# Initialize HybridDatabase
db = HybridDatabase()

# Initialize DynamoDB for cart operations
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
carts_table = dynamodb.Table('vyaparai-carts-prod')

# ============================================================================
# Request/Response Models
# ============================================================================

class OrderItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)


class CreateOrderRequest(BaseModel):
    store_id: str = Field(..., description="Store identifier")
    address_id: str = Field(..., description="Delivery address ID from customer profile")
    payment_method_id: str = Field(..., description="Payment method ID or type (cod, upi, card)")
    items: List[OrderItemRequest] = Field(..., min_items=1)
    notes: Optional[str] = Field(None, max_length=500)
    delivery_instructions: Optional[str] = Field(None, max_length=500)
    delivery_fee: Optional[float] = Field(None, ge=0)


class OrderResponse(BaseModel):
    id: str
    order_number: str
    tracking_id: Optional[str] = None
    store_id: str
    customer_id: str
    customer_name: str
    customer_phone: str
    status: str
    payment_status: str
    payment_method: str
    payment_id: Optional[str] = None
    items: List[Dict[str, Any]]
    subtotal: float
    delivery_fee: float
    total: float
    delivery_address: Dict[str, Any]
    customer_note: Optional[str] = None
    delivery_instructions: Optional[str] = None
    cancel_reason: Optional[str] = None
    created_at: str
    updated_at: str
    estimated_delivery: Optional[str] = None


class CreateOrderResponseData(BaseModel):
    order_id: str
    order_number: str
    tracking_id: str
    status: str
    total: float
    created_at: str
    estimated_delivery: str


class CreateOrderResponse(BaseModel):
    success: bool
    order: CreateOrderResponseData
    message: str


class OrderHistoryResponse(BaseModel):
    success: bool
    orders: List[Dict[str, Any]]
    count: int
    last_key: Optional[Dict[str, Any]] = None


class OrderDetailsResponse(BaseModel):
    success: bool
    order: Dict[str, Any]


class CancelOrderRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class CancelOrderResponse(BaseModel):
    success: bool
    message: str
    order_id: str
    status: str


# ============================================================================
# Helper Functions
# ============================================================================

def generate_order_number() -> str:
    """Generate a user-friendly order number"""
    timestamp = int(datetime.now().timestamp())
    return f"ORD-{timestamp}"


def generate_tracking_id() -> str:
    """Generate a tracking ID"""
    return f"TRK-{uuid.uuid4().hex[:12].upper()}"


def get_customer_address(customer: dict, address_id: str) -> Optional[dict]:
    """Get address from customer profile by ID"""
    addresses = customer.get('addresses', [])
    for addr in addresses:
        if addr.get('address_id') == address_id:
            return addr
    return None


async def clear_customer_cart(customer_id: str, store_id: str) -> bool:
    """
    Clear the customer's cart for a specific store after successful order creation.

    This is called AFTER order creation succeeds, ensuring atomic behavior:
    - If order creation fails, cart remains intact
    - If order succeeds, cart is cleared

    Returns True if cart was cleared successfully, False otherwise.

    IMPORTANT: The cart table stores customer_id with "user-" prefix (from X-Session-ID header)
    but the customer_id from verify_customer_token doesn't have this prefix.
    We need to add the prefix to match the cart table's key format.
    """
    try:
        # Cart table uses "user-{customer_id}" as the primary key
        # This matches the X-Session-ID header format used by the cart API
        cart_customer_id = f"user-{customer_id}"

        carts_table.delete_item(
            Key={
                'customer_id': cart_customer_id,
                'store_id': store_id
            }
        )
        logger.info(f"Cart cleared for customer {cart_customer_id} at store {store_id}")
        return True
    except Exception as e:
        # Log but don't fail - order was already created successfully
        # Frontend will handle this gracefully via syncWithBackend
        logger.error(f"Failed to clear cart for {customer_id} at {store_id}: {str(e)}")
        return False


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=CreateOrderResponse)
async def create_customer_order(
    order_request: CreateOrderRequest,
    customer: dict = Depends(verify_customer_token)
):
    """
    Create a new order for the authenticated customer.
    Uses transactional stock reservation (Saga pattern).
    """
    try:
        customer_id = customer['customer_id']

        # Get delivery address from customer profile
        delivery_address = get_customer_address(customer, order_request.address_id)
        if not delivery_address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid delivery address"
            )

        # Generate order identifiers
        order_id = f"ord_{int(datetime.now().timestamp() * 1000)}"
        order_number = generate_order_number()
        tracking_id = generate_tracking_id()

        # Get product details and calculate totals
        # For now, we'll get this from the inventory service
        from app.services.inventory_service import inventory_service

        items_with_details = []
        subtotal = Decimal('0')

        for item in order_request.items:
            # Get product from inventory
            product = await inventory_service.get_product(
                order_request.store_id,
                item.product_id
            )

            if not product:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {item.product_id} not found in store inventory"
                )

            unit_price = Decimal(str(product.get('selling_price', product.get('mrp', 0))))
            item_total = unit_price * item.quantity
            subtotal += item_total

            items_with_details.append({
                'inventory_id': product.get('inventory_id', item.product_id),
                'product_id': item.product_id,
                'product_name': product.get('product_name', 'Unknown Product'),
                'quantity': item.quantity,
                'unit_price': float(unit_price),
                'item_total': float(item_total),
                'mrp': float(product.get('mrp', unit_price))
            })

        # Calculate delivery fee
        delivery_fee = Decimal(str(order_request.delivery_fee or 0))
        if delivery_fee == 0 and subtotal < 200:
            delivery_fee = Decimal('20')  # Default delivery fee for small orders

        total = subtotal + delivery_fee

        # Prepare transaction items for stock reservation
        transaction_items = [
            TransactionOrderItem(
                product_id=item['product_id'],
                product_name=item['product_name'],
                quantity=item['quantity'],
                unit_price=Decimal(str(item['unit_price'])),
                unit='pieces'
            )
            for item in items_with_details
        ]

        # Prepare order data for database
        order_data = OrderData(
            order_id=order_id,
            customer_phone=customer.get('phone', ''),
            customer_id=customer_id,
            store_id=order_request.store_id,
            items=items_with_details,
            total_amount=total,
            status='placed',
            channel='web',
            language='en',
            intent='checkout',
            confidence=Decimal('1.0'),
            entities=[],
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            payment_method=order_request.payment_method_id,
            delivery_address=json.dumps(delivery_address),
            customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            delivery_notes=order_request.delivery_instructions,
            order_number=order_number,
            tracking_id=tracking_id
        )

        # Use transactional service to create order with stock reservation
        order_transaction_service = get_order_transaction_service()

        transaction_result = await order_transaction_service.create_order_with_stock_reservation(
            store_id=order_request.store_id,
            items=transaction_items,
            order_data=order_data
        )

        if not transaction_result.success:
            error_code = transaction_result.error_code

            if error_code == 'INSUFFICIENT_STOCK':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Insufficient stock",
                        "message": transaction_result.error,
                        "failed_items": transaction_result.failed_items or []
                    }
                )
            else:
                logger.error(f"Order transaction failed: {transaction_result.error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Order creation failed: {transaction_result.error}"
                )

        # ====================================================================
        # ATOMIC CART CLEARING: Clear cart AFTER successful order creation
        # This ensures:
        # 1. If order fails -> cart remains (user can retry)
        # 2. If order succeeds -> cart is cleared (consistent state)
        # ====================================================================
        cart_cleared = await clear_customer_cart(customer_id, order_request.store_id)
        if cart_cleared:
            logger.info(f"Cart atomically cleared after order {order_id}")
        else:
            # Non-fatal: order was created, frontend will handle cart sync
            logger.warning(f"Cart clearing failed for order {order_id}, frontend will sync")

        # Calculate estimated delivery
        from datetime import timedelta
        estimated_delivery = (datetime.utcnow() + timedelta(hours=2)).isoformat()

        # ====================================================================
        # INCREMENT CUSTOMER ORDER COUNT
        # Update the customer record to track order_count and total_spent
        # ====================================================================
        try:
            customers_table = dynamodb.Table('vyaparai-customers-prod')
            customers_table.update_item(
                Key={'customer_id': customer_id},
                UpdateExpression='SET order_count = if_not_exists(order_count, :zero) + :inc, total_spent = if_not_exists(total_spent, :zero) + :spent, updated_at = :updated',
                ExpressionAttributeValues={
                    ':inc': 1,
                    ':zero': Decimal('0'),
                    ':spent': Decimal(str(total)),
                    ':updated': datetime.utcnow().isoformat()
                }
            )
            logger.info(f"Customer {customer_id} order_count incremented")
        except Exception as e:
            # Non-fatal: order was created, stats update failure shouldn't block
            logger.warning(f"Failed to update customer order stats: {e}")

        logger.info(f"Customer order created: {order_id} for customer {customer_id}")

        return CreateOrderResponse(
            success=True,
            order=CreateOrderResponseData(
                order_id=order_id,
                order_number=order_number,
                tracking_id=tracking_id,
                status='placed',
                total=float(total),
                created_at=datetime.utcnow().isoformat(),
                estimated_delivery=estimated_delivery
            ),
            message="Order placed successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating customer order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )


@router.get("", response_model=OrderHistoryResponse)
async def get_customer_orders(
    limit: int = Query(20, ge=1, le=100),
    last_key: Optional[str] = Query(None, description="Last evaluated key for pagination"),
    customer: dict = Depends(verify_customer_token)
):
    """
    Get order history for the authenticated customer.
    Returns paginated list of orders.
    """
    try:
        customer_id = customer['customer_id']

        # Get orders from DynamoDB using customer_id
        # We need to query by customer_id which requires a GSI
        db_result = await db.get_orders_by_customer(customer_id, limit=limit)

        if not db_result.success:
            logger.error(f"Failed to fetch orders: {db_result.error}")
            # Return empty list instead of error for better UX
            return OrderHistoryResponse(
                success=True,
                orders=[],
                count=0,
                last_key=None
            )

        # Format orders for response
        orders = []
        for order in db_result.data:
            orders.append({
                "id": order.order_id,
                "order_number": getattr(order, 'order_number', order.order_id),
                "tracking_id": getattr(order, 'tracking_id', None),
                "store_id": order.store_id,
                "customer_id": order.customer_id or customer_id,
                "customer_name": getattr(order, 'customer_name', ''),
                "customer_phone": order.customer_phone,
                "status": order.status,
                "payment_status": getattr(order, 'payment_status', 'pending'),
                "payment_method": order.payment_method or 'cod',
                "items": order.items,
                "subtotal": float(order.total_amount),
                "delivery_fee": 0,
                "total": float(order.total_amount),
                "delivery_address": json.loads(order.delivery_address) if order.delivery_address else {},
                "customer_note": getattr(order, 'customer_note', None),
                "delivery_instructions": order.delivery_notes,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "estimated_delivery": getattr(order, 'estimated_delivery', None)
            })

        return OrderHistoryResponse(
            success=True,
            orders=orders,
            count=len(orders),
            last_key=None  # TODO: Implement pagination
        )

    except Exception as e:
        logger.error(f"Error fetching customer orders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch orders: {str(e)}"
        )


@router.get("/{order_id}", response_model=OrderDetailsResponse)
async def get_customer_order_details(
    order_id: str,
    customer: dict = Depends(verify_customer_token)
):
    """
    Get detailed information about a specific order.
    Only returns order if it belongs to the authenticated customer.
    """
    try:
        customer_id = customer['customer_id']

        # Get order from DynamoDB
        db_result = await db.get_order(order_id)

        if not db_result.success:
            if "not found" in str(db_result.error).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve order: {db_result.error}"
            )

        order = db_result.data

        # Verify order belongs to this customer
        order_customer_id = getattr(order, 'customer_id', None) or order.customer_phone
        if order_customer_id != customer_id and order.customer_phone != customer.get('phone'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this order"
            )

        # Format order for response
        order_response = {
            "id": order.order_id,
            "order_number": getattr(order, 'order_number', order.order_id),
            "tracking_id": getattr(order, 'tracking_id', None),
            "store_id": order.store_id,
            "customer_id": customer_id,
            "customer_name": getattr(order, 'customer_name', f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()),
            "customer_phone": order.customer_phone or customer.get('phone', ''),
            "status": order.status,
            "payment_status": getattr(order, 'payment_status', 'pending'),
            "payment_method": order.payment_method or 'cod',
            "payment_id": getattr(order, 'payment_id', None),
            "items": order.items,
            "subtotal": float(order.total_amount),
            "delivery_fee": 0,
            "total": float(order.total_amount),
            "delivery_address": json.loads(order.delivery_address) if order.delivery_address else {},
            "customer_note": getattr(order, 'customer_note', None),
            "delivery_instructions": order.delivery_notes,
            "cancel_reason": getattr(order, 'cancel_reason', None),
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "estimated_delivery": getattr(order, 'estimated_delivery', None)
        }

        return OrderDetailsResponse(
            success=True,
            order=order_response
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch order details: {str(e)}"
        )


@router.post("/{order_id}/cancel", response_model=CancelOrderResponse)
async def cancel_customer_order(
    order_id: str,
    cancel_request: CancelOrderRequest,
    customer: dict = Depends(verify_customer_token)
):
    """
    Cancel an order.
    Only the customer who placed the order can cancel it.
    Orders can only be cancelled if status is 'placed' or 'confirmed'.
    """
    try:
        customer_id = customer['customer_id']

        # Get order from DynamoDB
        db_result = await db.get_order(order_id)

        if not db_result.success:
            if "not found" in str(db_result.error).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve order: {db_result.error}"
            )

        order = db_result.data

        # Verify order belongs to this customer
        order_customer_id = getattr(order, 'customer_id', None) or order.customer_phone
        if order_customer_id != customer_id and order.customer_phone != customer.get('phone'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this order"
            )

        # Check if order can be cancelled
        cancellable_statuses = ['placed', 'confirmed', 'pending']
        if order.status.lower() not in cancellable_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order cannot be cancelled. Current status: {order.status}"
            )

        # Update order status to cancelled
        update_result = await db.update_order_status(order_id, 'cancelled')

        if not update_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel order: {update_result.error}"
            )

        # TODO: Restore stock (reverse the reservation)
        # This should be done through the order transaction service

        logger.info(f"Order {order_id} cancelled by customer {customer_id}. Reason: {cancel_request.reason}")

        return CancelOrderResponse(
            success=True,
            message="Order cancelled successfully",
            order_id=order_id,
            status="cancelled"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}"
        )
