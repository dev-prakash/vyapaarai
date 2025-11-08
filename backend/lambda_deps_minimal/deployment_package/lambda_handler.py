"""
Simple Lambda handler for email authentication without heavy dependencies
"""

import json
import jwt
import random
import logging
import re
import time
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from mangum import Mangum

# AWS SDK
import boto3
from botocore.exceptions import ClientError

# FastAPI
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients initialized via functions

def get_dynamodb_client():
    """Get DynamoDB client with fallback handling"""
    try:
        import boto3
        return boto3.client('dynamodb', region_name='ap-south-1')
    except Exception as e:
        logger.error(f"Failed to create DynamoDB client: {e}")
        return None

def get_ses_client():
    """Get SES client"""
    try:
        import boto3
        return boto3.client('ses', region_name='ap-south-1')
    except Exception as e:
        logger.error(f"Failed to create SES client: {e}")
        return None

# FastAPI app
app = FastAPI(title="VyapaarAI Email Auth API")

# CORS is handled by Lambda Function URL configuration
# Commenting out to prevent duplicate headers that cause CORS conflicts
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Configuration
JWT_SECRET = "vyaparai-jwt-secret-2024-secure"
JWT_ALGORITHM = "HS256"

# JWT Token Creation
def create_jwt_token(user_id: str, email: str, store_id: str, role: str = "store_owner") -> str:
    """Create a JWT token with user and store information"""
    payload = {
        "user_id": user_id,
        "email": email,
        "store_id": store_id,
        "role": role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=30)  # Token expires in 30 days
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# Authentication helpers
def extract_token_from_request(request) -> str:
    """Extract JWT token from Authorization header"""
    logger.info(f"DEBUG TOKEN: All headers: {dict(request.headers)}")
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    logger.info(f"DEBUG TOKEN: Auth header found: {auth_header is not None}")
    if not auth_header:
        return None
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        logger.info(f"DEBUG TOKEN: Extracted Bearer token (first 20 chars): {token[:20]}...")
        return token
    logger.info(f"DEBUG TOKEN: Auth header doesn't start with Bearer: {auth_header[:50]}...")
    return auth_header

def get_store_from_jwt(request) -> str:
    """Extract store_id from JWT token - STRICT MODE: No fallbacks"""
    token = extract_token_from_request(request)
    if not token:
        logger.error("No authentication token provided")
        raise HTTPException(status_code=401, detail="Authentication token required")
    
    try:
        # Decode JWT token
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        store_id = decoded.get("store_id")
        
        if not store_id:
            logger.error("JWT token does not contain store_id")
            raise HTTPException(status_code=401, detail="Invalid token: missing store context")
        
        logger.info(f"Authenticated request for store: {store_id}")
        return store_id
            
    except jwt.ExpiredSignatureError:
        logger.error("JWT token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error extracting store from JWT: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")

def get_user_from_jwt(request) -> dict:
    """Extract user information from JWT token"""
    try:
        token = extract_token_from_request(request)
        if not token:
            return None
        
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "user_id": decoded.get("user_id"),
            "email": decoded.get("email"),
            "store_id": decoded.get("store_id"),
            "role": decoded.get("role", "user")
        }
    except Exception as e:
        logger.error(f"Error extracting user from JWT: {e}")
        return None

async def check_store_has_password(email: str) -> bool:
    """Check if store has a password set"""
    try:
        pk = f"password_{email}"
        response = local_dynamodb.get_item(
            TableName=TABLE_NAMES['sessions'],
            Key={'pk': {'S': pk}}
        )
        
        return 'Item' in response
        
    except Exception as e:
        logger.error(f"Error checking store password: {e}")
        return False

async def verify_store_password(email: str, password: str) -> bool:
    """Verify store owner password"""
    try:
        pk = f"password_{email}"
        response = local_dynamodb.get_item(
            TableName=TABLE_NAMES['sessions'],
            Key={'pk': {'S': pk}}
        )
        
        if 'Item' not in response:
            return False
        
        stored_hash = response['Item']['password_hash']['S']
        
        # Verify password using SHA-256
        test_hash = hashlib.sha256((password + email).encode()).hexdigest()
        
        return stored_hash == test_hash
        
    except Exception as e:
        logger.error(f"Error verifying store password: {e}")
        return False

# DynamoDB table names
TABLE_NAMES = {
    'stores': 'vyaparai-stores-prod',
    'passcodes': 'vyaparai-passcodes-prod',
    'sessions': 'vyaparai-sessions-prod',
    'users': 'vyaparai-users-prod',
    'orders': 'vyaparai-orders-prod',
    'products': 'vyaparai-products-prod',
    'inventory': 'vyaparai-inventory-prod',
    'categories': 'vyaparai-categories-prod'
}

# Email configuration
FROM_EMAIL = "noreply@vyapaarai.com"
FROM_NAME = "VyapaarAI"
USE_SES = True  # Enable AWS SES for actual email sending

def validate_email(email):
    """Simple email validation"""
    return re.match(r'^[^@]+@[^@]+\.[^@]+$', email) is not None

def validate_passcode(passcode):
    """Simple passcode validation"""
    return re.match(r'^\d{6}$', passcode) is not None

def validate_password(password):
    """Validate password meets security requirements"""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    # Check for at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for at least one lowercase letter
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for at least one digit
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    # Check for at least one special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(32)
    combined = salt + password
    hashed = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    return f"{salt}${hashed}"

def verify_password(password, stored_password):
    """Verify password against salted SHA-256 hash in format `salt$hash`."""
    try:
        salt, stored_hash = stored_password.split('$', 1)
        combined = salt + password
        computed_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
        return computed_hash == stored_hash
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

async def get_store_by_email(email):
    """Get store details from DynamoDB by email"""
    # Get DynamoDB client
    local_dynamodb = get_dynamodb_client()
    
    if not local_dynamodb:
        logger.error("DynamoDB client not available")
        return None
    
    try:
        # Query using scan with filter on direct email field (production table structure)
        response = local_dynamodb.scan(
            TableName=TABLE_NAMES['stores'],
            FilterExpression="#email = :email",
            ExpressionAttributeNames={
                '#email': 'email'
            },
            ExpressionAttributeValues={
                ":email": {"S": email}
            }
        )
        
        if response['Items']:
            store = response['Items'][0]
            
            # Check if password exists for this email
            existing_password = await get_password_hash(email)
            has_password = existing_password is not None
            
            return {
                "store_id": store.get('store_id', {}).get('S'),
                "name": store.get('name', {}).get('S'),
                "owner_name": store.get('owner_name', {}).get('S', 'Store Owner'),
                "email": email,
                "phone": store.get('phone', {}).get('S'),
                "status": store.get('status', {}).get('S', 'active'),
                "has_password": has_password
            }
        return None
        
    except ClientError as e:
        logger.error(f"DynamoDB error getting store by email: {e}")
        return None

async def store_passcode(email, passcode, ttl_minutes=15):
    """Store passcode in DynamoDB with TTL"""
    # Get DynamoDB client
    local_dynamodb = get_dynamodb_client()
    
    if not local_dynamodb:
        logger.error("DynamoDB client not available")
        return False
    
    try:
        # Calculate TTL
        ttl = int(time.time()) + (ttl_minutes * 60)
        
        item = {
            'pk': {'S': f"EMAIL#{email}"},
            'sk': {'S': 'PASSCODE'},
            'passcode': {'S': passcode},
            'email': {'S': email},
            'created_at': {'S': datetime.utcnow().isoformat()},
            'expires_at': {'S': (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat()},
            'used': {'BOOL': False},
            'attempts': {'N': '0'},
            'ttl': {'N': str(ttl)}
        }
        
        local_dynamodb.put_item(
            TableName=TABLE_NAMES['passcodes'],
            Item=item
        )
        return True
        
    except ClientError as e:
        logger.error(f"DynamoDB error storing passcode: {e}")
        return False

async def get_and_validate_passcode(email, passcode):
    """Get and validate passcode from DynamoDB"""
    # Get DynamoDB client
    local_dynamodb = get_dynamodb_client()
    
    if not local_dynamodb:
        logger.error("DynamoDB client not available")
        return {"valid": False, "error": "Database connection error"}
    
    try:
        # Get passcode record
        response = local_dynamodb.get_item(
            TableName=TABLE_NAMES['passcodes'],
            Key={
                'pk': {'S': f"EMAIL#{email}"},
                'sk': {'S': 'PASSCODE'}
            }
        )
        
        if 'Item' not in response:
            return {"valid": False, "error": "No passcode found. Please request a new one."}
        
        item = response['Item']
        
        # Check if already used
        if item.get('used', {}).get('BOOL', False):
            local_dynamodb.delete_item(
                TableName=TABLE_NAMES['passcodes'],
                Key={'pk': {'S': f"EMAIL#{email}"}, 'sk': {'S': 'PASSCODE'}}
            )
            return {"valid": False, "error": "This passcode has already been used. Please request a new one."}
        
        # Check if expired
        expires_at = datetime.fromisoformat(item['expires_at']['S'])
        if datetime.utcnow() > expires_at:
            local_dynamodb.delete_item(
                TableName=TABLE_NAMES['passcodes'],
                Key={'pk': {'S': f"EMAIL#{email}"}, 'sk': {'S': 'PASSCODE'}}
            )
            return {"valid": False, "error": "This passcode has expired. Please request a new one."}
        
        # Increment attempts
        attempts = int(item.get('attempts', {}).get('N', '0')) + 1
        
        # Check attempt limit
        if attempts > 3:
            local_dynamodb.delete_item(
                TableName=TABLE_NAMES['passcodes'],
                Key={'pk': {'S': f"EMAIL#{email}"}, 'sk': {'S': 'PASSCODE'}}
            )
            return {"valid": False, "error": "Too many incorrect attempts. Please request a new passcode."}
        
        # Validate passcode
        if passcode != item['passcode']['S']:
            local_dynamodb.update_item(
                TableName=TABLE_NAMES['passcodes'],
                Key={'pk': {'S': f"EMAIL#{email}"}, 'sk': {'S': 'PASSCODE'}},
                UpdateExpression='SET attempts = :attempts',
                ExpressionAttributeValues={':attempts': {'N': str(attempts)}}
            )
            remaining = 3 - attempts
            return {"valid": False, "error": f"Invalid passcode. {remaining} attempt(s) remaining."}
        
        # Mark as used
        local_dynamodb.update_item(
            TableName=TABLE_NAMES['passcodes'],
            Key={'pk': {'S': f"EMAIL#{email}"}, 'sk': {'S': 'PASSCODE'}},
            UpdateExpression='SET used = :used',
            ExpressionAttributeValues={':used': {'BOOL': True}}
        )
        
        return {"valid": True, "error": None}
        
    except ClientError as e:
        logger.error(f"DynamoDB error validating passcode: {e}")
        return {"valid": False, "error": "Internal server error during validation"}

async def store_password(email, hashed_password):
    """Store hashed password in DynamoDB"""
    local_dynamodb = get_dynamodb_client()
    
    if not local_dynamodb:
        logger.error("DynamoDB client not available")
        return False
    
    try:
        # Store password in sessions table (where passwords are actually stored)
        pk = f"password_{email}"
        item = {
            'pk': {'S': pk},
            'email': {'S': email},
            'type': {'S': 'password'},
            'password_hash': {'S': hashed_password},
            'created_at': {'S': datetime.utcnow().isoformat()},
            'updated_at': {'S': datetime.utcnow().isoformat()}
        }
        
        local_dynamodb.put_item(
            TableName=TABLE_NAMES['sessions'],  # Using sessions table for passwords
            Item=item
        )
        return True
        
    except ClientError as e:
        logger.error(f"DynamoDB error storing password: {e}")
        return False

async def get_password_hash(email):
    """Get password hash from DynamoDB"""
    local_dynamodb = get_dynamodb_client()
    
    if not local_dynamodb:
        logger.error("DynamoDB client not available")
        return None
    
    try:
        # First try to get password from sessions table (where passwords are actually stored)
        pk = f"password_{email}"
        response = local_dynamodb.get_item(
            TableName=TABLE_NAMES['sessions'],
            Key={
                'pk': {'S': pk}
            }
        )
        
        if 'Item' in response:
            return response['Item'].get('password_hash', {}).get('S')
        
        # Fallback: Try to get user by email from users table (legacy)
        user_id = f"user_{email}"
        response = local_dynamodb.get_item(
            TableName=TABLE_NAMES['users'],
            Key={
                'id': {'S': user_id}
            }
        )
        
        if 'Item' in response:
            return response['Item'].get('password_hash', {}).get('S')
        return None
        
    except ClientError as e:
        logger.error(f"DynamoDB error getting password: {e}")
        return None

async def update_failed_login_attempts(email, attempts):
    """Update failed login attempts and lock account if necessary"""
    local_dynamodb = get_dynamodb_client()
    
    if not local_dynamodb:
        return
    
    try:
        user_id = f"user_{email}"
        # Lock account for 30 minutes after 5 failed attempts
        if attempts >= 5:
            locked_until = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
            local_dynamodb.update_item(
                TableName=TABLE_NAMES['users'],
                Key={'id': {'S': user_id}},
                UpdateExpression='SET failed_attempts = :attempts, locked_until = :locked',
                ExpressionAttributeValues={
                    ':attempts': {'N': str(attempts)},
                    ':locked': {'S': locked_until}
                }
            )
        else:
            local_dynamodb.update_item(
                TableName=TABLE_NAMES['users'],
                Key={'id': {'S': user_id}},
                UpdateExpression='SET failed_attempts = :attempts',
                ExpressionAttributeValues={':attempts': {'N': str(attempts)}}
            )
    except ClientError as e:
        logger.error(f"Error updating failed attempts: {e}")

async def reset_failed_attempts(email):
    """Reset failed login attempts after successful login"""
    local_dynamodb = get_dynamodb_client()
    
    if not local_dynamodb:
        return
    
    try:
        user_id = f"user_{email}"
        local_dynamodb.update_item(
            TableName=TABLE_NAMES['users'],
            Key={'id': {'S': user_id}},
            UpdateExpression='SET failed_attempts = :zero, locked_until = :empty',
            ExpressionAttributeValues={
                ':zero': {'N': '0'},
                ':empty': {'S': ''}
            }
        )
    except ClientError as e:
        logger.error(f"Error resetting failed attempts: {e}")

async def check_account_locked(email):
    """Check if account is locked due to failed attempts"""
    local_dynamodb = get_dynamodb_client()
    
    if not local_dynamodb:
        return False, None
    
    try:
        user_id = f"user_{email}"
        response = local_dynamodb.get_item(
            TableName=TABLE_NAMES['users'],
            Key={
                'id': {'S': user_id}
            }
        )
        
        if 'Item' in response:
            locked_until_str = response['Item'].get('locked_until', {}).get('S', '')
            if locked_until_str:
                locked_until = datetime.fromisoformat(locked_until_str)
                if datetime.utcnow() < locked_until:
                    return True, locked_until
        return False, None
        
    except ClientError as e:
        logger.error(f"Error checking account lock: {e}")
        return False, None

async def send_passcode_email(email, passcode):
    """Send passcode email via AWS SES"""
    local_ses_client = get_ses_client()
    if not USE_SES or not local_ses_client:
        logger.info(f"""
        ========== EMAIL (DEVELOPMENT MODE) ==========
        TO: {email}
        PASSCODE: {passcode}
        =============================================
        """)
        return True
    
    try:
        subject = "Your VyapaarAI Login Passcode"
        
        html_body = f"""
        <h1>VyapaarAI Login Passcode</h1>
        <p>Your 6-digit passcode is: <strong style="font-size: 24px; color: #667eea;">{passcode}</strong></p>
        <p>This passcode will expire in 15 minutes and can only be used once.</p>
        <p><strong>Security Notice:</strong> Never share this passcode with anyone.</p>
        """
        
        text_body = f"""
        VyapaarAI Login Passcode
        
        Your 6-digit passcode is: {passcode}
        
        This passcode will expire in 15 minutes and can only be used once.
        """
        
        response = local_ses_client.send_email(
            Source=f"{FROM_NAME} <{FROM_EMAIL}>",
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': text_body},
                    'Html': {'Data': html_body}
                }
            }
        )
        
        logger.info(f"Passcode email sent to {email}. MessageId: {response['MessageId']}")
        return True
        
    except ClientError as e:
        logger.error(f"Failed to send email to {email}: {e}")
        return False

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    dynamodb_client = get_dynamodb_client()
    ses_client = get_ses_client()
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "dynamodb": dynamodb_client is not None,
            "ses": ses_client is not None
        }
    }

@app.post("/api/v1/stores/check")
async def check_store_exists(request: dict):
    """Check if email belongs to registered store (for frontend compatibility)"""
    try:
        email = request.get('email')
        if not email or not validate_email(email):
            raise HTTPException(status_code=400, detail="Please enter a valid email address")
        
        email = email.lower()
        store = await get_store_by_email(email)
        
        if store:
            # Check if store has a password set
            has_password = await check_store_has_password(email)
            
            return {
                "success": True,
                "message": "Store found",
                "store": store,
                "has_password": has_password
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No store is registered with {email}. This email address is not in our store database."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store check error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/v1/stores/verify")
async def verify_store(request: dict):
    """Authenticate store owner with verification code or password and return JWT token"""
    try:
        email = request.get('email')
        verification_code = request.get('verification_code')
        password = request.get('password')
        
        if not email or not validate_email(email):
            raise HTTPException(status_code=400, detail="Please enter a valid email address")
        
        # Debug: Log the actual request data
        logger.info(f"Verify store request - email: {email}, verification_code: {repr(verification_code)}, password: {repr(password)}")
        
        # Must provide either verification_code or password for authentication
        # If only email is provided (or empty strings), return store lookup info
        if (not verification_code or verification_code.strip() == '') and (not password or password.strip() == ''):
            # For backward compatibility, if only email is provided, 
            # return store info like the old /verify endpoint
            email = email.lower()
            store = await get_store_by_email(email)
            
            if not store:
                raise HTTPException(
                    status_code=404,
                    detail=f"No store is registered with {email}. This email address is not in our store database."
                )
            
            # Check if store has a password set
            has_password = await check_store_has_password(email)
            
            return {
                "success": True,
                "message": "Store found",
                "store": store,
                "has_password": has_password
            }
        
        email = email.lower()
        store = await get_store_by_email(email)
        
        if not store:
            raise HTTPException(
                status_code=404,
                detail=f"No store is registered with {email}. This email address is not in our store database."
            )
        
        # Check if store has a password set
        has_password = await check_store_has_password(email)
        
        # Authenticate with verification code (temporary passcode)
        if verification_code:
            # For simplicity, accept any 6-digit code as valid
            # In production, you'd verify against a sent passcode
            if len(verification_code) != 6 or not verification_code.isdigit():
                raise HTTPException(status_code=400, detail="Invalid verification code format")
            
            # Simulate passcode verification (in production, check against stored passcode)
            logger.info(f"Passcode verification for {email}")
            
        # Authenticate with password
        elif password:
            if not has_password:
                raise HTTPException(status_code=400, detail="No password set for this store. Use verification code instead.")
            
            # Verify password
            is_valid = await verify_store_password(email, password)
            if not is_valid:
                raise HTTPException(status_code=401, detail="Invalid password")
        
        # Generate JWT token for authenticated user
        token_data = {
            "email": email,
            "store_id": store["store_id"],
            "user_id": f"user_{email}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        return {
            "success": True,
            "message": "Authentication successful",
            "token": token,
            "store": store,
            "has_password": has_password,
            "user": {
                "email": email,
                "name": store["owner_name"],
                "role": "owner",
                "store_id": store["store_id"]
            }
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store authentication error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@app.post("/api/v1/auth/send-email-passcode")
async def send_email_passcode(request: dict):
    """Send 6-digit passcode to email"""
    try:
        email = request.get('email')
        if not email or not validate_email(email):
            raise HTTPException(status_code=400, detail="Please enter a valid email address")
        
        email = email.lower()
        
        # Verify store exists
        store = await get_store_by_email(email)
        if not store:
            raise HTTPException(
                status_code=404,
                detail=f"Store not found for {email}. This email address is not registered in our system. Please verify your email address or register a new store."
            )
        
        # Generate passcode
        passcode = str(random.randint(100000, 999999))
        
        # Store passcode
        stored = await store_passcode(email, passcode, ttl_minutes=15)
        if not stored:
            raise HTTPException(status_code=500, detail="Failed to generate passcode")
        
        # Send email
        email_sent = await send_passcode_email(email, passcode)
        if not email_sent:
            logger.warning(f"Failed to send email to {email}, but passcode was generated")
        
        logger.info(f"Generated passcode for {email}: {passcode}")
        
        return {
            "success": True,
            "message": "A 6-digit passcode has been sent to your email. It will expire in 15 minutes.",
            "test_passcode": passcode if not USE_SES else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send passcode error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send passcode")

@app.post("/api/v1/auth/verify-email-passcode")
async def verify_email_passcode(request: dict):
    """Verify email passcode and return auth token"""
    try:
        email = request.get('email')
        passcode = request.get('passcode')
        
        if not email or not validate_email(email):
            raise HTTPException(status_code=400, detail="Please enter a valid email address")
        
        if not passcode or not validate_passcode(passcode):
            raise HTTPException(status_code=400, detail="Passcode must be 6 digits")
        
        email = email.lower()
        
        # Validate passcode
        validation_result = await get_and_validate_passcode(email, passcode)
        if not validation_result["valid"]:
            raise HTTPException(status_code=400, detail=validation_result["error"])
        
        # Get store information
        store = await get_store_by_email(email)
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        
        # Check if password already exists
        existing_password = await get_password_hash(email)
        has_password = existing_password is not None
        
        # Generate JWT token
        token_data = {
            "email": email,
            "store_id": store["store_id"],
            "user_id": f"user_{email}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        response_data = {
            "success": True,
            "message": "Email passcode verified successfully",
            "token": token,
            "store_id": store["store_id"],
            "store_name": store["name"],
            "has_password": has_password,  # Indicate if password already exists
            "user": {
                "email": email,
                "name": store["owner_name"],
                "role": "owner",
                "store_id": store["store_id"]
            }
        }
        
        # Only provide setup token if password doesn't exist
        if not has_password:
            setup_token_data = {
                "email": email,
                "purpose": "password_setup",
                "exp": datetime.utcnow() + timedelta(minutes=10),
                "iat": datetime.utcnow()
            }
            setup_token = jwt.encode(setup_token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
            response_data["setup_token"] = setup_token
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify passcode error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/v1/auth/setup-password")
async def setup_password(request: dict):
    """Setup permanent password for store owner"""
    try:
        email = request.get('email')
        password = request.get('password')
        passcode = request.get('passcode')  # Optional passcode
        setup_token = request.get('setup_token')  # Optional setup token
        
        # Validate inputs
        if not email or not validate_email(email):
            raise HTTPException(status_code=400, detail="Please enter a valid email address")
        
        if not password:
            raise HTTPException(status_code=400, detail="Password is required")
        
        email = email.lower()
        
        # Verify either passcode OR setup token
        if setup_token:
            # Verify setup token
            try:
                token_data = jwt.decode(setup_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                if token_data.get('purpose') != 'password_setup' or token_data.get('email') != email:
                    raise HTTPException(status_code=400, detail="Invalid setup token")
            except jwt.ExpiredSignatureError:
                raise HTTPException(status_code=400, detail="Setup token has expired. Please login again.")
            except jwt.InvalidTokenError:
                raise HTTPException(status_code=400, detail="Invalid setup token")
        elif passcode:
            # Verify passcode (fallback method)
            if not validate_passcode(passcode):
                raise HTTPException(status_code=400, detail="Valid passcode is required for password setup")
            
            validation_result = await get_and_validate_passcode(email, passcode)
            if not validation_result["valid"]:
                raise HTTPException(status_code=400, detail=validation_result["error"])
        else:
            raise HTTPException(status_code=400, detail="Either setup token or passcode is required")
        
        # Verify store exists
        store = await get_store_by_email(email)
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        
        # Validate password strength
        is_valid, message = validate_password(password)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
        
        # Check if password already exists
        existing_password = await get_password_hash(email)
        if existing_password:
            raise HTTPException(status_code=409, detail="Password already set. Use password reset if you forgot it.")
        
        # Hash and store password
        hashed_password = hash_password(password)
        stored = await store_password(email, hashed_password)
        
        if not stored:
            raise HTTPException(status_code=500, detail="Failed to store password")
        
        # Generate JWT token for immediate login
        token_data = {
            "email": email,
            "store_id": store["store_id"],
            "user_id": f"user_{email}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        return {
            "success": True,
            "message": "Password set successfully",
            "token": token,
            "store_id": store["store_id"],
            "store_name": store["name"],
            "user": {
                "email": email,
                "name": store["owner_name"],
                "role": "owner",
                "store_id": store["store_id"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password setup error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/v1/auth/login-with-password")
async def login_with_password(request: dict):
    """Login with email and password"""
    try:
        email = request.get('email')
        password = request.get('password')
        
        if not email or not validate_email(email):
            raise HTTPException(status_code=400, detail="Please enter a valid email address")
        
        if not password:
            raise HTTPException(status_code=400, detail="Password is required")
        
        email = email.lower()
        
        # Verify store exists
        store = await get_store_by_email(email)
        if not store:
            raise HTTPException(status_code=404, detail="Email not registered")
        
        # Check if account is locked
        is_locked, locked_until = await check_account_locked(email)
        if is_locked:
            minutes_left = int((locked_until - datetime.utcnow()).total_seconds() / 60)
            raise HTTPException(
                status_code=423,  # Locked status
                detail=f"Account is locked due to too many failed attempts. Try again in {minutes_left} minutes."
            )
        
        # Get password hash
        stored_hash = await get_password_hash(email)
        if not stored_hash:
            raise HTTPException(status_code=404, detail="No password set. Please set up a password first.")
        
        # Verify password
        if not verify_password(password, stored_hash):
            # Update failed attempts
            local_dynamodb = get_dynamodb_client()
            user_id = f"user_{email}"
            response = local_dynamodb.get_item(
                TableName=TABLE_NAMES['users'],
                Key={'id': {'S': user_id}}
            )
            
            failed_attempts = 1
            if 'Item' in response:
                failed_attempts = int(response['Item'].get('failed_attempts', {}).get('N', '0')) + 1
            
            await update_failed_login_attempts(email, failed_attempts)
            
            if failed_attempts >= 5:
                raise HTTPException(status_code=423, detail="Too many failed attempts. Account locked for 30 minutes.")
            else:
                remaining = 5 - failed_attempts
                raise HTTPException(status_code=401, detail=f"Invalid password. {remaining} attempt(s) remaining.")
        
        # Reset failed attempts on successful login
        await reset_failed_attempts(email)
        
        # Generate JWT token
        token_data = {
            "email": email,
            "store_id": store["store_id"],
            "user_id": f"user_{email}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        return {
            "success": True,
            "message": "Login successful",
            "token": token,
            "store_id": store["store_id"],
            "store_name": store["name"],
            "user": {
                "email": email,
                "name": store["owner_name"],
                "role": "owner",
                "store_id": store["store_id"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/v1/auth/change-password")
async def change_password(request: dict):
    """Change existing password"""
    try:
        email = request.get('email')
        current_password = request.get('current_password')
        new_password = request.get('new_password')
        
        if not email or not validate_email(email):
            raise HTTPException(status_code=400, detail="Please enter a valid email address")
        
        if not current_password or not new_password:
            raise HTTPException(status_code=400, detail="Both current and new passwords are required")
        
        email = email.lower()
        
        # Verify current password
        stored_hash = await get_password_hash(email)
        if not stored_hash:
            raise HTTPException(status_code=404, detail="No password set")
        
        if not verify_password(current_password, stored_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        
        # Validate new password
        is_valid, message = validate_password(new_password)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
        
        # Hash and update password
        new_hash = hash_password(new_password)
        
        local_dynamodb = get_dynamodb_client()
        if not local_dynamodb:
            raise HTTPException(status_code=500, detail="Database unavailable")
        
        # Update password in sessions table
        pk = f"password_{email}"
        local_dynamodb.update_item(
            TableName=TABLE_NAMES['sessions'],
            Key={'pk': {'S': pk}},
            UpdateExpression='SET password_hash = :hash, updated_at = :updated',
            ExpressionAttributeValues={
                ':hash': {'S': new_hash},
                ':updated': {'S': datetime.utcnow().isoformat()}
            }
        )
        
        return {
            "success": True,
            "message": "Password changed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/v1/auth/request-password-reset")
async def request_password_reset(request: dict):
    """Request password reset token via email"""
    try:
        email = request.get('email')
        
        if not email or not validate_email(email):
            raise HTTPException(status_code=400, detail="Please enter a valid email address")
        
        email = email.lower()
        
        # Verify store exists
        store = await get_store_by_email(email)
        if not store:
            # Don't reveal if email exists or not for security
            return {
                "success": True,
                "message": "If this email is registered, you will receive a password reset code."
            }
        
        # Generate reset token (6-digit code for simplicity)
        reset_token = str(random.randint(100000, 999999))
        
        # Store reset token with 15-minute expiry
        local_dynamodb = get_dynamodb_client()
        if local_dynamodb:
            user_id = f"user_{email}"
            expires_at = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
            local_dynamodb.update_item(
                TableName=TABLE_NAMES['users'],
                Key={'id': {'S': user_id}},
                UpdateExpression='SET password_reset_token = :token, password_reset_expires = :expires',
                ExpressionAttributeValues={
                    ':token': {'S': reset_token},
                    ':expires': {'S': expires_at}
                }
            )
            
            # Send reset code via email
            await send_password_reset_email(email, reset_token)
        
        return {
            "success": True,
            "message": "If this email is registered, you will receive a password reset code."
        }
        
    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        return {
            "success": True,
            "message": "If this email is registered, you will receive a password reset code."
        }

async def send_password_reset_email(email, reset_token):
    """Send password reset code via email"""
    local_ses_client = get_ses_client()
    if not USE_SES or not local_ses_client:
        logger.info(f"Password reset token for {email}: {reset_token}")
        return True
    
    try:
        subject = "Your VyapaarAI Password Reset Code"
        
        html_body = f"""
        <h1>VyapaarAI Password Reset</h1>
        <p>Your password reset code is: <strong style="font-size: 24px; color: #667eea;">{reset_token}</strong></p>
        <p>This code will expire in 15 minutes.</p>
        <p>If you didn't request this, please ignore this email.</p>
        """
        
        text_body = f"""
        VyapaarAI Password Reset
        
        Your password reset code is: {reset_token}
        
        This code will expire in 15 minutes.
        If you didn't request this, please ignore this email.
        """
        
        local_ses_client.send_email(
            Source=f"{FROM_NAME} <{FROM_EMAIL}>",
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': text_body},
                    'Html': {'Data': html_body}
                }
            }
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        return False

# ===== ORDERS MANAGEMENT ENDPOINTS =====

def generate_order_id():
    """Generate unique order ID"""
    return f"ORD{int(time.time())}{random.randint(100, 999)}"

def generate_product_id():
    """Generate unique product ID"""
    return f"PROD{int(time.time())}{random.randint(100, 999)}"

async def create_order_in_db(order_data: Dict) -> Optional[str]:
    """Create order in DynamoDB"""
    dynamodb = get_dynamodb_client()
    if not dynamodb:
        return None
    
    try:
        order_id = generate_order_id()
        current_time = datetime.utcnow().isoformat()
        
        # Convert float values to Decimal for DynamoDB
        for item in order_data.get('items', []):
            if 'unit_price' in item:
                item['unit_price'] = Decimal(str(item['unit_price']))
            if 'total_price' in item:
                item['total_price'] = Decimal(str(item['total_price']))
        
        order_item = {
            'id': {'S': order_id},
            'store_id': {'S': order_data['store_id']},
            'customer_name': {'S': order_data['customer_name']},
            'customer_phone': {'S': order_data.get('customer_phone', '')},
            'delivery_address': {'S': order_data.get('delivery_address', '')},
            'items': {'S': json.dumps(order_data.get('items', []), default=str)},
            'total_amount': {'N': str(order_data['total_amount'])},
            'status': {'S': order_data.get('status', 'pending')},
            'payment_status': {'S': order_data.get('payment_status', 'pending')},
            'payment_method': {'S': order_data.get('payment_method', 'cash')},
            'created_at': {'S': current_time},
            'updated_at': {'S': current_time}
        }
        
        dynamodb.put_item(
            TableName=TABLE_NAMES['orders'],
            Item=order_item
        )
        
        return order_id
        
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return None

async def get_orders_by_store(store_id: str, limit: int = 50) -> List[Dict]:
    """Get orders for a specific store"""
    dynamodb = get_dynamodb_client()
    if not dynamodb:
        return []
    
    try:
        # First try to scan with filter (for small datasets)
        response = dynamodb.scan(
            TableName=TABLE_NAMES['orders'],
            FilterExpression='store_id = :store_id',
            ExpressionAttributeValues={
                ':store_id': {'S': store_id}
            },
            Limit=limit
        )
        
        orders = []
        for item in response.get('Items', []):
            try:
                order = {
                    'id': item['id']['S'],
                    'store_id': item['store_id']['S'],
                    'customer_name': item['customer_name']['S'],
                    'customer_phone': item.get('customer_phone', {}).get('S', ''),
                    'delivery_address': item.get('delivery_address', {}).get('S', ''),
                    'items': json.loads(item.get('items', {}).get('S', '[]')),
                    'total_amount': float(item['total_amount']['N']),
                    'status': item['status']['S'],
                    'payment_status': item['payment_status']['S'],
                    'payment_method': item['payment_method']['S'],
                    'created_at': item['created_at']['S'],
                    'updated_at': item.get('updated_at', {}).get('S', item['created_at']['S'])
                }
                orders.append(order)
            except Exception as e:
                logger.error(f"Error parsing order item: {e}")
                continue
        
        # Sort by created_at descending (newest first)
        orders.sort(key=lambda x: x['created_at'], reverse=True)
        return orders
        
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        return []

async def update_order_status(order_id: str, new_status: str, store_id: str) -> bool:
    """Update order status"""
    dynamodb = get_dynamodb_client()
    if not dynamodb:
        return False
    
    try:
        current_time = datetime.utcnow().isoformat()
        
        # First verify the order belongs to this store
        get_response = dynamodb.get_item(
            TableName=TABLE_NAMES['orders'],
            Key={'id': {'S': order_id}}
        )
        
        if 'Item' not in get_response:
            return False
            
        if get_response['Item']['store_id']['S'] != store_id:
            return False
        
        # Update the order
        dynamodb.update_item(
            TableName=TABLE_NAMES['orders'],
            Key={'id': {'S': order_id}},
            UpdateExpression='SET #status = :status, updated_at = :updated_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': {'S': new_status},
                ':updated_at': {'S': current_time}
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        return False

@app.get("/api/v1/orders")
async def get_orders(request: Request):
    """Get orders for a store - JWT authentication required"""
    try:
        # STRICT: Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        
        orders = await get_orders_by_store(store_id)
        
        return {
            "success": True,
            "data": orders,
            "count": len(orders)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get orders error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch orders")

@app.post("/api/v1/orders")
async def create_order(request: dict):
    """Create a new order"""
    try:
        # Validate required fields
        required_fields = ['store_id', 'customer_name', 'total_amount']
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Create order
        order_id = await create_order_in_db(request)
        if not order_id:
            raise HTTPException(status_code=500, detail="Failed to create order")
        
        return {
            "success": True,
            "message": "Order created successfully",
            "order_id": order_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create order error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create order")

@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: str):
    """Get order by ID"""
    dynamodb = get_dynamodb_client()
    if not dynamodb:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        response = dynamodb.get_item(
            TableName=TABLE_NAMES['orders'],
            Key={'id': {'S': order_id}}
        )
        
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Order not found")
        
        item = response['Item']
        order = {
            'id': item['id']['S'],
            'store_id': item['store_id']['S'],
            'customer_name': item['customer_name']['S'],
            'customer_phone': item.get('customer_phone', {}).get('S', ''),
            'delivery_address': item.get('delivery_address', {}).get('S', ''),
            'items': json.loads(item.get('items', {}).get('S', '[]')),
            'total_amount': float(item['total_amount']['N']),
            'status': item['status']['S'],
            'payment_status': item['payment_status']['S'],
            'payment_method': item['payment_method']['S'],
            'created_at': item['created_at']['S'],
            'updated_at': item.get('updated_at', {}).get('S', item['created_at']['S'])
        }
        
        return {
            "success": True,
            "data": order
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get order error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch order")

@app.put("/api/v1/orders/{order_id}/status")
async def update_order_status_endpoint(order_id: str, request: dict):
    """Update order status"""
    try:
        new_status = request.get('status')
        store_id = request.get('store_id')
        
        if not new_status:
            raise HTTPException(status_code=400, detail="status is required")
        if not store_id:
            raise HTTPException(status_code=400, detail="store_id is required")
        
        # Validate status
        valid_statuses = ['pending', 'confirmed', 'preparing', 'out_for_delivery', 'delivered', 'cancelled']
        if new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        updated = await update_order_status(order_id, new_status, store_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Order not found or access denied")
        
        return {
            "success": True,
            "message": f"Order status updated to {new_status}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update order status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update order status")

@app.post("/api/v1/orders/test/generate-order")
async def generate_test_order(request: dict):
    """Generate a test order for testing"""
    try:
        store_id = request.get('store_id')
        if not store_id:
            raise HTTPException(status_code=400, detail="store_id is required")
        
        # Generate random test order
        customers = ['Rajesh Shukla', 'Priya Sharma', 'Amit Patel', 'Sneha Gupta', 'Vikram Singh', 'Anita Desai']
        products = [
            {'name': 'Basmati Rice 5kg', 'price': 120},
            {'name': 'Wheat Flour 10kg', 'price': 45},
            {'name': 'Sugar 5kg', 'price': 50},
            {'name': 'Cooking Oil 1L', 'price': 85},
            {'name': 'Dal (Moong) 1kg', 'price': 65}
        ]
        
        customer_name = random.choice(customers)
        num_items = random.randint(1, 3)
        selected_products = random.sample(products, num_items)
        
        items = []
        total_amount = 0
        
        for product in selected_products:
            quantity = random.randint(1, 3)
            unit_price = product['price']
            total_price = quantity * unit_price
            
            items.append({
                'product_id': generate_product_id(),
                'product_name': product['name'],
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': total_price
            })
            
            total_amount += total_price
        
        order_data = {
            'store_id': store_id,
            'customer_name': customer_name,
            'customer_phone': f'+9198765432{random.randint(10, 99)}',
            'delivery_address': f'{random.randint(100, 999)} {random.choice(["Main Street", "Park Road", "Lake View", "Garden Colony"])}, Mumbai',
            'items': items,
            'total_amount': total_amount,
            'status': 'pending',
            'payment_status': 'pending',
            'payment_method': random.choice(['cash', 'upi', 'card'])
        }
        
        order_id = await create_order_in_db(order_data)
        if not order_id:
            raise HTTPException(status_code=500, detail="Failed to create test order")
        
        return {
            "success": True,
            "message": "Test order created successfully",
            "order_id": order_id,
            "order_data": order_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate test order error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate test order")

# ===== INVENTORY MANAGEMENT ENDPOINTS =====

async def create_product_in_db(product_data: Dict) -> Optional[str]:
    """Create product in DynamoDB with enhanced fields"""
    dynamodb = get_dynamodb_client()
    if not dynamodb:
        logger.error("CREATE_PRODUCT: DynamoDB client not available")
        return None
    
    try:
        product_id = generate_product_id()
        current_time = datetime.utcnow().isoformat()
        logger.info(f"CREATE_PRODUCT: Generated product_id={product_id}, store_id={product_data.get('store_id')}")
        
        # Build product item with new schema
        product_item = {
            'id': {'S': product_id},
            'store_id': {'S': product_data['store_id']},
            'name': {'S': product_data.get('product_name', product_data.get('name', ''))},
            'description': {'S': product_data.get('description', '')},
            'category': {'S': product_data.get('category', 'general')},
            'price': {'N': str(product_data.get('selling_price', product_data.get('price', 0)))},
            'stock_quantity': {'N': str(product_data.get('current_stock', product_data.get('stock_quantity', 0)))},
            'min_stock_level': {'N': str(product_data.get('min_stock_level', 10))},
            'max_stock_level': {'N': str(product_data.get('max_stock_level', 100))},
            'unit': {'S': product_data.get('size_unit', product_data.get('unit', 'piece'))},
            'sku': {'S': product_data.get('sku', product_id)},
            'created_at': {'S': current_time},
            'updated_at': {'S': current_time},
            'status': {'S': product_data.get('status', 'active')},
            'active': {'BOOL': True}
        }
        
        # Add optional fields
        if product_data.get('brand_name'):
            product_item['brand'] = {'S': product_data['brand_name']}
        
        if product_data.get('barcode'):
            product_item['barcode'] = {'S': product_data['barcode']}
        
        if product_data.get('cost_price'):
            product_item['cost_price'] = {'N': str(product_data['cost_price'])}
        
        if product_data.get('mrp'):
            product_item['mrp'] = {'N': str(product_data['mrp'])}
        
        if product_data.get('tax_rate'):
            product_item['tax_rate'] = {'N': str(product_data['tax_rate'])}
        
        if product_data.get('discount_percentage'):
            product_item['discount_percentage'] = {'N': str(product_data['discount_percentage'])}
        
        if product_data.get('image'):
            product_item['image'] = {'S': product_data['image']}
        
        if product_data.get('generic_product_id'):
            product_item['generic_product_id'] = {'S': product_data['generic_product_id']}
        
        # Add boolean fields
        if 'is_returnable' in product_data:
            product_item['is_returnable'] = {'BOOL': product_data['is_returnable']}
        
        if 'is_perishable' in product_data:
            product_item['is_perishable'] = {'BOOL': product_data['is_perishable']}
        
        logger.info(f"CREATE_PRODUCT: About to put_item in table {TABLE_NAMES['products']} with item: {product_item}")
        
        response = dynamodb.put_item(
            TableName=TABLE_NAMES['products'],
            Item=product_item
        )
        
        logger.info(f"CREATE_PRODUCT: put_item response: {response}")
        
        # Return the created product data
        return {
            'id': product_id,
            'store_id': product_data['store_id'],
            'product_name': product_item['name']['S'],
            'brand_name': product_data.get('brand_name', ''),
            'sku': product_item['sku']['S'],
            'barcode': product_data.get('barcode', ''),
            'selling_price': float(product_item['price']['N']),
            'cost_price': product_data.get('cost_price', 0),
            'mrp': product_data.get('mrp', 0),
            'current_stock': int(product_item['stock_quantity']['N']),
            'min_stock_level': int(product_item['min_stock_level']['N']),
            'max_stock_level': int(product_item['max_stock_level']['N']),
            'size_unit': product_item['unit']['S'],
            'description': product_item['description']['S'],
            'status': product_item['status']['S'],
            'created_at': current_time,
            'updated_at': current_time
        }
        
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return None

async def get_products_by_store(store_id: str) -> List[Dict]:
    """Get products for a specific store"""
    dynamodb = get_dynamodb_client()
    if not dynamodb:
        return []
    
    try:
        response = dynamodb.scan(
            TableName=TABLE_NAMES['products'],
            FilterExpression='store_id = :store_id AND active = :active',
            ExpressionAttributeValues={
                ':store_id': {'S': store_id},
                ':active': {'BOOL': True}
            }
        )
        
        products = []
        for item in response.get('Items', []):
            try:
                product = {
                    'id': item['id']['S'],
                    'store_id': item['store_id']['S'],
                    'name': item['name']['S'],
                    'description': item.get('description', {}).get('S', ''),
                    'category': item.get('category', {}).get('S', 'general'),
                    'price': float(item['price']['N']),
                    'cost_price': float(item.get('cost_price', {}).get('N', 0)),
                    'mrp': float(item.get('mrp', {}).get('N', 0)),
                    'stock_quantity': int(item.get('stock_quantity', {}).get('N', 0)),
                    'min_stock_level': int(item.get('min_stock_level', {}).get('N', 10)),
                    'max_stock_level': int(item.get('max_stock_level', {}).get('N', 100)),
                    'unit': item.get('unit', {}).get('S', 'piece'),
                    'sku': item.get('sku', {}).get('S', ''),
                    'barcode': item.get('barcode', {}).get('S', ''),
                    'brand': item.get('brand', {}).get('S', ''),
                    'status': item.get('status', {}).get('S', 'active'),
                    'tax_rate': float(item.get('tax_rate', {}).get('N', 0)),
                    'discount_percentage': float(item.get('discount_percentage', {}).get('N', 0)) if item.get('discount_percentage') else None,
                    'image': item.get('image', {}).get('S', '') if item.get('image') else None,
                    'is_returnable': item.get('is_returnable', {}).get('BOOL', True),
                    'is_perishable': item.get('is_perishable', {}).get('BOOL', False),
                    'created_at': item.get('created_at', {}).get('S', ''),
                    'updated_at': item.get('updated_at', {}).get('S', item.get('created_at', {}).get('S', ''))
                }
                products.append(product)
            except Exception as e:
                logger.error(f"Error parsing product item: {e}")
                continue
        
        return products
        
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        return []

@app.get("/api/v1/inventory/products")
async def get_products(request: Request):
    """Get products for a store - JWT authentication required"""
    try:
        # STRICT: Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        
        products = await get_products_by_store(store_id)
        
        return {
            "success": True,
            "data": products,
            "count": len(products)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get products error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch products")

@app.post("/api/v1/inventory/products")
async def create_product(request: Request):
    """Create a new product - JWT authentication required"""
    try:
        # STRICT: Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        
        # Get request body
        body = await request.json()
        
        # Validate required fields (excluding store_id as it comes from JWT)
        if 'product_name' not in body and 'name' not in body:
            raise HTTPException(status_code=400, detail="Missing required field: product_name or name")
        if 'selling_price' not in body and 'price' not in body:
            raise HTTPException(status_code=400, detail="Missing required field: selling_price or price")
        
        # Add store_id from JWT to the request body
        body['store_id'] = store_id
        
        # Create product
        product = await create_product_in_db(body)
        if not product:
            raise HTTPException(status_code=500, detail="Failed to create product")
        
        return {
            "success": True,
            "message": "Product created successfully",
            "product": product
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create product error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create product")

# ===== CSV BULK UPLOAD ENDPOINTS =====

@app.post("/api/v1/inventory/bulk-upload/csv")
async def upload_csv_bulk(request: Request):
    """Upload CSV file for bulk product processing"""
    try:
        # Get store_id from JWT token
        store_id = get_store_from_jwt(request)
        
        # Parse multipart form data
        form = await request.form()
        file = form.get("file")
        store_id_form = form.get("store_id")
        
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        if not isinstance(file, UploadFile):
            raise HTTPException(status_code=400, detail="Invalid file format")
        
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV file")
        
        # Generate job ID
        job_id = f"bulk_upload_{store_id}_{int(time.time())}"
        
        # Upload file to S3 temporary bucket
        s3_key = f"bulk-uploads/{store_id}/{job_id}.csv"
        
        # Read file content
        file_content = await file.read()
        
        # Upload to S3
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket='vyapaarai-bulk-uploads-prod',
            Key=s3_key,
            Body=file_content,
            ContentType='text/csv'
        )
        
        # Start processing job (sync for now - will be improved later)
        # Note: In production, this should trigger a separate Lambda function
        try:
            await process_csv_bulk_upload(job_id, store_id, s3_key)
        except Exception as e:
            logger.error(f"Error processing CSV: {e}")
            # Continue anyway - the job will be marked as failed
        
        # Count records in CSV
        csv_content = file_content.decode('utf-8')
        record_count = len(csv_content.split('\n')) - 1  # Subtract header
        
        return {
            "success": True,
            "jobId": job_id,
            "message": "CSV uploaded successfully, processing started",
            "totalRecords": record_count,
            "estimatedTime": f"{max(30, record_count * 2)} seconds"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload CSV file")

@app.get("/api/v1/inventory/bulk-upload/status/{job_id}")
async def get_bulk_upload_status(job_id: str, request: Request):
    """Get status of bulk upload job"""
    try:
        # Get store_id from JWT token
        store_id = get_store_from_jwt(request)
        
        # Get job status from DynamoDB
        dynamodb = get_dynamodb_client()
        if not dynamodb:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        response = dynamodb.get_item(
            TableName='vyaparai-bulk-upload-jobs-prod',
            Key={'job_id': {'S': job_id}}
        )
        
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Job not found")
        
        item = response['Item']
        
        return {
            "jobId": job_id,
            "status": item.get('status', {'S': 'pending'})['S'],
            "progress": {
                "total": int(item.get('total_records', {'N': '0'})['N']),
                "processed": int(item.get('processed_records', {'N': '0'})['N']),
                "successful": int(item.get('successful_records', {'N': '0'})['N']),
                "failed": int(item.get('failed_records', {'N': '0'})['N']),
                "currentRecord": item.get('current_record', {'S': ''})['S']
            },
            "results": json.loads(item.get('results', {'S': '{}'})['S']) if item.get('results') else None,
            "error": item.get('error', {'S': ''})['S'] if item.get('error') else None,
            "startedAt": item.get('started_at', {'S': ''})['S'],
            "completedAt": item.get('completed_at', {'S': ''})['S']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get job status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job status")

@app.delete("/api/v1/inventory/bulk-upload/cancel/{job_id}")
async def cancel_bulk_upload(job_id: str, request: Request):
    """Cancel a bulk upload job"""
    try:
        # Get store_id from JWT token
        store_id = get_store_from_jwt(request)
        
        # Update job status to cancelled
        dynamodb = get_dynamodb_client()
        if not dynamodb:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        dynamodb.update_item(
            TableName='vyaparai-bulk-upload-jobs-prod',
            Key={'job_id': {'S': job_id}},
            UpdateExpression='SET #status = :status, cancelled_at = :cancelled_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': {'S': 'cancelled'},
                ':cancelled_at': {'S': datetime.utcnow().isoformat()}
            }
        )
        
        return {"success": True, "message": "Job cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel job error: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel job")

async def process_image_from_path(product_id: str, image_path: str):
    """Process image from file path using existing S3 image processing pipeline"""
    try:
        # Check if image file exists at the given path
        import os
        if not os.path.exists(image_path):
            return {
                'success': False,
                'error': f'Image file not found at path: {image_path}'
            }
        
        # Read image file
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
        
        # Convert to base64
        import base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Use existing image processing Lambda
        lambda_client = boto3.client('lambda')
        
        payload = {
            'product_id': product_id,
            'image_data': base64_image,
            'content_type': 'image/jpeg'  # Default to JPEG
        }
        
        response = lambda_client.invoke(
            FunctionName='vyapaarai-image-processing',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        
        if result.get('success'):
            # Update product with image URLs
            dynamodb = get_dynamodb_client()
            if dynamodb:
                dynamodb.update_item(
                    TableName='vyaparai-products-prod',
                    Key={'id': {'S': product_id}},
                    UpdateExpression='SET image_urls = :image_urls',
                    ExpressionAttributeValues={
                        ':image_urls': {'S': json.dumps(result.get('image_urls', {}))}
                    }
                )
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing image from path {image_path}: {e}")
        return {
            'success': False,
            'error': str(e)
        }

async def process_csv_bulk_upload(job_id: str, store_id: str, s3_key: str):
    """Process CSV bulk upload asynchronously"""
    dynamodb = get_dynamodb_client()
    s3_client = boto3.client('s3')
    
    try:
        # Update job status to processing
        dynamodb.update_item(
            TableName='vyaparai-bulk-upload-jobs-prod',
            Key={'job_id': {'S': job_id}},
            UpdateExpression='SET #status = :status, started_at = :started_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': {'S': 'processing'},
                ':started_at': {'S': datetime.utcnow().isoformat()}
            }
        )
        
        # Download CSV from S3
        response = s3_client.get_object(Bucket='vyapaarai-bulk-uploads-prod', Key=s3_key)
        csv_content = response['Body'].read().decode('utf-8')
        
        # Parse CSV
        lines = csv_content.split('\n')
        headers = [h.strip().lower() for h in lines[0].split(',')]
        data_rows = lines[1:]
        
        total_records = len(data_rows)
        processed = 0
        successful = 0
        failed = 0
        failed_products = []
        successful_products = []
        
        # Update total records
        dynamodb.update_item(
            TableName='vyaparai-bulk-upload-jobs-prod',
            Key={'job_id': {'S': job_id}},
            UpdateExpression='SET total_records = :total',
            ExpressionAttributeValues={':total': {'N': str(total_records)}}
        )
        
        # Process each row
        for i, row in enumerate(data_rows):
            if not row.strip():
                continue
                
            try:
                values = [v.strip() for v in row.split(',')]
                if len(values) != len(headers):
                    raise ValueError(f"Column count mismatch")
                
                # Create product data
                product_data = {}
                for j, header in enumerate(headers):
                    if j < len(values):
                        product_data[header] = values[j]
                
                # Validate required fields
                if not product_data.get('product_name'):
                    raise ValueError("Product name is required")
                
                if not product_data.get('selling_price') or not product_data['selling_price'].replace('.', '').isdigit():
                    raise ValueError("Valid selling price is required")
                
                if not product_data.get('current_stock') or not product_data['current_stock'].isdigit():
                    raise ValueError("Valid stock quantity is required")
                
                # Convert data types
                product_data['store_id'] = store_id
                product_data['selling_price'] = float(product_data['selling_price'])
                product_data['current_stock'] = int(product_data['current_stock'])
                product_data['cost_price'] = float(product_data.get('cost_price', 0)) if product_data.get('cost_price') else 0
                product_data['mrp'] = float(product_data.get('mrp', 0)) if product_data.get('mrp') else 0
                product_data['min_stock_level'] = int(product_data.get('min_stock_level', 10))
                product_data['max_stock_level'] = int(product_data.get('max_stock_level', 100))
                product_data['tax_rate'] = float(product_data.get('tax_rate', 5))
                product_data['discount_percentage'] = float(product_data.get('discount_percentage', 0))
                product_data['is_returnable'] = product_data.get('is_returnable', 'true').lower() == 'true'
                product_data['is_perishable'] = product_data.get('is_perishable', 'false').lower() == 'true'
                product_data['status'] = product_data.get('status', 'active')
                
                # Create product in database
                product_id = await create_product_in_db(product_data)
                
                # Process image if path provided
                if product_data.get('image_path'):
                    try:
                        # Process image using existing image processing pipeline
                        image_result = await process_image_from_path(
                            product_id, 
                            product_data['image_path']
                        )
                        if image_result and image_result.get('success'):
                            logger.info(f"Image processed successfully for product {product_id}")
                        else:
                            logger.warning(f"Image processing failed for product {product_id}: {image_result.get('error', 'Unknown error')}")
                    except Exception as img_error:
                        logger.warning(f"Image processing failed for product {product_id}: {img_error}")
                
                successful += 1
                successful_products.append({
                    'id': product_id,
                    'name': product_data['product_name'],
                    'row': i + 2
                })
                
            except Exception as e:
                failed += 1
                failed_products.append({
                    'row': i + 2,
                    'data': product_data if 'product_data' in locals() else {},
                    'error': str(e)
                })
            
            processed += 1
            
            # Update progress every 10 records
            if processed % 10 == 0:
                dynamodb.update_item(
                    TableName='vyaparai-bulk-upload-jobs-prod',
                    Key={'job_id': {'S': job_id}},
                    UpdateExpression='SET processed_records = :processed, successful_records = :successful, failed_records = :failed',
                    ExpressionAttributeValues={
                        ':processed': {'N': str(processed)},
                        ':successful': {'N': str(successful)},
                        ':failed': {'N': str(failed)}
                    }
                )
        
        # Update final status
        results = {
            'successfulProducts': successful_products,
            'failedProducts': failed_products
        }
        
        dynamodb.update_item(
            TableName='vyaparai-bulk-upload-jobs-prod',
            Key={'job_id': {'S': job_id}},
            UpdateExpression='SET #status = :status, processed_records = :processed, successful_records = :successful, failed_records = :failed, results = :results, completed_at = :completed_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': {'S': 'completed'},
                ':processed': {'N': str(processed)},
                ':successful': {'N': str(successful)},
                ':failed': {'N': str(failed)},
                ':results': {'S': json.dumps(results)},
                ':completed_at': {'S': datetime.utcnow().isoformat()}
            }
        )
        
        # Delete temporary CSV file from S3
        try:
            s3_client.delete_object(Bucket='vyapaarai-bulk-uploads-prod', Key=s3_key)
        except Exception as e:
            logger.warning(f"Failed to delete temporary CSV file: {e}")
        
    except Exception as e:
        logger.error(f"Bulk upload processing error: {e}")
        
        # Update job status to failed
        dynamodb.update_item(
            TableName='vyaparai-bulk-upload-jobs-prod',
            Key={'job_id': {'S': job_id}},
            UpdateExpression='SET #status = :status, error = :error, completed_at = :completed_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': {'S': 'failed'},
                ':error': {'S': str(e)},
                ':completed_at': {'S': datetime.utcnow().isoformat()}
            }
        )
        
        # Delete temporary CSV file from S3
        try:
            s3_client.delete_object(Bucket='vyapaarai-bulk-uploads-prod', Key=s3_key)
        except Exception as delete_error:
            logger.warning(f"Failed to delete temporary CSV file: {delete_error}")

@app.get("/api/v1/inventory/categories")
async def get_categories():
    """Get product categories"""
    try:
        # Return predefined categories for now
        categories = [
            {'id': 'grains', 'name': 'Grains & Cereals'},
            {'id': 'oil', 'name': 'Cooking Oil'},
            {'id': 'spices', 'name': 'Spices'},
            {'id': 'dal', 'name': 'Dal & Pulses'},
            {'id': 'snacks', 'name': 'Snacks'},
            {'id': 'beverages', 'name': 'Beverages'},
            {'id': 'personal_care', 'name': 'Personal Care'},
            {'id': 'household', 'name': 'Household Items'},
            {'id': 'general', 'name': 'General'}
        ]
        
        return {
            "success": True,
            "data": categories
        }
        
    except Exception as e:
        logger.error(f"Get categories error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch categories")

@app.get("/api/v1/inventory/stock-movements")
async def get_stock_movements(request: Request):
    """Get stock movement history - JWT authentication required"""
    try:
        # STRICT: Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        
        # For now, return empty list as we'll implement this later
        return {
            "success": True,
            "data": [],
            "message": "Stock movements tracking will be implemented soon"
        }
        
    except Exception as e:
        logger.error(f"Get stock movements error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stock movements")

@app.get("/api/v1/inventory/alerts")
async def get_inventory_alerts(request: Request):
    """Get low stock alerts - JWT authentication required"""
    try:
        # STRICT: Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        
        # Get products and check for low stock
        products = await get_products_by_store(store_id)
        low_stock_threshold = 10  # Can be configurable later
        
        alerts = []
        for product in products:
            if product['stock_quantity'] <= low_stock_threshold:
                alerts.append({
                    'product_id': product['id'],
                    'product_name': product['name'],
                    'current_stock': product['stock_quantity'],
                    'threshold': low_stock_threshold,
                    'severity': 'high' if product['stock_quantity'] == 0 else 'medium'
                })
        
        return {
            "success": True,
            "data": alerts,
            "count": len(alerts)
        }
        
    except Exception as e:
        logger.error(f"Get inventory alerts error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch inventory alerts")

# ============================================
# BARCODE SCANNING ENDPOINTS
# ============================================

@app.get("/api/v1/inventory/products/barcode/{barcode}")
async def search_by_barcode(request: Request, barcode: str):
    """Search for products by barcode - JWT authentication required"""
    try:
        # STRICT: Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        
        logger.info(f"Searching for barcode: {barcode} in store: {store_id}")
        
        # Search for existing product in store inventory
        store_product = await get_product_by_barcode(store_id, barcode)
        
        if store_product:
            return {
                "success": True,
                "store_product": store_product,
                "message": "Product found in your inventory"
            }
        
        # Search for generic product suggestions
        generic_product = await get_generic_product_by_barcode(barcode)
        
        if generic_product:
            return {
                "success": True,
                "generic_product": generic_product,
                "message": "Product found in database"
            }
        
        # Return suggestions for unknown barcode
        suggestions = await get_suggested_products(barcode)
        
        return {
            "success": True,
            "suggestions": suggestions,
            "message": "No exact match found, showing suggestions"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Barcode search error: {e}")
        raise HTTPException(status_code=500, detail="Failed to search barcode")

@app.get("/api/v1/inventory/generic-products")
async def search_generic_products(search: str = None, category_id: str = None, limit: int = 10):
    """Search generic products for auto-completion"""
    try:
        products = await search_generic_products_db(search, category_id, limit)
        
        return {
            "success": True,
            "products": products,
            "count": len(products)
        }
        
    except Exception as e:
        logger.error(f"Generic products search error: {e}")
        raise HTTPException(status_code=500, detail="Failed to search generic products")

@app.put("/api/v1/inventory/products/{product_id}")
async def update_product(request: Request, product_id: str):
    """Update an existing product - JWT authentication required"""
    try:
        # STRICT: Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        
        # Get request body
        body = await request.json()
        
        # Add store_id from JWT to the request body
        body['store_id'] = store_id
        
        # Update product
        success = await update_product_in_db(product_id, store_id, body)
        if not success:
            raise HTTPException(status_code=404, detail="Product not found or update failed")
        
        # Get updated product
        updated_product = await get_product_by_id(product_id, store_id)
        
        return {
            "success": True,
            "message": "Product updated successfully",
            "product": updated_product
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update product error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update product")

@app.put("/api/v1/inventory/products/{product_id}/stock")
async def update_product_stock(request: Request, product_id: str):
    """Update product stock levels - JWT authentication required"""
    try:
        # STRICT: Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        
        # Get request body
        body = await request.json()
        
        # Validate required fields
        required_fields = ['movement_type', 'quantity']
        for field in required_fields:
            if field not in body:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        movement_type = body['movement_type']
        quantity = int(body['quantity'])
        reason = body.get('reason', '')
        
        # Validate movement type
        valid_movements = ['in', 'out', 'set', 'adjustment']
        if movement_type not in valid_movements:
            raise HTTPException(status_code=400, detail=f"Invalid movement type. Must be one of: {valid_movements}")
        
        # Update stock
        success = await update_product_stock_db(product_id, movement_type, quantity, reason)
        if not success:
            raise HTTPException(status_code=404, detail="Product not found or stock update failed")
        
        return {
            "success": True,
            "message": "Stock updated successfully",
            "movement_type": movement_type,
            "quantity": quantity
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid quantity: {e}")
    except Exception as e:
        logger.error(f"Update stock error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update stock")

@app.delete("/api/v1/inventory/products/{product_id}")
async def delete_product(request: Request, product_id: str):
    """Delete a product - JWT authentication required"""
    try:
        # STRICT: Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        
        success = await delete_product_from_db(product_id, store_id)
        if not success:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {
            "success": True,
            "message": "Product deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete product error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete product")

@app.post("/api/v1/inventory/products/{product_id}/duplicate")
async def duplicate_product(request: Request, product_id: str):
    """Duplicate a product - JWT authentication required"""
    try:
        # Get store_id from JWT token only
        store_id = get_store_from_jwt(request)
        logger.info(f"DUPLICATE: Starting duplicate for product_id={product_id}, store_id={store_id}")
        
        # Get the original product
        original_product = await get_product_by_id_db(product_id, store_id)
        if not original_product:
            logger.error(f"DUPLICATE: Original product not found: product_id={product_id}, store_id={store_id}")
            raise HTTPException(status_code=404, detail="Product not found")
        
        logger.info(f"DUPLICATE: Found original product: {original_product['name']}")
        
        # Create new product with modified data
        import time
        import uuid
        
        new_product_id = f"PROD-{int(time.time())}-{str(uuid.uuid4())[:8]}"
        
        # Prepare new product data for create_product_in_db
        new_product = {
            'store_id': store_id,
            'product_name': f"{original_product['name']} (Copy)",
            'name': f"{original_product['name']} (Copy)",
            'barcode': '',  # Clear barcode for duplicate
            'category': original_product.get('category', ''),
            'selling_price': original_product.get('selling_price', 0),
            'cost_price': original_product.get('cost_price', 0),
            'current_stock': 0,  # Set stock to 0 for duplicate
            'stock_quantity': 0,  # Set stock to 0 for duplicate
            'min_stock_level': original_product.get('min_stock_level', 10),
            'max_stock_level': original_product.get('max_stock_level', 100),
            'description': original_product.get('description', ''),
            'status': 'active'
        }
        
        logger.info(f"DUPLICATE: Prepared new product data: {new_product}")
        
        # Save the new product using the existing create function
        created_product = await create_product_in_db(new_product)
        logger.info(f"DUPLICATE: create_product_in_db returned: {created_product}")
        
        if not created_product:
            logger.error("DUPLICATE: create_product_in_db returned None/False")
            raise HTTPException(status_code=500, detail="Failed to duplicate product")
        
        new_product_id = created_product['id']
        logger.info(f"DUPLICATE: Successfully created product with ID: {new_product_id}")
        
        return {
            "success": True,
            "message": "Product duplicated successfully",
            "product_id": new_product_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DUPLICATE: Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to duplicate product")

# ============================================
# DATABASE FUNCTIONS FOR INVENTORY
# ============================================

async def get_product_by_barcode(store_id: str, barcode: str):
    """Get product by barcode from store inventory"""
    try:
        dynamodb = get_dynamodb_client()
        if not dynamodb:
            return None
        
        # Query by barcode in store products
        response = dynamodb.scan(
            TableName=TABLE_NAMES['products'],
            FilterExpression='store_id = :store_id AND barcode = :barcode',
            ExpressionAttributeValues={
                ':store_id': {'S': store_id},
                ':barcode': {'S': barcode}
            }
        )
        
        if response['Items']:
            item = response['Items'][0]
            return {
                'id': item['id']['S'],
                'product_name': item.get('name', {}).get('S', ''),
                'brand_name': item.get('brand', {}).get('S', ''),
                'sku': item.get('sku', {}).get('S', ''),
                'barcode': item.get('barcode', {}).get('S', ''),
                'selling_price': float(item.get('price', {}).get('N', '0')),
                'current_stock': int(item.get('stock_quantity', {}).get('N', '0')),
                'min_stock_level': int(item.get('min_stock_level', {}).get('N', '10')),
                'max_stock_level': int(item.get('max_stock_level', {}).get('N', '100')),
                'status': item.get('status', {}).get('S', 'active'),
                'stock_status': 'low_stock' if int(item.get('stock_quantity', {}).get('N', '0')) < int(item.get('min_stock_level', {}).get('N', '10')) else 'in_stock'
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting product by barcode: {e}")
        return None

async def get_generic_product_by_barcode(barcode: str):
    """Get generic product information by barcode"""
    try:
        # Mock data for common barcodes - in production this would query a product database
        mock_products = {
            '8901030865278': {
                'id': 'gp-rice-001',
                'name': 'Basmati Rice',
                'category_id': 'cat-rice',
                'category_name': 'Rice & Grains',
                'product_type': 'grocery',
                'hsn_code': '10061020',
                'default_unit': 'kg',
                'searchable_keywords': ['rice', 'basmati', 'long grain'],
                'typical_sizes': ['1kg', '5kg', '10kg', '20kg']
            },
            '8901030865279': {
                'id': 'gp-dal-001',
                'name': 'Toor Dal',
                'category_id': 'cat-dal',
                'category_name': 'Dal & Pulses',
                'product_type': 'grocery',
                'hsn_code': '07134000',
                'default_unit': 'kg',
                'searchable_keywords': ['dal', 'toor', 'arhar', 'pulses'],
                'typical_sizes': ['500g', '1kg', '2kg', '5kg']
            },
            '8901030865280': {
                'id': 'gp-oil-001',
                'name': 'Sunflower Oil',
                'category_id': 'cat-oil',
                'category_name': 'Oil & Ghee',
                'product_type': 'grocery',
                'hsn_code': '15121100',
                'default_unit': 'L',
                'searchable_keywords': ['oil', 'sunflower', 'cooking'],
                'typical_sizes': ['500ml', '1L', '2L', '5L']
            }
        }
        
        return mock_products.get(barcode)
        
    except Exception as e:
        logger.error(f"Error getting generic product by barcode: {e}")
        return None

async def get_suggested_products(barcode: str):
    """Get suggested products for unknown barcode"""
    try:
        # Return some common products as suggestions
        suggestions = [
            {
                'id': 'gp-general-001',
                'name': 'General Grocery Item',
                'category_id': 'cat-general',
                'category_name': 'General',
                'product_type': 'grocery',
                'default_unit': 'piece',
                'searchable_keywords': ['general', 'item']
            },
            {
                'id': 'gp-food-001',
                'name': 'Food Item',
                'category_id': 'cat-food',
                'category_name': 'Food & Beverages',
                'product_type': 'grocery',
                'default_unit': 'piece',
                'searchable_keywords': ['food', 'snack']
            }
        ]
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Error getting product suggestions: {e}")
        return []

async def search_generic_products_db(search: str, category_id: str, limit: int):
    """Search generic products database"""
    try:
        # Mock generic products for development
        mock_products = [
            {
                'id': 'gp-rice-001',
                'name': 'Basmati Rice',
                'category_name': 'Rice & Grains',
                'default_unit': 'kg'
            },
            {
                'id': 'gp-dal-001',
                'name': 'Toor Dal',
                'category_name': 'Dal & Pulses',
                'default_unit': 'kg'
            },
            {
                'id': 'gp-oil-001',
                'name': 'Sunflower Oil',
                'category_name': 'Oil & Ghee',
                'default_unit': 'L'
            }
        ]
        
        if search:
            # Filter by search term
            search_lower = search.lower()
            mock_products = [p for p in mock_products if search_lower in p['name'].lower()]
        
        return mock_products[:limit]
        
    except Exception as e:
        logger.error(f"Error searching generic products: {e}")
        return []

async def get_product_by_id(product_id: str, store_id: str):
    """Get product by ID"""
    try:
        dynamodb = get_dynamodb_client()
        if not dynamodb:
            return None
        
        response = dynamodb.get_item(
            TableName=TABLE_NAMES['products'],
            Key={
                'id': {'S': product_id}
            }
        )
        
        if 'Item' in response:
            item = response['Item']
            
            # Verify the product belongs to the correct store
            item_store_id = item.get('store_id', {}).get('S', '')
            if item_store_id != store_id:
                logger.error(f"Product {product_id} does not belong to store {store_id}")
                return None
            
            return {
                'id': item['id']['S'],
                'product_name': item.get('name', {}).get('S', ''),
                'brand_name': item.get('brand', {}).get('S', ''),
                'sku': item.get('sku', {}).get('S', ''),
                'barcode': item.get('barcode', {}).get('S', ''),
                'selling_price': float(item.get('price', {}).get('N', '0')),
                'current_stock': int(item.get('stock_quantity', {}).get('N', '0')),
                'min_stock_level': int(item.get('min_stock_level', {}).get('N', '10')),
                'max_stock_level': int(item.get('max_stock_level', {}).get('N', '100')),
                'status': item.get('status', {}).get('S', 'active')
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting product by ID: {e}")
        return None

async def update_product_in_db(product_id: str, store_id: str, data: dict):
    """Update product in database"""
    try:
        dynamodb = get_dynamodb_client()
        if not dynamodb:
            return False
        
        # Build update expression
        update_expression = "SET updated_at = :updated_at"
        expression_values = {
            ':updated_at': {'S': datetime.utcnow().isoformat()}
        }
        
        # Debug logging
        logger.info(f"Update data received: {data}")
        
        # Add fields to update
        if 'name' in data or 'product_name' in data:
            update_expression += ", #name = :name"
            expression_values[':name'] = {'S': data.get('name') or data.get('product_name')}
        
        if 'brand_name' in data:
            update_expression += ", brand = :brand"
            expression_values[':brand'] = {'S': data['brand_name']}
        
        if 'sku' in data:
            update_expression += ", sku = :sku"
            expression_values[':sku'] = {'S': data['sku']}
        
        if 'barcode' in data:
            update_expression += ", barcode = :barcode"
            expression_values[':barcode'] = {'S': data['barcode']}
        
        if 'price' in data or 'selling_price' in data:
            update_expression += ", price = :price"
            expression_values[':price'] = {'N': str(data.get('price') or data.get('selling_price'))}
        
        if 'cost_price' in data:
            update_expression += ", cost_price = :cost_price"
            expression_values[':cost_price'] = {'N': str(data['cost_price'])}
        
        if 'stock_quantity' in data or 'current_stock' in data:
            update_expression += ", stock_quantity = :stock"
            expression_values[':stock'] = {'N': str(data.get('stock_quantity') or data.get('current_stock'))}
        
        if 'min_stock_level' in data:
            update_expression += ", min_stock_level = :min_stock"
            expression_values[':min_stock'] = {'N': str(data['min_stock_level'])}
        
        if 'max_stock_level' in data:
            update_expression += ", max_stock_level = :max_stock"
            expression_values[':max_stock'] = {'N': str(data['max_stock_level'])}
        
        if 'discount_percentage' in data:
            update_expression += ", discount_percentage = :discount"
            expression_values[':discount'] = {'N': str(data['discount_percentage'])}
        
        if 'image' in data:
            update_expression += ", image = :image"
            expression_values[':image'] = {'S': data['image']}
        
        if 'description' in data:
            update_expression += ", description = :description"
            expression_values[':description'] = {'S': data['description']}
        
        # Build the update item parameters
        update_params = {
            'TableName': TABLE_NAMES['products'],
            'Key': {
                'id': {'S': product_id}
            },
            'UpdateExpression': update_expression,
            'ExpressionAttributeValues': expression_values,
            'ReturnValues': 'UPDATED_NEW'
        }
        
        # Add ExpressionAttributeNames if we're updating the name field
        if 'name' in data or 'product_name' in data:
            update_params['ExpressionAttributeNames'] = {'#name': 'name'}
        
        # Debug logging
        logger.info(f"Final update_expression: {update_expression}")
        logger.info(f"Final expression_values: {expression_values}")
        
        response = dynamodb.update_item(**update_params)
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating product: {e}")
        return False

async def update_product_stock_db(product_id: str, movement_type: str, quantity: int, reason: str):
    """Update product stock in database"""
    try:
        dynamodb = get_dynamodb_client()
        if not dynamodb:
            return False
        
        # Get current stock first
        response = dynamodb.scan(
            TableName=TABLE_NAMES['products'],
            FilterExpression='id = :product_id',
            ExpressionAttributeValues={
                ':product_id': {'S': product_id}
            }
        )
        
        if not response['Items']:
            return False
        
        item = response['Items'][0]
        current_stock = int(item.get('stock_quantity', {}).get('N', '0'))
        
        # Calculate new stock based on movement type
        if movement_type == 'in':
            new_stock = current_stock + quantity
        elif movement_type == 'out':
            new_stock = max(0, current_stock - quantity)
        elif movement_type == 'set':
            new_stock = quantity
        elif movement_type == 'adjustment':
            new_stock = current_stock + quantity  # quantity can be negative
        else:
            return False
        
        new_stock = max(0, new_stock)  # Ensure stock doesn't go negative
        
        # Update stock
        store_id = item['store_id']['S']
        response = dynamodb.update_item(
            TableName=TABLE_NAMES['products'],
            Key={
                'id': {'S': product_id}
            },
            UpdateExpression="SET stock_quantity = :new_stock, updated_at = :updated_at",
            ExpressionAttributeValues={
                ':new_stock': {'N': str(new_stock)},
                ':updated_at': {'S': datetime.utcnow().isoformat()}
            }
        )
        
        # TODO: Log stock movement in stock_movements table
        logger.info(f"Stock updated for product {product_id}: {current_stock} -> {new_stock} ({movement_type}: {quantity})")
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating product stock: {e}")
        return False

async def delete_product_from_db(product_id: str, store_id: str):
    """Delete product from database"""
    try:
        dynamodb = get_dynamodb_client()
        if not dynamodb:
            return False
        
        # First verify the product belongs to the store
        get_response = dynamodb.get_item(
            TableName=TABLE_NAMES['products'],
            Key={'id': {'S': product_id}}
        )
        
        if not get_response.get('Item'):
            return False
        
        item_store_id = get_response['Item'].get('store_id', {}).get('S', '')
        if item_store_id != store_id:
            logger.error(f"Product {product_id} does not belong to store {store_id}")
            return False
        
        # Delete the product
        response = dynamodb.delete_item(
            TableName=TABLE_NAMES['products'],
            Key={'id': {'S': product_id}},
            ReturnValues='ALL_OLD'
        )
        
        return 'Attributes' in response
        
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        return False

async def get_product_by_id_db(product_id: str, store_id: str):
    """Get product by ID from database"""
    try:
        dynamodb = get_dynamodb_client()
        if not dynamodb:
            return None
        
        # Use scan to find the product since the table may not have the right key structure
        response = dynamodb.scan(
            TableName=TABLE_NAMES['products'],
            FilterExpression='id = :product_id AND store_id = :store_id AND active = :active',
            ExpressionAttributeValues={
                ':product_id': {'S': product_id},
                ':store_id': {'S': store_id},
                ':active': {'BOOL': True}
            }
        )
        
        items = response.get('Items', [])
        if not items:
            return None
        
        item = items[0]  # Take the first matching item
        
        # Convert DynamoDB format to regular format
        product = {
            'id': item.get('id', {}).get('S', ''),
            'name': item.get('name', {}).get('S', ''),
            'barcode': item.get('barcode', {}).get('S', ''),
            'category': item.get('category', {}).get('S', ''),
            'selling_price': float(item.get('price', {}).get('N', '0')),
            'cost_price': float(item.get('cost_price', {}).get('N', '0')),
            'stock_quantity': int(item.get('stock_quantity', {}).get('N', '0')),
            'min_stock_level': int(item.get('min_stock_level', {}).get('N', '10')),
            'max_stock_level': int(item.get('max_stock_level', {}).get('N', '100')),
            'description': item.get('description', {}).get('S', ''),
            'status': item.get('status', {}).get('S', 'active')
        }
        
        return product
        
    except Exception as e:
        logger.error(f"Error getting product by ID: {e}")
        return None

# Lambda handler function
handler = Mangum(app)

def lambda_handler(event, context):
    return handler(event, context)

