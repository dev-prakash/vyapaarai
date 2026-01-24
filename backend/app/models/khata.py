"""
Khata (Digital Credit Management) Pydantic Models

Request/Response models for credit management API endpoints.
Used for:
- Input validation
- Response serialization
- API documentation (OpenAPI/Swagger)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class TransactionType(str, Enum):
    """Types of Khata transactions"""
    CREDIT_SALE = "credit_sale"
    PAYMENT = "payment"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"


class PaymentMethod(str, Enum):
    """Supported payment methods"""
    CASH = "cash"
    UPI = "upi"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE = "cheque"
    OTHER = "other"


class ReminderFrequency(str, Enum):
    """Payment reminder frequency options"""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class ReminderStatus(str, Enum):
    """Status of payment reminders"""
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderType(str, Enum):
    """Type of reminder delivery"""
    SMS = "sms"
    PUSH = "push"
    BOTH = "both"


class AdjustmentType(str, Enum):
    """Types of balance adjustments"""
    CORRECTION = "correction"
    WRITE_OFF = "write_off"
    OPENING_BALANCE = "opening_balance"
    DISPUTE_RESOLUTION = "dispute_resolution"


# =============================================================================
# Request Models - Credit Sale
# =============================================================================

class CreditSaleItem(BaseModel):
    """Item in a credit sale"""
    product_id: str = Field(..., description="Product identifier")
    name: str = Field(..., description="Product name")
    quantity: int = Field(..., ge=1, description="Quantity purchased")
    unit_price: Decimal = Field(..., ge=0, description="Unit price in INR")
    unit: str = Field(default="pieces", description="Unit of measurement")

    @validator('unit_price', pre=True)
    def convert_price(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class CreditSaleRequest(BaseModel):
    """Request to record a credit sale"""
    customer_phone: str = Field(
        ...,
        regex=r'^\+?[1-9]\d{9,14}$',
        description="Customer phone number (e.g., +919876543210)"
    )
    customer_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Customer name (required for new customers)"
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Total credit sale amount in INR"
    )
    items: Optional[List[CreditSaleItem]] = Field(
        None,
        description="List of items in the sale"
    )
    order_id: Optional[str] = Field(
        None,
        description="Associated order ID if any"
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Transaction notes"
    )
    idempotency_key: Optional[str] = Field(
        None,
        max_length=64,
        description="Client-provided idempotency key"
    )

    @validator('amount', pre=True)
    def convert_amount(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}
        schema_extra = {
            "example": {
                "customer_phone": "+919876543210",
                "customer_name": "Ramesh Kumar",
                "amount": 500.00,
                "items": [
                    {
                        "product_id": "PROD-001",
                        "name": "Rice",
                        "quantity": 2,
                        "unit_price": 150.00,
                        "unit": "kg"
                    }
                ],
                "notes": "Regular credit purchase",
                "idempotency_key": "sale-2026-01-21-001"
            }
        }


# =============================================================================
# Request Models - Payment
# =============================================================================

class PaymentRequest(BaseModel):
    """Request to record a payment"""
    customer_phone: str = Field(
        ...,
        regex=r'^\+?[1-9]\d{9,14}$',
        description="Customer phone number"
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Payment amount in INR"
    )
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.CASH,
        description="Payment method"
    )
    reference_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Payment reference (receipt number, UPI ID, etc.)"
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Payment notes"
    )
    idempotency_key: Optional[str] = Field(
        None,
        max_length=64,
        description="Client-provided idempotency key"
    )

    @validator('amount', pre=True)
    def convert_amount(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}
        schema_extra = {
            "example": {
                "customer_phone": "+919876543210",
                "amount": 500.00,
                "payment_method": "cash",
                "reference_id": "RCPT-001",
                "notes": "Cash payment received",
                "idempotency_key": "pmt-2026-01-21-001"
            }
        }


# =============================================================================
# Request Models - Balance Adjustment
# =============================================================================

class BalanceAdjustmentRequest(BaseModel):
    """Request to adjust customer balance"""
    customer_phone: str = Field(
        ...,
        regex=r'^\+?[1-9]\d{9,14}$',
        description="Customer phone number"
    )
    amount: Decimal = Field(
        ...,
        description="Adjustment amount (positive to increase, negative to decrease)"
    )
    adjustment_type: AdjustmentType = Field(
        default=AdjustmentType.CORRECTION,
        description="Type of adjustment"
    )
    notes: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for adjustment (required)"
    )
    idempotency_key: Optional[str] = Field(
        None,
        max_length=64,
        description="Client-provided idempotency key"
    )

    @validator('amount', pre=True)
    def convert_amount(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}
        schema_extra = {
            "example": {
                "customer_phone": "+919876543210",
                "amount": -50.00,
                "adjustment_type": "correction",
                "notes": "Correcting entry error from 20th Jan sale",
                "idempotency_key": "adj-2026-01-21-001"
            }
        }


# =============================================================================
# Request Models - Transaction Reversal
# =============================================================================

class ReversalRequest(BaseModel):
    """Request to reverse a transaction"""
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for reversal"
    )
    idempotency_key: Optional[str] = Field(
        None,
        max_length=64,
        description="Client-provided idempotency key"
    )

    class Config:
        schema_extra = {
            "example": {
                "reason": "Customer returned items, sale cancelled",
                "idempotency_key": "rev-2026-01-21-001"
            }
        }


# =============================================================================
# Request Models - Customer Management
# =============================================================================

class CreateCustomerRequest(BaseModel):
    """Request to create a new credit customer"""
    phone: str = Field(
        ...,
        regex=r'^\+?[1-9]\d{9,14}$',
        description="Customer phone number"
    )
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Customer name"
    )
    credit_limit: Decimal = Field(
        default=Decimal("5000.00"),
        ge=0,
        le=Decimal("500000"),
        description="Credit limit in INR"
    )
    preferred_language: str = Field(
        default="hi",
        regex=r'^[a-z]{2}$',
        description="Preferred language code (ISO 639-1)"
    )
    reminder_enabled: bool = Field(
        default=True,
        description="Enable payment reminders"
    )
    reminder_frequency: ReminderFrequency = Field(
        default=ReminderFrequency.WEEKLY,
        description="Reminder frequency"
    )

    @validator('credit_limit', pre=True)
    def convert_limit(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}
        schema_extra = {
            "example": {
                "phone": "+919876543210",
                "name": "Ramesh Kumar",
                "credit_limit": 5000.00,
                "preferred_language": "hi",
                "reminder_enabled": True,
                "reminder_frequency": "weekly"
            }
        }


class UpdateCreditLimitRequest(BaseModel):
    """Request to update customer credit limit"""
    credit_limit: Decimal = Field(
        ...,
        ge=0,
        le=Decimal("500000"),
        description="New credit limit in INR"
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for limit change"
    )

    @validator('credit_limit', pre=True)
    def convert_limit(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


# =============================================================================
# Request Models - Payment Reminders
# =============================================================================

class CreateReminderRequest(BaseModel):
    """Request to create a payment reminder"""
    customer_phone: str = Field(
        ...,
        regex=r'^\+?[1-9]\d{9,14}$',
        description="Customer phone number"
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="When to send reminder (defaults to now + frequency)"
    )
    reminder_type: ReminderType = Field(
        default=ReminderType.SMS,
        description="Type of reminder"
    )

    class Config:
        schema_extra = {
            "example": {
                "customer_phone": "+919876543210",
                "scheduled_at": "2026-01-28T10:00:00Z",
                "reminder_type": "sms"
            }
        }


# =============================================================================
# Response Models - Transaction
# =============================================================================

class TransactionResponse(BaseModel):
    """Response for a transaction operation"""
    success: bool = Field(..., description="Whether operation succeeded")
    transaction_id: Optional[str] = Field(None, description="Transaction identifier")
    new_balance: Optional[float] = Field(None, description="New outstanding balance")
    message: Optional[str] = Field(None, description="Success/info message")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")
    processing_time_ms: float = Field(default=0, description="Processing time in milliseconds")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "transaction_id": "TXN-A1B2C3D4E5F6",
                "new_balance": 500.00,
                "message": "Credit sale recorded successfully",
                "processing_time_ms": 45.5
            }
        }


# =============================================================================
# Response Models - Customer Balance
# =============================================================================

class CustomerBalanceResponse(BaseModel):
    """Response for customer balance query"""
    phone: str = Field(..., description="Customer phone number")
    name: str = Field(..., description="Customer name")
    outstanding_balance: float = Field(..., description="Current outstanding balance")
    credit_limit: float = Field(..., description="Credit limit")
    available_credit: float = Field(..., description="Available credit")
    last_transaction_at: Optional[str] = Field(None, description="Last transaction timestamp")
    reminder_enabled: bool = Field(default=True, description="Reminders enabled")
    reminder_frequency: str = Field(default="weekly", description="Reminder frequency")

    class Config:
        schema_extra = {
            "example": {
                "phone": "+919876543210",
                "name": "Ramesh Kumar",
                "outstanding_balance": 1500.00,
                "credit_limit": 5000.00,
                "available_credit": 3500.00,
                "last_transaction_at": "2026-01-20T15:30:00Z",
                "reminder_enabled": True,
                "reminder_frequency": "weekly"
            }
        }


# =============================================================================
# Response Models - Transaction List
# =============================================================================

class TransactionItem(BaseModel):
    """Individual transaction in a list"""
    id: str = Field(..., description="Transaction ID")
    type: TransactionType = Field(..., description="Transaction type")
    amount: float = Field(..., description="Transaction amount")
    balance_after: float = Field(..., description="Balance after transaction")
    created_at: str = Field(..., description="Transaction timestamp")
    created_by: str = Field(..., description="User who created transaction")
    notes: Optional[str] = Field(None, description="Transaction notes")

    class Config:
        schema_extra = {
            "example": {
                "id": "TXN-A1B2C3D4E5F6",
                "type": "credit_sale",
                "amount": 500.00,
                "balance_after": 1500.00,
                "created_at": "2026-01-20T15:30:00Z",
                "created_by": "owner@store.com",
                "notes": "Regular purchase"
            }
        }


class CustomerLedgerResponse(BaseModel):
    """Response for customer ledger/transaction history"""
    success: bool = Field(..., description="Whether query succeeded")
    customer: Optional[CustomerBalanceResponse] = Field(None, description="Customer details")
    transactions: List[TransactionItem] = Field(default=[], description="Transaction list")
    next_cursor: Optional[str] = Field(None, description="Pagination cursor")
    has_more: bool = Field(default=False, description="Whether more records exist")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "customer": {
                    "phone": "+919876543210",
                    "name": "Ramesh Kumar",
                    "outstanding_balance": 1500.00,
                    "credit_limit": 5000.00,
                    "available_credit": 3500.00
                },
                "transactions": [],
                "next_cursor": None,
                "has_more": False
            }
        }


# =============================================================================
# Response Models - Customer List
# =============================================================================

class CustomerListItem(BaseModel):
    """Customer in a list"""
    phone: str
    name: str
    outstanding_balance: float
    credit_limit: float
    last_transaction_at: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "phone": "+919876543210",
                "name": "Ramesh Kumar",
                "outstanding_balance": 1500.00,
                "credit_limit": 5000.00,
                "last_transaction_at": "2026-01-20T15:30:00Z"
            }
        }


class CustomersWithBalanceResponse(BaseModel):
    """Response for customers with outstanding balance"""
    success: bool
    customers: List[CustomerListItem] = []
    total_outstanding: float = 0
    customer_count: int = 0
    next_cursor: Optional[str] = None
    has_more: bool = False

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "customers": [],
                "total_outstanding": 15000.00,
                "customer_count": 10,
                "next_cursor": None,
                "has_more": False
            }
        }


# =============================================================================
# Response Models - Store Summary
# =============================================================================

class StoreOutstandingSummary(BaseModel):
    """Summary of store's outstanding credit"""
    store_id: str
    total_outstanding: float
    total_credit_limit: float
    utilization_rate: float
    total_customers: int
    customers_with_balance: int
    generated_at: str

    class Config:
        schema_extra = {
            "example": {
                "store_id": "STORE-001",
                "total_outstanding": 75000.00,
                "total_credit_limit": 250000.00,
                "utilization_rate": 30.0,
                "total_customers": 50,
                "customers_with_balance": 25,
                "generated_at": "2026-01-21T10:00:00Z"
            }
        }


# =============================================================================
# Response Models - Payment Reminders
# =============================================================================

class ReminderResponse(BaseModel):
    """Response for reminder operations"""
    success: bool
    reminder_id: Optional[str] = None
    scheduled_at: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "reminder_id": "REM-A1B2C3",
                "scheduled_at": "2026-01-28T10:00:00Z",
                "message": "Reminder scheduled successfully"
            }
        }


class ReminderListItem(BaseModel):
    """Reminder in a list"""
    reminder_id: str
    customer_phone: str
    outstanding_amount: float
    scheduled_at: str
    status: ReminderStatus
    reminder_type: ReminderType
    sent_at: Optional[str] = None
    failure_reason: Optional[str] = None


class RemindersListResponse(BaseModel):
    """Response for reminders list"""
    success: bool
    reminders: List[ReminderListItem] = []
    next_cursor: Optional[str] = None
    has_more: bool = False


# =============================================================================
# Pagination
# =============================================================================

class PaginationParams(BaseModel):
    """Common pagination parameters"""
    cursor: Optional[str] = Field(None, description="Pagination cursor from previous response")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum records to return")


# =============================================================================
# Filters
# =============================================================================

class DateRangeFilter(BaseModel):
    """Date range filter for queries"""
    start_date: Optional[str] = Field(
        None,
        description="Start date (ISO format: YYYY-MM-DD)"
    )
    end_date: Optional[str] = Field(
        None,
        description="End date (ISO format: YYYY-MM-DD)"
    )

    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v


class TransactionFilter(DateRangeFilter):
    """Filter for transaction queries"""
    transaction_type: Optional[TransactionType] = Field(
        None,
        description="Filter by transaction type"
    )
    min_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Minimum transaction amount"
    )
    max_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Maximum transaction amount"
    )

    @validator('min_amount', 'max_amount', pre=True)
    def convert_amounts(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v
