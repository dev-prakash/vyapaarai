"""
FastAPI REST endpoints for VyaparAI Order Processing Service
Provides comprehensive API for order processing across all channels and languages

Authentication:
- Store management endpoints require store_owner authentication
- Customer order history requires customer authentication
- Webhook endpoints are unauthenticated (verified by signature)
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Literal
from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import asyncio
from decimal import Decimal

# Local imports
from app.middleware.rate_limit import rate_limit_dependency
from app.services.payment_service import PaymentService
from app.services.inventory_service import inventory_service
from app.services.unified_order_service import unified_order_service, OrderProcessingResult
from app.services.order_transaction_service import (
    OrderTransactionService, OrderItem, OrderTransactionResult,
    get_order_transaction_service
)
from app.services.notification_service import notification_service
from app.models.order import Order, OrderStatus, PaymentStatus, PaymentMethod
from app.database.hybrid_db import HybridDatabase, OrderData, HybridOrderResult
from app.core.security import (
    get_current_user, get_current_store_owner, get_current_customer,
    get_optional_current_user
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/orders", tags=["orders"])
payment_service = PaymentService()

# Initialize HybridDatabase for real order storage
db = HybridDatabase()
logger.info("HybridDatabase initialized for orders")

# =============================================================================
# DEPRECATED: In-memory storage for development/fallback
# WARNING: This storage is NOT suitable for production:
# - Data is lost on process restart
# - Does not work with multiple workers/instances
# - No persistence or reliability guarantees
#
# TODO: These should be fully migrated to DynamoDB in production
# The NLP order processing flow should use the same DynamoDB storage
# as the checkout flow for consistency.
# =============================================================================
orders_db: Dict[str, Dict[str, Any]] = {}  # DEPRECATED - use DynamoDB
customer_orders: Dict[str, List[str]] = {}  # DEPRECATED - use DynamoDB

# Warning flag to track if deprecated storage is used
_DEPRECATED_STORAGE_WARNING_SHOWN = False

def _warn_deprecated_storage():
    """Log warning about deprecated in-memory storage usage"""
    global _DEPRECATED_STORAGE_WARNING_SHOWN
    if not _DEPRECATED_STORAGE_WARNING_SHOWN:
        logger.warning(
            "DEPRECATION WARNING: Using in-memory storage for orders. "
            "This is NOT suitable for production. "
            "Data will be lost on restart and does not work with multiple workers. "
            "Migrate to DynamoDB for production use."
        )
        _DEPRECATED_STORAGE_WARNING_SHOWN = True

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ProcessOrderRequest(BaseModel):
    """Request model for order processing"""
    message: str = Field(..., min_length=1, description="Order message in any Indian language")
    session_id: Optional[str] = Field(None, description="Session identifier for tracking")
    channel: Literal["whatsapp", "rcs", "sms", "web"] = Field("whatsapp", description="Communication channel")
    store_id: Optional[str] = Field(None, description="Store identifier")
    customer_phone: Optional[str] = Field(None, description="Customer phone number")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()
    
    @validator('customer_phone')
    def validate_phone(cls, v):
        if v and not v.startswith('+91'):
            v = '+91' + v
        return v

class ProcessOrderResponse(BaseModel):
    """Response model for order processing"""
    success: bool = Field(..., description="Processing success status")
    order_id: str = Field(..., description="Unique order identifier")
    response: str = Field(..., description="Generated response message")
    intent: str = Field(..., description="Detected intent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Intent confidence score")
    entities: List[Dict[str, Any]] = Field(..., description="Extracted entities")
    language: str = Field(..., description="Detected language")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    channel_format: Dict[str, Any] = Field(..., description="Channel-specific formatted response")
    timestamp: datetime = Field(..., description="Processing timestamp")
    original_text: str = Field(..., description="Original input text")
    translated_text: Optional[str] = Field(None, description="Translated text (if applicable)")
    gemini_used: bool = Field(..., description="Whether Gemini was used for response generation")
    error_occurred: bool = Field(..., description="Whether an error occurred during processing")
    error_message: Optional[str] = Field(None, description="Error message if any")

class OrderConfirmRequest(BaseModel):
    """Request model for order confirmation"""
    order_id: str = Field(..., description="Order identifier to confirm")
    customer_details: Dict[str, Any] = Field(..., description="Customer information")
    delivery_address: Optional[str] = Field(None, description="Delivery address")
    payment_method: Literal["cod", "upi", "card"] = Field("cod", description="Payment method")
    special_instructions: Optional[str] = Field(None, description="Special delivery instructions")

class OrderConfirmResponse(BaseModel):
    """Response model for order confirmation"""
    success: bool = Field(..., description="Confirmation success status")
    order_id: str = Field(..., description="Order identifier")
    order_status: str = Field(..., description="Updated order status")
    estimated_delivery: str = Field(..., description="Estimated delivery time")
    total_amount: float = Field(..., description="Total order amount")
    confirmation_message: str = Field(..., description="Confirmation message for customer")

class OrderStatusResponse(BaseModel):
    """Response model for order status"""
    order_id: str = Field(..., description="Order identifier")
    status: str = Field(..., description="Current order status")
    created_at: datetime = Field(..., description="Order creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    customer_phone: Optional[str] = Field(None, description="Customer phone number")
    store_id: Optional[str] = Field(None, description="Store identifier")
    intent: str = Field(..., description="Original intent")
    entities: List[Dict[str, Any]] = Field(..., description="Order entities")
    total_amount: Optional[float] = Field(None, description="Order total amount")
    delivery_address: Optional[str] = Field(None, description="Delivery address")
    payment_method: Optional[str] = Field(None, description="Payment method")

class OrderHistoryResponse(BaseModel):
    """Response model for order history"""
    customer_phone: str = Field(..., description="Customer phone number")
    orders: List[OrderStatusResponse] = Field(..., description="List of orders")
    total_orders: int = Field(..., description="Total number of orders")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    has_next: bool = Field(..., description="Whether there are more pages")

class WebhookResponse(BaseModel):
    """Response model for webhook endpoints"""
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data")

class OrderItemRequest(BaseModel):
    product_id: Optional[str] = None
    product_name: str
    name: Optional[str] = None
    quantity: float = 1.0
    unit: str = "pieces"
    unit_price: float
    notes: Optional[str] = None

class CreateOrderRequest(BaseModel):
    store_id: str = "STORE-001"
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    delivery_address: str
    items: List[OrderItemRequest]
    payment_method: str = "upi"  # upi, card, cod, wallet
    delivery_notes: Optional[str] = None
    is_urgent: bool = False
    channel: str = "web"
    language: str = "en"

class UpdateOrderStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None

class PaymentConfirmationRequest(BaseModel):
    payment_id: str
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    payment_status: str = "completed"

# =============================================================================
# CHANNEL FORMATTERS
# =============================================================================

def format_whatsapp_response(text: str, phone: str, order_id: str) -> Dict[str, Any]:
    """Format response for WhatsApp Cloud API"""
    return {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {
            "body": text
        },
        "context": {
            "message_id": order_id
        }
    }

def format_rcs_response(text: str, suggestions: List[Dict[str, str]], order_id: str) -> Dict[str, Any]:
    """Format response for Google RCS"""
    return {
        "messageId": order_id,
        "text": text,
        "suggestions": suggestions,
        "richCard": {
            "title": "VyaparAI Order",
            "description": text,
            "media": {
                "height": "MEDIUM_HEIGHT",
                "contentInfo": {
                    "fileUrl": "https://vyaparai.com/logo.png",
                    "forceRefresh": False
                }
            }
        }
    }

def format_sms_response(text: str) -> List[str]:
    """Format response for SMS (split into 160-char segments)"""
    segments = []
    while text:
        if len(text) <= 160:
            segments.append(text)
            break
        else:
            # Find last space within 160 characters
            cut_point = text.rfind(' ', 0, 160)
            if cut_point == -1:
                cut_point = 159
            segments.append(text[:cut_point])
            text = text[cut_point:].lstrip()
    return segments

# =============================================================================
# MAIN ENDPOINTS
# =============================================================================

@router.post("/process", response_model=ProcessOrderResponse, status_code=status.HTTP_200_OK)
async def process_order(
    request: ProcessOrderRequest,
    rate_limit: bool = Depends(rate_limit_dependency)
):
    """
    Process order message in any Indian language
    
    - **message**: Order message in any supported language
    - **channel**: Communication channel (whatsapp/rcs/sms/web)
    - **store_id**: Optional store identifier
    - **customer_phone**: Customer phone number for tracking
    
    Returns processed order with intent, entities, and formatted response.
    """
    try:
        # Generate unique order ID
        order_id = str(uuid.uuid4())
        
        # Process order using unified service
        result = await unified_order_service.process_order(
            message=request.message,
            session_id=request.session_id or order_id,
            channel=request.channel,
            store_id=request.store_id
        )
        
        # Format response based on channel
        channel_format = {}
        if request.channel == "whatsapp" and request.customer_phone:
            channel_format = format_whatsapp_response(
                result.response, 
                request.customer_phone, 
                order_id
            )
        elif request.channel == "rcs":
            suggestions = unified_order_service._get_rcs_suggestions(result.intent)
            channel_format = format_rcs_response(
                result.response, 
                suggestions, 
                order_id
            )
        elif request.channel == "sms":
            segments = format_sms_response(result.response)
            channel_format = {"segments": segments, "total_segments": len(segments)}
        else:
            channel_format = {"text": result.response}
        
        # Store order in database
        # NOTE: NLP-processed orders currently use deprecated in-memory storage
        # TODO: Migrate to DynamoDB for consistency with checkout flow
        _warn_deprecated_storage()

        order_data = {
            "order_id": order_id,
            "status": "processed",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "customer_phone": request.customer_phone,
            "store_id": request.store_id,
            "intent": result.intent,
            "entities": result.entities,
            "language": result.language,
            "original_text": result.original_text,
            "response": result.response,
            "metadata": request.metadata
        }
        orders_db[order_id] = order_data

        # Track customer orders (deprecated - use DynamoDB queries instead)
        if request.customer_phone:
            if request.customer_phone not in customer_orders:
                customer_orders[request.customer_phone] = []
            customer_orders[request.customer_phone].append(order_id)
        
        logger.info(f"Order processed successfully: {order_id}")
        
        return ProcessOrderResponse(
            success=True,
            order_id=order_id,
            response=result.response,
            intent=result.intent,
            confidence=result.confidence,
            entities=result.entities,
            language=result.language,
            processing_time_ms=result.processing_time_ms,
            channel_format=channel_format,
            timestamp=datetime.now(),
            original_text=result.original_text,
            translated_text=result.translated_text,
            gemini_used=result.gemini_used,
            error_occurred=result.error_occurred,
            error_message=result.error_message
        )
        
    except Exception as e:
        logger.error(f"Error processing order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process order: {str(e)}"
        )

@router.post("/confirm/{order_id}", response_model=OrderConfirmResponse, status_code=status.HTTP_200_OK)
async def confirm_order(
    order_id: str,
    request: OrderConfirmRequest,
    rate_limit: bool = Depends(rate_limit_dependency)
):
    """
    Confirm an order with customer details
    
    - **order_id**: Order identifier to confirm
    - **customer_details**: Customer information
    - **delivery_address**: Delivery address
    - **payment_method**: Payment method (cod/upi/card)
    
    Returns confirmation details and estimated delivery time.
    """
    try:
        # Get order from DynamoDB
        db_result = await db.get_order(order_id)

        if not db_result.success:
            if "not found" in str(db_result.error).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found"
                )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve order: {db_result.error}"
            )

        order_data = db_result.data
        total_amount = order_data.total_amount

        # Update order status to confirmed
        update_result = await db.update_order_status(order_id, "confirmed")

        if not update_result.success:
            logger.error(f"Failed to update order status: {update_result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to confirm order: {update_result.error}"
            )

        # Generate confirmation message
        confirmation_message = f"Order confirmed! Your order will be delivered in 30-45 minutes. Total: ₹{total_amount:.2f}"

        logger.info(f"Order {order_id} confirmed in DynamoDB")

        return OrderConfirmResponse(
            success=True,
            order_id=order_id,
            order_status="confirmed",
            estimated_delivery="30-45 minutes",
            total_amount=total_amount,
            confirmation_message=confirmation_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm order: {str(e)}"
        )

# =============================================================================
# ORDER HISTORY & ANALYTICS ENDPOINTS
# =============================================================================

from app.core.cache import cache_result, invalidate_orders_cache

@router.get("/history", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
# NOTE: @cache_result decorator removed - was causing 500 errors due to
# serialization issues with current_user dict dependency. Consider implementing
# manual caching with explicit cache key (excluding non-serializable params).
async def get_order_history(
    store_id: str = Query(..., description="Store identifier"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    order_status: Optional[str] = Query(None, description="Filter by order status"),
    payment_method: Optional[str] = Query(None, description="Filter by payment method"),
    search: Optional[str] = Query(None, description="Search in order ID, customer name, or phone"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Get paginated order history with advanced filtering (Store Owner Only)

    Requires authentication with store_owner token.
    Supports filtering by date range, status, payment method, and search terms.
    Returns paginated results with total count.
    """
    # Verify user has access to the requested store
    if current_user.get('store_id') and current_user['store_id'] != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this store's orders"
        )
    try:
        # Filter orders by store
        store_orders = {k: v for k, v in orders_db.items() if v.get("store_id") == store_id}
        
        # Apply filters
        filtered_orders = []
        for order_id, order in store_orders.items():
            # Date filter
            if start_date:
                order_date = order.get("created_at")
                if isinstance(order_date, str):
                    order_date = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
                if order_date < datetime.fromisoformat(start_date):
                    continue
            
            if end_date:
                order_date = order.get("created_at")
                if isinstance(order_date, str):
                    order_date = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
                if order_date > datetime.fromisoformat(end_date):
                    continue
            
            # Status filter
            if order_status and order.get("status") != order_status:
                continue
            
            # Payment method filter
            if payment_method and order.get("payment_method") != payment_method:
                continue
            
            # Search filter
            if search:
                search_lower = search.lower()
                order_id_match = order_id.lower().find(search_lower) != -1
                customer_phone_match = order.get("customer_phone", "").lower().find(search_lower) != -1
                if not (order_id_match or customer_phone_match):
                    continue
            
            filtered_orders.append((order_id, order))
        
        # Sort orders
        reverse = sort_order.lower() == "desc"
        if sort_by == "total_amount":
            filtered_orders.sort(key=lambda x: x[1].get("total_amount", 0), reverse=reverse)
        elif sort_by == "created_at":
            filtered_orders.sort(key=lambda x: x[1].get("created_at"), reverse=reverse)
        else:
            filtered_orders.sort(key=lambda x: x[0], reverse=reverse)
        
        # Paginate
        total_count = len(filtered_orders)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_orders = filtered_orders[start_idx:end_idx]
        
        # Format response
        orders = []
        for order_id, order in page_orders:
            orders.append({
                "order_id": order_id,
                "customer_phone": order.get("customer_phone"),
                "status": order.get("status"),
                "total_amount": order.get("total_amount"),
                "payment_method": order.get("payment_method"),
                "created_at": order.get("created_at"),
                "updated_at": order.get("updated_at"),
                "items": order.get("entities", {}).get("items", [])
            })
        
        return {
            "orders": orders,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            },
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "status": order_status,
                "payment_method": payment_method,
                "search": search
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting order history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order history: {str(e)}"
        )

@router.get("/export", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def export_orders(
    store_id: str = Query(..., description="Store identifier"),
    format: str = Query("csv", description="Export format (csv/pdf)"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Export orders to CSV or PDF format (Store Owner Only)

    Requires authentication with store_owner token.
    Supports filtering by date range and exports in the specified format.
    """
    # Verify user has access to the requested store
    if current_user.get('store_id') and current_user['store_id'] != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this store's orders"
        )
    try:
        # Get filtered orders (reuse history logic)
        store_orders = {k: v for k, v in orders_db.items() if v.get("store_id") == store_id}
        
        filtered_orders = []
        for order_id, order in store_orders.items():
            # Date filter
            if start_date:
                order_date = order.get("created_at")
                if isinstance(order_date, str):
                    order_date = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
                if order_date < datetime.fromisoformat(start_date):
                    continue
            
            if end_date:
                order_date = order.get("created_at")
                if isinstance(order_date, str):
                    order_date = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
                if order_date > datetime.fromisoformat(end_date):
                    continue
            
            filtered_orders.append((order_id, order))
        
        if format.lower() == "csv":
            # Generate CSV
            csv_data = "Order ID,Customer Phone,Status,Total Amount,Payment Method,Created At\n"
            for order_id, order in filtered_orders:
                csv_data += f"{order_id},{order.get('customer_phone', '')},{order.get('status', '')},{order.get('total_amount', 0)},{order.get('payment_method', '')},{order.get('created_at', '')}\n"
            
            return {
                "format": "csv",
                "data": csv_data,
                "filename": f"orders_{store_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                "count": len(filtered_orders)
            }
        
        elif format.lower() == "pdf":
            # Generate PDF (simplified for now)
            pdf_data = f"Orders Report for Store {store_id}\n"
            pdf_data += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            pdf_data += f"Total Orders: {len(filtered_orders)}\n\n"
            
            for order_id, order in filtered_orders:
                pdf_data += f"Order: {order_id}\n"
                pdf_data += f"Customer: {order.get('customer_phone', '')}\n"
                pdf_data += f"Status: {order.get('status', '')}\n"
                pdf_data += f"Amount: ₹{order.get('total_amount', 0)}\n"
                pdf_data += f"Payment: {order.get('payment_method', '')}\n"
                pdf_data += f"Created: {order.get('created_at', '')}\n\n"
            
            return {
                "format": "pdf",
                "data": pdf_data,
                "filename": f"orders_{store_id}_{datetime.now().strftime('%Y%m%d')}.pdf",
                "count": len(filtered_orders)
            }
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported format. Use 'csv' or 'pdf'"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export orders: {str(e)}"
        )

@router.get("/stats/daily", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_daily_stats(
    store_id: str = Query(..., description="Store identifier"),
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD format)"),
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Get detailed daily statistics for a store (Store Owner Only)

    Requires authentication with store_owner token.
    Returns comprehensive metrics including revenue, order counts, and trends.
    """
    # Verify user has access to the requested store
    if current_user.get('store_id') and current_user['store_id'] != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this store's statistics"
        )
    try:
        # Use today if no date specified
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        target_date = datetime.strptime(date, '%Y-%m-%d')
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Filter orders for the day
        daily_orders = []
        total_revenue = 0
        status_counts = {"pending": 0, "confirmed": 0, "completed": 0, "cancelled": 0}
        payment_methods = {}
        
        for order_id, order in orders_db.items():
            if order.get("store_id") != store_id:
                continue
            
            order_date = order.get("created_at")
            if isinstance(order_date, str):
                order_date = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
            
            if start_of_day <= order_date <= end_of_day:
                daily_orders.append(order)
                total_revenue += order.get("total_amount", 0)
                
                status = order.get("status", "pending")
                status_counts[status] = status_counts.get(status, 0) + 1
                
                payment_method = order.get("payment_method", "unknown")
                payment_methods[payment_method] = payment_methods.get(payment_method, 0) + 1
        
        # Calculate additional metrics
        avg_order_value = total_revenue / len(daily_orders) if daily_orders else 0
        unique_customers = len(set(order.get("customer_phone") for order in daily_orders))
        
        return {
            "date": date,
            "store_id": store_id,
            "summary": {
                "total_orders": len(daily_orders),
                "total_revenue": total_revenue,
                "average_order_value": round(avg_order_value, 2),
                "unique_customers": unique_customers
            },
            "status_breakdown": status_counts,
            "payment_breakdown": payment_methods,
            "hourly_breakdown": {
                # Simplified hourly breakdown
                "morning": len([o for o in daily_orders if 6 <= datetime.fromisoformat(o.get("created_at").replace('Z', '+00:00')).hour < 12]),
                "afternoon": len([o for o in daily_orders if 12 <= datetime.fromisoformat(o.get("created_at").replace('Z', '+00:00')).hour < 18]),
                "evening": len([o for o in daily_orders if 18 <= datetime.fromisoformat(o.get("created_at").replace('Z', '+00:00')).hour < 24]),
                "night": len([o for o in daily_orders if 0 <= datetime.fromisoformat(o.get("created_at").replace('Z', '+00:00')).hour < 6])
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting daily stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get daily stats: {str(e)}"
        )

@router.get("/history/customer/{customer_phone}", response_model=OrderHistoryResponse, status_code=status.HTTP_200_OK)
async def get_customer_order_history(
    customer_phone: str,
    page: int = 1,
    page_size: int = 10
):
    """
    Get customer's order history
    
    - **customer_phone**: Customer phone number
    - **page**: Page number (default: 1)
    - **page_size**: Page size (default: 10)
    
    Returns paginated order history for the customer.
    """
    try:
        # Normalize phone number
        if not customer_phone.startswith('+91'):
            customer_phone = '+91' + customer_phone
        
        # Get customer orders
        customer_order_ids = customer_orders.get(customer_phone, [])
        total_orders = len(customer_order_ids)
        
        # Paginate
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_order_ids = customer_order_ids[start_idx:end_idx]
        
        # Get order details
        orders = []
        for order_id in page_order_ids:
            if order_id in orders_db:
                order = orders_db[order_id]
                orders.append(OrderStatusResponse(
                    order_id=order_id,
                    status=order["status"],
                    created_at=order["created_at"],
                    updated_at=order["updated_at"],
                    customer_phone=order.get("customer_phone"),
                    store_id=order.get("store_id"),
                    intent=order["intent"],
                    entities=order["entities"],
                    total_amount=order.get("total_amount"),
                    delivery_address=order.get("delivery_address"),
                    payment_method=order.get("payment_method")
                ))
        
        return OrderHistoryResponse(
            customer_phone=customer_phone,
            orders=orders,
            total_orders=total_orders,
            page=page,
            page_size=page_size,
            has_next=end_idx < total_orders
        )
        
    except Exception as e:
        logger.error(f"Error getting order history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order history: {str(e)}"
        )

# =============================================================================
# INDIVIDUAL ORDER ENDPOINTS
# =============================================================================

@router.get("/{order_id}/status", response_model=OrderStatusResponse, status_code=status.HTTP_200_OK)
async def get_order_status(order_id: str):
    """
    Get order status summary (lightweight endpoint)

    - **order_id**: Order identifier

    Returns order status information. For full details use GET /{order_id}
    """
    try:
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

        return OrderStatusResponse(
            order_id=order.order_id,
            status=order.status,
            created_at=order.created_at,
            updated_at=order.updated_at,
            customer_phone=order.customer_phone,
            store_id=order.store_id,
            intent=order.intent or "order",
            entities={"items": order.items},
            total_amount=order.total_amount,
            delivery_address=order.delivery_address,
            payment_method=order.payment_method
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order status: {str(e)}"
        )

@router.post("/{order_id}/cancel", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def cancel_order(
    order_id: str,
    reason: Optional[str] = None,
    rate_limit: bool = Depends(rate_limit_dependency),
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel an order (Authenticated Users Only)

    Store owners can cancel any order in their store.
    Customers can only cancel their own orders.

    - **order_id**: Order identifier to cancel
    - **reason**: Optional cancellation reason

    Returns cancellation confirmation.
    """
    try:
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

        # Authorization check
        user_store_id = current_user.get('store_id')
        user_phone = current_user.get('phone')
        user_customer_id = current_user.get('customer_id')
        order_store_id = order.store_id
        order_customer_phone = order.customer_phone

        # Store owners can cancel orders in their store
        # Customers can only cancel their own orders
        is_store_owner = user_store_id and user_store_id == order_store_id
        is_order_customer = (user_phone and user_phone == order_customer_phone) or \
                           (user_customer_id and str(user_customer_id) in str(order.customer_id or ''))

        if not is_store_owner and not is_order_customer:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to cancel this order"
            )

        # Update order status in DynamoDB
        update_result = await db.update_order_status(order_id, "cancelled")

        if not update_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel order: {update_result.error}"
            )

        logger.info(f"Order cancelled: {order_id} by user {current_user.get('user_id') or current_user.get('customer_id')}")

        return {
            "success": True,
            "order_id": order_id,
            "status": "cancelled",
            "message": "Order cancelled successfully",
            "cancellation_reason": reason,
            "processing_time_ms": update_result.processing_time_ms
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}"
        )



# =============================================================================
# WEBHOOK ENDPOINTS
# =============================================================================

@router.post("/webhooks/whatsapp", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def whatsapp_webhook(request: Request):
    """
    WhatsApp Cloud API webhook endpoint
    
    Processes incoming WhatsApp messages and returns formatted responses.
    """
    try:
        # Parse WhatsApp webhook payload
        payload = await request.json()
        
        # Extract message details
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return WebhookResponse(
                status="success",
                message="No messages to process",
                data=None
            )
        
        message = messages[0]
        phone_number = message.get("from")
        message_text = message.get("text", {}).get("body", "")
        message_id = message.get("id")
        
        if not message_text:
            return WebhookResponse(
                status="success",
                message="No text message to process",
                data=None
            )
        
        # Process message
        result = await unified_order_service.process_order(
            message=message_text,
            session_id=message_id,
            channel="whatsapp"
        )
        
        # Format WhatsApp response
        whatsapp_response = format_whatsapp_response(
            result.response,
            phone_number,
            message_id
        )
        
        logger.info(f"WhatsApp webhook processed: {message_id}")
        
        return WebhookResponse(
            status="success",
            message="Message processed successfully",
            data=whatsapp_response
        )
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        return WebhookResponse(
            status="error",
            message=f"Failed to process message: {str(e)}",
            data=None
        )

@router.post("/webhooks/rcs", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def rcs_webhook(request: Request):
    """
    Google RCS webhook endpoint
    
    Processes incoming RCS messages and returns rich card responses.
    """
    try:
        # Parse RCS webhook payload
        payload = await request.json()
        
        # Extract message details
        message_text = payload.get("message", {}).get("text", "")
        user_id = payload.get("user", {}).get("userId", "")
        message_id = payload.get("messageId", "")
        
        if not message_text:
            return WebhookResponse(
                status="success",
                message="No text message to process",
                data=None
            )
        
        # Process message
        result = await unified_order_service.process_order(
            message=message_text,
            session_id=message_id,
            channel="rcs"
        )
        
        # Format RCS response
        suggestions = unified_order_service._get_rcs_suggestions(result.intent)
        rcs_response = format_rcs_response(
            result.response,
            suggestions,
            message_id
        )
        
        logger.info(f"RCS webhook processed: {message_id}")
        
        return WebhookResponse(
            status="success",
            message="Message processed successfully",
            data=rcs_response
        )
        
    except Exception as e:
        logger.error(f"RCS webhook error: {e}")
        return WebhookResponse(
            status="error",
            message=f"Failed to process message: {str(e)}",
            data=None
        )

@router.post("/webhooks/sms", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def sms_webhook(request: Request):
    """
    SMS webhook endpoint
    
    Processes incoming SMS messages and returns 160-char limited responses.
    """
    try:
        # Parse SMS webhook payload
        payload = await request.json()
        
        # Extract message details
        message_text = payload.get("message", "")
        phone_number = payload.get("from", "")
        message_id = payload.get("id", "")
        
        if not message_text:
            return WebhookResponse(
                status="success",
                message="No text message to process",
                data=None
            )
        
        # Process message
        result = await unified_order_service.process_order(
            message=message_text,
            session_id=message_id,
            channel="sms"
        )
        
        # Format SMS response
        sms_segments = format_sms_response(result.response)
        
        logger.info(f"SMS webhook processed: {message_id}")
        
        return WebhookResponse(
            status="success",
            message="Message processed successfully",
            data={
                "to": phone_number,
                "segments": sms_segments,
                "total_segments": len(sms_segments)
            }
        )
        
    except Exception as e:
        logger.error(f"SMS webhook error: {e}")
        return WebhookResponse(
            status="error",
            message=f"Failed to process message: {str(e)}",
            data=None
        )

# =============================================================================
# METRICS ENDPOINT
# =============================================================================

@router.get("/metrics", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_metrics():
    """
    Get order processing metrics
    
    Returns comprehensive metrics including:
    - Orders processed today
    - Language distribution
    - Intent distribution
    - Average response time
    - Error rate
    """
    try:
        # Get unified service metrics
        service_metrics = unified_order_service.get_metrics()
        performance_summary = unified_order_service.get_performance_summary()
        
        # Calculate today's orders
        today = datetime.now().date()
        today_orders = [
            order for order in orders_db.values()
            if order["created_at"].date() == today
        ]
        
        # Calculate order status distribution
        status_distribution = {}
        for order in orders_db.values():
            status = order["status"]
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        metrics = {
            "orders_today": len(today_orders),
            "total_orders": len(orders_db),
            "unique_customers": len(customer_orders),
            "language_distribution": service_metrics["language_distribution"],
            "intent_distribution": service_metrics["intent_distribution"],
            "status_distribution": status_distribution,
            "performance": {
                "avg_processing_time_ms": service_metrics["avg_processing_time"],
                "total_requests": service_metrics["total_requests"],
                "error_rate": (service_metrics["error_count"] / max(service_metrics["total_requests"], 1)) * 100,
                "gemini_usage_rate": (service_metrics["gemini_usage"] / max(service_metrics["total_requests"], 1)) * 100,
                "template_usage_rate": (service_metrics["template_usage"] / max(service_metrics["total_requests"], 1)) * 100
            },
            "channel_distribution": service_metrics["channel_distribution"],
            "timestamp": datetime.now().isoformat()
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}"
        )

# =============================================================================
# TEST ENDPOINTS (Development Only)
# =============================================================================

class TestOrderRequest(BaseModel):
    """Request model for test order generation"""
    store_id: str = Field(..., description="Store identifier")
    customer_name: Optional[str] = Field(None, description="Customer name")
    customer_phone: Optional[str] = Field(None, description="Customer phone number")
    order_type: Optional[str] = Field("random", description="Type of order to generate")

@router.post("/test/generate-order", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def generate_test_order(request: TestOrderRequest):
    """
    Generate a test order for development and testing
    
    This endpoint creates a realistic test order with Indian context
    for testing the order flow and WebSocket integration.
    """
    try:
        import random
        from datetime import datetime, timedelta
        
        # Generate realistic Indian order data
        customer_names = [
            "Rajesh Kumar", "Priya Sharma", "Amit Patel", "Neha Singh", "Suresh Verma",
            "Anjali Gupta", "Rahul Mehta", "Kavita Reddy", "Vikram Malhotra", "Sunita Joshi"
        ]
        
        indian_products = [
            {"name": "Amul Milk", "price": 60, "unit": "1L"},
            {"name": "Aashirvaad Atta", "price": 45, "unit": "1kg"},
            {"name": "India Gate Basmati Rice", "price": 120, "unit": "1kg"},
            {"name": "Tata Salt", "price": 20, "unit": "1kg"},
            {"name": "Maggi Noodles", "price": 14, "unit": "70g"},
            {"name": "Colgate Toothpaste", "price": 45, "unit": "100g"},
            {"name": "Fresh Tomatoes", "price": 40, "unit": "1kg"},
            {"name": "Fresh Onions", "price": 30, "unit": "1kg"}
        ]
        
        # Generate order data
        order_id = f"TEST-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        customer_name = request.customer_name or random.choice(customer_names)
        customer_phone = request.customer_phone or f"+9198765{random.randint(10000, 99999)}"
        
        # Generate random items
        num_items = random.randint(1, 4)
        items = []
        for i in range(num_items):
            product = random.choice(indian_products)
            quantity = random.randint(1, 3)
            items.append({
                "id": f"item_{i+1}",
                "productName": product["name"],
                "quantity": quantity,
                "unit": product["unit"],
                "price": product["price"],
                "total": product["price"] * quantity
            })
        
        # Calculate totals
        subtotal = sum(item["total"] for item in items)
        tax = subtotal * 0.05  # 5% tax
        delivery_fee = 0 if subtotal > 500 else 50
        total = subtotal + tax + delivery_fee
        
        # Generate order
        order_data = {
            "id": order_id,
            "customerName": customer_name,
            "customerPhone": customer_phone,
            "deliveryAddress": f"123, MG Road, Bangalore, Karnataka 560001",
            "items": items,
            "total": round(total, 2),
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "deliveryFee": delivery_fee,
            "status": "pending",
            "paymentMethod": random.choice(["cash", "card", "upi", "cod"]),
            "paymentStatus": "pending",
            "orderDate": datetime.now().isoformat(),
            "deliveryTime": (datetime.now() + timedelta(minutes=45)).isoformat(),
            "notes": "Test order generated for development",
            "channel": "test",
            "language": "en",
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "store_id": request.store_id
        }
        
        # Store order
        orders_db[order_id] = order_data
        
        # Add to customer orders
        if customer_phone not in customer_orders:
            customer_orders[customer_phone] = []
        customer_orders[customer_phone].append(order_id)
        
        # Emit WebSocket event if available
        try:
            from app.websocket.socket_manager import socket_manager
            await socket_manager.emit_new_order(order_data)
            logger.info(f"Emitted WebSocket event for test order {order_id}")
        except Exception as e:
            logger.warning(f"Failed to emit WebSocket event: {e}")
        
        logger.info(f"Generated test order: {order_id}")
        
        return {
            "success": True,
            "order_id": order_id,
            "order_data": order_data,
            "message": f"Test order {order_id} generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error generating test order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate test order: {str(e)}"
        )

@router.post("/")
async def create_order_with_payment(
    order_data: CreateOrderRequest,
    current_user: dict = Depends(get_optional_current_user)
):
    """
    Create order with payment integration - TRANSACTIONALLY SAFE

    Uses Saga pattern to ensure:
    1. Stock is reserved FIRST (atomic deduction)
    2. Order is created only if stock reservation succeeds
    3. If order creation fails, stock is automatically restored

    Authentication is optional - allows both authenticated and guest orders.
    If authenticated, the order is linked to the user's account.
    """

    try:
        # Validate required fields
        if not order_data.store_id:
            return JSONResponse(
                status_code=400,
                content={"error": "store_id is required"}
            )

        if not order_data.items or len(order_data.items) == 0:
            return JSONResponse(
                status_code=400,
                content={"error": "Order must contain at least one item"}
            )

        # Generate order ID
        order_id = f"ORD{uuid.uuid4().hex[:8].upper()}"

        # Calculate order totals
        subtotal = sum(item.quantity * item.unit_price for item in order_data.items)
        tax_rate = 0.05  # 5% GST
        tax_amount = subtotal * tax_rate
        delivery_fee = 20 if subtotal < 200 else 0
        total_amount = subtotal + tax_amount + delivery_fee

        # Convert items to JSON
        items_json = json.dumps([item.dict() for item in order_data.items])

        # Create order object
        order = Order(
            id=order_id,
            store_id=order_data.store_id,
            customer_name=order_data.customer_name,
            customer_phone=order_data.customer_phone,
            customer_email=order_data.customer_email,
            delivery_address=order_data.delivery_address,
            items=items_json,
            subtotal=subtotal,
            tax_amount=tax_amount,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
            status=OrderStatus.PENDING,
            payment_method=PaymentMethod(order_data.payment_method),
            payment_status=PaymentStatus.PENDING,
            delivery_notes=order_data.delivery_notes,
            is_urgent=order_data.is_urgent,
            channel=order_data.channel,
            language=order_data.language,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Handle payment based on method
        payment_required = order_data.payment_method != "cod"
        payment_id = None

        if payment_required:
            # Create payment intent for online payments
            payment_result = await payment_service.create_payment_intent(
                order_id=order_id,
                amount=Decimal(str(total_amount)),
                customer_info={
                    "name": order_data.customer_name,
                    "phone": order_data.customer_phone,
                    "email": order_data.customer_email
                }
            )

            if not payment_result["success"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment intent creation failed: {payment_result.get('error', 'Unknown error')}"
                )

            payment_id = payment_result["payment_id"]
            order.payment_id = payment_id
            order.payment_created_at = datetime.utcnow()
            order.payment_gateway_response = json.dumps(payment_result.get("gateway_response", {}))
        else:
            # Handle Cash on Delivery
            cod_result = await payment_service.process_cod_payment(
                order_id=order_id,
                amount=Decimal(str(total_amount))
            )

            if cod_result["success"]:
                payment_id = cod_result["payment_id"]
                order.payment_id = payment_id
                order.payment_created_at = datetime.utcnow()
                order.payment_gateway_response = json.dumps(cod_result.get("gateway_response", {}))

        # Prepare order items for transactional service
        transaction_items = [
            OrderItem(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=int(item.quantity),
                unit_price=Decimal(str(item.unit_price)),
                unit=item.unit
            )
            for item in order_data.items
        ]

        # Prepare order data for database
        dynamodb_items = []
        for item in order_data.items:
            item_dict = item.dict()
            item_dict['unit_price'] = Decimal(str(item_dict['unit_price']))
            item_dict['quantity'] = int(item_dict['quantity'])
            dynamodb_items.append(item_dict)

        order_data_obj = OrderData(
            order_id=order_id,
            customer_phone=order_data.customer_phone,
            store_id=order_data.store_id,
            items=dynamodb_items,
            total_amount=Decimal(str(total_amount)),
            status=OrderStatus.PENDING.value,
            channel=order_data.channel,
            language=order_data.language,
            intent="checkout",
            confidence=Decimal("1.0"),
            entities=[],
            created_at=order.created_at.isoformat(),
            updated_at=order.updated_at.isoformat()
        )

        # ========================================================================
        # TRANSACTIONAL ORDER CREATION WITH SAGA PATTERN
        # This ensures: Reserve stock -> Create order -> Rollback on failure
        # ========================================================================
        order_transaction_service = get_order_transaction_service()

        transaction_result = await order_transaction_service.create_order_with_stock_reservation(
            store_id=order_data.store_id,
            items=transaction_items,
            order_data=order_data_obj
        )

        if not transaction_result.success:
            # Transaction failed - could be insufficient stock or database error
            error_code = transaction_result.error_code

            if error_code == 'INSUFFICIENT_STOCK':
                # Return detailed stock error
                failed_items = transaction_result.failed_items or []
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Insufficient stock",
                        "message": transaction_result.error,
                        "failed_items": failed_items,
                        "order_id": order_id
                    }
                )
            else:
                # Other error (database, unexpected)
                logger.error(
                    f"Order transaction failed for {order_id}: "
                    f"{transaction_result.error} (code: {error_code})"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Order creation failed: {transaction_result.error}"
                )

        logger.info(
            f"Order {order_id} created successfully (transactional) "
            f"in {transaction_result.processing_time_ms:.2f}ms"
        )

        return {
            "success": True,
            "order_id": order_id,
            "payment_id": payment_id,
            "total_amount": total_amount,
            "payment_required": payment_required,
            "payment_method": order_data.payment_method,
            "order": order.to_dict(),
            "message": "Order created successfully",
            "transaction_time_ms": transaction_result.processing_time_ms
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in order creation: {e}")
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")

@router.post("/{order_id}/payment/confirm")
async def confirm_order_payment(order_id: str, payment_data: PaymentConfirmationRequest):
    """Confirm payment for an order"""
    
    try:
        # Verify payment
        if payment_data.razorpay_payment_id and payment_data.razorpay_signature:
            verification_result = await payment_service.verify_payment(
                payment_id=payment_data.payment_id,
                razorpay_payment_id=payment_data.razorpay_payment_id,
                razorpay_signature=payment_data.razorpay_signature
            )
            
            if not verification_result["success"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment verification failed: {verification_result.get('error', 'Unknown error')}"
                )
        
        # Update order status based on payment
        payment_status = PaymentStatus(payment_data.payment_status)
        
        # In production, this would update the database
        # order = db.query(Order).filter(Order.id == order_id).first()
        # order.payment_status = payment_status
        # order.status = OrderStatus.CONFIRMED if payment_status == PaymentStatus.COMPLETED else OrderStatus.PENDING
        # order.payment_completed_at = datetime.utcnow()
        # db.commit()
        
        return {
            "success": True,
            "order_id": order_id,
            "payment_status": payment_status.value,
            "order_status": "confirmed" if payment_status == PaymentStatus.COMPLETED else "pending",
            "message": "Payment confirmed successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment confirmation failed: {str(e)}")

@router.get("/{order_id}")
async def get_order_details(order_id: str):
    """Get order details by ID"""

    try:
        # Get order from DynamoDB
        db_result = await db.get_order(order_id)

        if not db_result.success:
            if "not found" in str(db_result.error).lower():
                raise HTTPException(status_code=404, detail="Order not found")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve order: {db_result.error}"
            )

        # Extract order data from result
        order_data = db_result.data

        logger.info(f"Order {order_id} retrieved from DynamoDB in {db_result.processing_time_ms}ms")

        # Convert OrderData to response format
        order_response = {
            "id": order_data.order_id,
            "store_id": order_data.store_id,
            "customer_phone": order_data.customer_phone,
            "items": order_data.items,
            "total_amount": order_data.total_amount,
            "status": order_data.status,
            "channel": order_data.channel,
            "language": order_data.language,
            "created_at": order_data.created_at,
            "updated_at": order_data.updated_at
        }

        return {
            "success": True,
            "order": order_response,
            "processing_time_ms": db_result.processing_time_ms
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get order details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get order details: {str(e)}")

@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    status_data: UpdateOrderStatusRequest,
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Update order status (Store Owner Only)

    Requires authentication with store_owner token.
    Only store owners can update order status.
    Sends push notification to customer for relevant status changes.
    """

    try:
        # Validate status
        try:
            new_status = OrderStatus(status_data.status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid order status")

        # Get order details first (need customer_id for notification)
        order_result = await db.get_order(order_id)
        if not order_result.success:
            if "not found" in str(order_result.error).lower():
                raise HTTPException(status_code=404, detail="Order not found")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve order: {order_result.error}"
            )

        order_data = order_result.data

        # Update order status in DynamoDB
        update_result = await db.update_order_status(order_id, new_status.value)

        if not update_result.success:
            if "not found" in str(update_result.error).lower():
                raise HTTPException(status_code=404, detail="Order not found")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update order status: {update_result.error}"
            )

        logger.info(f"Order {order_id} status updated to {new_status.value} in DynamoDB")

        # Send push notification for relevant status changes
        notification_sent = False
        notification_statuses = ['confirmed', 'preparing', 'ready', 'out_for_delivery', 'delivered']

        if new_status.value in notification_statuses:
            try:
                # Get customer_id from order data
                customer_id = order_data.customer_id if hasattr(order_data, 'customer_id') else None

                if customer_id:
                    # Generate order number from order_id if not available
                    order_number = getattr(order_data, 'order_number', None) or order_id[:8].upper()

                    notification_result = await notification_service.send_order_notification(
                        customer_id=customer_id,
                        order_id=order_id,
                        order_number=order_number,
                        status=new_status.value
                    )

                    if notification_result.success:
                        logger.info(f"Push notification sent for order {order_id} status: {new_status.value}")
                        notification_sent = True
                    else:
                        logger.warning(
                            f"Push notification failed for order {order_id}: {notification_result.error}"
                        )
                else:
                    logger.info(f"No customer_id for order {order_id}, skipping notification")

            except Exception as notif_err:
                # Don't fail the status update if notification fails
                logger.error(f"Error sending notification for order {order_id}: {notif_err}")

        return {
            "success": True,
            "order_id": order_id,
            "status": new_status.value,
            "message": "Order status updated successfully",
            "notification_sent": notification_sent,
            "processing_time_ms": update_result.processing_time_ms
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update order status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update order status: {str(e)}")

@router.get("")
async def get_orders_by_query(
    store_id: str = Query(..., description="Store ID to get orders for"),
    limit: int = Query(50, ge=1, le=100, description="Maximum orders to return"),
    offset: int = Query(0, ge=0, description="Number of orders to skip")
):
    """
    Get orders for a store using query parameter

    This endpoint is for dashboard use - returns orders for the specified store.
    """
    try:
        import boto3
        from boto3.dynamodb.conditions import Attr

        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        orders_table = dynamodb.Table('vyaparai-orders-prod')

        # Scan with filter by store_id (until GSI is created)
        response = orders_table.scan(
            FilterExpression=Attr('store_id').eq(store_id),
            Limit=500  # Scan more to ensure we get enough after filtering
        )

        orders = response.get('Items', [])

        # Sort by created_at descending and limit
        orders = sorted(orders, key=lambda x: x.get('created_at', ''), reverse=True)[:limit]
        logger.info(f"Found {len(orders)} orders for store {store_id}")

        # Format orders for frontend
        formatted_orders = []
        for order in orders:
            # Convert Decimal to float for JSON serialization
            total_amt = order.get('total_amount', 0)
            if hasattr(total_amt, '__float__'):
                total_amt = float(total_amt)

            formatted_orders.append({
                "id": order.get('id') or order.get('order_id'),
                "order_id": order.get('id') or order.get('order_id'),
                "order_number": order.get('order_number', ''),
                "store_id": order.get('store_id'),
                "customer_name": order.get('customer_name', 'Unknown'),
                "customer_phone": order.get('customer_phone', 'N/A'),
                "delivery_address": order.get('delivery_address', 'N/A'),
                "items": order.get('items', []),
                "total_amount": total_amt,
                "total": total_amt,
                "status": order.get('status', 'placed'),
                "payment_status": order.get('payment_status', 'pending'),
                "payment_method": order.get('payment_method', 'cash'),
                "created_at": order.get('created_at', ''),
                "updated_at": order.get('updated_at', '')
            })

        return {
            "success": True,
            "data": formatted_orders,
            "total": len(formatted_orders),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Failed to get orders: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get orders: {str(e)}")


@router.get("/store/{store_id}/orders")
async def get_store_orders(
    store_id: str,
    limit: int = Query(50, ge=1, le=100, description="Maximum orders to return"),
    offset: int = Query(0, ge=0, description="Number of orders to skip"),
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Get orders for a store (Store Owner Only)

    Requires authentication with store_owner token.
    Returns paginated list of orders for the specified store.
    """
    # Verify user has access to the requested store
    if current_user.get('store_id') and current_user['store_id'] != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this store's orders"
        )

    try:
        # Get orders from DynamoDB
        db_result = await db.get_orders_by_store(store_id, limit=limit, offset=offset)

        if not db_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve orders: {db_result.error}"
            )

        orders = []
        for order in db_result.data:
            orders.append({
                "id": order.order_id,
                "store_id": order.store_id,
                "customer_phone": order.customer_phone,
                "total_amount": order.total_amount,
                "status": order.status,
                "payment_method": order.payment_method,
                "created_at": order.created_at,
                "updated_at": order.updated_at
            })

        return {
            "success": True,
            "orders": orders,
            "total": len(orders),
            "limit": limit,
            "offset": offset,
            "processing_time_ms": db_result.processing_time_ms
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get orders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get orders: {str(e)}")

@router.post("/calculate-total")
async def calculate_order_total(items: List[OrderItemRequest], tax_rate: float = 0.05, delivery_fee: float = 20.0):
    """Calculate order total with tax and delivery"""
    
    try:
        subtotal = sum(item.quantity * item.unit_price for item in items)
        tax_amount = subtotal * tax_rate
        total_delivery_fee = delivery_fee if subtotal < 200 else 0
        total_amount = subtotal + tax_amount + total_delivery_fee
        
        return {
            "success": True,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "tax_rate": tax_rate,
            "delivery_fee": total_delivery_fee,
            "total_amount": total_amount,
            "breakdown": {
                "items": [item.dict() for item in items],
                "subtotal": subtotal,
                "tax": tax_amount,
                "delivery": total_delivery_fee,
                "total": total_amount
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate total: {str(e)}")
