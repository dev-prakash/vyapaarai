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
from fastapi import FastAPI, HTTPException
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
# Commenting out to prevent duplicate headers
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

def verify_password(password, hashed_password):
    """Verify password against hashed password"""
    try:
        salt, stored_hash = hashed_password.split('$', 1)
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
            return {
                "store_id": store.get('store_id', {}).get('S'),
                "name": store.get('name', {}).get('S'),
                "owner_name": store.get('owner_name', {}).get('S', 'Store Owner'),
                "email": email,
                "phone": store.get('phone', {}).get('S'),
                "status": store.get('status', {}).get('S', 'active')
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
        # Store password with user credentials in users table
        user_id = f"user_{email}"
        item = {
            'id': {'S': user_id},
            'email': {'S': email},
            'password_hash': {'S': hashed_password},
            'created_at': {'S': datetime.utcnow().isoformat()},
            'updated_at': {'S': datetime.utcnow().isoformat()},
            'password_reset_token': {'S': ''},  # Empty by default
            'password_reset_expires': {'S': ''},  # Empty by default
            'failed_attempts': {'N': '0'},
            'locked_until': {'S': ''}  # Empty by default
        }
        
        local_dynamodb.put_item(
            TableName=TABLE_NAMES['users'],  # Using users table for user credentials
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
        # Try to get user by email from users table
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

@app.post("/api/v1/stores/verify")
async def verify_store(request: dict):
    """Check if email belongs to registered store"""
    try:
        email = request.get('email')
        if not email or not validate_email(email):
            raise HTTPException(status_code=400, detail="Please enter a valid email address")
        
        email = email.lower()
        store = await get_store_by_email(email)
        
        if store:
            return {
                "success": True,
                "message": "Store found",
                "store": store
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No store is registered with {email}. This email address is not in our store database. You can register a new store or try a different email address if you already have one registered."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store verification error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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
        
        user_id = f"user_{email}"
        local_dynamodb.update_item(
            TableName=TABLE_NAMES['users'],
            Key={'id': {'S': user_id}},
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
async def get_orders(store_id: str = None):
    """Get orders for a store"""
    try:
        if not store_id:
            raise HTTPException(status_code=400, detail="store_id parameter is required")
        
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
        return None
    
    try:
        product_id = generate_product_id()
        current_time = datetime.utcnow().isoformat()
        
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
        
        if product_data.get('generic_product_id'):
            product_item['generic_product_id'] = {'S': product_data['generic_product_id']}
        
        # Add boolean fields
        if 'is_returnable' in product_data:
            product_item['is_returnable'] = {'BOOL': product_data['is_returnable']}
        
        if 'is_perishable' in product_data:
            product_item['is_perishable'] = {'BOOL': product_data['is_perishable']}
        
        dynamodb.put_item(
            TableName=TABLE_NAMES['products'],
            Item=product_item
        )
        
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
                    'stock_quantity': int(item['stock_quantity']['N']),
                    'unit': item.get('unit', {}).get('S', 'piece'),
                    'sku': item.get('sku', {}).get('S', ''),
                    'created_at': item['created_at']['S'],
                    'updated_at': item.get('updated_at', {}).get('S', item['created_at']['S'])
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
async def get_products(store_id: str = None):
    """Get products for a store"""
    try:
        if not store_id:
            raise HTTPException(status_code=400, detail="store_id parameter is required")
        
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
async def create_product(request: dict):
    """Create a new product"""
    try:
        # Validate required fields
        required_fields = ['store_id']
        if 'product_name' not in request and 'name' not in request:
            required_fields.append('product_name or name')
        if 'selling_price' not in request and 'price' not in request:
            required_fields.append('selling_price or price')
        
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Create product
        product = await create_product_in_db(request)
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
async def get_stock_movements(store_id: str = None):
    """Get stock movement history"""
    try:
        if not store_id:
            raise HTTPException(status_code=400, detail="store_id parameter is required")
        
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
async def get_inventory_alerts(store_id: str = None):
    """Get low stock alerts"""
    try:
        if not store_id:
            raise HTTPException(status_code=400, detail="store_id parameter is required")
        
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
async def search_by_barcode(barcode: str, store_id: str = None):
    """Search for products by barcode"""
    try:
        if not store_id:
            raise HTTPException(status_code=400, detail="store_id parameter is required")
        
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
async def update_product(product_id: str, request: dict):
    """Update an existing product"""
    try:
        # Validate store_id
        store_id = request.get('store_id')
        if not store_id:
            raise HTTPException(status_code=400, detail="store_id is required")
        
        # Update product
        success = await update_product_in_db(product_id, store_id, request)
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
async def update_product_stock(product_id: str, request: dict):
    """Update product stock levels"""
    try:
        # Validate required fields
        required_fields = ['movement_type', 'quantity']
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        movement_type = request['movement_type']
        quantity = int(request['quantity'])
        reason = request.get('reason', '')
        
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
async def delete_product(product_id: str, store_id: str = None):
    """Delete a product"""
    try:
        if not store_id:
            raise HTTPException(status_code=400, detail="store_id parameter is required")
        
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
                'id': {'S': product_id},
                'store_id': {'S': store_id}
            }
        )
        
        if 'Item' in response:
            item = response['Item']
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
        
        # Add fields to update
        if 'product_name' in data:
            update_expression += ", #name = :name"
            expression_values[':name'] = {'S': data['product_name']}
        
        if 'brand_name' in data:
            update_expression += ", brand = :brand"
            expression_values[':brand'] = {'S': data['brand_name']}
        
        if 'sku' in data:
            update_expression += ", sku = :sku"
            expression_values[':sku'] = {'S': data['sku']}
        
        if 'barcode' in data:
            update_expression += ", barcode = :barcode"
            expression_values[':barcode'] = {'S': data['barcode']}
        
        if 'selling_price' in data:
            update_expression += ", price = :price"
            expression_values[':price'] = {'N': str(data['selling_price'])}
        
        if 'cost_price' in data:
            update_expression += ", cost_price = :cost_price"
            expression_values[':cost_price'] = {'N': str(data['cost_price'])}
        
        if 'current_stock' in data:
            update_expression += ", stock_quantity = :stock"
            expression_values[':stock'] = {'N': str(data['current_stock'])}
        
        if 'min_stock_level' in data:
            update_expression += ", min_stock_level = :min_stock"
            expression_values[':min_stock'] = {'N': str(data['min_stock_level'])}
        
        if 'max_stock_level' in data:
            update_expression += ", max_stock_level = :max_stock"
            expression_values[':max_stock'] = {'N': str(data['max_stock_level'])}
        
        if 'description' in data:
            update_expression += ", description = :description"
            expression_values[':description'] = {'S': data['description']}
        
        response = dynamodb.update_item(
            TableName=TABLE_NAMES['products'],
            Key={
                'id': {'S': product_id},
                'store_id': {'S': store_id}
            },
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames={'#name': 'name'} if 'product_name' in data else {},
            ReturnValues='UPDATED_NEW'
        )
        
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
                'id': {'S': product_id},
                'store_id': {'S': store_id}
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
        
        response = dynamodb.delete_item(
            TableName=TABLE_NAMES['products'],
            Key={
                'id': {'S': product_id},
                'store_id': {'S': store_id}
            },
            ReturnValues='ALL_OLD'
        )
        
        return 'Attributes' in response
        
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        return False

def generate_product_id():
    """Generate unique product ID using timestamp and random string"""
    timestamp = int(time.time())
    random_str = secrets.token_hex(4)
    return f"PROD-{timestamp}-{random_str}"

# Create Lambda handler
handler = Mangum(app, lifespan="off")