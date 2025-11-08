"""
Customer Authentication API endpoints for VyaparAI
Supports Google OAuth, Facebook OAuth, Email/Password, and Phone OTP
"""

import jwt
import boto3
import hashlib
import secrets
import random
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, validator, EmailStr
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/customer/auth", tags=["customer-authentication"])

# JWT Configuration
JWT_SECRET = "vyaparai_customer_jwt_secret_change_in_production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 30  # 30 days

# OAuth Configuration
GOOGLE_CLIENT_ID = "1095992426096-qce7i5oqtn52et6ohek8j3t06c2m5oog.apps.googleusercontent.com"
FACEBOOK_APP_ID = "788136330687220"
FACEBOOK_APP_SECRET = "your_facebook_app_secret"  # Get from environment

# DynamoDB Configuration
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
customers_table = dynamodb.Table('vyaparai-customers-prod')

# In-memory OTP storage (use DynamoDB/Redis in production)
otp_storage: Dict[str, dict] = {}

# ============================================================================
# Request/Response Models
# ============================================================================

class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., description="Google JWT credential token")

class FacebookAuthRequest(BaseModel):
    accessToken: str = Field(..., description="Facebook access token")
    userID: str = Field(..., description="Facebook user ID")

class EmailPasswordRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    phone: Optional[str] = Field(None, description="Phone number (optional)")

class EmailPasswordLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")

class SendOTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number in international format")

    @validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^\+[1-9]\d{10,14}$', v):
            raise ValueError('Phone must be in international format (e.g., +919876543210)')
        return v

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

def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{pwd_hash}${salt}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        pwd_hash, salt = hashed.split('$')
        return hashlib.sha256((password + salt).encode()).hexdigest() == pwd_hash
    except:
        return False

def create_jwt_token(customer_id: str, email: str) -> str:
    """Create JWT token for customer"""
    payload = {
        'customer_id': customer_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

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
    try:
        # Verify Facebook token
        verify_url = f"https://graph.facebook.com/debug_token?input_token={request.accessToken}&access_token={FACEBOOK_APP_ID}|{FACEBOOK_APP_SECRET}"
        verify_response = requests.get(verify_url)

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

        # Get user info from Facebook
        user_url = f"https://graph.facebook.com/v18.0/{request.userID}?fields=id,name,email,first_name,last_name&access_token={request.accessToken}"
        user_response = requests.get(user_url)

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

        customer = {
            'customer_id': customer_id,
            'email': request.email,
            'password_hash': password_hash,
            'first_name': request.first_name,
            'last_name': request.last_name,
            'phone': request.phone,
            'auth_provider': 'email',
            'status': 'active',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'email_verified': False,
            'phone_verified': False,
            'order_count': 0,
            'total_spent': 0,
            'addresses': [],
            'payment_methods': []
        }

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
    Login customer with email and password
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

        if not verify_password(request.password, customer['password_hash']):
            return AuthResponse(
                success=False,
                error="Invalid email or password"
            )

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
    Send OTP to phone number
    """
    try:
        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))

        # Store OTP with expiration (5 minutes)
        otp_storage[request.phone] = {
            'otp': otp,
            'expires_at': datetime.utcnow() + timedelta(minutes=5),
            'attempts': 0
        }

        # TODO: Send OTP via SMS service (AWS SNS, Twilio, etc.)
        logger.info(f"OTP generated for {request.phone}: {otp}")

        # In development, return OTP in response
        return {
            'success': True,
            'message': 'OTP sent successfully',
            'otp': otp  # Remove this in production!
        }

    except Exception as e:
        logger.error(f"Send OTP error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send OTP: {str(e)}"
        )

@router.post("/verify-otp", response_model=AuthResponse)
async def verify_otp(request: VerifyOTPRequest):
    """
    Verify OTP and login/register customer
    """
    try:
        # Check if OTP exists
        if request.phone not in otp_storage:
            return AuthResponse(
                success=False,
                error="OTP not found or expired"
            )

        otp_data = otp_storage[request.phone]

        # Check expiration
        if datetime.utcnow() > otp_data['expires_at']:
            del otp_storage[request.phone]
            return AuthResponse(
                success=False,
                error="OTP expired"
            )

        # Check attempts
        if otp_data['attempts'] >= 3:
            del otp_storage[request.phone]
            return AuthResponse(
                success=False,
                error="Too many failed attempts"
            )

        # Verify OTP
        if request.otp != otp_data['otp']:
            otp_storage[request.phone]['attempts'] += 1
            return AuthResponse(
                success=False,
                error="Invalid OTP"
            )

        # OTP verified, remove from storage
        del otp_storage[request.phone]

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
