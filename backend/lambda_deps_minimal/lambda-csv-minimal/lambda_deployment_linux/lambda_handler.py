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
import os
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

# Services
from services.product_catalog_service import ProductCatalogService, extract_region_from_store_data
from services.import_service import ProductImportService, COMMON_INDIAN_PRODUCTS
from utils.product_matching import find_all_matches, extract_barcodes_from_data, generate_image_hash, detect_language_from_text, get_regional_language_for_state

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

# New table environment variables for shared product catalog architecture
# Defaults keep backward compatibility during migration
GLOBAL_PRODUCTS_TABLE = os.environ.get('GLOBAL_PRODUCTS_TABLE', 'vyaparai-global-products-prod')
STORE_INVENTORY_TABLE = os.environ.get('STORE_INVENTORY_TABLE', 'vyaparai-store-inventory-prod')
LEGACY_PRODUCTS_TABLE = os.environ.get('PRODUCTS_TABLE', 'vyaparai-products-prod')  # Keep existing for migration

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

# ===== TEST ENDPOINT FOR PRODUCT CATALOG SERVICE INTEGRATION =====
@app.get("/api/v1/test/catalog-service")
async def test_catalog_service(request: Request):
    """Test endpoint to verify ProductCatalogService integration"""
    try:
        catalog_service = ProductCatalogService()
        
        # Test table connections
        global_table_name = catalog_service.global_table.name
        inventory_table_name = catalog_service.inventory_table.name
        
        return {
            "success": True,
            "message": "ProductCatalogService initialized successfully",
            "tables": {
                "global_products": global_table_name,
                "store_inventory": inventory_table_name
            },
            "env_vars": {
                "GLOBAL_PRODUCTS_TABLE": GLOBAL_PRODUCTS_TABLE,
                "STORE_INVENTORY_TABLE": STORE_INVENTORY_TABLE,
                "LEGACY_PRODUCTS_TABLE": LEGACY_PRODUCTS_TABLE
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

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
    """Get store inventory with global product details joined"""
    try:
        # Extract store_id from JWT (keep existing logic)
        store_id = get_store_from_jwt(request)
        
        # Parse query parameters
        limit = int(request.query_params.get('limit', 50))
        last_key = request.query_params.get('last_key')
        
        # Initialize catalog service
        catalog_service = ProductCatalogService()
        
        # Get store inventory with global product data
        result = await catalog_service.get_store_inventory(
            store_id=store_id,
            limit=limit,
            last_key=json.loads(last_key) if last_key else None
        )
        
        # Transform for frontend compatibility
        products = []
        for item in result['items']:
            global_product = item['global_product']
            inventory_data = {k: v for k, v in item.items() if k != 'global_product'}
            
            # Handle image URLs - check both canonical and legacy image fields
            image_urls = global_product.get('canonical_image_urls', {})
            if not image_urls:
                # Fallback to legacy image field if available
                legacy_image = global_product.get('image')
                if legacy_image:
                    image_urls = {
                        'original': legacy_image,
                        'thumbnail': legacy_image,
                        'medium': legacy_image,
                        'large': legacy_image
                    }
            
            # Merge data in expected format
            product = {
                # Global product fields
                "id": global_product['product_id'],  # For frontend compatibility
                "product_id": global_product['product_id'],
                "global_product_id": global_product['product_id'],
                "name": global_product['name'],
                "brand": global_product.get('brand'),
                "category": global_product.get('category'),
                "barcode": global_product.get('barcode'),
                "additional_barcodes": global_product.get('additional_barcodes', []),
                "canonical_image_urls": image_urls,
                "image_urls": image_urls,  # Alias for compatibility
                "image": image_urls.get('original') if image_urls else None,  # Single image field for compatibility
                "verification_status": global_product.get('verification_status'),
                
                # Store-specific fields
                "inventory_id": f"{store_id}_{global_product['product_id']}",
                "quantity": inventory_data.get('quantity', 0),
                "stock_quantity": inventory_data.get('quantity', 0),  # Frontend expects this field
                "current_stock": inventory_data.get('quantity', 0),  # Alias for compatibility
                "cost_price": inventory_data.get('cost_price'),
                "selling_price": inventory_data.get('selling_price'),
                "price": inventory_data.get('selling_price'),  # Alias for compatibility
                "reorder_level": inventory_data.get('reorder_level'),
                "min_stock_level": inventory_data.get('reorder_level', 10),  # Frontend expects this
                "max_stock_level": 100,  # Default value
                "supplier": inventory_data.get('supplier'),
                "location": inventory_data.get('location'),
                "notes": inventory_data.get('notes'),
                "last_updated": inventory_data.get('last_updated'),
                "updated_at": inventory_data.get('last_updated'),
                "created_at": global_product.get('created_at'),
                "unit": "piece",  # Default unit
                "status": "active",  # Default status
                "mrp": inventory_data.get('selling_price'),  # Use selling price as MRP
                "discount_percentage": None,
                "description": "",  # Default empty description
                "tags": [],  # Default empty tags
                
                # Metadata
                "is_shared_product": True,
                "stores_using_count": global_product.get('stores_using_count', 1)
            }
            products.append(product)
        
        return {
            "success": True,
            "data": products,  # Frontend expects 'data' field
            "products": products,  # Keep for backward compatibility
            "total_count": len(products),
            "last_key": json.dumps(result['last_key']) if result.get('last_key') else None,
            "has_more": bool(result.get('last_key'))
        }
        
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/v1/inventory/products/legacy")
async def get_products_legacy(request: Request):
    """Legacy products listing for comparison"""
    try:
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
        logger.error(f"Get products (legacy) error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch products (legacy)")

@app.post("/api/v1/inventory/products/match")
async def match_product(request: Request):
    """Find potential matches for a product before creation"""
    try:
        # Get store_id from JWT (keep existing logic) 
        store_id = get_store_from_jwt(request)
        
        # Parse request body
        body = await request.json()
        
        # Import matching utilities
        from utils.product_matching import find_all_matches, extract_barcodes_from_data, generate_image_hash
        
        # Prepare candidate product data
        candidate_product = {
            'name': body.get('name'),
            'brand': body.get('brand'), 
            'category': body.get('category'),
            'barcodes': extract_barcodes_from_data(body)
        }
        
        # Generate image hash if provided
        if body.get('image_data'):
            import base64
            image_bytes = base64.b64decode(body['image_data']) if isinstance(body['image_data'], str) else body['image_data']
            candidate_product['image_hash'] = generate_image_hash(image_bytes)
        
        # Initialize catalog service
        catalog_service = ProductCatalogService()
        
        # Get a sample of existing products for comparison (limit for performance)
        # First try exact barcode match
        exact_match = None
        if candidate_product['barcodes']:
            exact_match = await catalog_service.find_existing_product(
                barcode=candidate_product['barcodes'][0]
            )
        
        if exact_match:
            # Found exact barcode match
            matches = [{
                'product_id': exact_match['product_id'],
                'name': exact_match['name'],
                'brand': exact_match.get('brand'),
                'barcode': exact_match.get('barcode'),
                'confidence': 1.0,
                'match_reason': 'exact_barcode_match',
                'image_urls': exact_match.get('canonical_image_urls', {}),
                'stores_using_count': exact_match.get('stores_using_count', 0)
            }]
            
            suggestion = 'use_existing'
            
        else:
            # No exact match - do fuzzy matching
            # For performance, scan recent products (you may want to optimize this further)
            try:
                response = catalog_service.global_table.scan(
                    Limit=1000,  # Limit for performance
                    FilterExpression='verification_status = :status',
                    ExpressionAttributeValues={':status': 'verified'}
                )
                existing_products = response['Items']
            except:
                # Fallback if filtering fails
                response = catalog_service.global_table.scan(Limit=500)
                existing_products = response['Items']
            
            # Find fuzzy matches
            all_matches = find_all_matches(candidate_product, existing_products, fuzzy_threshold=0.7)
            
            # Transform matches for API response
            matches = []
            for match in all_matches[:5]:  # Top 5 matches
                product = match['product']
                matches.append({
                    'product_id': product['product_id'],
                    'name': product['name'],
                    'brand': product.get('brand'),
                    'barcode': product.get('barcode'),
                    'confidence': round(match['confidence'], 2),
                    'match_reason': match['match_reason'],
                    'image_urls': product.get('canonical_image_urls', {}),
                    'stores_using_count': product.get('stores_using_count', 0),
                    'similarities': match.get('similarities', {})
                })
            
            # Determine suggestion
            if matches and matches[0]['confidence'] >= 0.9:
                suggestion = 'use_existing'
            elif matches and matches[0]['confidence'] >= 0.7:
                suggestion = 'review_matches'
            else:
                suggestion = 'create_new'
        
        return {
            'success': True,
            'matches': matches,
            'suggestion': suggestion,
            'total_matches': len(matches),
            'candidate_product': {
                'name': candidate_product['name'],
                'brand': candidate_product['brand'],
                'barcodes': candidate_product['barcodes']
            }
        }
        
    except Exception as e:
        logger.error(f"Error matching product: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@app.get("/api/v1/inventory/products/global/{product_id}")
async def get_global_product(product_id: str, request: Request):
    """Get global product details by ID"""
    try:
        catalog_service = ProductCatalogService()
        
        response = catalog_service.global_table.get_item(
            Key={'product_id': product_id}
        )
        
        if 'Item' not in response:
            return {'success': False, 'error': 'Product not found'}
        
        product = response['Item']
        return {
            'success': True,
            'product': product
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/inventory/products/{product_id}/regional-names")
async def get_product_regional_names(product_id: str, request: Request):
    """Get all regional name variants for a product"""
    try:
        store_id = get_store_from_jwt(request)
        catalog_service = ProductCatalogService()
        regional_data = await catalog_service.get_regional_name_variants(product_id)
        if not regional_data:
            return {'success': False, 'error': 'Product not found'}
        return {
            "success": True,
            "product_id": product_id,
            "primary_name": regional_data.get('primary_name'),
            "regional_names": regional_data.get('regional_names', {}),
            "contributed_names": regional_data.get('contributed_names', {}),
            "primary_regions": regional_data.get('primary_regions', []),
            "total_regions": len(regional_data.get('regional_names', {})),
            "total_contributed": sum(len(contributions) for contributions in regional_data.get('contributed_names', {}).values())
        }
    except Exception as e:
        print(f"Error getting regional names: {e}")
        return {'success': False, 'error': str(e)}

@app.post("/api/v1/inventory/products/{product_id}/regional-names")
async def add_regional_name(product_id: str, request: Request):
    """Add/contribute a regional name for a product"""
    try:
        store_id = get_store_from_jwt(request)
        body = await request.json()
        region_code = body.get('region_code')
        regional_name = body.get('regional_name')
        if not regional_name:
            return {'success': False, 'error': 'Regional name is required'}
        if not region_code:
            store_data = {'address': '', 'state': '', 'city': ''}
            region_code = extract_region_from_store_data(store_data)
        detected_language = detect_language_from_text(regional_name)
        expected_language = get_regional_language_for_state(region_code)
        language_confidence = "high" if detected_language == expected_language else "medium"
        catalog_service = ProductCatalogService()
        success = await catalog_service.add_regional_name(
            product_id=product_id,
            region_code=region_code,
            regional_name=regional_name,
            contributed_by_store=store_id
        )
        if success:
            return {
                "success": True,
                "message": "Regional name contributed successfully",
                "contribution": {
                    "product_id": product_id,
                    "region_code": region_code,
                    "regional_name": regional_name,
                    "detected_language": detected_language,
                    "language_confidence": language_confidence,
                    "status": "pending_verification"
                }
            }
        else:
            return {'success': False, 'error': 'Failed to add regional name'}
    except Exception as e:
        print(f"Error adding regional name: {e}")
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/inventory/products/search-regional")
async def search_by_regional_name(request: Request):
    """Search products by regional name"""
    try:
        store_id = get_store_from_jwt(request)
        query_name = request.query_params.get('name')
        region_code = request.query_params.get('region')
        limit = int(request.query_params.get('limit', 20))
        if not query_name:
            return {'success': False, 'error': 'Search name is required'}
        if not region_code:
            store_data = {'address': '', 'state': '', 'city': ''}
            region_code = extract_region_from_store_data(store_data)
        catalog_service = ProductCatalogService()
        matches = await catalog_service.search_by_regional_name(query_name, region_code)
        results = []
        for match in matches[:limit]:
            product = match['product']
            results.append({
                'product_id': product['product_id'],
                'primary_name': product['name'],
                'matched_regional_name': match.get('matched_name'),
                'matched_region': match.get('matched_region'),
                'confidence': round(match['confidence'], 2),
                'match_reason': match['match_reason'],
                'brand': product.get('brand'),
                'category': product.get('category'),
                'barcode': product.get('barcode'),
                'image_urls': product.get('canonical_image_urls', {}),
                'stores_using_count': product.get('stores_using_count', 0)
            })
        return {
            'success': True,
            'query': {
                'name': query_name,
                'region': region_code,
                'detected_language': detect_language_from_text(query_name)
            },
            'results': results,
            'total_matches': len(results),
            'search_region': region_code
        }
    except Exception as e:
        print(f"Error searching by regional name: {e}")
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/stores/profile/region")
async def get_store_region_info(request: Request):
    """Get store's regional information and language preferences"""
    try:
        store_id = get_store_from_jwt(request)
        store_profile = {
            'store_id': store_id,
            'region_code': 'IN-MH',
            'region_auto_detected': True,
            'primary_language': 'mr',
            'supported_languages': ['en', 'mr', 'hi'],
            'regional_preferences': {
                'show_regional_names': True,
                'contribute_names': True,
                'auto_detect_language': True,
                'prefer_regional_display': True
            }
        }
        return {
            'success': True,
            'region_info': store_profile
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.put("/api/v1/stores/profile/region")
async def update_store_region_preferences(request: Request):
    """Update store's regional preferences"""
    try:
        store_id = get_store_from_jwt(request)
        body = await request.json()
        preferences = {
            'region_code': body.get('region_code'),
            'primary_language': body.get('primary_language'),
            'show_regional_names': body.get('show_regional_names', True),
            'contribute_names': body.get('contribute_names', True),
            'auto_detect_language': body.get('auto_detect_language', True),
            'prefer_regional_display': body.get('prefer_regional_display', True)
        }
        valid_regions = ['IN-MH', 'IN-TN', 'IN-KA', 'IN-AP', 'IN-TG', 'IN-KL', 'IN-GJ', 'IN-PB', 'IN-WB', 'IN-UP', 'IN-MP', 'IN-RJ', 'IN-BR', 'IN-JH', 'IN-HR', 'IN-DL', 'IN-CG', 'IN-OR', 'IN-AS']
        if preferences['region_code'] and preferences['region_code'] not in valid_regions:
            return {'success': False, 'error': 'Invalid region code'}
        return {
            'success': True,
            'message': 'Regional preferences updated successfully',
            'updated_preferences': preferences
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/analytics/regional-coverage")
async def get_regional_coverage_analytics(request: Request):
    """Get analytics on regional name coverage"""
    try:
        store_id = get_store_from_jwt(request)
        catalog_service = ProductCatalogService()
        response = catalog_service.global_table.scan(
            ProjectionExpression='product_id, #name, regional_names, primary_regions',
            ExpressionAttributeNames={'#name': 'name'},
            Limit=1000
        )
        products = response['Items']
        total_products = len(products)
        products_with_regional = sum(1 for p in products if p.get('regional_names'))
        region_coverage: Dict[str, int] = {}
        for product in products:
            regional_names = product.get('regional_names', {})
            for region in regional_names.keys():
                region_coverage[region] = region_coverage.get(region, 0) + 1
        coverage_stats: Dict[str, Dict[str, Any]] = {}
        for region, count in region_coverage.items():
            coverage_stats[region] = {
                'products': count,
                'percentage': round((count / total_products) * 100, 1) if total_products > 0 else 0
            }
        return {
            'success': True,
            'analytics': {
                'total_products': total_products,
                'products_with_regional_names': products_with_regional,
                'overall_coverage_percentage': round((products_with_regional / total_products) * 100, 1) if total_products > 0 else 0,
                'coverage_by_region': coverage_stats,
                'top_regions': sorted(coverage_stats.items(), key=lambda x: x[1]['products'], reverse=True)[:5]
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
@app.post("/api/v1/inventory/products")
async def create_product(request: Request):
    """Create product using shared catalog architecture"""
    try:
        # Get store_id from JWT (keep existing logic)
        store_id = get_store_from_jwt(request)
        
        # Parse request body
        body = await request.json()
        
        # Extract product data
        product_data = {
            'name': body.get('name') or body.get('product_name'),
            'brand': body.get('brand'),
            'category': body.get('category'),
            'barcodes': extract_barcodes_from_data(body),
            'attributes': body.get('attributes', {}),
            'created_by': store_id
        }
        
        # Generate image hash if image data provided
        if body.get('image_data'):
            # Convert base64 to bytes if needed
            import base64
            image_bytes = base64.b64decode(body['image_data']) if isinstance(body['image_data'], str) else body['image_data']
            product_data['image_hash'] = generate_image_hash(image_bytes)
        
        # Initialize catalog service
        catalog_service = ProductCatalogService()
        
        # Try to find existing product
        existing_product = await catalog_service.find_existing_product(
            barcode=product_data['barcodes'][0] if product_data['barcodes'] else None,
            name=product_data['name'],
            brand=product_data['brand'],
            image_hash=product_data.get('image_hash')
        )
        
        if existing_product:
            # Product exists - add to store inventory
            inventory_data = {
                'quantity': body.get('quantity', 0),
                'cost_price': body.get('cost_price'),
                'selling_price': body.get('selling_price', body.get('price')),  # Support both field names
                'reorder_level': body.get('reorder_level'),
                'supplier': body.get('supplier'),
                'location': body.get('location'),
                'notes': body.get('notes')
            }
            
            inventory_item = await catalog_service.add_to_store_inventory(
                store_id, existing_product['product_id'], inventory_data
            )
            
            return {
                "success": True,
                "message": "Product added to inventory",
                "is_new_product": False,
                "global_product_id": existing_product['product_id'],
                "inventory_id": f"{store_id}_{existing_product['product_id']}",
                "product": {
                    **existing_product,
                    **inventory_item,
                    "display_name": existing_product['name']  # Use global name for now
                }
            }
        
        else:
            # Product doesn't exist - create new global product
            global_product_id = await catalog_service.create_global_product(product_data)
            
            # Add to store inventory
            inventory_data = {
                'quantity': body.get('quantity', 0),
                'cost_price': body.get('cost_price'),
                'selling_price': body.get('selling_price', body.get('price')),
                'reorder_level': body.get('reorder_level'),
                'supplier': body.get('supplier'),
                'location': body.get('location'),
                'notes': body.get('notes')
            }
            
            inventory_item = await catalog_service.add_to_store_inventory(
                store_id, global_product_id, inventory_data
            )
            
            # Get the created global product for response
            created_product = catalog_service.global_table.get_item(
                Key={'product_id': global_product_id}
            )['Item']
            
            return {
                "success": True,
                "message": "New product created and added to inventory",
                "is_new_product": True,
                "global_product_id": global_product_id,
                "inventory_id": f"{store_id}_{global_product_id}",
                "product": {
                    **created_product,
                    **inventory_item,
                    "display_name": created_product['name']
                }
            }
            
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/v1/inventory/products/legacy")
async def create_product_legacy(request: Request):
    """Create a new product - Legacy implementation for migration testing"""
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
            "message": "Product created successfully (legacy)",
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
    """Upload CSV file with intelligent preview of deduplication results"""
    try:
        # Get store_id from JWT token (keep existing logic)
        store_id = get_store_from_jwt(request)
        
        # Parse multipart, read file (keep existing logic)
        try:
            form = await request.form()
        except Exception as e:
            logger.error(f"Failed to parse multipart form: {e}")
            raise HTTPException(status_code=400, detail="Invalid multipart form data")
        csv_file = form.get("file")
        if not csv_file:
            raise HTTPException(status_code=400, detail="No file provided")
        if not csv_file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV file")
        
        # Generate job ID (keep existing style)
        job_id = f"bulk_upload_{store_id}_{int(time.time())}"
        
        # Upload CSV to S3 (keep existing logic)
        s3_client = boto3.client('s3')
        bucket_name = 'vyapaarai-bulk-uploads-prod'
        s3_key = f"bulk-uploads/{store_id}/{job_id}.csv"
        
        csv_content = await csv_file.read()
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=csv_content,
            ContentType='text/csv'
        )
        
        # NEW: Intelligent Preview Analysis
        import csv as _csv
        import io
        from services.product_catalog_service import ProductCatalogService
        from utils.product_matching import extract_barcodes_from_data
        
        # Parse CSV content for preview
        csv_text = csv_content.decode('utf-8')
        csv_reader = _csv.DictReader(io.StringIO(csv_text))
        
        # Sample first 10 rows for preview analysis
        sample_rows = []
        total_records = 0
        for i, row in enumerate(csv_reader):
            total_records += 1
            if i < 10:
                sample_rows.append(row)
        
        # Analyze sample for predictions
        catalog_service = ProductCatalogService()
        preview_stats = {
            'likely_matches': 0,
            'likely_new_products': 0,
            'potential_duplicates': [],
            'invalid_rows': 0,
            'sample_analysis': []
        }
        
        for row in sample_rows:
            try:
                name = row.get('name') or row.get('product_name')
                brand = row.get('brand')
                barcodes = extract_barcodes_from_data(row)
                
                if not name:
                    preview_stats['invalid_rows'] += 1
                    continue
                
                existing_product = None
                if barcodes:
                    existing_product = await catalog_service.find_existing_product(barcode=barcodes[0])
                if not existing_product and name and brand:
                    existing_product = await catalog_service.find_existing_product(name=name, brand=brand)
                
                if existing_product:
                    preview_stats['likely_matches'] += 1
                    preview_stats['sample_analysis'].append({
                        'csv_name': name,
                        'matched_to': existing_product['name'],
                        'match_type': 'existing_product',
                        'confidence': 'high'
                    })
                else:
                    preview_stats['likely_new_products'] += 1
                    preview_stats['sample_analysis'].append({
                        'csv_name': name,
                        'match_type': 'new_product',
                        'confidence': 'high'
                    })
                
                # Check for potential duplicates within CSV sample
                for other_row in sample_rows:
                    other_name = other_row.get('name') or other_row.get('product_name')
                    if other_name and other_name != name and other_name.lower().strip() == name.lower().strip():
                        if name not in preview_stats['potential_duplicates']:
                            preview_stats['potential_duplicates'].append(name)
            except Exception as e:
                logger.warning(f"Error analyzing sample row: {e}")
                preview_stats['invalid_rows'] += 1
        
        # Calculate projections based on sample
        sample_size = len(sample_rows) - preview_stats['invalid_rows']
        if sample_size > 0:
            match_ratio = preview_stats['likely_matches'] / sample_size
            new_ratio = preview_stats['likely_new_products'] / sample_size
            projected_matches = int(total_records * match_ratio)
            projected_new = int(total_records * new_ratio)
        else:
            match_ratio = 0
            projected_matches = 0
            projected_new = total_records
        
        # Estimate processing time
        estimated_minutes = max(1, int(total_records / 100))
        
        # Create DynamoDB job record (existing low-level client API)
        dynamodb = get_dynamodb_client()
        if dynamodb:
            try:
                dynamodb.put_item(
                    TableName='vyaparai-bulk-upload-jobs-prod',
                    Item={
                        'job_id': {'S': job_id},
                        'store_id': {'S': store_id},
                        'status': {'S': 'uploaded'},
                        's3_key': {'S': s3_key},
                        'created_at': {'S': datetime.utcnow().isoformat()},
                        'total_records': {'N': str(total_records)},
                        'processed': {'N': '0'},
                        'successful': {'N': '0'},
                        'failed': {'N': '0'},
                        'preview': {'S': json.dumps({
                            'sample_size': len(sample_rows),
                            'projected_matches': projected_matches,
                            'projected_new_products': projected_new,
                            'potential_duplicates': preview_stats['potential_duplicates'][:5],
                            'invalid_rows': preview_stats['invalid_rows'],
                            'estimated_processing_minutes': estimated_minutes
                        })}
                    }
                )
            except Exception as e:
                logger.error(f"Error creating job record in DynamoDB: {e}")
                raise HTTPException(status_code=500, detail="Failed to create job record")
        
        # Enhanced response with preview
        return {
            "success": True,
            "jobId": job_id,
            "totalRecords": total_records,
            "fileName": csv_file.filename,
            "preview": {
                "sample_analyzed": len(sample_rows),
                "projected_results": {
                    "likely_matches": projected_matches,
                    "likely_new_products": projected_new,
                    "estimated_deduplication_rate": f"{int(match_ratio * 100)}%" if sample_size > 0 else "0%"
                },
                "potential_issues": {
                    "duplicate_names_in_csv": len(preview_stats['potential_duplicates']),
                    "invalid_rows": preview_stats['invalid_rows'],
                    "examples": preview_stats['potential_duplicates'][:3]
                },
                "estimated_processing_time": f"{estimated_minutes} minutes",
                "deduplication_benefits": {
                    "storage_saved": f"~{projected_matches * 0.5} MB" if projected_matches > 0 else "0 MB",
                    "catalog_efficiency": "High" if match_ratio > 0.3 else ("Medium" if match_ratio > 0.1 else "Low")
                }
            },
            "sample_analysis": preview_stats['sample_analysis'][:5]
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

async def process_csv_row(row_data: dict, store_id: str, job_id: str):
    """Process a single CSV row using shared catalog architecture"""
    try:
        # Initialize catalog service
        catalog_service = ProductCatalogService()
        
        # Extract product data from CSV row
        product_data = {
            'name': row_data.get('name') or row_data.get('product_name'),
            'brand': row_data.get('brand'),
            'category': row_data.get('category'),
            'barcodes': extract_barcodes_from_data(row_data),
            'attributes': {
                'weight': row_data.get('weight'),
                'unit': row_data.get('unit'),
                'description': row_data.get('description')
            },
            'created_by': store_id
        }
        
        # Extract inventory data
        def to_int(val):
            try:
                return int(val) if val not in (None, "") else None
            except Exception:
                return None
        def to_float(val):
            try:
                return float(val) if val not in (None, "") else None
            except Exception:
                return None
        
        inventory_data = {
            'quantity': to_int(row_data.get('quantity')) or 0,
            'cost_price': to_float(row_data.get('cost_price')),
            'selling_price': to_float(row_data.get('selling_price') or row_data.get('price')),
            'reorder_level': to_int(row_data.get('reorder_level')),
            'supplier': row_data.get('supplier'),
            'location': row_data.get('location') or row_data.get('aisle'),
            'notes': row_data.get('notes')
        }
        
        # Handle image processing if image_path provided
        image_hash = None
        if row_data.get('image_path'):
            try:
                with open(row_data['image_path'], 'rb') as f:
                    image_bytes = f.read()
                image_hash = generate_image_hash(image_bytes)
                if image_hash:
                    product_data['image_hash'] = image_hash
            except Exception as e:
                logger.warning(f"Image processing failed for row: {e}")
        
        # Try to find existing product
        existing_product = await catalog_service.find_existing_product(
            barcode=product_data['barcodes'][0] if product_data['barcodes'] else None,
            name=product_data['name'],
            brand=product_data['brand'],
            image_hash=image_hash
        )
        
        if existing_product:
            # Product exists - add to store inventory
            product_id = existing_product['product_id']
            await catalog_service.add_to_store_inventory(
                store_id, product_id, inventory_data
            )
            
            return {
                'status': 'matched_existing',
                'product_id': product_id,
                'global_product_id': product_id,
                'inventory_id': f"{store_id}_{product_id}",
                'match_reason': 'existing_product_found'
            }
        else:
            # Product doesn't exist - create new global product
            global_product_id = await catalog_service.create_global_product(product_data)
            
            # Add to store inventory
            await catalog_service.add_to_store_inventory(
                store_id, global_product_id, inventory_data
            )
            
            return {
                'status': 'created_new',
                'product_id': global_product_id,
                'global_product_id': global_product_id,
                'inventory_id': f"{store_id}_{global_product_id}",
                'match_reason': 'new_product_created'
            }
            
    except Exception as e:
        logger.error(f"Error processing CSV row: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'row_data': row_data
        }

async def process_csv_file(store_id: str, job_id: str, csv_file_path: str):
    """Process entire CSV file with shared catalog"""
    import csv
    import boto3
    from decimal import Decimal
    
    # Download CSV from S3
    s3 = boto3.client('s3')
    bucket_name = 'vyapaarai-bulk-uploads-prod'
    
    try:
        response = s3.get_object(Bucket=bucket_name, Key=csv_file_path)
        csv_content = response['Body'].read().decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(csv_content.splitlines())
        
        # Process statistics
        total_rows = 0
        products_matched = 0
        products_created = 0
        errors = 0
        
        processed_products = []
        
        for row in csv_reader:
            total_rows += 1
            
            # Process each row
            result = await process_csv_row(row, store_id, job_id)
            
            if result['status'] == 'matched_existing':
                products_matched += 1
            elif result['status'] == 'created_new':
                products_created += 1
            elif result['status'] == 'error':
                errors += 1
            
            processed_products.append(result)
            
            # Update job progress every 10 rows
            if total_rows % 10 == 0:
                await update_job_progress(job_id, {
                    'processed': total_rows,
                    'successful': products_matched + products_created,
                    'failed': errors,
                    'status': 'processing'
                })
        
        # Final job update
        await update_job_progress(job_id, {
            'processed': total_rows,
            'successful': products_matched + products_created,
            'failed': errors,
            'status': 'completed',
            'completed_at': datetime.utcnow().isoformat()
        })
        
        return {
            'success': True,
            'total_rows': total_rows,
            'products_matched': products_matched,
            'products_created': products_created,
            'errors': errors,
            'processed_products': processed_products
        }
        
    except Exception as e:
        await update_job_progress(job_id, {
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.utcnow().isoformat()
        })
        raise

async def update_job_progress(job_id: str, updates: dict):
    """Update job progress in DynamoDB (existing job schema)"""
    try:
        import boto3
        from decimal import Decimal
        dynamodb = boto3.client('dynamodb', region_name='ap-south-1')
        
        # Build update expression
        update_expr = "SET "
        expr_attr_values = {}
        expr_attr_names = {}
        
        for key, value in updates.items():
            placeholder = f":{key}"
            nameholder = f"#{key}" if key in ['status'] else key
            if nameholder != key:
                expr_attr_names[f"#{key}"] = key
                update_expr += f"#{key} = {placeholder}, "
            else:
                update_expr += f"{key} = {placeholder}, "
            
            # Convert numbers to Decimal-compatible AttributeValue
            if isinstance(value, (int, float)):
                expr_attr_values[placeholder] = {'N': str(value)}
            else:
                expr_attr_values[placeholder] = {'S': str(value)}
        
        update_expr = update_expr.rstrip(', ')
        
        kwargs = {
            'TableName': 'vyaparai-bulk-upload-jobs-prod',
            'Key': {'job_id': {'S': job_id}},
            'UpdateExpression': update_expr,
            'ExpressionAttributeValues': expr_attr_values
        }
        if expr_attr_names:
            kwargs['ExpressionAttributeNames'] = expr_attr_names
        
        dynamodb.update_item(**kwargs)
        
    except Exception as e:
        logger.warning(f"Error updating job progress: {e}")

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

@app.get("/api/v1/inventory/bulk-upload/jobs/{job_id}/status")
async def get_enhanced_job_status(job_id: str, request: Request):
    """Get detailed job status with deduplication metrics"""
    try:
        store_id = get_store_from_jwt(request)
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        jobs_table = dynamodb.Table('vyaparai-bulk-upload-jobs-prod')
        response = jobs_table.get_item(Key={'jobId': job_id})
        if 'Item' not in response:
            return {'success': False, 'error': 'Job not found'}
        job = response['Item']
        processed_rows = job.get('processed_rows') or job.get('processed') or 0
        products_matched = job.get('products_matched') or 0
        return {
            'success': True,
            'job': job,
            'insights': {
                'deduplication_rate': f"{int((products_matched / max(processed_rows, 1)) * 100)}%",
                'storage_saved': f"~{products_matched * 0.5} MB",
                'catalog_contribution': f"{job.get('products_created', 0)} new products added to shared catalog"
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

# =============================================================================
# ADMIN ENDPOINTS - Product Management and Quality Control
# =============================================================================

@app.get("/api/v1/admin/products/statuses")
async def get_product_statuses():
    """Get available product statuses and quality score definitions"""
    try:
        from services.product_catalog_service import PRODUCT_STATUSES, QUALITY_SCORES
        return {
            "success": True,
            "product_statuses": PRODUCT_STATUSES,
            "quality_scores": QUALITY_SCORES
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/admin/products/needing-review")
async def get_products_needing_review(request: Request):
    """Get products that need admin review"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        limit = int(request.query_params.get('limit', 50))
        last_key = request.query_params.get('last_key')
        
        catalog_service = ProductCatalogService()
        result = await catalog_service.get_products_needing_review(limit=limit, last_key=last_key)
        
        return {
            "success": True,
            "products": result['products'],
            "count": result['count'],
            "last_key": result['last_key'],
            "has_more": bool(result['last_key'])
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/admin/products/global")
async def get_all_global_products(request: Request):
    """Get all global products for admin catalog management"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin' and user_data.get('role') != 'super_admin':
            return {'success': False, 'error': 'Admin access required'}

        limit = int(request.query_params.get('limit', 1000))
        last_key = request.query_params.get('last_key')
        search = request.query_params.get('search', '')
        category = request.query_params.get('category', '')
        status = request.query_params.get('status', '')

        dynamodb = get_dynamodb_client()
        if not dynamodb:
            return {'success': False, 'error': 'Database connection failed'}

        # Build scan parameters
        scan_params = {
            'TableName': 'vyaparai-global-products-prod',
            'Limit': limit
        }

        # Add pagination if last_key provided
        if last_key:
            scan_params['ExclusiveStartKey'] = json.loads(last_key)

        # Scan the table
        response = dynamodb.scan(**scan_params)

        # Convert DynamoDB format to Python dict
        products = []
        for item in response.get('Items', []):
            product = {
                'product_id': item.get('product_id', {}).get('S', ''),
                'name': item.get('name', {}).get('S', ''),
                'brand': item.get('brand', {}).get('S', ''),
                'category': item.get('category', {}).get('S', ''),
                'verification_status': item.get('verification_status', {}).get('S', 'pending'),
                'quality_score': int(item.get('quality_score', {}).get('N', '0')),
                'stores_using_count': int(item.get('stores_using_count', {}).get('N', '0')),
                'created_at': item.get('created_at', {}).get('S', ''),
                'updated_at': item.get('updated_at', {}).get('S', ''),
                'barcode': item.get('barcode', {}).get('S', ''),
                'regional_names': item.get('regional_names', {}).get('M', {}),
                'attributes': item.get('attributes', {}).get('M', {})
            }

            # Apply filters
            if search and search.lower() not in product['name'].lower() and search.lower() not in product['brand'].lower():
                continue
            if category and product['category'] != category:
                continue
            if status and product['verification_status'] != status:
                continue

            products.append(product)

        # Get last evaluated key for pagination
        last_evaluated_key = response.get('LastEvaluatedKey')

        return {
            "success": True,
            "products": products,
            "count": len(products),
            "last_key": json.dumps(last_evaluated_key) if last_evaluated_key else None,
            "has_more": bool(last_evaluated_key)
        }

    except Exception as e:
        logger.error(f"Error fetching global products: {e}")
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/admin/products/by-status/{status}")
async def get_products_by_status(status: str, request: Request):
    """Get products filtered by verification status"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        limit = int(request.query_params.get('limit', 50))
        last_key = request.query_params.get('last_key')
        
        catalog_service = ProductCatalogService()
        result = await catalog_service.get_products_by_status(status=status, limit=limit, last_key=last_key)
        
        return {
            "success": True,
            "products": result['products'],
            "count": result['count'],
            "last_key": result['last_key'],
            "has_more": bool(result['last_key'])
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.post("/api/v1/admin/products/global")
async def create_global_product(request: Request):
    """Create a new global product"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin' and user_data.get('role') != 'super_admin':
            return {'success': False, 'error': 'Admin access required'}

        body = await request.json()

        # Validate required fields
        if not body.get('name') or not body.get('category'):
            return {'success': False, 'error': 'Product name and category are required'}

        dynamodb = get_dynamodb_client()
        if not dynamodb:
            return {'success': False, 'error': 'Database connection failed'}

        # Generate product ID
        product_id = f"GP{int(time.time() * 1000)}"

        # Prepare attributes
        attributes = body.get('attributes', {})
        attributes_dynamo = {}
        if attributes:
            for key, value in attributes.items():
                if value:
                    attributes_dynamo[key] = {'S': str(value)}

        # Prepare item for DynamoDB
        now = datetime.utcnow().isoformat() + 'Z'
        item = {
            'product_id': {'S': product_id},
            'name': {'S': body.get('name')},
            'category': {'S': body.get('category')},
            'verification_status': {'S': body.get('verification_status', 'pending')},
            'quality_score': {'N': str(body.get('quality_score', 0))},
            'stores_using_count': {'N': '0'},
            'created_at': {'S': now},
            'updated_at': {'S': now},
            'created_by': {'S': user_data.get('user_id', 'admin')}
        }

        # Optional fields
        if body.get('brand'):
            item['brand'] = {'S': body.get('brand')}
        if body.get('barcode'):
            item['barcode'] = {'S': body.get('barcode')}
        if body.get('description'):
            item['description'] = {'S': body.get('description')}
        if body.get('image'):
            item['image'] = {'S': body.get('image')}
        if attributes_dynamo:
            item['attributes'] = {'M': attributes_dynamo}

        # Insert into DynamoDB
        dynamodb.put_item(
            TableName='vyaparai-global-products-prod',
            Item=item
        )

        logger.info(f"Created global product: {product_id}")

        return {
            'success': True,
            'message': 'Global product created successfully',
            'product_id': product_id,
            'product': {
                'product_id': product_id,
                'name': body.get('name'),
                'brand': body.get('brand'),
                'category': body.get('category'),
                'barcode': body.get('barcode'),
                'description': body.get('description'),
                'verification_status': body.get('verification_status', 'pending'),
                'quality_score': body.get('quality_score', 0),
                'attributes': body.get('attributes', {}),
                'created_at': now,
                'updated_at': now
            }
        }

    except Exception as e:
        logger.error(f"Error creating global product: {e}")
        return {'success': False, 'error': str(e)}

@app.put("/api/v1/admin/products/global/{product_id}")
async def update_global_product(product_id: str, request: Request):
    """Update an existing global product"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin' and user_data.get('role') != 'super_admin':
            return {'success': False, 'error': 'Admin access required'}

        body = await request.json()

        dynamodb = get_dynamodb_client()
        if not dynamodb:
            return {'success': False, 'error': 'Database connection failed'}

        # Build update expression
        update_parts = []
        expression_values = {}
        expression_names = {}

        now = datetime.utcnow().isoformat() + 'Z'
        update_parts.append('#updated_at = :updated_at')
        expression_values[':updated_at'] = {'S': now}
        expression_names['#updated_at'] = 'updated_at'

        # Update fields if provided
        if body.get('name'):
            update_parts.append('#name = :name')
            expression_values[':name'] = {'S': body.get('name')}
            expression_names['#name'] = 'name'

        if body.get('brand'):
            update_parts.append('brand = :brand')
            expression_values[':brand'] = {'S': body.get('brand')}

        if body.get('category'):
            update_parts.append('category = :category')
            expression_values[':category'] = {'S': body.get('category')}

        if body.get('barcode'):
            update_parts.append('barcode = :barcode')
            expression_values[':barcode'] = {'S': body.get('barcode')}

        if body.get('description'):
            update_parts.append('description = :description')
            expression_values[':description'] = {'S': body.get('description')}

        if body.get('image'):
            update_parts.append('image = :image')
            expression_values[':image'] = {'S': body.get('image')}

        if 'verification_status' in body:
            update_parts.append('verification_status = :verification_status')
            expression_values[':verification_status'] = {'S': body.get('verification_status')}

        if 'quality_score' in body:
            update_parts.append('quality_score = :quality_score')
            expression_values[':quality_score'] = {'N': str(body.get('quality_score'))}

        # Handle attributes
        if body.get('attributes'):
            attributes_dynamo = {}
            for key, value in body.get('attributes').items():
                if value:
                    attributes_dynamo[key] = {'S': str(value)}
            if attributes_dynamo:
                update_parts.append('attributes = :attributes')
                expression_values[':attributes'] = {'M': attributes_dynamo}

        if not update_parts:
            return {'success': False, 'error': 'No fields to update'}

        # Execute update
        update_expression = 'SET ' + ', '.join(update_parts)

        dynamodb.update_item(
            TableName='vyaparai-global-products-prod',
            Key={'product_id': {'S': product_id}},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names if expression_names else None
        )

        logger.info(f"Updated global product: {product_id}")

        return {
            'success': True,
            'message': 'Global product updated successfully',
            'product_id': product_id,
            'updated_at': now
        }

    except Exception as e:
        logger.error(f"Error updating global product: {e}")
        return {'success': False, 'error': str(e)}

@app.put("/api/v1/admin/products/{product_id}/status")
async def update_product_status(product_id: str, request: Request):
    """Update product verification status"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        body = await request.json()
        new_status = body.get('status')
        notes = body.get('notes')
        
        if not new_status:
            return {'success': False, 'error': 'Status is required'}
        
        catalog_service = ProductCatalogService()
        success = await catalog_service.update_product_status(
            product_id=product_id,
            new_status=new_status,
            updated_by=user_data.get('user_id', 'admin'),
            notes=notes
        )
        
        if success:
            return {
                "success": True,
                "message": f"Product status updated to {new_status}",
                "product_id": product_id,
                "new_status": new_status
            }
        else:
            return {'success': False, 'error': 'Failed to update status'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.put("/api/v1/admin/products/{product_id}/approve")
async def approve_product(product_id: str, request: Request):
    """Approve a product - set status to verified"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') not in ['admin', 'super_admin']:
            return {'success': False, 'error': 'Admin access required'}
        
        catalog_service = ProductCatalogService()
        success = await catalog_service.update_product_status(
            product_id=product_id,
            new_status='verified',
            updated_by=user_data.get('user_id', 'admin'),
            notes='Product approved by admin'
        )
        
        if success:
            return {
                "success": True,
                "message": "Product approved successfully",
                "product_id": product_id,
                "new_status": "verified"
            }
        else:
            return {'success': False, 'error': 'Failed to approve product'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.put("/api/v1/admin/products/{product_id}/reject")
async def reject_product(product_id: str, request: Request):
    """Reject a product - set status to rejected"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') not in ['admin', 'super_admin']:
            return {'success': False, 'error': 'Admin access required'}
        
        catalog_service = ProductCatalogService()
        success = await catalog_service.update_product_status(
            product_id=product_id,
            new_status='flagged',
            updated_by=user_data.get('user_id', 'admin'),
            notes='Product rejected by admin'
        )
        
        if success:
            return {
                "success": True,
                "message": "Product rejected successfully",
                "product_id": product_id,
                "new_status": "flagged"
            }
        else:
            return {'success': False, 'error': 'Failed to reject product'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.post("/api/v1/admin/products/bulk-update-status")
async def bulk_update_product_status(request: Request):
    """Bulk update product statuses"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        body = await request.json()
        product_ids = body.get('product_ids', [])
        new_status = body.get('status')
        notes = body.get('notes')
        
        if not product_ids or not new_status:
            return {'success': False, 'error': 'Product IDs and status are required'}
        
        catalog_service = ProductCatalogService()
        results = await catalog_service.bulk_update_product_status(
            product_ids=product_ids,
            new_status=new_status,
            updated_by=user_data.get('user_id', 'admin'),
            notes=notes
        )
        
        return {
            "success": True,
            "results": results,
            "message": f"Updated {results['successful']} out of {results['total_requested']} products"
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.post("/api/v1/admin/products/bulk-import")
async def bulk_import_products(request: Request):
    """Bulk import products for admin seeding"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        body = await request.json()
        products_data = body.get('products', [])
        source = body.get('source', 'admin')
        
        if not products_data:
            return {'success': False, 'error': 'Products data is required'}
        
        catalog_service = ProductCatalogService()
        import_stats = await catalog_service.bulk_import_products(
            products_data=products_data,
            imported_by=user_data.get('user_id', 'admin'),
            source=source
        )
        
        return {
            "success": True,
            "import_stats": import_stats,
            "message": f"Import completed: {import_stats['successful']} successful, {import_stats['failed']} failed, {import_stats['duplicates_found']} duplicates found"
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/admin/products/{product_id}/history")
async def get_product_status_history(product_id: str, request: Request):
    """Get product status change history"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        catalog_service = ProductCatalogService()
        response = catalog_service.global_table.get_item(Key={'product_id': product_id})
        
        if 'Item' not in response:
            return {'success': False, 'error': 'Product not found'}
        
        product = response['Item']
        status_history = product.get('status_history', [])
        
        return {
            "success": True,
            "product_id": product_id,
            "current_status": product.get('verification_status'),
            "status_history": status_history,
            "last_updated_by": product.get('last_updated_by'),
            "admin_notes": product.get('admin_notes')
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/admin/analytics/product-quality")
async def get_product_quality_analytics(request: Request):
    """Get product quality analytics for admin dashboard"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        catalog_service = ProductCatalogService()
        
        # Get status distribution
        status_counts = {}
        quality_scores = []
        
        # Scan all products to get analytics
        response = catalog_service.global_table.scan()
        
        for item in response['Items']:
            status = item.get('verification_status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            quality_score = item.get('quality_score')
            if quality_score is not None:
                quality_scores.append(quality_score)
        
        # Calculate quality score statistics
        quality_stats = {}
        if quality_scores:
            quality_stats = {
                'average': sum(quality_scores) / len(quality_scores),
                'min': min(quality_scores),
                'max': max(quality_scores),
                'count': len(quality_scores)
            }
        
        return {
            "success": True,
            "analytics": {
                "status_distribution": status_counts,
                "quality_score_stats": quality_stats,
                "total_products": len(response['Items']),
                "products_needing_review": status_counts.get('pending', 0) + status_counts.get('flagged', 0)
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# =============================================================================
# IMPORT PIPELINE ENDPOINTS - External Data Sources
# =============================================================================

@app.get("/api/v1/admin/import/sources")
async def get_import_sources():
    """Get available import sources and their capabilities"""
    try:
        return {
            "success": True,
            "sources": {
                "open_food_facts": {
                    "name": "Open Food Facts",
                    "description": "Global food product database with Indian products",
                    "capabilities": ["product_data", "nutrition_info", "images", "barcodes"],
                    "categories": ["rice", "spices", "dairy", "oil", "snacks", "beverages"],
                    "max_products_per_request": 1000
                },
                "common_indian_products": {
                    "name": "Common Indian Products",
                    "description": "Curated list of popular Indian products with regional names",
                    "capabilities": ["product_data", "regional_names", "verified_barcodes"],
                    "product_count": len(COMMON_INDIAN_PRODUCTS),
                    "categories": ["Rice & Grains", "Spices & Condiments", "Dairy", "Cooking Oil", "Snacks"]
                }
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.post("/api/v1/admin/import/open-food-facts")
async def import_from_open_food_facts(request: Request):
    """Import products from Open Food Facts API"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        body = await request.json()
        limit = body.get('limit', 100)
        category = body.get('category')
        
        if limit > 1000:
            return {'success': False, 'error': 'Limit cannot exceed 1000 products per request'}
        
        # Import products from Open Food Facts
        import_service = ProductImportService()
        async with import_service:
            products = await import_service.fetch_indian_products_from_off(
                limit=limit, 
                category=category
            )
        
        if not products:
            return {
                "success": True,
                "message": "No products found from Open Food Facts",
                "import_stats": {
                    "total_found": 0,
                    "successful": 0,
                    "failed": 0,
                    "duplicates_found": 0
                }
            }
        
        # Import products using existing bulk import functionality
        catalog_service = ProductCatalogService()
        import_stats = await catalog_service.bulk_import_products(
            products_data=products,
            imported_by=user_data.get('user_id', 'admin'),
            source='open_food_facts'
        )
        
        return {
            "success": True,
            "message": f"Import from Open Food Facts completed",
            "import_stats": import_stats,
            "source": "open_food_facts",
            "category": category,
            "limit_requested": limit
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.post("/api/v1/admin/import/common-indian-products")
async def import_common_indian_products(request: Request):
    """Import common Indian products with regional names"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        body = await request.json()
        selected_products = body.get('product_indices', [])  # Optional: import specific products
        
        # Use selected products or all products
        if selected_products:
            products_to_import = [COMMON_INDIAN_PRODUCTS[i] for i in selected_products if i < len(COMMON_INDIAN_PRODUCTS)]
        else:
            products_to_import = COMMON_INDIAN_PRODUCTS
        
        # Add import metadata
        for product in products_to_import:
            product['attributes'] = product.get('attributes', {})
            product['attributes']['source'] = 'common_indian_products'
            product['attributes']['imported_at'] = datetime.utcnow().isoformat()
            product['verification_status'] = 'admin_created'
        
        # Import products using existing bulk import functionality
        catalog_service = ProductCatalogService()
        import_stats = await catalog_service.bulk_import_products(
            products_data=products_to_import,
            imported_by=user_data.get('user_id', 'admin'),
            source='common_indian_products'
        )
        
        return {
            "success": True,
            "message": f"Import of common Indian products completed",
            "import_stats": import_stats,
            "source": "common_indian_products",
            "total_available": len(COMMON_INDIAN_PRODUCTS),
            "imported": len(products_to_import)
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/admin/import/common-indian-products/preview")
async def preview_common_indian_products(request: Request):
    """Preview common Indian products before import"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        # Return preview of all common Indian products
        preview_products = []
        for i, product in enumerate(COMMON_INDIAN_PRODUCTS):
            preview_products.append({
                "index": i,
                "name": product['name'],
                "brand": product['brand'],
                "category": product['category'],
                "barcode": product['barcode'],
                "has_regional_names": bool(product.get('regional_names')),
                "regional_languages": list(product.get('regional_names', {}).keys()),
                "attributes": product.get('attributes', {})
            })
        
        return {
            "success": True,
            "products": preview_products,
            "total_count": len(COMMON_INDIAN_PRODUCTS),
            "categories": list(set(p['category'] for p in COMMON_INDIAN_PRODUCTS))
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.post("/api/v1/admin/import/validate-products")
async def validate_products_for_import(request: Request):
    """Validate products before import to check for duplicates and data quality"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        body = await request.json()
        products = body.get('products', [])
        
        if not products:
            return {'success': False, 'error': 'No products provided for validation'}
        
        catalog_service = ProductCatalogService()
        validation_results = []
        
        for i, product in enumerate(products):
            validation_result = {
                "index": i,
                "product_name": product.get('name', 'Unknown'),
                "barcode": product.get('barcode'),
                "issues": [],
                "warnings": [],
                "quality_score": 0
            }
            
            # Check for required fields
            if not product.get('name'):
                validation_result['issues'].append("Missing product name")
            if not product.get('barcode'):
                validation_result['warnings'].append("Missing barcode")
            if not product.get('brand'):
                validation_result['warnings'].append("Missing brand")
            if not product.get('category'):
                validation_result['warnings'].append("Missing category")
            
            # Check for duplicates
            if product.get('barcode'):
                existing = await catalog_service.find_existing_product(
                    barcode=product['barcode'],
                    name=product.get('name'),
                    brand=product.get('brand')
                )
                if existing:
                    validation_result['issues'].append(f"Duplicate product found: {existing.get('name', 'Unknown')}")
            
            # Calculate quality score
            validation_result['quality_score'] = catalog_service.calculate_quality_score(product)
            
            # Add quality warnings
            if validation_result['quality_score'] < 40:
                validation_result['warnings'].append("Low quality score - missing important data")
            elif validation_result['quality_score'] < 60:
                validation_result['warnings'].append("Medium quality score - consider adding more details")
            
            validation_results.append(validation_result)
        
        # Summary statistics
        total_products = len(products)
        products_with_issues = len([r for r in validation_results if r['issues']])
        products_with_warnings = len([r for r in validation_results if r['warnings']])
        avg_quality_score = sum(r['quality_score'] for r in validation_results) / total_products if total_products > 0 else 0
        
        return {
            "success": True,
            "validation_results": validation_results,
            "summary": {
                "total_products": total_products,
                "products_with_issues": products_with_issues,
                "products_with_warnings": products_with_warnings,
                "average_quality_score": round(avg_quality_score, 2),
                "ready_for_import": products_with_issues == 0
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/api/v1/admin/import/analytics")
async def get_import_analytics(request: Request):
    """Get import analytics and statistics"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        catalog_service = ProductCatalogService()
        
        # Get all products and analyze by import source
        response = catalog_service.global_table.scan()
        all_products = response['Items']
        
        # Analyze by import source
        source_stats = {}
        quality_by_source = {}
        
        for product in all_products:
            source = product.get('import_source', 'unknown')
            quality_score = product.get('quality_score', 0)
            
            if source not in source_stats:
                source_stats[source] = {
                    'count': 0,
                    'quality_scores': [],
                    'status_distribution': {}
                }
            
            source_stats[source]['count'] += 1
            source_stats[source]['quality_scores'].append(quality_score)
            
            status = product.get('verification_status', 'unknown')
            source_stats[source]['status_distribution'][status] = source_stats[source]['status_distribution'].get(status, 0) + 1
        
        # Calculate quality statistics by source
        for source, stats in source_stats.items():
            quality_scores = stats['quality_scores']
            if quality_scores:
                quality_by_source[source] = {
                    'average': sum(quality_scores) / len(quality_scores),
                    'min': min(quality_scores),
                    'max': max(quality_scores),
                    'count': len(quality_scores)
                }
        
        return {
            "success": True,
            "analytics": {
                "total_products": len(all_products),
                "source_statistics": source_stats,
                "quality_by_source": quality_by_source,
                "import_sources": list(source_stats.keys())
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.post("/api/v1/admin/cleanup/catalog")
async def cleanup_catalog_data(request: Request):
    """Admin endpoint to cleanup all catalog data (with backup)"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        body = await request.json()
        
        # Safety check - require special confirmation
        confirmation = body.get('confirmation')
        if confirmation != 'DELETE_ALL_CATALOG_DATA':
            return {
                'success': False,
                'error': 'Invalid confirmation. Use "DELETE_ALL_CATALOG_DATA" to confirm'
            }
        
        clear_jobs = body.get('clear_csv_jobs', False)
        
        # Import cleanup service
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        from scripts.cleanup_catalog_data import CatalogCleanupService
        
        cleanup_service = CatalogCleanupService()
        summary = await cleanup_service.run_full_cleanup(clear_csv_jobs=clear_jobs)
        
        return {
            'success': True,
            'cleanup_summary': summary,
            'message': 'Catalog cleanup completed successfully'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

@app.get("/api/v1/admin/cleanup/validate")
async def validate_cleanup_status(request: Request):
    """Validate current cleanup status"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'admin':
            return {'success': False, 'error': 'Admin access required'}
        
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        from scripts.cleanup_catalog_data import CatalogCleanupService
        cleanup_service = CatalogCleanupService()
        validation = await cleanup_service.validate_cleanup()
        
        return {
            'success': True,
            'validation_results': validation
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


# Admin User Management Endpoints
@app.post("/api/v1/admin/auth/login")
async def admin_login(request: Request):
    """Admin login endpoint"""
    try:
        body = await request.json()
        email = body.get('email', '').lower()
        password = body.get('password', '')
        
        if not email or not password:
            return {'success': False, 'error': 'Email and password required'}
        
        # Get DynamoDB client
        local_dynamodb = get_dynamodb_client()
        if not local_dynamodb:
            return {'success': False, 'error': 'Database connection error'}
        
        # Get user by email
        response = local_dynamodb.get_item(
            TableName=TABLE_NAMES['users'],
            Key={'id': {'S': f'user_{email}'}}
        )
        
        if 'Item' not in response:
            return {'success': False, 'error': 'Invalid credentials'}
        
        user = response['Item']
        
        # Check if user is admin
        user_role = user.get('role', {}).get('S', '')
        if user_role not in ['admin', 'super_admin']:
            return {'success': False, 'error': 'Admin access required'}
        
        # Check if user is active
        user_status = user.get('status', {}).get('S', 'active')
        if user_status != 'active':
            return {'success': False, 'error': 'Account is inactive'}
        
        # Verify password (support both bcrypt and legacy SHA-256)
        stored_password = user.get('password_hash', {}).get('S', '')
        password_valid = False
        
        # Try bcrypt first (for admin users)
        try:
            import bcrypt
            password_valid = bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8'))
        except:
            # Fallback to legacy SHA-256 verification
            password_valid = verify_password(password, stored_password)
        
        if not password_valid:
            return {'success': False, 'error': 'Invalid credentials'}
        
        # Generate admin token
        token = create_jwt_token(
            user_id=user['id']['S'],
            email=email,
            store_id='admin',
            role=user_role
        )
        
        # Update last login
        local_dynamodb.update_item(
            TableName=TABLE_NAMES['users'],
            Key={'id': {'S': f'user_{email}'}},
            UpdateExpression='SET last_login = :login_time',
            ExpressionAttributeValues={
                ':login_time': {'S': datetime.utcnow().isoformat()}
            }
        )
        
        return {
            'success': True,
            'token': token,
            'user': {
                'id': user['id']['S'],
                'email': email,
                'name': user.get('name', {}).get('S', ''),
                'role': user_role,
                'status': user_status
            }
        }
        
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        return {'success': False, 'error': 'Login failed'}


@app.get("/api/v1/admin/users")
async def get_admin_users(request: Request):
    """Get all admin users"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') not in ['admin', 'super_admin']:
            return {'success': False, 'error': 'Admin access required'}
        
        # Get DynamoDB client
        local_dynamodb = get_dynamodb_client()
        if not local_dynamodb:
            return {'success': False, 'error': 'Database connection error'}
        
        # Scan for admin users
        response = local_dynamodb.scan(
            TableName=TABLE_NAMES['users'],
            FilterExpression='begins_with(id, :prefix) AND (role = :admin_role OR role = :super_admin_role)',
            ExpressionAttributeValues={
                ':prefix': {'S': 'user_'},
                ':admin_role': {'S': 'admin'},
                ':super_admin_role': {'S': 'super_admin'}
            }
        )
        
        users = []
        for item in response.get('Items', []):
            users.append({
                'id': item['id']['S'],
                'email': item.get('email', {}).get('S', ''),
                'name': item.get('name', {}).get('S', ''),
                'phone': item.get('phone', {}).get('S', ''),
                'role': item.get('role', {}).get('S', ''),
                'status': item.get('status', {}).get('S', 'active'),
                'created_at': item.get('created_at', {}).get('S', ''),
                'updated_at': item.get('updated_at', {}).get('S', ''),
                'last_login': item.get('last_login', {}).get('S', ''),
                'created_by': item.get('created_by', {}).get('S', '')
            })
        
        return {
            'success': True,
            'users': users
        }
        
    except Exception as e:
        logger.error(f"Error getting admin users: {str(e)}")
        return {'success': False, 'error': 'Failed to get admin users'}


@app.post("/api/v1/admin/users")
async def create_admin_user(request: Request):
    """Create a new admin user"""
    try:
        # Check super admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'super_admin':
            return {'success': False, 'error': 'Super admin access required'}
        
        body = await request.json()
        email = body.get('email', '').lower()
        name = body.get('name', '')
        phone = body.get('phone', '')
        role = body.get('role', 'admin')
        password = body.get('password', '')
        
        if not email or not name or not password:
            return {'success': False, 'error': 'Email, name, and password are required'}
        
        if role not in ['admin', 'super_admin']:
            return {'success': False, 'error': 'Invalid role'}
        
        # Get DynamoDB client
        local_dynamodb = get_dynamodb_client()
        if not local_dynamodb:
            return {'success': False, 'error': 'Database connection error'}
        
        # Check if user already exists
        response = local_dynamodb.get_item(
            TableName=TABLE_NAMES['users'],
            Key={'id': {'S': f'user_{email}'}}
        )
        
        if 'Item' in response:
            return {'success': False, 'error': 'User already exists'}
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create user
        user_id = f'user_{email}'
        current_time = datetime.utcnow().isoformat()
        
        user_item = {
            'id': {'S': user_id},
            'email': {'S': email},
            'name': {'S': name},
            'role': {'S': role},
            'status': {'S': 'active'},
            'password_hash': {'S': password_hash},
            'created_at': {'S': current_time},
            'updated_at': {'S': current_time},
            'created_by': {'S': user_data.get('user_id', 'system')}
        }
        
        if phone:
            user_item['phone'] = {'S': phone}
        
        local_dynamodb.put_item(
            TableName=TABLE_NAMES['users'],
            Item=user_item
        )
        
        return {
            'success': True,
            'message': 'Admin user created successfully',
            'user': {
                'id': user_id,
                'email': email,
                'name': name,
                'phone': phone,
                'role': role,
                'status': 'active',
                'created_at': current_time,
                'updated_at': current_time
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        return {'success': False, 'error': 'Failed to create admin user'}


@app.put("/api/v1/admin/users/{user_id}")
async def update_admin_user(request: Request, user_id: str):
    """Update an admin user"""
    try:
        # Check admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') not in ['admin', 'super_admin']:
            return {'success': False, 'error': 'Admin access required'}
        
        body = await request.json()
        name = body.get('name', '')
        phone = body.get('phone', '')
        role = body.get('role', '')
        password = body.get('password', '')
        
        # Get DynamoDB client
        local_dynamodb = get_dynamodb_client()
        if not local_dynamodb:
            return {'success': False, 'error': 'Database connection error'}
        
        # Check if user exists
        response = local_dynamodb.get_item(
            TableName=TABLE_NAMES['users'],
            Key={'id': {'S': user_id}}
        )
        
        if 'Item' not in response:
            return {'success': False, 'error': 'User not found'}
        
        user = response['Item']
        current_role = user.get('role', {}).get('S', '')
        
        # Only super admin can change roles
        if role and role != current_role and user_data.get('role') != 'super_admin':
            return {'success': False, 'error': 'Only super admin can change user roles'}
        
        # Build update expression
        update_expression = 'SET updated_at = :updated_at'
        expression_values = {
            ':updated_at': {'S': datetime.utcnow().isoformat()}
        }
        
        if name:
            update_expression += ', name = :name'
            expression_values[':name'] = {'S': name}
        
        if phone is not None:
            update_expression += ', phone = :phone'
            expression_values[':phone'] = {'S': phone}
        
        if role and user_data.get('role') == 'super_admin':
            update_expression += ', role = :role'
            expression_values[':role'] = {'S': role}
        
        if password:
            update_expression += ', password_hash = :password_hash'
            expression_values[':password_hash'] = {'S': hash_password(password)}
        
        local_dynamodb.update_item(
            TableName=TABLE_NAMES['users'],
            Key={'id': {'S': user_id}},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
        
        return {
            'success': True,
            'message': 'Admin user updated successfully'
        }
        
    except Exception as e:
        logger.error(f"Error updating admin user: {str(e)}")
        return {'success': False, 'error': 'Failed to update admin user'}


@app.put("/api/v1/admin/users/{user_id}/status")
async def update_admin_user_status(request: Request, user_id: str):
    """Update admin user status"""
    try:
        # Check super admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'super_admin':
            return {'success': False, 'error': 'Super admin access required'}
        
        body = await request.json()
        status = body.get('status', '')
        
        if status not in ['active', 'inactive']:
            return {'success': False, 'error': 'Invalid status'}
        
        # Get DynamoDB client
        local_dynamodb = get_dynamodb_client()
        if not local_dynamodb:
            return {'success': False, 'error': 'Database connection error'}
        
        # Update user status
        local_dynamodb.update_item(
            TableName=TABLE_NAMES['users'],
            Key={'id': {'S': user_id}},
            UpdateExpression='SET status = :status, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':status': {'S': status},
                ':updated_at': {'S': datetime.utcnow().isoformat()}
            }
        )
        
        return {
            'success': True,
            'message': f'User status updated to {status}'
        }
        
    except Exception as e:
        logger.error(f"Error updating user status: {str(e)}")
        return {'success': False, 'error': 'Failed to update user status'}


@app.delete("/api/v1/admin/users/{user_id}")
async def delete_admin_user(request: Request, user_id: str):
    """Delete an admin user"""
    try:
        # Check super admin permissions
        user_data = get_user_from_jwt(request)
        if user_data.get('role') != 'super_admin':
            return {'success': False, 'error': 'Super admin access required'}
        
        # Prevent self-deletion
        if user_id == user_data.get('user_id'):
            return {'success': False, 'error': 'Cannot delete your own account'}
        
        # Get DynamoDB client
        local_dynamodb = get_dynamodb_client()
        if not local_dynamodb:
            return {'success': False, 'error': 'Database connection error'}
        
        # Delete user
        local_dynamodb.delete_item(
            TableName=TABLE_NAMES['users'],
            Key={'id': {'S': user_id}}
        )
        
        return {
            'success': True,
            'message': 'Admin user deleted successfully'
        }
        
    except Exception as e:
        logger.error(f"Error deleting admin user: {str(e)}")
        return {'success': False, 'error': 'Failed to delete admin user'}


# Lambda handler
handler = Mangum(app)
lambda_handler = handler
