"""
Authentication API endpoints for VyaparAI
Simple authentication for development with JWT tokens
"""

import jwt
import random
import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, validator

from app.core.exceptions import (
    InvalidOTPError, ValidationError, AuthenticationError,
    create_error_response, handle_phone_validation_error, handle_otp_validation_error
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Development JWT secret (use environment variable in production)
JWT_SECRET = "dev_jwt_secret_key_change_in_production"
JWT_ALGORITHM = "HS256"

class LoginRequest(BaseModel):
    phone: str = Field(..., description="Phone number")
    otp: Optional[str] = Field(None, description="OTP code (optional for dev mode)")
    
    @validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in international format (e.g., +919876543210)')
        return v
    
    @validator('otp')
    def validate_otp(cls, v):
        if v is not None and not re.match(r'^\d{4,6}$', v):
            raise ValueError('OTP must be 4-6 digits')
        return v

class LoginResponse(BaseModel):
    token: str = Field(..., description="JWT token")
    store_id: str = Field(..., description="Store identifier")
    store_name: str = Field(..., description="Store name")
    user: dict = Field(..., description="User information")

class VerifyOTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number")
    otp: str = Field(..., description="OTP code")
    
    @validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in international format (e.g., +919876543210)')
        return v
    
    @validator('otp')
    def validate_otp(cls, v):
        if not re.match(r'^\d{4,6}$', v):
            raise ValueError('OTP must be 4-6 digits')
        return v

class VerifyOTPResponse(BaseModel):
    valid: bool = Field(..., description="Whether OTP is valid")
    token: Optional[str] = Field(None, description="JWT token if valid")
    message: str = Field(..., description="Response message")

class EmailPasscodeRequest(BaseModel):
    email: str = Field(..., description="Email address")
    
    @validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
            raise ValueError('Please enter a valid email address')
        return v

class EmailPasscodeResponse(BaseModel):
    success: bool = Field(..., description="Whether passcode was sent")
    message: str = Field(..., description="Response message")
    test_passcode: Optional[str] = Field(None, description="Test passcode for development")

class VerifyEmailPasscodeRequest(BaseModel):
    email: str = Field(..., description="Email address")
    passcode: str = Field(..., description="6-digit passcode")
    
    @validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
            raise ValueError('Please enter a valid email address')
        return v
    
    @validator('passcode')
    def validate_passcode(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('Passcode must be 6 digits')
        return v

class StoreVerificationRequest(BaseModel):
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    
    @validator('phone')
    def validate_phone(cls, v):
        if v and not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in international format')
        return v
    
    @validator('email')
    def validate_email(cls, v):
        if v and not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
            raise ValueError('Please enter a valid email address')
        return v

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Simple login for development - accepts any phone with OTP 1234
    """
    logger.info(f"Login attempt for phone: {request.phone}")
    
    try:
        # In dev mode, accept OTP 1234 or empty OTP
        if request.otp and request.otp != "1234":
            logger.warning(f"Invalid OTP attempt: {request.otp}")
            raise InvalidOTPError("Invalid OTP. Use 1234 for development.")
    
        # Generate JWT token
        token_data = {
            "phone": request.phone,
            "store_id": "STORE-001",
            "user_id": f"user_{request.phone}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        logger.info(f"Login successful for phone: {request.phone}")
        
        return LoginResponse(
            token=token,
            store_id="STORE-001",
            store_name="Test Kirana Store",
            user={
                "phone": request.phone,
                "name": "Store Owner",
                "role": "owner",
                "store_id": "STORE-001"
            }
        )
    except InvalidOTPError:
        raise
    except Exception as e:
        logger.error(f"Token generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authentication token"
        )

@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(request: VerifyOTPRequest):
    """
    Verify OTP - always returns true for OTP 1234 in dev mode
    """
    logger.info(f"OTP verification for phone: {request.phone}")
    
    try:
        # Validate OTP
        if request.otp != "1234":
            logger.warning(f"Invalid OTP attempt: {request.otp} for phone: {request.phone}")
            raise InvalidOTPError("The OTP provided is invalid or expired")
        
        # Generate JWT token for valid OTP
        token_data = {
            "phone": request.phone,
            "store_id": "STORE-001",
            "user_id": f"user_{request.phone}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        logger.info(f"OTP verification successful for phone: {request.phone}")
        
        return VerifyOTPResponse(
            valid=True,
            token=token,
            message="OTP verified successfully"
        )
        
    except InvalidOTPError:
        raise
    except Exception as e:
        logger.error(f"OTP verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during OTP verification"
        )

@router.post("/refresh")
async def refresh_token(token: str):
    """
    Refresh JWT token
    """
    try:
        # Decode existing token
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Create new token with extended expiry
        payload["exp"] = datetime.utcnow() + timedelta(days=7)
        payload["iat"] = datetime.utcnow()
        
        new_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        return {
            "token": new_token,
            "expires_in": 7 * 24 * 60 * 60  # 7 days in seconds
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

@router.get("/me")
async def get_current_user(token: str):
    """
    Get current user information from token
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "phone": payload.get("phone"),
            "store_id": payload.get("store_id"),
            "user_id": payload.get("user_id"),
            "role": payload.get("role")
        }
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

@router.post("/send-email-passcode", response_model=EmailPasscodeResponse)
async def send_email_passcode(request: EmailPasscodeRequest):
    """
    Send email passcode for authentication
    In development, returns a test passcode
    """
    logger.info(f"Email passcode request for: {request.email}")
    
    try:
        # In development, we'll just return a test passcode
        test_passcode = "123456"
        
        logger.info(f"Mock email passcode sent to: {request.email}")
        logger.info(f"Test passcode: {test_passcode}")
        
        return EmailPasscodeResponse(
            success=True,
            message="Email passcode sent successfully",
            test_passcode=test_passcode  # Only for development
        )
        
    except Exception as e:
        logger.error(f"Email passcode sending error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email passcode"
        )

@router.post("/verify-email-passcode")
async def verify_email_passcode(request: VerifyEmailPasscodeRequest):
    """
    Verify email passcode and return auth token
    """
    logger.info(f"Email passcode verification for: {request.email}")
    
    try:
        # In development, accept 123456 as valid passcode
        if request.passcode != "123456":
            logger.warning(f"Invalid email passcode attempt: {request.passcode}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid passcode"
            )
        
        # Generate JWT token for valid passcode
        token_data = {
            "email": request.email,
            "store_id": "STORE-001",
            "user_id": f"user_{request.email}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        logger.info(f"Email passcode verification successful for: {request.email}")
        
        return {
            "success": True,
            "message": "Email passcode verified successfully",
            "token": token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email passcode verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during passcode verification"
        )

# Utility function for other modules to verify tokens
def verify_token(token: str) -> dict:
    """Verify JWT token and return payload"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
