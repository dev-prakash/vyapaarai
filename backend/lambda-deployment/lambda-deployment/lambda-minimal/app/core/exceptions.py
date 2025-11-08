"""
Custom exceptions for VyaparAI API
"""

from fastapi import HTTPException, status


class VyaparAIException(Exception):
    """Base exception for VyaparAI"""
    pass


class InvalidOTPError(VyaparAIException):
    """Raised when OTP is invalid"""
    pass


class ValidationError(VyaparAIException):
    """Raised when validation fails"""
    pass


class AuthenticationError(VyaparAIException):
    """Raised when authentication fails"""
    pass


def create_error_response(error_code: str, detail: str, status_code: int = 400):
    """Create standardized error response"""
    return HTTPException(
        status_code=status_code,
        detail={
            "error_code": error_code,
            "detail": detail
        }
    )


def handle_phone_validation_error(phone: str):
    """Handle phone validation errors"""
    return create_error_response(
        "INVALID_PHONE",
        f"Invalid phone number format: {phone}",
        status.HTTP_422_UNPROCESSABLE_ENTITY
    )


def handle_otp_validation_error(otp: str):
    """Handle OTP validation errors"""
    return create_error_response(
        "INVALID_OTP",
        f"Invalid OTP format: {otp}",
        status.HTTP_422_UNPROCESSABLE_ENTITY
    )