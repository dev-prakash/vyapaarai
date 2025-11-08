"""
Authentication API endpoints for VyaparAI
Simple authentication for development with JWT tokens
"""

import jwt
import random
import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, validator

from app.core.exceptions import (
    InvalidOTPError, ValidationError, AuthenticationError,
    create_error_response, handle_phone_validation_error, handle_otp_validation_error
)
from app.services.email_service import send_passcode_email

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Development JWT secret (use environment variable in production)
JWT_SECRET = "dev_jwt_secret_key_change_in_production"
JWT_ALGORITHM = "HS256"

# In-memory storage for email passcodes (use Redis/DynamoDB in production)
email_passcodes: Dict[str, dict] = {}

# Store owner email whitelist (use database in production)
STORE_OWNER_EMAILS = [
    "owner@vyaparai.com",
    "admin@vyaparai.com",
    "test@vyaparai.com",
    "prakashsukumar@gmail.com",
    "devprakashsen@gmail.com"
]

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

class SendOTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number")
    
    @validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in international format (e.g., +919876543210)')
        return v

class SendOTPResponse(BaseModel):
    success: bool = Field(..., description="Whether OTP was sent")
    message: str = Field(..., description="Response message")
    otp: Optional[str] = Field(None, description="Test OTP for development")

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

@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(request: SendOTPRequest):
    """
    Send OTP to phone number for development
    """
    logger.info(f"Send OTP request for phone: {request.phone}")
    
    try:
        # In development mode, we'll just return a test OTP
        test_otp = "1234"
        
        logger.info(f"Mock OTP sent to: {request.phone}")
        logger.info(f"Test OTP: {test_otp}")
        
        return SendOTPResponse(
            success=True,
            message="OTP sent successfully",
            otp=test_otp  # Only for development
        )
        
    except Exception as e:
        logger.error(f"Send OTP error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )

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
    - Generates a random 6-digit passcode
    - Stores it with 15-minute expiry
    - Single-use only
    """
    logger.info(f"Email passcode request for: {request.email}")
    
    try:
        # Check if email is registered (whitelist for now)
        if request.email.lower() not in [e.lower() for e in STORE_OWNER_EMAILS]:
            logger.warning(f"Unregistered email attempt: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email not registered. Please contact support to register your store."
            )
        
        # Generate random 6-digit passcode
        passcode = str(random.randint(100000, 999999))
        
        # Store passcode with metadata
        email_passcodes[request.email.lower()] = {
            "passcode": passcode,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=15),
            "used": False,
            "attempts": 0
        }
        
        logger.info(f"Generated passcode for {request.email}: {passcode}")
        
        # Send email with passcode (async but we don't wait)
        import asyncio
        asyncio.create_task(send_passcode_email(request.email, passcode))
        
        # For development, return the passcode
        return EmailPasscodeResponse(
            success=True,
            message="A 6-digit passcode has been sent to your email. It will expire in 15 minutes.",
            test_passcode=passcode  # Only for development
        )
        
    except HTTPException:
        raise
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
    - Validates passcode exists and hasn't expired
    - Ensures single-use only
    - Limits attempts to 3
    """
    logger.info(f"Email passcode verification for: {request.email}")
    
    try:
        email_lower = request.email.lower()
        
        # Check if passcode exists for this email
        if email_lower not in email_passcodes:
            logger.warning(f"No passcode found for email: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No passcode found. Please request a new one."
            )
        
        passcode_data = email_passcodes[email_lower]
        
        # Check if passcode has been used
        if passcode_data["used"]:
            logger.warning(f"Attempted to reuse passcode for: {request.email}")
            del email_passcodes[email_lower]  # Clean up used passcode
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This passcode has already been used. Please request a new one."
            )
        
        # Check if passcode has expired
        if datetime.utcnow() > passcode_data["expires_at"]:
            logger.warning(f"Expired passcode attempt for: {request.email}")
            del email_passcodes[email_lower]  # Clean up expired passcode
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This passcode has expired. Please request a new one."
            )
        
        # Increment attempt counter
        passcode_data["attempts"] += 1
        
        # Check if too many attempts
        if passcode_data["attempts"] > 3:
            logger.warning(f"Too many passcode attempts for: {request.email}")
            del email_passcodes[email_lower]  # Clean up after too many attempts
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many incorrect attempts. Please request a new passcode."
            )
        
        # Verify the passcode
        if request.passcode != passcode_data["passcode"]:
            logger.warning(f"Invalid passcode attempt {passcode_data['attempts']}/3 for: {request.email}")
            remaining = 3 - passcode_data["attempts"]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid passcode. {remaining} attempt(s) remaining."
            )
        
        # Mark passcode as used
        passcode_data["used"] = True
        
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
        
        # Clean up used passcode
        del email_passcodes[email_lower]
        
        return {
            "success": True,
            "message": "Email passcode verified successfully",
            "token": token,
            "store_id": "STORE-001",
            "store_name": "VyaparAI Demo Store",
            "user": {
                "email": request.email,
                "name": "Store Owner",
                "role": "owner",
                "store_id": "STORE-001"
            }
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
