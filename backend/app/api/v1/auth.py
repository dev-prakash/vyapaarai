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
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field, validator

from app.core.exceptions import (
    InvalidOTPError, ValidationError, AuthenticationError,
    create_error_response, handle_phone_validation_error, handle_otp_validation_error
)
from app.core.security import (
    get_jwt_secret, get_jwt_algorithm,
    create_store_owner_token, verify_token,
    JWT_STORE_OWNER_TOKEN_EXPIRE_DAYS
)
from app.core.cache import (
    store_otp_redis, get_otp_redis, update_otp_redis, delete_otp_redis,
    get_otp_storage_status, OTP_DEFAULT_EXPIRY
)
from app.core.validation import (
    validate_phone_indian, validate_email, sanitize_string,
    check_injection_patterns, MAX_NAME_LENGTH, MAX_EMAIL_LENGTH
)
from app.core.audit import (
    log_auth_success, log_auth_failure, log_otp_send, log_otp_verify
)
from app.services.email_service import send_passcode_email
from app.services.sms_service import sms_service, send_otp_sms
from app.core.database import get_dynamodb, SESSIONS_TABLE, STORES_TABLE
import hashlib

logger = logging.getLogger(__name__)

# Initialize DynamoDB tables
_dynamodb = get_dynamodb()
sessions_table = _dynamodb.Table(SESSIONS_TABLE) if _dynamodb else None
stores_table = _dynamodb.Table(STORES_TABLE) if _dynamodb else None

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])

# JWT configuration - imported from centralized security module
# DO NOT define JWT_SECRET here - use get_jwt_secret() instead

# Environment detection
import os
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_DEVELOPMENT = ENVIRONMENT == "development"

# In-memory storage for email passcodes (OTPs now use Redis via app.core.cache)
email_passcodes: Dict[str, dict] = {}

# OTP Configuration
OTP_EXPIRY_MINUTES = 5
OTP_MAX_ATTEMPTS = 3
OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = OTP_EXPIRY_MINUTES * 60

# Store owner email whitelist (use database in production)
STORE_OWNER_EMAILS = [
    "owner@vyaparai.com",
    "admin@vyaparai.com",
    "test@vyaparai.com",
    "prakashsukumar@gmail.com",
    "devprakashsen@gmail.com"
]


def generate_secure_otp(length: int = OTP_LENGTH) -> str:
    """
    Generate a cryptographically secure OTP.
    Uses secrets module for secure random number generation.
    """
    # Generate a random number with the specified number of digits
    otp = ''.join([str(secrets.randbelow(10)) for _ in range(length)])
    return otp


def store_otp(phone: str, otp: str) -> None:
    """
    Store OTP with metadata for verification.
    Uses Redis with automatic TTL expiration (falls back to in-memory if Redis unavailable).
    """
    otp_data = {
        'otp': otp,
        'created_at': datetime.utcnow().isoformat(),
        'attempts': 0,
        'verified': False
    }
    store_otp_redis(phone, otp_data, expiry_seconds=OTP_EXPIRY_SECONDS)
    logger.info(f"OTP stored for phone: {phone[-4:].rjust(len(phone), '*')}")


def verify_stored_otp(phone: str, otp: str) -> tuple[bool, str]:
    """
    Verify OTP against stored value in Redis.

    Returns:
        Tuple of (is_valid, error_message)
    """
    otp_data = get_otp_redis(phone)

    if otp_data is None:
        return False, "No OTP found. Please request a new OTP."

    # Note: Expiration is handled automatically by Redis TTL
    # The get_otp_redis function returns None if expired

    # Check if already verified (prevent reuse)
    if otp_data.get('verified'):
        delete_otp_redis(phone)
        return False, "OTP already used. Please request a new OTP."

    # Check attempt limit
    otp_data['attempts'] = otp_data.get('attempts', 0) + 1
    if otp_data['attempts'] > OTP_MAX_ATTEMPTS:
        delete_otp_redis(phone)
        return False, "Too many incorrect attempts. Please request a new OTP."

    # Update attempt count in Redis
    update_otp_redis(phone, otp_data)

    # Verify OTP
    if otp_data.get('otp') != otp:
        remaining = OTP_MAX_ATTEMPTS - otp_data['attempts']
        return False, f"Invalid OTP. {remaining} attempt(s) remaining."

    # OTP is valid - mark as verified
    otp_data['verified'] = True
    update_otp_redis(phone, otp_data)
    return True, "OTP verified successfully"

class LoginRequest(BaseModel):
    phone: str = Field(..., description="Phone number")
    otp: Optional[str] = Field(None, description="OTP code (optional for dev mode)")

    @validator('phone')
    def validate_phone(cls, v):
        # Check for injection patterns first
        is_safe, threat_type = check_injection_patterns(v)
        if not is_safe:
            raise ValueError(f'Invalid input detected')

        # Use centralized phone validation
        is_valid, result = validate_phone_indian(v)
        if not is_valid:
            raise ValueError(result)
        return result  # Return normalized phone

    @validator('otp')
    def validate_otp(cls, v):
        if v is not None:
            # OTP should only contain digits
            if not re.match(r'^\d{4,6}$', v):
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
        # Check for injection patterns first
        is_safe, threat_type = check_injection_patterns(v)
        if not is_safe:
            raise ValueError(f'Invalid input detected')

        # Use centralized phone validation
        is_valid, result = validate_phone_indian(v)
        if not is_valid:
            raise ValueError(result)
        return result  # Return normalized phone

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
        # Check for injection patterns first
        is_safe, threat_type = check_injection_patterns(v)
        if not is_safe:
            raise ValueError(f'Invalid input detected')

        # Use centralized phone validation
        is_valid, result = validate_phone_indian(v)
        if not is_valid:
            raise ValueError(result)
        return result  # Return normalized phone

class SendOTPResponse(BaseModel):
    success: bool = Field(..., description="Whether OTP was sent")
    message: str = Field(..., description="Response message")
    otp: Optional[str] = Field(None, description="Test OTP for development")

class EmailPasscodeRequest(BaseModel):
    email: str = Field(..., description="Email address")

    @validator('email')
    def validate_email_field(cls, v):
        # Check for injection patterns first
        is_safe, threat_type = check_injection_patterns(v)
        if not is_safe:
            raise ValueError(f'Invalid input detected')

        # Use centralized email validation
        is_valid, result = validate_email(v)
        if not is_valid:
            raise ValueError(result)
        return result  # Return normalized email (lowercase, stripped)

class EmailPasscodeResponse(BaseModel):
    success: bool = Field(..., description="Whether passcode was sent")
    message: str = Field(..., description="Response message")
    test_passcode: Optional[str] = Field(None, description="Test passcode for development")

class VerifyEmailPasscodeRequest(BaseModel):
    email: str = Field(..., description="Email address")
    passcode: str = Field(..., description="6-digit passcode")

    @validator('email')
    def validate_email_field(cls, v):
        # Check for injection patterns first
        is_safe, threat_type = check_injection_patterns(v)
        if not is_safe:
            raise ValueError(f'Invalid input detected')

        # Use centralized email validation
        is_valid, result = validate_email(v)
        if not is_valid:
            raise ValueError(result)
        return result  # Return normalized email (lowercase, stripped)

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
        if v:
            # Check for injection patterns first
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError(f'Invalid input detected')

            # Use centralized phone validation
            is_valid, result = validate_phone_indian(v)
            if not is_valid:
                raise ValueError(result)
            return result  # Return normalized phone
        return v

    @validator('email')
    def validate_email_field(cls, v):
        if v:
            # Check for injection patterns first
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError(f'Invalid input detected')

            # Use centralized email validation
            is_valid, result = validate_email(v)
            if not is_valid:
                raise ValueError(result)
            return result  # Return normalized email
        return v

class LoginWithPasswordRequest(BaseModel):
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")

    @validator('email')
    def validate_email_field(cls, v):
        # Check for injection patterns first
        is_safe, threat_type = check_injection_patterns(v)
        if not is_safe:
            raise ValueError(f'Invalid input detected')

        # Use centralized email validation
        is_valid, result = validate_email(v)
        if not is_valid:
            raise ValueError(result)
        return result  # Return normalized email (lowercase, stripped)

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

@router.post("/login-with-password")
async def login_with_password(request_data: LoginWithPasswordRequest, request: Request):
    """
    Login with email and password.
    Verifies the password against the stored hash in sessions table.
    """
    logger.info(f"Password login attempt for email: {request_data.email}")

    try:
        if not sessions_table:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Look up the password hash from sessions table
        password_key = f"password_{request_data.email.lower()}"
        try:
            password_response = sessions_table.get_item(
                Key={'pk': password_key}
            )
        except Exception as e:
            logger.error(f"Error fetching password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify password"
            )

        if 'Item' not in password_response:
            logger.warning(f"No password found for email: {request_data.email}")
            log_auth_failure(request_data.email, "password", "No password set", request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        stored_hash = password_response['Item'].get('password_hash', '')

        # Verify password - format is salt$hash
        if '$' in stored_hash:
            salt, expected_hash = stored_hash.split('$', 1)
            hash_input = f"{salt}{request_data.password}".encode('utf-8')
            computed_hash = hashlib.sha256(hash_input).hexdigest()

            if computed_hash != expected_hash:
                logger.warning(f"Invalid password attempt for email: {request_data.email}")
                log_auth_failure(request_data.email, "password", "Invalid password", request)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
        else:
            logger.warning(f"Invalid password hash format for email: {request_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Look up store info for the token - use store_id from password record
        store_info = None
        stored_store_id = password_response['Item'].get('store_id')

        if stores_table and stored_store_id:
            try:
                # Direct lookup by store_id (most efficient)
                store_response = stores_table.get_item(
                    Key={'id': stored_store_id}
                )
                if 'Item' in store_response:
                    store_info = store_response['Item']
                    logger.info(f"Found store by id: {stored_store_id}")
            except Exception as e:
                logger.warning(f"Could not fetch store by id: {e}")

        # Fallback: scan by email in both top-level and contact_info
        if not store_info and stores_table:
            try:
                response = stores_table.scan(
                    FilterExpression='email = :email OR #ci.#em = :email',
                    ExpressionAttributeNames={'#ci': 'contact_info', '#em': 'email'},
                    ExpressionAttributeValues={':email': request_data.email.lower()}
                )
                if response.get('Items') and len(response['Items']) > 0:
                    store_info = response['Items'][0]
                    logger.info(f"Found store by email scan: {store_info.get('store_id')}")
            except Exception as e:
                logger.warning(f"Could not fetch store info by email: {e}")

        store_id = store_info.get('store_id') or store_info.get('id') or stored_store_id or 'STORE-001' if store_info else (stored_store_id or 'STORE-001')
        store_name = store_info.get('name', 'VyaparAI Store') if store_info else 'VyaparAI Store'

        # Generate JWT token
        token_data = {
            "sub": f"user_{request_data.email}",
            "email": request_data.email,
            "store_id": store_id,
            "user_id": f"user_{request_data.email}",
            "role": "owner"
        }

        token = create_store_owner_token(token_data)
        logger.info(f"Password login successful for email: {request_data.email}")

        # Audit log: successful login
        log_auth_success(f"user_{request_data.email}", "password", request, store_id)

        return {
            "success": True,
            "message": "Login successful",
            "token": token,
            "store_id": store_id,
            "store_name": store_name,
            "user": {
                "email": request_data.email,
                "name": store_info.get('owner_name', 'Store Owner') if store_info else 'Store Owner',
                "role": "owner",
                "store_id": store_id
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password login error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(otp_request: SendOTPRequest, request: Request):
    """
    Send OTP to phone number.
    In production, this integrates with SMS gateway.
    In development, OTP is returned in response for testing.
    """
    logger.info(f"Send OTP request for phone: {otp_request.phone[-4:].rjust(len(otp_request.phone), '*')}")

    try:
        # Generate secure OTP
        otp = generate_secure_otp()

        # Store OTP with expiration metadata
        store_otp(otp_request.phone, otp)

        # Audit log: OTP sent
        log_otp_send(otp_request.phone, request)

        # Send OTP via SMS (Gupshup)
        sms_result = await send_otp_sms(otp_request.phone, otp)

        if sms_result.success:
            logger.info(f"OTP sent via SMS to: {otp_request.phone[-4:].rjust(len(otp_request.phone), '*')}")
        else:
            # Log the error but don't fail - OTP is still stored for verification
            logger.warning(f"SMS delivery failed: {sms_result.error}. OTP still stored for verification.")

        # Only return OTP in response during development
        response_otp = otp if IS_DEVELOPMENT else None

        return SendOTPResponse(
            success=True,
            message="OTP sent successfully. Valid for 5 minutes.",
            otp=response_otp  # Only returned in development mode
        )

    except Exception as e:
        logger.error(f"Send OTP error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )

@router.post("/login", response_model=LoginResponse)
async def login(login_request: LoginRequest, request: Request):
    """
    Login with phone and OTP.
    Validates OTP against stored value (generated by /send-otp).
    """
    logger.info(f"Login attempt for phone: {login_request.phone[-4:].rjust(len(login_request.phone), '*')}")

    try:
        # OTP is required for login
        if not login_request.otp:
            log_auth_failure(login_request.phone, "otp", "OTP not provided", request)
            raise InvalidOTPError("OTP is required. Please request an OTP first.")

        # Verify OTP against stored value
        is_valid, error_message = verify_stored_otp(login_request.phone, login_request.otp)
        if not is_valid:
            logger.warning(f"Invalid OTP attempt for phone: {login_request.phone[-4:].rjust(len(login_request.phone), '*')}")
            log_otp_verify(login_request.phone, False, request, error_message)
            raise InvalidOTPError(error_message)

        # OTP verified successfully
        log_otp_verify(login_request.phone, True, request)

        # Generate JWT token using centralized security module
        user_id = f"user_{login_request.phone}"
        token_data = {
            "sub": user_id,
            "phone": login_request.phone,
            "store_id": "STORE-001",
            "user_id": user_id,
            "role": "owner"
        }

        token = create_store_owner_token(token_data)
        logger.info(f"Login successful for phone: {login_request.phone[-4:].rjust(len(login_request.phone), '*')}")

        # Audit log: successful login
        log_auth_success(user_id, "otp", request, "STORE-001")

        # Clean up used OTP from Redis
        delete_otp_redis(login_request.phone)

        return LoginResponse(
            token=token,
            store_id="STORE-001",
            store_name="Test Kirana Store",
            user={
                "phone": login_request.phone,
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
async def verify_otp(verify_request: VerifyOTPRequest, request: Request):
    """
    Verify OTP against stored value.
    Returns JWT token on successful verification.
    """
    logger.info(f"OTP verification for phone: {verify_request.phone[-4:].rjust(len(verify_request.phone), '*')}")

    try:
        # Validate OTP against stored value
        is_valid, error_message = verify_stored_otp(verify_request.phone, verify_request.otp)
        if not is_valid:
            logger.warning(f"Invalid OTP verification for phone: {verify_request.phone[-4:].rjust(len(verify_request.phone), '*')}")
            log_otp_verify(verify_request.phone, False, request, error_message)
            raise InvalidOTPError(error_message)

        # OTP verified successfully
        log_otp_verify(verify_request.phone, True, request)

        # Generate JWT token for valid OTP using centralized security module
        user_id = f"user_{verify_request.phone}"
        token_data = {
            "sub": user_id,
            "phone": verify_request.phone,
            "store_id": "STORE-001",
            "user_id": user_id,
            "role": "owner"
        }

        token = create_store_owner_token(token_data)
        logger.info(f"OTP verification successful for phone: {verify_request.phone[-4:].rjust(len(verify_request.phone), '*')}")

        # Audit log: successful authentication
        log_auth_success(user_id, "otp", request, "STORE-001")

        # Clean up verified OTP from Redis
        delete_otp_redis(verify_request.phone)

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
        # Decode existing token using centralized security module
        payload = verify_token(token)

        # Remove exp/iat from payload before creating new token
        payload_clean = {k: v for k, v in payload.items() if k not in ["exp", "iat", "type"]}

        # Create new token with extended expiry
        new_token = create_store_owner_token(payload_clean)

        return {
            "token": new_token,
            "expires_in": JWT_STORE_OWNER_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
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
        payload = verify_token(token)
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
        
        # Generate JWT token for valid passcode using centralized security module
        token_data = {
            "sub": f"user_{request.email}",
            "email": request.email,
            "store_id": "STORE-001",
            "user_id": f"user_{request.email}",
            "role": "owner"
        }

        token = create_store_owner_token(token_data)
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

# Note: verify_token is now imported from app.core.security
# This local wrapper is kept for backward compatibility with existing imports
def verify_token_local(token: str) -> dict:
    """
    Verify JWT token and return payload.

    DEPRECATED: Import verify_token from app.core.security instead.
    """
    try:
        return verify_token(token)
    except (jwt.InvalidTokenError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
