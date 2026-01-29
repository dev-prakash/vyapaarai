"""
Centralized Exception Handling for VyaparAI

This module provides:
- Custom exception classes for different error types
- Standardized error response format
- Exception handlers for FastAPI
- Utility functions for raising common exceptions
"""

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import traceback
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    # Base exception
    "VyaparAIException",
    # Authentication/Authorization
    "AuthenticationError",
    "AuthorizationError",
    "InvalidOTPError",
    # Rate limiting
    "RateLimitError",
    # Validation
    "ValidationError",
    # Resources
    "NotFoundError",
    "DatabaseError",
    "ExternalServiceError",
    "ConfigurationError",
    # Order-related
    "OrderError",
    "OrderNotFoundError",
    "OrderValidationError",
    "InsufficientStockError",
    # Inventory-related
    "InventoryError",
    "ProductNotFoundError",
    # Store-related
    "StoreError",
    "StoreNotFoundError",
    "StoreInactiveError",
    # Payment-related
    "PaymentError",
    "PaymentFailedError",
    # Customer-related
    "CustomerError",
    "CustomerNotFoundError",
    # Khata (Credit Management) exceptions
    "CreditLimitExceededError",
    "DuplicateTransactionError",
    "ReminderDeliveryError",
    "InvalidPaymentAmountError",
    "TransactionRollbackError",
    # Response helpers
    "create_error_response",
    "vyaparai_exception_handler",
    # Validation helpers
    "handle_validation_error",
    "handle_phone_validation_error",
    "handle_otp_validation_error",
    # Utility raise functions
    "raise_not_found",
    "raise_unauthorized",
    "raise_forbidden",
    "raise_validation_error",
    "raise_rate_limit_error",
    "raise_database_error",
    "raise_external_service_error",
    # Constants
    "ERROR_CODE_MAPPINGS",
    "COMMON_ERROR_MESSAGES",
]

class VyaparAIException(Exception):
    """Base exception for VyaparAI application"""
    
    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR", details: Dict[str, Any] = None, status_code: int = 500):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

class AuthenticationError(VyaparAIException):
    """Authentication related errors"""
    
    def __init__(self, message: str = "Authentication failed", details: Dict[str, Any] = None):
        super().__init__(message, "AUTH_ERROR", details, 401)

class InvalidOTPError(VyaparAIException):
    """Invalid OTP error"""
    
    def __init__(self, message: str = "Invalid or expired OTP", details: Dict[str, Any] = None):
        super().__init__(message, "INVALID_OTP", details, 400)

class RateLimitError(VyaparAIException):
    """Rate limiting error"""
    
    def __init__(self, message: str = "Rate limit exceeded", details: Dict[str, Any] = None):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", details, 429)

class ValidationError(VyaparAIException):
    """Data validation error"""
    
    def __init__(self, message: str = "Validation failed", details: Dict[str, Any] = None):
        super().__init__(message, "VALIDATION_ERROR", details, 400)

class NotFoundError(VyaparAIException):
    """Resource not found error"""
    
    def __init__(self, message: str = "Resource not found", details: Dict[str, Any] = None):
        super().__init__(message, "NOT_FOUND", details, 404)

class DatabaseError(VyaparAIException):
    """Database operation error"""
    
    def __init__(self, message: str = "Database operation failed", details: Dict[str, Any] = None):
        super().__init__(message, "DATABASE_ERROR", details, 500)

class ExternalServiceError(VyaparAIException):
    """External service error"""
    
    def __init__(self, message: str = "External service error", details: Dict[str, Any] = None):
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details, 502)

def create_error_response(error: VyaparAIException, status_code: Optional[int] = None) -> JSONResponse:
    """Create standardized error response"""
    
    if status_code is None:
        status_code = error.status_code
    
    error_response = {
        "success": False,
        "error": {
            "code": error.error_code,
            "message": error.message,
            "details": error.details
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Log the error
    logger.error(f"VyaparAI Error: {error.error_code} - {error.message}", extra={
        "error_code": error.error_code,
        "status_code": status_code,
        "details": error.details
    })
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )

async def vyaparai_exception_handler(request, exc: VyaparAIException) -> JSONResponse:
    """Global exception handler for VyaparAI exceptions"""
    
    logger.error(f"VyaparAI Exception: {exc.error_code} - {exc.message}")
    
    return create_error_response(exc)

def handle_validation_error(field: str, message: str, value: Any = None) -> ValidationError:
    """Create a validation error for a specific field"""
    details = {
        "field": field,
        "value": value,
        "constraint": message
    }
    return ValidationError(f"Validation failed for field '{field}': {message}", details)

def handle_phone_validation_error(phone: str) -> ValidationError:
    """Create a phone number validation error"""
    details = {
        "field": "phone",
        "value": phone,
        "constraint": "Phone number must be in international format (e.g., +919876543210)"
    }
    return ValidationError("Invalid phone number format", details)

def handle_otp_validation_error(otp: str) -> ValidationError:
    """Create an OTP validation error"""
    details = {
        "field": "otp",
        "value": otp,
        "constraint": "OTP must be 4-6 digits"
    }
    return ValidationError("Invalid OTP format", details)

# Error code mappings for consistent handling
ERROR_CODE_MAPPINGS = {
    "AUTH_ERROR": 401,
    "INVALID_OTP": 400,
    "RATE_LIMIT_EXCEEDED": 429,
    "VALIDATION_ERROR": 400,
    "NOT_FOUND": 404,
    "DATABASE_ERROR": 500,
    "EXTERNAL_SERVICE_ERROR": 502,
    "INTERNAL_ERROR": 500,
    # Khata (Credit Management) error codes
    "CREDIT_LIMIT_EXCEEDED": 400,
    "DUPLICATE_TRANSACTION": 409,
    "REMINDER_DELIVERY_FAILED": 502,
    "INVALID_PAYMENT_AMOUNT": 400,
    "TRANSACTION_ROLLBACK_FAILED": 500,
}

# Common error messages
COMMON_ERROR_MESSAGES = {
    "INVALID_OTP": "The OTP provided is invalid or expired",
    "RATE_LIMIT_EXCEEDED": "Too many requests. Please try again later",
    "PHONE_NOT_FOUND": "Phone number not found in our records",
    "OTP_EXPIRED": "OTP has expired. Please request a new one",
    "INVALID_PHONE_FORMAT": "Invalid phone number format",
    "DATABASE_CONNECTION_ERROR": "Database connection error",
    "EXTERNAL_API_ERROR": "External service temporarily unavailable",
    # Khata (Credit Management) messages
    "CREDIT_LIMIT_EXCEEDED": "Customer has exceeded their credit limit",
    "DUPLICATE_TRANSACTION": "This transaction has already been processed",
    "REMINDER_DELIVERY_FAILED": "Failed to send payment reminder",
    "INVALID_PAYMENT_AMOUNT": "The payment amount is invalid",
    "TRANSACTION_ROLLBACK_FAILED": "Critical: Transaction rollback failed - manual intervention required",
}


# =============================================================================
# Additional Exception Classes for Comprehensive Error Handling
# =============================================================================

class AuthorizationError(VyaparAIException):
    """Authorization/permission related errors"""

    def __init__(self, message: str = "Access denied", details: Dict[str, Any] = None):
        super().__init__(message, "AUTHZ_ERROR", details, 403)


class OrderError(VyaparAIException):
    """Order-related errors"""

    def __init__(self, message: str = "Order operation failed", error_code: str = "ORDER_ERROR",
                 details: Dict[str, Any] = None, status_code: int = 400):
        super().__init__(message, error_code, details, status_code)


class OrderNotFoundError(OrderError):
    """Order not found error"""

    def __init__(self, order_id: str, details: Dict[str, Any] = None):
        super().__init__(
            f"Order '{order_id}' not found",
            "ORDER_NOT_FOUND",
            {**(details or {}), "order_id": order_id},
            404
        )


class OrderValidationError(OrderError):
    """Order validation error"""

    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, "ORDER_VALIDATION_ERROR", details, 400)


class InsufficientStockError(OrderError):
    """Insufficient stock for order"""

    def __init__(self, product_id: str, requested: int, available: int, details: Dict[str, Any] = None):
        super().__init__(
            f"Insufficient stock for product '{product_id}': requested {requested}, available {available}",
            "INSUFFICIENT_STOCK",
            {**(details or {}), "product_id": product_id, "requested": requested, "available": available},
            400
        )


class InventoryError(VyaparAIException):
    """Inventory-related errors"""

    def __init__(self, message: str = "Inventory operation failed", error_code: str = "INVENTORY_ERROR",
                 details: Dict[str, Any] = None, status_code: int = 400):
        super().__init__(message, error_code, details, status_code)


class ProductNotFoundError(InventoryError):
    """Product not found in inventory"""

    def __init__(self, product_id: str, store_id: str = None, details: Dict[str, Any] = None):
        detail_info = {**(details or {}), "product_id": product_id}
        if store_id:
            detail_info["store_id"] = store_id
        super().__init__(
            f"Product '{product_id}' not found",
            "PRODUCT_NOT_FOUND",
            detail_info,
            404
        )


class StoreError(VyaparAIException):
    """Store-related errors"""

    def __init__(self, message: str = "Store operation failed", error_code: str = "STORE_ERROR",
                 details: Dict[str, Any] = None, status_code: int = 400):
        super().__init__(message, error_code, details, status_code)


class StoreNotFoundError(StoreError):
    """Store not found error"""

    def __init__(self, store_id: str, details: Dict[str, Any] = None):
        super().__init__(
            f"Store '{store_id}' not found",
            "STORE_NOT_FOUND",
            {**(details or {}), "store_id": store_id},
            404
        )


class StoreInactiveError(StoreError):
    """Store is inactive error"""

    def __init__(self, store_id: str, details: Dict[str, Any] = None):
        super().__init__(
            f"Store '{store_id}' is currently inactive",
            "STORE_INACTIVE",
            {**(details or {}), "store_id": store_id},
            403
        )


class PaymentError(VyaparAIException):
    """Payment-related errors"""

    def __init__(self, message: str = "Payment operation failed", error_code: str = "PAYMENT_ERROR",
                 details: Dict[str, Any] = None, status_code: int = 400):
        super().__init__(message, error_code, details, status_code)


class PaymentFailedError(PaymentError):
    """Payment processing failed"""

    def __init__(self, reason: str, transaction_id: str = None, details: Dict[str, Any] = None):
        detail_info = {**(details or {}), "reason": reason}
        if transaction_id:
            detail_info["transaction_id"] = transaction_id
        super().__init__(
            f"Payment failed: {reason}",
            "PAYMENT_FAILED",
            detail_info,
            400
        )


class CustomerError(VyaparAIException):
    """Customer-related errors"""

    def __init__(self, message: str = "Customer operation failed", error_code: str = "CUSTOMER_ERROR",
                 details: Dict[str, Any] = None, status_code: int = 400):
        super().__init__(message, error_code, details, status_code)


class CustomerNotFoundError(CustomerError):
    """Customer not found error"""

    def __init__(self, identifier: str, details: Dict[str, Any] = None):
        super().__init__(
            f"Customer '{identifier}' not found",
            "CUSTOMER_NOT_FOUND",
            {**(details or {}), "identifier": identifier},
            404
        )


# =============================================================================
# Khata (Digital Credit Management) Exceptions
# =============================================================================

class CreditLimitExceededError(CustomerError):
    """Customer has exceeded their credit limit"""

    def __init__(self, customer_id: str, credit_limit: float, current_balance: float,
                 requested_amount: float, details: Dict[str, Any] = None):
        available_credit = max(0, credit_limit - current_balance)
        super().__init__(
            f"Credit limit exceeded for customer '{customer_id}'. "
            f"Available credit: ₹{available_credit:.2f}, Requested: ₹{requested_amount:.2f}",
            "CREDIT_LIMIT_EXCEEDED",
            {
                **(details or {}),
                "customer_id": customer_id,
                "credit_limit": credit_limit,
                "current_balance": current_balance,
                "requested_amount": requested_amount,
                "available_credit": available_credit
            },
            400
        )


class DuplicateTransactionError(VyaparAIException):
    """Idempotency key has already been used for a transaction"""

    def __init__(self, idempotency_key: str, original_transaction_id: str = None,
                 details: Dict[str, Any] = None):
        detail_info = {**(details or {}), "idempotency_key": idempotency_key}
        if original_transaction_id:
            detail_info["original_transaction_id"] = original_transaction_id
        super().__init__(
            f"Transaction with idempotency key '{idempotency_key}' has already been processed",
            "DUPLICATE_TRANSACTION",
            detail_info,
            409
        )


class ReminderDeliveryError(VyaparAIException):
    """SMS/notification reminder failed to deliver"""

    def __init__(self, customer_id: str, reminder_type: str, reason: str,
                 details: Dict[str, Any] = None):
        super().__init__(
            f"Failed to deliver {reminder_type} reminder to customer '{customer_id}': {reason}",
            "REMINDER_DELIVERY_FAILED",
            {
                **(details or {}),
                "customer_id": customer_id,
                "reminder_type": reminder_type,
                "reason": reason
            },
            502
        )


class InvalidPaymentAmountError(PaymentError):
    """Payment amount is invalid (exceeds balance, negative, etc.)"""

    def __init__(self, customer_id: str, payment_amount: float, outstanding_balance: float,
                 reason: str = None, details: Dict[str, Any] = None):
        if reason is None:
            if payment_amount <= 0:
                reason = "Payment amount must be positive"
            elif payment_amount > outstanding_balance:
                reason = f"Payment amount (₹{payment_amount:.2f}) exceeds outstanding balance (₹{outstanding_balance:.2f})"
            else:
                reason = "Invalid payment amount"
        super().__init__(
            f"Invalid payment for customer '{customer_id}': {reason}",
            "INVALID_PAYMENT_AMOUNT",
            {
                **(details or {}),
                "customer_id": customer_id,
                "payment_amount": payment_amount,
                "outstanding_balance": outstanding_balance,
                "reason": reason
            },
            400
        )


class TransactionRollbackError(VyaparAIException):
    """
    CRITICAL: Compensating transaction failed during Saga rollback.

    This error indicates a potentially inconsistent state that requires
    immediate manual intervention. Should trigger alerts to operations team.
    """

    def __init__(self, original_transaction_id: str, rollback_reason: str,
                 rollback_error: str, details: Dict[str, Any] = None):
        # Log as CRITICAL - this requires immediate attention
        logger.critical(
            f"TRANSACTION ROLLBACK FAILED - INCONSISTENT STATE POSSIBLE. "
            f"Transaction: {original_transaction_id}, Reason: {rollback_reason}, "
            f"Rollback Error: {rollback_error}"
        )
        super().__init__(
            f"Critical: Failed to rollback transaction '{original_transaction_id}'. "
            f"Manual intervention required. Rollback error: {rollback_error}",
            "TRANSACTION_ROLLBACK_FAILED",
            {
                **(details or {}),
                "original_transaction_id": original_transaction_id,
                "rollback_reason": rollback_reason,
                "rollback_error": rollback_error,
                "severity": "CRITICAL",
                "requires_manual_intervention": True
            },
            500
        )


class ConfigurationError(VyaparAIException):
    """Configuration/setup error"""

    def __init__(self, message: str = "Configuration error", details: Dict[str, Any] = None):
        super().__init__(message, "CONFIG_ERROR", details, 500)


# =============================================================================
# Utility Functions for Exception Handling
# =============================================================================

def raise_not_found(resource_type: str, identifier: str) -> None:
    """Raise a NotFoundError for a specific resource type"""
    raise NotFoundError(
        f"{resource_type} with identifier '{identifier}' not found",
        {"resource_type": resource_type, "identifier": identifier}
    )


def raise_unauthorized(message: str = "Authentication required") -> None:
    """Raise an AuthenticationError"""
    raise AuthenticationError(message)


def raise_forbidden(message: str = "Access denied", resource: str = None) -> None:
    """Raise an AuthorizationError"""
    details = {"resource": resource} if resource else None
    raise AuthorizationError(message, details)


def raise_validation_error(field: str, message: str, value: Any = None) -> None:
    """Raise a ValidationError for a specific field"""
    raise handle_validation_error(field, message, value)


def raise_rate_limit_error(limit_type: str = "general", retry_after: int = None) -> None:
    """Raise a RateLimitError with optional retry information"""
    details = {"limit_type": limit_type}
    if retry_after:
        details["retry_after_seconds"] = retry_after
    raise RateLimitError("Rate limit exceeded. Please try again later.", details)


def raise_database_error(operation: str, table: str = None, original_error: Exception = None) -> None:
    """Raise a DatabaseError with context"""
    details = {"operation": operation}
    if table:
        details["table"] = table
    if original_error:
        details["original_error"] = str(original_error)
    raise DatabaseError(f"Database operation '{operation}' failed", details)


def raise_external_service_error(service: str, operation: str, original_error: Exception = None) -> None:
    """Raise an ExternalServiceError with context"""
    details = {"service": service, "operation": operation}
    if original_error:
        details["original_error"] = str(original_error)
    raise ExternalServiceError(f"External service '{service}' failed during '{operation}'", details)
