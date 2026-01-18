"""
Customer Authentication API endpoints for VyaparAI
Supports Google OAuth, Facebook OAuth, Email/Password, and Phone OTP
"""

import os
import jwt
import secrets
import random
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, status, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator, EmailStr
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests

from app.core.security import (
    get_jwt_secret, get_jwt_algorithm,
    create_customer_token, verify_token,
    JWT_CUSTOMER_TOKEN_EXPIRE_DAYS
)
from app.core.password import (
    hash_password, verify_password,
    is_password_hashed_with_bcrypt, migrate_sha256_to_bcrypt
)
from app.core.validation import (
    validate_phone_indian, validate_email, sanitize_string,
    check_injection_patterns, MAX_NAME_LENGTH, MAX_ADDRESS_LENGTH
)
from app.core.cache import (
    store_otp_redis, get_otp_redis, delete_otp_redis,
    increment_otp_attempts, OTP_MAX_ATTEMPTS
)
from app.core.database import get_dynamodb, CUSTOMERS_TABLE
from app.services.geocoding_service import geocoding_service

logger = logging.getLogger(__name__)

# Environment detection for secure OTP handling
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_DEVELOPMENT = ENVIRONMENT == "development"

# Create router
router = APIRouter(prefix="/customer/auth", tags=["customer-authentication"])

# JWT Configuration - imported from centralized security module
# DO NOT define JWT_SECRET here - use get_jwt_secret() instead

# OAuth Configuration - MUST be set via environment variables
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")

# Validate OAuth credentials at import time
if not GOOGLE_CLIENT_ID:
    logger.warning("GOOGLE_CLIENT_ID not set - Google OAuth will be disabled")
if not FACEBOOK_APP_ID or not FACEBOOK_APP_SECRET:
    logger.warning("Facebook OAuth credentials not set - Facebook OAuth will be disabled")

# DynamoDB Configuration - using centralized DatabaseManager
# Initialization happens at module import time (during Lambda INIT phase)
# This provides Lambda-compatible credential handling and connection pooling
_dynamodb = get_dynamodb()
customers_table = _dynamodb.Table(CUSTOMERS_TABLE) if _dynamodb else None

# ============================================================================
# Request/Response Models
# ============================================================================

class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., description="Google JWT credential token")

class FacebookAuthRequest(BaseModel):
    accessToken: str = Field(..., description="Facebook access token")
    userID: str = Field(..., description="Facebook user ID")

class AddressData(BaseModel):
    line1: str = Field(..., max_length=200)
    line2: Optional[str] = Field(None, max_length=200)
    city: str = Field(..., max_length=100)
    state: str = Field(..., max_length=100)
    pincode: str = Field(..., max_length=10)
    landmark: Optional[str] = Field(None, max_length=200)

    @validator('line1', 'line2', 'city', 'state', 'landmark', pre=True)
    def sanitize_text_fields(cls, v):
        if v:
            # Check for injection patterns
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            # Sanitize the string
            return sanitize_string(v, max_length=MAX_ADDRESS_LENGTH, escape_html=True)
        return v

    @validator('pincode')
    def validate_pincode(cls, v):
        if v:
            # Indian pincode: 6 digits
            if not re.match(r'^\d{6}$', v):
                raise ValueError('Pincode must be 6 digits')
        return v

class PaymentMethodsData(BaseModel):
    """Payment methods - only safe-to-store identifiers, no raw card data"""
    upi: Optional[str] = Field(None, description="UPI ID")
    paytm: Optional[str] = Field(None, description="Paytm/Wallet phone number")
    # Card tokens will be added during checkout via payment gateway

class PreferencesData(BaseModel):
    newsletter: bool = Field(False, description="Subscribe to newsletter")
    notifications: bool = Field(True, description="Enable notifications")

class EmailPasswordRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (min 6 characters)")
    first_name: str = Field(..., max_length=100, description="First name")
    last_name: str = Field(..., max_length=100, description="Last name")
    phone: Optional[str] = Field(None, description="Phone number (optional)")
    mobile: Optional[str] = Field(None, description="Alternate mobile (optional)")
    address: Optional[AddressData] = Field(None, description="Address (optional)")
    aadhaar_number: Optional[str] = Field(None, description="Aadhaar number (optional, encrypted)")
    payment_methods: Optional[PaymentMethodsData] = Field(None, description="Payment methods (optional)")
    preferences: Optional[PreferencesData] = Field(None, description="User preferences (optional)")

    @validator('first_name', 'last_name', pre=True)
    def sanitize_names(cls, v):
        if v:
            # Check for injection patterns
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            # Sanitize and limit length
            return sanitize_string(v, max_length=MAX_NAME_LENGTH, escape_html=True, allow_newlines=False)
        return v

    @validator('phone', 'mobile')
    def validate_phone_fields(cls, v):
        if v:
            # Check for injection patterns
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')

            # Use centralized phone validation
            is_valid, result = validate_phone_indian(v)
            if not is_valid:
                raise ValueError(result)
            return result
        return v

    @validator('aadhaar_number')
    def validate_aadhaar(cls, v):
        if v:
            # Aadhaar is 12 digits
            cleaned = re.sub(r'\s+', '', v)
            if not re.match(r'^\d{12}$', cleaned):
                raise ValueError('Aadhaar number must be 12 digits')
            return cleaned
        return v

class EmailPasswordLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")

class SendOTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number in international format")

    @validator('phone')
    def validate_phone(cls, v):
        # Check for injection patterns first
        is_safe, threat_type = check_injection_patterns(v)
        if not is_safe:
            raise ValueError('Invalid input detected')

        # Use centralized phone validation
        is_valid, result = validate_phone_indian(v)
        if not is_valid:
            raise ValueError(result)
        return result  # Return normalized phone

class VerifyOTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number")
    otp: str = Field(..., description="6-digit OTP")

    @validator('otp')
    def validate_otp(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('OTP must be 6 digits')
        return v

class AuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    customer: Optional[dict] = None
    error: Optional[str] = None

# ============================================================================
# Helper Functions
# ============================================================================

def generate_customer_id() -> str:
    """Generate unique customer ID"""
    timestamp = int(datetime.now().timestamp() * 1000)
    random_str = secrets.token_hex(8)
    return f"cust_{random_str[:16]}"

# Password hashing functions are now imported from app.core.password
# hash_password() - Hash a password using bcrypt
# verify_password() - Verify a password against bcrypt hash
# is_password_hashed_with_bcrypt() - Check if hash is bcrypt format
# migrate_sha256_to_bcrypt() - Migrate old SHA-256 hashes to bcrypt

def create_jwt_token(customer_id: str, email: str) -> str:
    """Create JWT token for customer using centralized security module"""
    payload = {
        'sub': customer_id,
        'customer_id': customer_id,
        'email': email
    }
    return create_customer_token(payload)

def get_or_create_customer_by_email(email: str, first_name: str, last_name: str,
                                     auth_provider: str = 'email') -> dict:
    """Get existing customer or create new one"""
    try:
        # Try to find existing customer by email
        response = customers_table.scan(
            FilterExpression='email = :email',
            ExpressionAttributeValues={':email': email}
        )

        if response['Items']:
            customer = response['Items'][0]
            logger.info(f"Found existing customer: {customer['customer_id']}")
            return customer

        # Create new customer
        customer_id = generate_customer_id()
        customer = {
            'customer_id': customer_id,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'auth_provider': auth_provider,
            'status': 'active',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'email_verified': auth_provider in ['google', 'facebook'],  # OAuth emails are verified
            'phone_verified': False,
            'order_count': 0,
            'total_spent': 0,
            'addresses': [],
            'payment_methods': []
        }

        customers_table.put_item(Item=customer)
        logger.info(f"Created new customer: {customer_id}")
        return customer

    except Exception as e:
        logger.error(f"Error in get_or_create_customer: {str(e)}")
        raise

# ============================================================================
# Google OAuth Endpoint
# ============================================================================

@router.post("/google", response_model=AuthResponse)
async def google_auth(request: GoogleAuthRequest):
    """
    Authenticate customer using Google OAuth
    Verifies Google JWT token and creates/logs in customer
    """
    # Check if Google OAuth is configured
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured. Please contact support."
        )

    try:
        # Verify Google token
        idinfo = id_token.verify_oauth2_token(
            request.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )

        # Extract user info from Google token
        email = idinfo.get('email')
        given_name = idinfo.get('given_name', '')
        family_name = idinfo.get('family_name', '')

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not found in Google token"
            )

        # Get or create customer
        customer = get_or_create_customer_by_email(
            email=email,
            first_name=given_name,
            last_name=family_name,
            auth_provider='google'
        )

        # Generate JWT token
        token = create_jwt_token(customer['customer_id'], email)

        logger.info(f"Google auth successful for customer: {customer['customer_id']}")

        return AuthResponse(
            success=True,
            token=token,
            customer={
                'customer_id': customer['customer_id'],
                'email': customer['email'],
                'first_name': customer['first_name'],
                'last_name': customer['last_name']
            }
        )

    except ValueError as e:
        # Invalid token
        logger.error(f"Google token verification failed: {str(e)}")
        return AuthResponse(
            success=False,
            error="Invalid Google token"
        )
    except Exception as e:
        logger.error(f"Google auth error: {str(e)}")
        return AuthResponse(
            success=False,
            error=f"Authentication failed: {str(e)}"
        )

# ============================================================================
# Facebook OAuth Endpoint
# ============================================================================

@router.post("/facebook", response_model=AuthResponse)
async def facebook_auth(request: FacebookAuthRequest):
    """
    Authenticate customer using Facebook OAuth
    Verifies Facebook access token and creates/logs in customer
    """
    # Check if Facebook OAuth is configured
    if not FACEBOOK_APP_ID or not FACEBOOK_APP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Facebook OAuth is not configured. Please contact support."
        )

    try:
        # Verify Facebook token with timeout
        verify_url = f"https://graph.facebook.com/debug_token?input_token={request.accessToken}&access_token={FACEBOOK_APP_ID}|{FACEBOOK_APP_SECRET}"
        verify_response = requests.get(verify_url, timeout=10)

        if verify_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to verify Facebook token"
            )

        token_data = verify_response.json()
        if not token_data.get('data', {}).get('is_valid'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Facebook token"
            )

        # Get user info from Facebook with timeout
        user_url = f"https://graph.facebook.com/v18.0/{request.userID}?fields=id,name,email,first_name,last_name&access_token={request.accessToken}"
        user_response = requests.get(user_url, timeout=10)

        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get Facebook user info"
            )

        user_data = user_response.json()
        email = user_data.get('email')
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email permission not granted by user"
            )

        # Get or create customer
        customer = get_or_create_customer_by_email(
            email=email,
            first_name=first_name,
            last_name=last_name,
            auth_provider='facebook'
        )

        # Generate JWT token
        token = create_jwt_token(customer['customer_id'], email)

        logger.info(f"Facebook auth successful for customer: {customer['customer_id']}")

        return AuthResponse(
            success=True,
            token=token,
            customer={
                'customer_id': customer['customer_id'],
                'email': customer['email'],
                'first_name': customer['first_name'],
                'last_name': customer['last_name']
            }
        )

    except requests.RequestException as e:
        logger.error(f"Facebook API error: {str(e)}")
        return AuthResponse(
            success=False,
            error="Failed to communicate with Facebook"
        )
    except Exception as e:
        logger.error(f"Facebook auth error: {str(e)}")
        return AuthResponse(
            success=False,
            error=f"Authentication failed: {str(e)}"
        )

# ============================================================================
# Email/Password Endpoints
# ============================================================================

@router.post("/register", response_model=AuthResponse)
async def register(request: EmailPasswordRegisterRequest):
    """
    Register new customer with email and password
    """
    try:
        # Check if customer already exists
        response = customers_table.scan(
            FilterExpression='email = :email',
            ExpressionAttributeValues={':email': request.email}
        )

        if response['Items']:
            return AuthResponse(
                success=False,
                error="Email already registered"
            )

        # Create new customer
        customer_id = generate_customer_id()
        password_hash = hash_password(request.password)

        # Prepare addresses list with auto-geocoding
        addresses = []
        if request.address:
            address_id = f"addr_{secrets.token_hex(8)}"

            # Auto-geocode address during registration
            latitude = None
            longitude = None
            try:
                street_parts = [request.address.line1]
                if request.address.line2:
                    street_parts.append(request.address.line2)
                if request.address.landmark:
                    street_parts.append(f"near {request.address.landmark}")
                street = ", ".join(street_parts)

                geocode_result = await geocoding_service.geocode_address(
                    street=street,
                    city=request.address.city,
                    state=request.address.state,
                    pincode=request.address.pincode
                )

                if geocode_result:
                    latitude = geocode_result.get('latitude')
                    longitude = geocode_result.get('longitude')
                    logger.info(f"[Registration] Geocoded address: ({latitude}, {longitude})")
            except Exception as geo_error:
                logger.warning(f"[Registration] Geocoding error: {str(geo_error)}, continuing without coordinates")

            address_data = {
                "address_id": address_id,
                "type": "home",  # Default to home address
                "line1": request.address.line1,
                "line2": request.address.line2 or '',
                "city": request.address.city,
                "state": request.address.state,
                "pincode": request.address.pincode,
                "phone": request.phone or '',  # Use registration phone or empty string
                "landmark": request.address.landmark or '',
                "latitude": latitude,
                "longitude": longitude,
                "is_default": True,  # First address is always default
                "created_at": datetime.utcnow().isoformat()
            }
            addresses.append(address_data)

        # Prepare payment methods list (only UPI/wallet IDs, no card data)
        payment_methods = []
        if request.payment_methods:
            if request.payment_methods.upi:
                payment_methods.append({
                    "payment_id": f"pay_{secrets.token_hex(8)}",
                    "type": "upi",
                    "upi_id": request.payment_methods.upi,
                    "is_default": True,
                    "created_at": datetime.utcnow().isoformat()
                })
            if request.payment_methods.paytm:
                payment_methods.append({
                    "payment_id": f"pay_{secrets.token_hex(8)}",
                    "type": "wallet",
                    "wallet_provider": "paytm",
                    "wallet_phone": request.payment_methods.paytm,
                    "is_default": len(payment_methods) == 0,  # Default if first
                    "created_at": datetime.utcnow().isoformat()
                })

        # Prepare preferences
        preferences = {}
        if request.preferences:
            preferences = {
                "newsletter": request.preferences.newsletter,
                "notifications": request.preferences.notifications,
                "language": "en",  # Default
                "currency": "INR"  # Indian Rupees
            }
        else:
            preferences = {
                "newsletter": False,
                "notifications": True,
                "language": "en",
                "currency": "INR"
            }

        customer = {
            'customer_id': customer_id,
            'email': request.email,
            'password_hash': password_hash,
            'first_name': request.first_name,
            'last_name': request.last_name,
            'phone': request.phone,
            'mobile': request.mobile,  # Alternate mobile
            'auth_provider': 'email',
            'status': 'active',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'email_verified': False,
            'phone_verified': False,
            'order_count': 0,
            'total_spent': 0,
            'addresses': addresses,
            'payment_methods': payment_methods,
            'preferences': preferences
        }

        # Add Aadhaar number if provided (encrypted storage recommended in production)
        if request.aadhaar_number:
            # In production, encrypt this using AWS KMS or similar
            customer['aadhaar_number'] = request.aadhaar_number
            customer['aadhaar_verified'] = False

        customers_table.put_item(Item=customer)

        # Generate JWT token
        token = create_jwt_token(customer_id, request.email)

        logger.info(f"Customer registered: {customer_id}")

        return AuthResponse(
            success=True,
            token=token,
            customer={
                'customer_id': customer_id,
                'email': request.email,
                'first_name': request.first_name,
                'last_name': request.last_name
            }
        )

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return AuthResponse(
            success=False,
            error=f"Registration failed: {str(e)}"
        )

@router.post("/login", response_model=AuthResponse)
async def login(request: EmailPasswordLoginRequest):
    """
    Login customer with email and password.
    Supports automatic migration from SHA-256 to bcrypt hashes.
    """
    try:
        # Find customer by email
        response = customers_table.scan(
            FilterExpression='email = :email',
            ExpressionAttributeValues={':email': request.email}
        )

        if not response['Items']:
            return AuthResponse(
                success=False,
                error="Invalid email or password"
            )

        customer = response['Items'][0]

        # Verify password
        if 'password_hash' not in customer:
            return AuthResponse(
                success=False,
                error="Please use social login (Google/Facebook) for this account"
            )

        stored_hash = customer['password_hash']
        password_valid = False
        new_hash = None

        # Check if hash is bcrypt format
        if is_password_hashed_with_bcrypt(stored_hash):
            # Modern bcrypt hash - verify directly
            password_valid = verify_password(request.password, stored_hash)
        else:
            # Legacy SHA-256 hash - try to migrate
            new_hash = migrate_sha256_to_bcrypt(request.password, stored_hash)
            if new_hash:
                password_valid = True
                logger.info(f"Migrating password hash for customer: {customer['customer_id']}")

        if not password_valid:
            return AuthResponse(
                success=False,
                error="Invalid email or password"
            )

        # If we have a new bcrypt hash, update it in the database
        if new_hash:
            try:
                customers_table.update_item(
                    Key={'customer_id': customer['customer_id']},
                    UpdateExpression='SET password_hash = :hash, updated_at = :updated',
                    ExpressionAttributeValues={
                        ':hash': new_hash,
                        ':updated': datetime.utcnow().isoformat()
                    }
                )
                logger.info(f"Password hash migrated to bcrypt for customer: {customer['customer_id']}")
            except Exception as e:
                # Don't fail login if migration fails - just log it
                logger.error(f"Failed to update password hash: {e}")

        # Generate JWT token
        token = create_jwt_token(customer['customer_id'], customer['email'])

        logger.info(f"Customer logged in: {customer['customer_id']}")

        return AuthResponse(
            success=True,
            token=token,
            customer={
                'customer_id': customer['customer_id'],
                'email': customer['email'],
                'first_name': customer.get('first_name', ''),
                'last_name': customer.get('last_name', '')
            }
        )

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return AuthResponse(
            success=False,
            error=f"Login failed: {str(e)}"
        )

# ============================================================================
# Phone OTP Endpoints
# ============================================================================

@router.post("/send-otp")
async def send_otp(request: SendOTPRequest):
    """
    Send OTP to phone number.
    Uses thread-safe Redis/memory storage with automatic expiration.
    """
    try:
        # Generate 6-digit OTP using secrets for better randomness
        otp = str(secrets.randbelow(900000) + 100000)

        # Store OTP with expiration (5 minutes) using thread-safe storage
        otp_data = {
            'otp': otp,
            'created_at': datetime.utcnow().isoformat(),
            'attempts': 0
        }

        stored = store_otp_redis(request.phone, otp_data, expiry_seconds=300)
        if not stored:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store OTP. Please try again."
            )

        # TODO: Send OTP via SMS service (AWS SNS, Twilio, etc.)
        # Mask phone number in logs for privacy
        masked_phone = request.phone[-4:].rjust(len(request.phone), '*')
        logger.info(f"OTP generated for {masked_phone}")

        # Only return OTP in development mode for testing
        # In production, OTP is sent via SMS and NOT returned in response
        response_otp = otp if IS_DEVELOPMENT else None

        return {
            'success': True,
            'message': 'OTP sent successfully. Valid for 5 minutes.',
            'otp': response_otp
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send OTP error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send OTP: {str(e)}"
        )

@router.post("/verify-otp", response_model=AuthResponse)
async def verify_otp(request: VerifyOTPRequest):
    """
    Verify OTP and login/register customer.
    Uses atomic increment for attempt counting to prevent race conditions.
    """
    try:
        # Get OTP data from thread-safe storage
        otp_data = get_otp_redis(request.phone)

        if not otp_data:
            return AuthResponse(
                success=False,
                error="OTP not found or expired"
            )

        # Verify OTP - compare first, then atomically increment attempts
        if request.otp != otp_data['otp']:
            # Wrong OTP - atomically increment attempts
            new_attempts, exceeded = increment_otp_attempts(request.phone)

            if exceeded:
                return AuthResponse(
                    success=False,
                    error="Too many failed attempts. Please request a new OTP."
                )

            remaining = OTP_MAX_ATTEMPTS - new_attempts
            return AuthResponse(
                success=False,
                error=f"Invalid OTP. {remaining} attempts remaining."
            )

        # OTP verified successfully - delete from storage
        delete_otp_redis(request.phone)

        # Find or create customer by phone
        response = customers_table.scan(
            FilterExpression='phone = :phone',
            ExpressionAttributeValues={':phone': request.phone}
        )

        if response['Items']:
            # Existing customer
            customer = response['Items'][0]
            # Mark phone as verified
            customers_table.update_item(
                Key={'customer_id': customer['customer_id']},
                UpdateExpression='SET phone_verified = :verified',
                ExpressionAttributeValues={':verified': True}
            )
        else:
            # Create new customer
            customer_id = generate_customer_id()
            customer = {
                'customer_id': customer_id,
                'phone': request.phone,
                'auth_provider': 'phone',
                'status': 'active',
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'email_verified': False,
                'phone_verified': True,
                'order_count': 0,
                'total_spent': 0,
                'first_name': '',
                'last_name': '',
                'addresses': [],
                'payment_methods': []
            }
            customers_table.put_item(Item=customer)

        # Generate JWT token (use phone as identifier)
        token = create_jwt_token(
            customer['customer_id'],
            customer.get('email', request.phone)
        )

        logger.info(f"Phone OTP verified for customer: {customer['customer_id']}")

        return AuthResponse(
            success=True,
            token=token,
            customer={
                'customer_id': customer['customer_id'],
                'phone': customer.get('phone', ''),
                'email': customer.get('email', ''),
                'first_name': customer.get('first_name', ''),
                'last_name': customer.get('last_name', '')
            }
        )

    except Exception as e:
        logger.error(f"Verify OTP error: {str(e)}")
        return AuthResponse(
            success=False,
            error=f"OTP verification failed: {str(e)}"
        )

# ============================================================================
# JWT Authentication Middleware
# ============================================================================

security = HTTPBearer()

async def verify_customer_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify JWT token and return customer data
    Used as dependency for protected endpoints
    """
    try:
        token = credentials.credentials
        payload = verify_token(token, expected_type="customer")

        customer_id = payload.get('customer_id')
        if not customer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

        # Get customer from database
        response = customers_table.get_item(Key={'customer_id': customer_id})
        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Customer not found"
            )

        return response['Item']

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

# ============================================================================
# Customer Profile Endpoints
# ============================================================================

class Address(BaseModel):
    address_id: Optional[str] = None
    type: str = Field(..., description="Address type: home, work, other")
    line1: str = Field(..., max_length=200, description="Address line 1")
    line2: Optional[str] = Field(None, max_length=200, description="Address line 2")
    city: str = Field(..., max_length=100)
    state: str = Field(..., max_length=100)
    pincode: str = Field(..., max_length=10)
    phone: str = Field(..., description="Contact phone for delivery")
    landmark: Optional[str] = Field(None, max_length=200)
    is_default: bool = False

    # Legacy support for 'street' field
    street: Optional[str] = Field(None, max_length=200)

    @validator('type')
    def validate_type(cls, v):
        allowed_types = ['home', 'work', 'other']
        if v.lower() not in allowed_types:
            raise ValueError(f'Address type must be one of: {", ".join(allowed_types)}')
        return v.lower()

    @validator('line1', 'line2', 'city', 'state', 'landmark', 'street', pre=True)
    def sanitize_text_fields(cls, v):
        if v:
            # Check for injection patterns
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            # Sanitize the string
            return sanitize_string(v, max_length=MAX_ADDRESS_LENGTH, escape_html=True)
        return v

    @validator('pincode')
    def validate_pincode(cls, v):
        if v:
            # Indian pincode: 6 digits
            if not re.match(r'^\d{6}$', v):
                raise ValueError('Pincode must be 6 digits')
        return v

    @validator('phone')
    def validate_phone(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')

            is_valid, result = validate_phone_indian(v)
            if not is_valid:
                raise ValueError(result)
            return result
        return v

class PaymentMethod(BaseModel):
    payment_id: Optional[str] = None
    type: str = Field(..., description="Payment type: upi, card, netbanking, cod, wallet")
    is_default: bool = False

    # UPI fields
    upi_id: Optional[str] = None
    provider: Optional[str] = None

    # Card fields
    token: Optional[str] = None
    last4: Optional[str] = None
    network: Optional[str] = None
    expiry: Optional[str] = None

    # Wallet fields
    wallet_provider: Optional[str] = None
    wallet_phone: Optional[str] = None

    # Legacy support for details field
    details: Optional[Dict[str, str]] = None

class CustomerProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    default_address_id: Optional[str] = None
    default_payment_id: Optional[str] = None

@router.get("/profile")
async def get_profile(customer: dict = Depends(verify_customer_token)):
    """
    Get customer profile with addresses, payment methods, and order history
    Requires authentication token in Authorization header
    """
    try:
        # Return full customer profile
        return {
            "success": True,
            "customer": {
                "customer_id": customer.get('customer_id'),
                "first_name": customer.get('first_name', ''),
                "last_name": customer.get('last_name', ''),
                "email": customer.get('email', ''),
                "phone": customer.get('phone', ''),  # May be empty for Google OAuth users
                "phone_verified": customer.get('phone_verified', False),
                "email_verified": customer.get('email_verified', False),
                "auth_provider": customer.get('auth_provider', ''),
                "status": customer.get('status', 'active'),
                "addresses": customer.get('addresses', []),
                "payment_methods": customer.get('payment_methods', []),
                "order_count": customer.get('order_count', 0),
                "total_spent": customer.get('total_spent', 0),
                "created_at": customer.get('created_at'),
                "updated_at": customer.get('updated_at'),
                "default_address_id": customer.get('default_address_id'),
                "default_payment_id": customer.get('default_payment_id')
            }
        }
    except Exception as e:
        logger.error(f"Get profile error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )

@router.put("/profile")
async def update_profile(
    profile_update: CustomerProfileUpdate,
    customer: dict = Depends(verify_customer_token)
):
    """
    Update customer profile information
    Requires authentication token in Authorization header
    """
    try:
        customer_id = customer['customer_id']

        # Build update expression
        update_parts = []
        expression_values = {}

        if profile_update.first_name is not None:
            update_parts.append("first_name = :first_name")
            expression_values[':first_name'] = profile_update.first_name

        if profile_update.last_name is not None:
            update_parts.append("last_name = :last_name")
            expression_values[':last_name'] = profile_update.last_name

        if profile_update.phone is not None:
            update_parts.append("phone = :phone")
            expression_values[':phone'] = profile_update.phone

        if profile_update.email is not None:
            update_parts.append("email = :email")
            expression_values[':email'] = profile_update.email

        if profile_update.default_address_id is not None:
            update_parts.append("default_address_id = :default_address_id")
            expression_values[':default_address_id'] = profile_update.default_address_id

        if profile_update.default_payment_id is not None:
            update_parts.append("default_payment_id = :default_payment_id")
            expression_values[':default_payment_id'] = profile_update.default_payment_id

        if not update_parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Always update timestamp
        update_parts.append("updated_at = :updated_at")
        expression_values[':updated_at'] = datetime.utcnow().isoformat()

        # Update customer in DynamoDB
        update_expression = "SET " + ", ".join(update_parts)

        response = customers_table.update_item(
            Key={'customer_id': customer_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )

        updated_customer = response['Attributes']

        logger.info(f"Customer profile updated: {customer_id}")

        return {
            "success": True,
            "message": "Profile updated successfully",
            "customer": {
                "customer_id": updated_customer.get('customer_id'),
                "first_name": updated_customer.get('first_name', ''),
                "last_name": updated_customer.get('last_name', ''),
                "email": updated_customer.get('email', ''),
                "phone": updated_customer.get('phone', ''),
                "phone_verified": updated_customer.get('phone_verified', False),
                "email_verified": updated_customer.get('email_verified', False)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )

@router.post("/profile/address")
async def add_address(
    address: Address,
    customer: dict = Depends(verify_customer_token)
):
    """Add new address to customer profile with auto-geocoding"""
    try:
        customer_id = customer['customer_id']
        address_id = f"addr_{secrets.token_hex(8)}"

        # Auto-geocode address to get lat/lng for nearby store searches
        latitude = None
        longitude = None

        try:
            # Build street address from line1, line2, and landmark
            street_parts = [address.line1]
            if address.line2:
                street_parts.append(address.line2)
            if address.landmark:
                street_parts.append(f"near {address.landmark}")
            street = ", ".join(street_parts)

            geocode_result = await geocoding_service.geocode_address(
                street=street,
                city=address.city,
                state=address.state,
                pincode=address.pincode
            )

            if geocode_result:
                latitude = geocode_result.get('latitude')
                longitude = geocode_result.get('longitude')
                logger.info(f"[Customer Address] Geocoded: ({latitude}, {longitude})")
            else:
                logger.warning(f"[Customer Address] Geocoding failed, continuing without coordinates")
        except Exception as geo_error:
            logger.warning(f"[Customer Address] Geocoding error: {str(geo_error)}, continuing without coordinates")

        address_data = {
            "address_id": address_id,
            "type": address.type,
            "line1": address.line1,
            "line2": address.line2 or '',
            "city": address.city,
            "state": address.state,
            "pincode": address.pincode,
            "phone": address.phone,
            "landmark": address.landmark or '',
            "latitude": latitude,
            "longitude": longitude,
            "is_default": address.is_default,
            "created_at": datetime.utcnow().isoformat()
        }

        addresses = customer.get('addresses', [])

        # If this is the first address or marked as default, make it default
        if not addresses or address.is_default:
            # Unset other default addresses
            for addr in addresses:
                addr['is_default'] = False
            address_data['is_default'] = True

        addresses.append(address_data)

        customers_table.update_item(
            Key={'customer_id': customer_id},
            UpdateExpression='SET addresses = :addresses, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':addresses': addresses,
                ':updated_at': datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Address added for customer: {customer_id}")

        return {
            "success": True,
            "message": "Address added successfully",
            "address": address_data
        }

    except Exception as e:
        logger.error(f"Add address error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add address: {str(e)}"
        )

@router.put("/profile/address/{address_id}/set-default")
async def set_default_address(
    address_id: str,
    customer: dict = Depends(verify_customer_token)
):
    """Set an address as the default address"""
    try:
        customer_id = customer['customer_id']
        addresses = customer.get('addresses', [])

        # Find the address and set it as default
        address_found = False
        for addr in addresses:
            if addr.get('address_id') == address_id:
                addr['is_default'] = True
                address_found = True
            else:
                addr['is_default'] = False

        if not address_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )

        # Update in DynamoDB
        customers_table.update_item(
            Key={'customer_id': customer_id},
            UpdateExpression='SET addresses = :addresses, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':addresses': addresses,
                ':updated_at': datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Default address updated for customer: {customer_id}")

        return {
            "success": True,
            "message": "Default address updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set default address error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set default address: {str(e)}"
        )

@router.post("/profile/payment-method")
async def add_payment_method(
    payment: PaymentMethod,
    customer: dict = Depends(verify_customer_token)
):
    """Add new payment method to customer profile"""
    try:
        customer_id = customer['customer_id']
        payment_id = f"pay_{secrets.token_hex(8)}"

        payment_data = {
            "payment_id": payment_id,
            "type": payment.type,
            "is_default": payment.is_default,
            "created_at": datetime.utcnow().isoformat()
        }

        # Add type-specific fields
        if payment.type == 'upi':
            if payment.upi_id:
                payment_data['upi_id'] = payment.upi_id
            if payment.provider:
                payment_data['provider'] = payment.provider
        elif payment.type == 'card':
            if payment.token:
                payment_data['token'] = payment.token
            if payment.last4:
                payment_data['last4'] = payment.last4
            if payment.network:
                payment_data['network'] = payment.network
            if payment.expiry:
                payment_data['expiry'] = payment.expiry
        elif payment.type == 'wallet':
            if payment.wallet_provider:
                payment_data['wallet_provider'] = payment.wallet_provider
            if payment.wallet_phone:
                payment_data['wallet_phone'] = payment.wallet_phone

        # Legacy support - if details field is provided, use it
        if payment.details:
            payment_data['details'] = payment.details

        payment_methods = customer.get('payment_methods', [])

        # If this is the first payment or marked as default, make it default
        if not payment_methods or payment.is_default:
            # Unset other default payment methods
            for pm in payment_methods:
                pm['is_default'] = False
            payment_data['is_default'] = True

        payment_methods.append(payment_data)

        customers_table.update_item(
            Key={'customer_id': customer_id},
            UpdateExpression='SET payment_methods = :payment_methods, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':payment_methods': payment_methods,
                ':updated_at': datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Payment method added for customer: {customer_id}")

        return {
            "success": True,
            "message": "Payment method added successfully",
            "payment_method": payment_data
        }

    except Exception as e:
        logger.error(f"Add payment method error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add payment method: {str(e)}"
        )
