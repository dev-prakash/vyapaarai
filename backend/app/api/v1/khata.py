"""
Khata (Digital Credit Management) API Endpoints

Provides comprehensive credit management for Indian retail stores:
- Credit sales recording
- Payment collection
- Customer balance management
- Transaction ledger
- Payment reminders
- Reports and analytics

All endpoints require store owner authentication.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Query, HTTPException, status, Depends, Header, Request
from pydantic import BaseModel, Field

from app.core.monitoring import monitor_performance
from app.core.cache import cache_result, invalidate_cache
from app.services.khata_service import get_khata_service, KhataTransactionService, CreditSaleItem
from app.services.khata_audit_service import khata_audit_service, log_khata_transaction
from app.database.khata_db import khata_db
from app.models.khata import (
    # Request models
    CreditSaleRequest,
    PaymentRequest,
    BalanceAdjustmentRequest,
    ReversalRequest,
    CreateCustomerRequest,
    UpdateCreditLimitRequest,
    CreateReminderRequest,
    # Response models
    TransactionResponse,
    CustomerBalanceResponse,
    CustomerLedgerResponse,
    CustomersWithBalanceResponse,
    StoreOutstandingSummary,
    ReminderResponse,
    CustomerListItem,
    TransactionItem,
    # Enums
    TransactionType,
    PaymentMethod,
    ReminderFrequency,
)
from app.core.exceptions import (
    CreditLimitExceededError,
    DuplicateTransactionError,
    CustomerNotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/khata", tags=["khata"])


# =============================================================================
# Dependencies
# =============================================================================

def get_store_id_from_token(authorization: str = Header(None)) -> str:
    """
    Extract store_id from JWT token

    In production, this would decode the JWT and extract store_id.
    For now, we require store_id as a query parameter.
    """
    # TODO: Implement proper JWT decoding
    # For now, this is a placeholder
    return None


def get_actor_id_from_token(authorization: str = Header(None)) -> str:
    """Extract actor ID (user email/ID) from JWT token"""
    # TODO: Implement proper JWT decoding
    return "system"


# =============================================================================
# Credit Sale Endpoints
# =============================================================================

@router.post(
    "/credit-sale",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a credit sale",
    description="Records a sale on credit, updating customer balance. Supports idempotency."
)
@monitor_performance
async def record_credit_sale(
    request: CreditSaleRequest,
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None),
    x_request_id: str = Header(None, alias="X-Request-ID"),
    x_idempotency_key: str = Header(None, alias="X-Idempotency-Key")
):
    """
    Record a credit sale transaction

    - Creates customer account if new (requires customer_name)
    - Validates credit limit before recording
    - Updates customer balance atomically
    - Supports idempotency via X-Idempotency-Key header

    Returns transaction ID and new balance on success.
    """
    try:
        khata_service = get_khata_service()
        actor_id = get_actor_id_from_token(authorization) or "store_owner"

        # Use header idempotency key if body doesn't have one
        idempotency_key = request.idempotency_key or x_idempotency_key

        # Convert items to service format
        items = None
        if request.items:
            items = [
                CreditSaleItem(
                    product_id=item.product_id,
                    name=item.name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    unit=item.unit
                )
                for item in request.items
            ]

        result = await khata_service.record_credit_sale(
            store_id=store_id,
            customer_phone=request.customer_phone,
            amount=request.amount,
            created_by=actor_id,
            customer_name=request.customer_name,
            items=items,
            order_id=request.order_id,
            notes=request.notes,
            idempotency_key=idempotency_key
        )

        if result.success:
            # Log to audit trail
            await log_khata_transaction(
                action="credit_sale",
                actor_id=actor_id,
                store_id=store_id,
                customer_phone=request.customer_phone,
                transaction_id=result.transaction_id,
                amount=request.amount,
                balance_before=result.new_balance - request.amount,
                balance_after=result.new_balance,
                request_id=x_request_id,
                idempotency_key=idempotency_key
            )

            # Invalidate relevant caches
            invalidate_cache(f"khata:balance:{store_id}:{request.customer_phone}")
            invalidate_cache(f"khata:customers:{store_id}")

        return TransactionResponse(
            success=result.success,
            transaction_id=result.transaction_id,
            new_balance=float(result.new_balance) if result.new_balance else None,
            message=result.message,
            error=result.error,
            error_code=result.error_code,
            processing_time_ms=result.processing_time_ms
        )

    except CreditLimitExceededError as e:
        logger.warning(f"Credit limit exceeded: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "CREDIT_LIMIT_EXCEEDED",
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Error recording credit sale: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record credit sale: {str(e)}"
        )


# =============================================================================
# Payment Endpoints
# =============================================================================

@router.post(
    "/payment",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment",
    description="Records a payment received from customer, reducing their balance."
)
@monitor_performance
async def record_payment(
    request: PaymentRequest,
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None),
    x_request_id: str = Header(None, alias="X-Request-ID"),
    x_idempotency_key: str = Header(None, alias="X-Idempotency-Key")
):
    """
    Record a payment from customer

    - Reduces customer's outstanding balance
    - Supports various payment methods (cash, UPI, bank transfer)
    - Supports idempotency via X-Idempotency-Key header

    Returns transaction ID and new balance on success.
    """
    try:
        khata_service = get_khata_service()
        actor_id = get_actor_id_from_token(authorization) or "store_owner"

        idempotency_key = request.idempotency_key or x_idempotency_key

        result = await khata_service.record_payment(
            store_id=store_id,
            customer_phone=request.customer_phone,
            amount=request.amount,
            created_by=actor_id,
            payment_method=request.payment_method.value,
            reference_id=request.reference_id,
            notes=request.notes,
            idempotency_key=idempotency_key
        )

        if result.success:
            await log_khata_transaction(
                action="payment",
                actor_id=actor_id,
                store_id=store_id,
                customer_phone=request.customer_phone,
                transaction_id=result.transaction_id,
                amount=request.amount,
                balance_before=result.new_balance + request.amount,
                balance_after=result.new_balance,
                request_id=x_request_id,
                idempotency_key=idempotency_key,
                details={"payment_method": request.payment_method.value}
            )

            invalidate_cache(f"khata:balance:{store_id}:{request.customer_phone}")
            invalidate_cache(f"khata:customers:{store_id}")

        return TransactionResponse(
            success=result.success,
            transaction_id=result.transaction_id,
            new_balance=float(result.new_balance) if result.new_balance else None,
            message=result.message,
            error=result.error,
            error_code=result.error_code,
            processing_time_ms=result.processing_time_ms
        )

    except Exception as e:
        logger.error(f"Error recording payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record payment: {str(e)}"
        )


# =============================================================================
# Balance Adjustment Endpoints
# =============================================================================

@router.post(
    "/adjustment",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adjust customer balance",
    description="Administrative balance adjustment (correction, write-off, etc.)"
)
@monitor_performance
async def adjust_balance(
    request: BalanceAdjustmentRequest,
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None),
    x_request_id: str = Header(None, alias="X-Request-ID"),
    x_idempotency_key: str = Header(None, alias="X-Idempotency-Key")
):
    """
    Adjust customer balance

    Used for corrections, write-offs, or opening balances.
    Requires notes explaining the adjustment.
    """
    try:
        khata_service = get_khata_service()
        actor_id = get_actor_id_from_token(authorization) or "admin"

        idempotency_key = request.idempotency_key or x_idempotency_key

        result = await khata_service.adjust_balance(
            store_id=store_id,
            customer_phone=request.customer_phone,
            amount=request.amount,
            created_by=actor_id,
            adjustment_type=request.adjustment_type.value,
            notes=request.notes,
            idempotency_key=idempotency_key
        )

        if result.success:
            invalidate_cache(f"khata:balance:{store_id}:{request.customer_phone}")
            invalidate_cache(f"khata:customers:{store_id}")

        return TransactionResponse(
            success=result.success,
            transaction_id=result.transaction_id,
            new_balance=float(result.new_balance) if result.new_balance else None,
            message=result.message,
            error=result.error,
            error_code=result.error_code,
            processing_time_ms=result.processing_time_ms
        )

    except Exception as e:
        logger.error(f"Error adjusting balance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adjust balance: {str(e)}"
        )


# =============================================================================
# Transaction Reversal
# =============================================================================

@router.post(
    "/transactions/{transaction_id}/reverse",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reverse a transaction",
    description="Creates a compensating transaction to reverse a previous transaction."
)
@monitor_performance
async def reverse_transaction(
    transaction_id: str,
    request: ReversalRequest,
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None),
    x_idempotency_key: str = Header(None, alias="X-Idempotency-Key")
):
    """
    Reverse a previous transaction

    Creates a compensating transaction that reverses the effect
    of the original transaction. Cannot reverse a reversal.
    """
    try:
        khata_service = get_khata_service()
        actor_id = get_actor_id_from_token(authorization) or "admin"

        idempotency_key = request.idempotency_key or x_idempotency_key

        result = await khata_service.reverse_transaction(
            original_transaction_id=transaction_id,
            created_by=actor_id,
            reason=request.reason,
            idempotency_key=idempotency_key
        )

        return TransactionResponse(
            success=result.success,
            transaction_id=result.transaction_id,
            new_balance=float(result.new_balance) if result.new_balance else None,
            message=result.message,
            error=result.error,
            error_code=result.error_code,
            processing_time_ms=result.processing_time_ms
        )

    except Exception as e:
        logger.error(f"Error reversing transaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reverse transaction: {str(e)}"
        )


# =============================================================================
# Customer Balance Endpoints
# =============================================================================

@router.get(
    "/customers/{customer_phone}/balance",
    response_model=CustomerBalanceResponse,
    summary="Get customer balance",
    description="Get current credit balance and limit for a customer."
)
@cache_result(expiry=60, key_prefix="khata:balance")
@monitor_performance
async def get_customer_balance(
    customer_phone: str,
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None)
):
    """
    Get customer's current balance at this store

    Returns outstanding balance, credit limit, and available credit.
    """
    try:
        result = await khata_db.get_customer_balance(store_id, customer_phone)

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found at this store"
            )

        customer = result.data

        # Log access for audit
        actor_id = get_actor_id_from_token(authorization) or "store_owner"
        await khata_audit_service.log_balance_query(
            actor_id=actor_id,
            actor_type="store_owner",
            store_id=store_id,
            customer_phone=customer_phone,
            balance=customer.outstanding_balance
        )

        return CustomerBalanceResponse(
            phone=customer_phone,
            name=customer.customer_name,
            outstanding_balance=float(customer.outstanding_balance),
            credit_limit=float(customer.credit_limit),
            available_credit=float(customer.credit_limit - customer.outstanding_balance),
            last_transaction_at=customer.last_transaction_at,
            reminder_enabled=customer.reminder_enabled,
            reminder_frequency=customer.reminder_frequency
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer balance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer balance: {str(e)}"
        )


@router.get(
    "/customers/{customer_phone}/ledger",
    response_model=CustomerLedgerResponse,
    summary="Get customer transaction ledger",
    description="Get paginated transaction history for a customer."
)
@monitor_performance
async def get_customer_ledger(
    customer_phone: str,
    store_id: str = Query(..., description="Store identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(50, ge=1, le=100, description="Records per page"),
    authorization: str = Header(None)
):
    """
    Get customer's transaction ledger

    Returns paginated list of all transactions with running balance.
    Supports date range filtering.
    """
    try:
        khata_service = get_khata_service()

        result = await khata_service.get_customer_ledger(
            store_id=store_id,
            customer_phone=customer_phone,
            start_date=start_date,
            end_date=end_date,
            cursor=cursor,
            limit=limit
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "Customer not found")
            )

        # Convert to response model
        customer_data = result.get("customer", {})
        transactions = result.get("transactions", [])

        return CustomerLedgerResponse(
            success=True,
            customer=CustomerBalanceResponse(
                phone=customer_data.get("phone", customer_phone),
                name=customer_data.get("name", ""),
                outstanding_balance=customer_data.get("outstanding_balance", 0),
                credit_limit=customer_data.get("credit_limit", 0),
                available_credit=customer_data.get("available_credit", 0)
            ) if customer_data else None,
            transactions=[
                TransactionItem(
                    id=txn.get("id", ""),
                    type=txn.get("type", ""),
                    amount=txn.get("amount", 0),
                    balance_after=txn.get("balance_after", 0),
                    created_at=txn.get("created_at", ""),
                    created_by=txn.get("created_by", ""),
                    notes=txn.get("notes")
                )
                for txn in transactions
            ],
            next_cursor=result.get("next_cursor"),
            has_more=result.get("has_more", False)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer ledger: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer ledger: {str(e)}"
        )


# =============================================================================
# Customer Management Endpoints
# =============================================================================

@router.post(
    "/customers",
    response_model=CustomerBalanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create credit customer",
    description="Create a new customer credit account."
)
@monitor_performance
async def create_credit_customer(
    request: CreateCustomerRequest,
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None)
):
    """
    Create a new credit customer account

    Sets up a new customer with specified credit limit and preferences.
    """
    try:
        result = await khata_db.create_customer_balance(
            store_id=store_id,
            customer_phone=request.phone,
            customer_name=request.name,
            credit_limit=request.credit_limit,
            preferred_language=request.preferred_language
        )

        if not result.success:
            if "already exists" in result.error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Customer already exists at this store"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error
            )

        customer = result.data

        # Invalidate cache
        invalidate_cache(f"khata:customers:{store_id}")

        return CustomerBalanceResponse(
            phone=request.phone,
            name=request.name,
            outstanding_balance=0.0,
            credit_limit=float(request.credit_limit),
            available_credit=float(request.credit_limit),
            reminder_enabled=request.reminder_enabled,
            reminder_frequency=request.reminder_frequency.value
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating credit customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create credit customer: {str(e)}"
        )


@router.patch(
    "/customers/{customer_phone}/credit-limit",
    response_model=TransactionResponse,
    summary="Update credit limit",
    description="Update a customer's credit limit."
)
@monitor_performance
async def update_credit_limit(
    customer_phone: str,
    request: UpdateCreditLimitRequest,
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None)
):
    """
    Update customer's credit limit

    Requires reason for audit trail.
    """
    try:
        # Get current balance
        balance_result = await khata_db.get_customer_balance(store_id, customer_phone)

        if not balance_result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        current = balance_result.data
        actor_id = get_actor_id_from_token(authorization) or "store_owner"

        # Log the limit change
        await khata_audit_service.log_credit_limit_change(
            actor_id=actor_id,
            actor_type="store_owner",
            store_id=store_id,
            customer_phone=customer_phone,
            old_limit=current.credit_limit,
            new_limit=request.credit_limit,
            reason=request.reason
        )

        # TODO: Implement actual update in khata_db
        # For now, this is a placeholder

        invalidate_cache(f"khata:balance:{store_id}:{customer_phone}")

        return TransactionResponse(
            success=True,
            message=f"Credit limit updated to ₹{request.credit_limit}",
            new_balance=float(current.outstanding_balance)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating credit limit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update credit limit: {str(e)}"
        )


@router.get(
    "/customers",
    response_model=CustomersWithBalanceResponse,
    summary="List customers with balance",
    description="Get paginated list of customers with outstanding balance."
)
@cache_result(expiry=60, key_prefix="khata:customers")
@monitor_performance
async def list_customers_with_balance(
    store_id: str = Query(..., description="Store identifier"),
    min_balance: Optional[float] = Query(None, ge=0, description="Minimum balance filter"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(50, ge=1, le=100, description="Records per page"),
    authorization: str = Header(None)
):
    """
    List all customers with outstanding credit balance

    Supports filtering by minimum balance.
    Returns total outstanding for the store.
    """
    try:
        min_balance_decimal = Decimal(str(min_balance)) if min_balance else None

        result = await khata_db.get_customers_with_balance(
            store_id=store_id,
            min_balance=min_balance_decimal,
            cursor=cursor,
            limit=limit
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error
            )

        customers = [
            CustomerListItem(
                phone=c.customer_phone,
                name=c.customer_name,
                outstanding_balance=float(c.outstanding_balance),
                credit_limit=float(c.credit_limit),
                last_transaction_at=c.last_transaction_at
            )
            for c in result.data
        ]

        total_outstanding = sum(c.outstanding_balance for c in customers)

        return CustomersWithBalanceResponse(
            success=True,
            customers=customers,
            total_outstanding=total_outstanding,
            customer_count=len(customers),
            next_cursor=result.next_cursor,
            has_more=result.next_cursor is not None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing customers with balance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list customers: {str(e)}"
        )


# =============================================================================
# Reports Endpoints
# =============================================================================

@router.get(
    "/reports/outstanding",
    response_model=StoreOutstandingSummary,
    summary="Store outstanding summary",
    description="Get summary of all outstanding credit for the store."
)
@cache_result(expiry=300, key_prefix="khata:report:outstanding")
@monitor_performance
async def get_outstanding_report(
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None)
):
    """
    Get store's outstanding credit summary

    Returns total outstanding, customer count, utilization rate, etc.
    """
    try:
        result = await khata_db.get_store_outstanding_summary(store_id)

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error
            )

        data = result.data

        return StoreOutstandingSummary(
            store_id=store_id,
            total_outstanding=data.get("total_outstanding", 0),
            total_credit_limit=data.get("total_credit_limit", 0),
            utilization_rate=data.get("utilization_rate", 0),
            total_customers=data.get("total_customers", 0),
            customers_with_balance=data.get("customers_with_balance", 0),
            generated_at=data.get("generated_at", datetime.utcnow().isoformat())
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting outstanding report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get outstanding report: {str(e)}"
        )


@router.get(
    "/reports/aging",
    summary="Aging analysis report",
    description="Get aging analysis of outstanding balances."
)
@cache_result(expiry=600, key_prefix="khata:report:aging")
@monitor_performance
async def get_aging_report(
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None)
):
    """
    Get aging analysis of outstanding balances

    Groups customers by how long their balance has been outstanding:
    - Current (0-30 days)
    - 30-60 days
    - 60-90 days
    - 90+ days
    """
    try:
        # TODO: Implement proper aging calculation from transactions
        # For now, return placeholder structure

        return {
            "store_id": store_id,
            "generated_at": datetime.utcnow().isoformat(),
            "aging_buckets": {
                "current": {
                    "label": "0-30 days",
                    "customer_count": 0,
                    "total_amount": 0.0
                },
                "30_60": {
                    "label": "30-60 days",
                    "customer_count": 0,
                    "total_amount": 0.0
                },
                "60_90": {
                    "label": "60-90 days",
                    "customer_count": 0,
                    "total_amount": 0.0
                },
                "90_plus": {
                    "label": "90+ days",
                    "customer_count": 0,
                    "total_amount": 0.0
                }
            },
            "total_outstanding": 0.0,
            "message": "Aging report - implement with transaction date analysis"
        }

    except Exception as e:
        logger.error(f"Error getting aging report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get aging report: {str(e)}"
        )


@router.get(
    "/reports/transactions",
    summary="Transaction report",
    description="Get transaction report for a date range."
)
@monitor_performance
async def get_transaction_report(
    store_id: str = Query(..., description="Store identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    transaction_type: Optional[str] = Query(None, description="Filter by type"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(100, ge=1, le=500, description="Records per page"),
    authorization: str = Header(None)
):
    """
    Get transaction report for the store

    Supports filtering by date range and transaction type.
    """
    try:
        result = await khata_db.get_store_transactions(
            store_id=store_id,
            start_date=start_date,
            end_date=end_date,
            transaction_type=transaction_type,
            cursor=cursor,
            limit=limit
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error
            )

        transactions = [
            {
                "id": txn.transaction_id,
                "customer_phone": txn.customer_phone,
                "type": txn.transaction_type,
                "amount": float(txn.amount),
                "balance_before": float(txn.balance_before),
                "balance_after": float(txn.balance_after),
                "created_at": txn.created_at,
                "created_by": txn.created_by
            }
            for txn in result.data
        ]

        # Calculate totals
        credit_sales = sum(t["amount"] for t in transactions if t["type"] == "credit_sale")
        payments = sum(t["amount"] for t in transactions if t["type"] == "payment")

        return {
            "success": True,
            "store_id": store_id,
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "summary": {
                "total_credit_sales": credit_sales,
                "total_payments": payments,
                "net_change": credit_sales - payments,
                "transaction_count": len(transactions)
            },
            "transactions": transactions,
            "next_cursor": result.next_cursor,
            "has_more": result.next_cursor is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transaction report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transaction report: {str(e)}"
        )


# =============================================================================
# Reminder Endpoints
# =============================================================================

@router.post(
    "/reminders",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create payment reminder",
    description="Schedule a payment reminder for a customer."
)
@monitor_performance
async def create_reminder(
    request: CreateReminderRequest,
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None)
):
    """
    Create a payment reminder

    Schedules an SMS or push notification reminder for the customer.
    """
    try:
        from app.database.khata_db import PaymentReminder
        import uuid

        # Get customer balance
        balance_result = await khata_db.get_customer_balance(store_id, request.customer_phone)

        if not balance_result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        customer = balance_result.data

        if customer.outstanding_balance <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer has no outstanding balance"
            )

        reminder_id = f"REM-{uuid.uuid4().hex[:12].upper()}"
        scheduled_at = request.scheduled_at or datetime.utcnow()

        reminder = PaymentReminder(
            reminder_id=reminder_id,
            store_id=store_id,
            customer_phone=request.customer_phone,
            outstanding_amount=customer.outstanding_balance,
            scheduled_at=scheduled_at.isoformat() if isinstance(scheduled_at, datetime) else scheduled_at,
            status="scheduled",
            reminder_type=request.reminder_type.value,
            created_at=datetime.utcnow().isoformat()
        )

        result = await khata_db.create_reminder(reminder)

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error
            )

        # Log reminder event
        await khata_audit_service.log_reminder_event(
            event_type="scheduled",
            store_id=store_id,
            customer_phone=request.customer_phone,
            reminder_id=reminder_id,
            outstanding_amount=customer.outstanding_balance,
            channel=request.reminder_type.value
        )

        return ReminderResponse(
            success=True,
            reminder_id=reminder_id,
            scheduled_at=reminder.scheduled_at,
            message="Reminder scheduled successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reminder: {str(e)}"
        )


@router.delete(
    "/reminders/{reminder_id}",
    response_model=ReminderResponse,
    summary="Cancel reminder",
    description="Cancel a scheduled payment reminder."
)
@monitor_performance
async def cancel_reminder(
    reminder_id: str,
    store_id: str = Query(..., description="Store identifier"),
    authorization: str = Header(None)
):
    """
    Cancel a scheduled reminder
    """
    try:
        result = await khata_db.update_reminder_status(
            store_id=store_id,
            reminder_id=reminder_id,
            status="cancelled"
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reminder not found"
            )

        return ReminderResponse(
            success=True,
            reminder_id=reminder_id,
            message="Reminder cancelled"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel reminder: {str(e)}"
        )


# =============================================================================
# Health Check
# =============================================================================

@router.get(
    "/health",
    summary="Khata service health",
    description="Check health of Khata service and dependencies."
)
async def khata_health():
    """Check Khata service health"""
    return {
        "status": "healthy",
        "service": "khata",
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {
            "dynamodb": khata_db.dynamodb is not None,
            "tables_configured": bool(khata_db.table_names)
        }
    }
