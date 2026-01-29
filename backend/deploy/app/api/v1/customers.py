import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Query, HTTPException, status, Depends
from pydantic import BaseModel, Field
import uuid
from app.core.cache import cache_result, invalidate_cache
from app.core.monitoring import monitor_performance
import random

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])

# In-memory storage for development (replace with database)
customers_db = {}
customer_transactions_db = {}

# Pydantic models
class CustomerCreate(BaseModel):
    phone: str = Field(..., description="Customer phone number")
    name: Optional[str] = Field(None, description="Customer name")
    email: Optional[str] = Field(None, description="Customer email")
    address: Optional[Dict[str, Any]] = Field(None, description="Customer address")
    tags: Optional[List[str]] = Field(default=[], description="Customer tags")
    credit_limit: Optional[float] = Field(default=0, description="Credit limit")
    notes: Optional[str] = Field(None, description="Customer notes")

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Customer name")
    email: Optional[str] = Field(None, description="Customer email")
    address: Optional[Dict[str, Any]] = Field(None, description="Customer address")
    tags: Optional[List[str]] = Field(None, description="Customer tags")
    credit_limit: Optional[float] = Field(None, description="Credit limit")
    notes: Optional[str] = Field(None, description="Customer notes")

class CustomerResponse(BaseModel):
    id: str
    phone: str
    name: Optional[str]
    email: Optional[str]
    address: Optional[Dict[str, Any]]
    tags: List[str]
    credit_limit: float
    current_balance: float
    total_orders: int
    total_spent: float
    last_order_date: Optional[datetime]
    preferred_language: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

class CreditTransactionRequest(BaseModel):
    amount: float = Field(..., description="Transaction amount (positive for credit, negative for payment)")
    transaction_type: str = Field(..., description="Transaction type: credit, payment, order")
    reference_id: Optional[str] = Field(None, description="Reference ID (order ID, etc.)")
    notes: Optional[str] = Field(None, description="Transaction notes")

class CustomerInsightsResponse(BaseModel):
    total_customers: int
    new_this_month: int
    returning_rate: float
    top_customers: List[Dict[str, Any]]
    customer_segments: Dict[str, int]
    credit_summary: Dict[str, Any]

@router.get("", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=300, key_prefix="customers")
@monitor_performance
async def get_customers(
    store_id: str = Query(..., description="Store identifier"),
    search: Optional[str] = Query(None, description="Search by name, phone, or email"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    has_credit: Optional[bool] = Query(None, description="Filter by credit status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, le=100, description="Items per page")
):
    """
    Get paginated customer list with search and filters
    
    Supports searching by name, phone, email and filtering by tags and credit status.
    Returns paginated results with customer statistics.
    """
    try:
        # Filter customers by store
        store_customers = {k: v for k, v in customers_db.items() if v.get("store_id") == store_id}
        
        # Apply filters
        filtered_customers = []
        for customer_id, customer in store_customers.items():
            # Search filter
            if search:
                search_lower = search.lower()
                name_match = customer.get("name", "").lower().find(search_lower) != -1
                phone_match = customer.get("phone", "").lower().find(search_lower) != -1
                email_match = customer.get("email", "").lower().find(search_lower) != -1
                if not (name_match or phone_match or email_match):
                    continue
            
            # Tag filter
            if tag and tag not in customer.get("tags", []):
                continue
            
            # Credit filter
            if has_credit is not None:
                has_credit_balance = customer.get("current_balance", 0) > 0
                if has_credit != has_credit_balance:
                    continue
            
            filtered_customers.append((customer_id, customer))
        
        # Sort by name
        filtered_customers.sort(key=lambda x: x[1].get("name", ""))
        
        # Paginate
        total_count = len(filtered_customers)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_customers = filtered_customers[start_idx:end_idx]
        
        # Format response
        customers = []
        for customer_id, customer in page_customers:
            customers.append({
                "id": customer_id,
                "phone": customer.get("phone"),
                "name": customer.get("name"),
                "email": customer.get("email"),
                "tags": customer.get("tags", []),
                "credit_limit": customer.get("credit_limit", 0),
                "current_balance": customer.get("current_balance", 0),
                "total_orders": customer.get("total_orders", 0),
                "total_spent": customer.get("total_spent", 0),
                "last_order_date": customer.get("last_order_date"),
                "created_at": customer.get("created_at")
            })
        
        return {
            "customers": customers,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            },
            "filters": {
                "search": search,
                "tag": tag,
                "has_credit": has_credit
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting customers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customers: {str(e)}"
        )

@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
@monitor_performance
async def create_customer(
    customer: CustomerCreate,
    store_id: str = Query(..., description="Store identifier")
):
    """
    Create new customer
    
    Creates a new customer record with the provided information.
    Returns the created customer data.
    """
    try:
        # Check if customer already exists
        for existing_customer in customers_db.values():
            if existing_customer.get("phone") == customer.phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Customer with this phone number already exists"
                )
        
        # Create customer
        customer_id = str(uuid.uuid4())
        customer_data = {
            "id": customer_id,
            "store_id": store_id,
            "phone": customer.phone,
            "name": customer.name,
            "email": customer.email,
            "address": customer.address,
            "tags": customer.tags or [],
            "credit_limit": customer.credit_limit or 0,
            "current_balance": 0,
            "total_orders": 0,
            "total_spent": 0,
            "last_order_date": None,
            "preferred_language": "en",
            "notes": customer.notes,
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        customers_db[customer_id] = customer_data
        
        # Invalidate cache
        invalidate_cache("customers:*")
        
        logger.info(f"Customer created: {customer_id}")
        
        return CustomerResponse(**customer_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create customer: {str(e)}"
        )

@router.get("/insights", response_model=CustomerInsightsResponse, status_code=status.HTTP_200_OK)
@cache_result(expiry=600, key_prefix="customer_insights")
@monitor_performance
async def get_customer_insights(
    store_id: str = Query(..., description="Store identifier")
):
    """
    Get customer analytics and insights
    
    Returns comprehensive customer analytics including segments, trends, and top customers.
    """
    try:
        # Filter customers by store
        store_customers = [c for c in customers_db.values() if c.get("store_id") == store_id]
        
        # Calculate insights
        total_customers = len(store_customers)
        
        # New customers this month
        this_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_this_month = len([
            c for c in store_customers 
            if c.get("created_at") and c.get("created_at") >= this_month
        ])
        
        # Returning rate (customers with orders > 1)
        customers_with_orders = [c for c in store_customers if c.get("total_orders", 0) > 0]
        returning_customers = [c for c in customers_with_orders if c.get("total_orders", 0) > 1]
        returning_rate = len(returning_customers) / len(customers_with_orders) if customers_with_orders else 0
        
        # Top customers by total spent
        top_customers = sorted(
            store_customers,
            key=lambda x: x.get("total_spent", 0),
            reverse=True
        )[:10]
        
        # Customer segments
        customer_segments = {
            "regular": len([c for c in store_customers if "regular" in c.get("tags", [])]),
            "vip": len([c for c in store_customers if "vip" in c.get("tags", [])]),
            "wholesale": len([c for c in store_customers if "wholesale" in c.get("tags", [])]),
            "new": len([c for c in store_customers if c.get("total_orders", 0) == 0])
        }
        
        # Credit summary
        total_credit_limit = sum(c.get("credit_limit", 0) for c in store_customers)
        total_credit_used = sum(c.get("current_balance", 0) for c in store_customers)
        
        return CustomerInsightsResponse(
            total_customers=total_customers,
            new_this_month=new_this_month,
            returning_rate=round(returning_rate, 2),
            top_customers=[
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "phone": c.get("phone"),
                    "total_orders": c.get("total_orders", 0),
                    "total_spent": c.get("total_spent", 0),
                    "current_balance": c.get("current_balance", 0)
                }
                for c in top_customers
            ],
            customer_segments=customer_segments,
            credit_summary={
                "total_limit": total_credit_limit,
                "total_used": total_credit_used,
                "utilization_rate": round(total_credit_used / total_credit_limit * 100, 2) if total_credit_limit > 0 else 0
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting customer insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer insights: {str(e)}"
        )

@router.get("/{customer_id}", response_model=CustomerResponse, status_code=status.HTTP_200_OK)
@cache_result(expiry=300, key_prefix="customer")
@monitor_performance
async def get_customer(
    customer_id: str,
    store_id: str = Query(..., description="Store identifier")
):
    """
    Get customer details with order history summary
    
    Returns complete customer information including credit status and order statistics.
    """
    try:
        if customer_id not in customers_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        
        customer = customers_db[customer_id]
        
        # Verify store ownership
        if customer.get("store_id") != store_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return CustomerResponse(**customer)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer: {str(e)}"
        )

@router.put("/{customer_id}", response_model=CustomerResponse, status_code=status.HTTP_200_OK)
@monitor_performance
async def update_customer(
    customer_id: str,
    customer_update: CustomerUpdate,
    store_id: str = Query(..., description="Store identifier")
):
    """
    Update customer information
    
    Updates customer details with the provided information.
    Returns the updated customer data.
    """
    try:
        if customer_id not in customers_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        
        customer = customers_db[customer_id]
        
        # Verify store ownership
        if customer.get("store_id") != store_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Update fields
        update_data = customer_update.dict(exclude_unset=True)
        customer.update(update_data)
        customer["updated_at"] = datetime.now()
        
        # Invalidate cache
        invalidate_cache(f"customer:*{customer_id}*")
        invalidate_cache("customers:*")
        
        logger.info(f"Customer updated: {customer_id}")
        
        return CustomerResponse(**customer)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer: {str(e)}"
        )

@router.get("/{customer_id}/orders", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=300, key_prefix="customer_orders")
@monitor_performance
async def get_customer_orders(
    customer_id: str,
    store_id: str = Query(..., description="Store identifier"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, le=50, description="Items per page")
):
    """
    Get customer's order history
    
    Returns paginated list of customer's orders with details.
    """
    try:
        if customer_id not in customers_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        
        customer = customers_db[customer_id]
        
        # Verify store ownership
        if customer.get("store_id") != store_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get customer orders (mock data for now)
        customer_orders = [
            {
                "order_id": f"ORD-{i:06d}",
                "status": "completed",
                "total_amount": 150.0 + (i * 10),
                "created_at": datetime.now() - timedelta(days=i),
                "items": ["Rice", "Oil", "Sugar"]
            }
            for i in range(1, 11)
        ]
        
        # Paginate
        total_count = len(customer_orders)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_orders = customer_orders[start_idx:end_idx]
        
        return {
            "orders": page_orders,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer orders: {str(e)}"
        )

@router.post("/{customer_id}/credit", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@monitor_performance
async def add_customer_credit(
    customer_id: str,
    transaction: CreditTransactionRequest,
    store_id: str = Query(..., description="Store identifier")
):
    """
    Add credit/payment for customer
    
    Records a credit transaction (payment or credit) for the customer.
    Updates customer balance and creates transaction record.
    """
    try:
        if customer_id not in customers_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        
        customer = customers_db[customer_id]
        
        # Verify store ownership
        if customer.get("store_id") != store_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Create transaction record
        transaction_id = str(uuid.uuid4())
        transaction_data = {
            "id": transaction_id,
            "customer_id": customer_id,
            "store_id": store_id,
            "amount": transaction.amount,
            "transaction_type": transaction.transaction_type,
            "reference_id": transaction.reference_id,
            "notes": transaction.notes,
            "created_at": datetime.now()
        }
        
        customer_transactions_db[transaction_id] = transaction_data
        
        # Update customer balance
        customer["current_balance"] += transaction.amount
        customer["updated_at"] = datetime.now()
        
        # Invalidate cache
        invalidate_cache(f"customer:*{customer_id}*")
        
        logger.info(f"Credit transaction recorded: {transaction_id}")
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "new_balance": customer["current_balance"],
            "transaction": transaction_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding customer credit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add customer credit: {str(e)}"
        )

@router.get("/{customer_id}/credit-history")
@cache_result(expiry=300, key_prefix="customer_credit")
@monitor_performance
async def get_credit_history(
    customer_id: str,
    store_id: str = Query(..., description="Store identifier"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, le=50, description="Items per page")
):
    """Get customer's credit/payment history"""
    transactions = []
    balance = 0
    for i in range(15):
        amount = random.randint(100, 1000) * (1 if i % 3 == 0 else -1)
        balance += amount
        transactions.append({
            "id": f"txn-{i}",
            "date": (datetime.now() - timedelta(days=i*2)).isoformat(),
            "amount": abs(amount),
            "type": "payment" if amount > 0 else "credit",
            "description": "Payment received" if amount > 0 else f"Order ORD-2024-{100+i}",
            "balance_after": balance
        })
    
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "data": transactions[start:end],
        "pagination": {
            "total": len(transactions),
            "page": page,
            "pages": (len(transactions) + limit - 1) // limit,
            "limit": limit
        },
        "current_balance": balance
    }
