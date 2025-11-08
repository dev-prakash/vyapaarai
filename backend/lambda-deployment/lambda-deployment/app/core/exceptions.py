from fastapi import HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import traceback
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

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
    "INTERNAL_ERROR": 500
}

# Common error messages
COMMON_ERROR_MESSAGES = {
    "INVALID_OTP": "The OTP provided is invalid or expired",
    "RATE_LIMIT_EXCEEDED": "Too many requests. Please try again later",
    "PHONE_NOT_FOUND": "Phone number not found in our records",
    "OTP_EXPIRED": "OTP has expired. Please request a new one",
    "INVALID_PHONE_FORMAT": "Invalid phone number format",
    "DATABASE_CONNECTION_ERROR": "Database connection error",
    "EXTERNAL_API_ERROR": "External service temporarily unavailable"
}
