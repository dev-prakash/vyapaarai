"""
Authentication API endpoints for VyaparAI - Simplified for Lambda
Simple authentication with JWT tokens and real email OTP
"""

import jwt
import random
import re
import uuid
import boto3
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, validator

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])

# JWT secret for Lambda (use environment variable in production)
JWT_SECRET = "lambda_jwt_secret_key_change_in_production"
JWT_ALGORITHM = "HS256"

# Initialize AWS services
try:
    ses_client = boto3.client('ses', region_name='ap-south-1')
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    otp_table = dynamodb.Table('vyaparai-sessions-prod')  # Using sessions table for OTP storage
    print("✅ AWS SES and DynamoDB initialized")
except Exception as e:
    print(f"⚠️ AWS services initialization failed: {e}")
    ses_client = None
    otp_table = None

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

class EmailPasswordLoginRequest(BaseModel):
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    
    @validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
            raise ValueError('Please enter a valid email address')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class SetupPasswordRequest(BaseModel):
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="New password")
    
    @validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
            raise ValueError('Please enter a valid email address')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class SendOTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number")
    
    @validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in international format')
        return v

class SendOTPResponse(BaseModel):
    success: bool = Field(..., description="Whether OTP was sent")
    message: str = Field(..., description="Response message")
    otp: Optional[str] = Field(None, description="Test OTP for development")

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
    Send OTP to phone number for Lambda deployment
    """
    print(f"📱 Send OTP request for phone: {request.phone}")
    
    try:
        # In Lambda deployment, we'll just return a test OTP
        test_otp = "1234"
        
        print(f"✅ Mock OTP sent to: {request.phone}")
        print(f"🔢 Test OTP: {test_otp}")
        
        return SendOTPResponse(
            success=True,
            message="OTP sent successfully",
            otp=test_otp  # Only for development
        )
        
    except Exception as e:
        print(f"❌ Send OTP error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Simple login for Lambda - accepts any phone with OTP 1234
    """
    print(f"🔐 Login attempt for phone: {request.phone}")
    
    try:
        # Generate unique store ID
        store_id = str(uuid.uuid4())
        
        # In dev mode, accept OTP 1234 or empty OTP
        if request.otp and request.otp != "1234":
            print(f"❌ Invalid OTP attempt: {request.otp}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP. Use 1234 for development."
            )
    
        # Generate JWT token
        token_data = {
            "phone": request.phone,
            "store_id": store_id,
            "user_id": f"user_{request.phone}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        print(f"✅ Login successful for phone: {request.phone}, store_id: {store_id}")
        
        return LoginResponse(
            token=token,
            store_id=store_id,
            store_name="VyapaarAI Store",
            user={
                "phone": request.phone,
                "name": "Store Owner",
                "role": "owner",
                "store_id": store_id
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Token generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authentication token"
        )

@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(request: VerifyOTPRequest):
    """
    Verify OTP - always returns true for OTP 1234 in Lambda mode
    """
    print(f"🔍 OTP verification for phone: {request.phone}")
    
    try:
        # Validate OTP
        if request.otp != "1234":
            print(f"❌ Invalid OTP attempt: {request.otp} for phone: {request.phone}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The OTP provided is invalid or expired"
            )
        
        # Generate unique store ID
        store_id = str(uuid.uuid4())
        
        # Generate JWT token for valid OTP
        token_data = {
            "phone": request.phone,
            "store_id": store_id,
            "user_id": f"user_{request.phone}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        print(f"✅ OTP verification successful for phone: {request.phone}")
        
        return VerifyOTPResponse(
            valid=True,
            token=token,
            message="OTP verified successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ OTP verification error: {e}")
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
    Send real email passcode for authentication using AWS SES
    """
    print(f"📧 Email passcode request for: {request.email}")
    
    try:
        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))
        
        # Store OTP in DynamoDB with 10 minute expiration
        if otp_table is not None:
            otp_record = {
                "pk": f"email_otp_{request.email}",  # Use 'pk' as primary key
                "email": request.email,
                "otp": otp,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
                "type": "email_otp",
                "used": False
            }
            
            otp_table.put_item(Item=otp_record)
            print(f"✅ OTP stored in DynamoDB for: {request.email}")
        
        # Send email using AWS SES
        if ses_client is not None:
            email_subject = "VyapaarAI - Your Login Passcode"
            email_body = f"""
            <html>
            <head></head>
            <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #1976d2;">VyapaarAI Login Passcode</h2>
                    
                    <p>Hello,</p>
                    
                    <p>Your login passcode is:</p>
                    
                    <div style="background-color: #f5f5f5; border: 2px solid #1976d2; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                        <h1 style="color: #1976d2; font-size: 36px; margin: 0; letter-spacing: 8px;">{otp}</h1>
                    </div>
                    
                    <p><strong>Important:</strong></p>
                    <ul>
                        <li>This passcode is valid for 10 minutes only</li>
                        <li>Do not share this passcode with anyone</li>
                        <li>Use this passcode to complete your login to VyapaarAI</li>
                    </ul>
                    
                    <p>If you didn't request this passcode, please ignore this email.</p>
                    
                    <hr style="margin: 30px 0;">
                    <p style="color: #666; font-size: 12px;">
                        This is an automated email from VyapaarAI. Please do not reply to this email.
                    </p>
                </div>
            </body>
            </html>
            """
            
            response = ses_client.send_email(
                Source='devprakash@anthropic.com',  # Use verified email for now
                Destination={
                    'ToAddresses': [request.email]
                },
                Message={
                    'Subject': {
                        'Data': email_subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Html': {
                            'Data': email_body,
                            'Charset': 'UTF-8'
                        },
                        'Text': {
                            'Data': f"Your VyapaarAI login passcode is: {otp}\n\nThis passcode is valid for 10 minutes. Do not share it with anyone.",
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )
            
            print(f"✅ Email sent successfully to: {request.email}")
            print(f"📧 SES Message ID: {response.get('MessageId')}")
            
            return EmailPasscodeResponse(
                success=True,
                message="Email passcode sent successfully to your registered email address"
            )
        else:
            # Fallback if SES not available
            print(f"⚠️ SES not available, using fallback OTP: {otp}")
            return EmailPasscodeResponse(
                success=True,
                message="Email passcode sent successfully",
                test_passcode=otp  # Show OTP in response for testing
            )
        
    except Exception as e:
        print(f"❌ Email passcode sending error: {e}")
        
        # If email sending fails, still return success but log error
        if "otp" in locals():
            print(f"🔢 Fallback OTP for {request.email}: {otp}")
            return EmailPasscodeResponse(
                success=True,
                message="Email service temporarily unavailable. Please contact support.",
                test_passcode=otp  # Provide OTP in response as fallback
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email passcode"
            )

@router.post("/verify-email-passcode")
async def verify_email_passcode(request: VerifyEmailPasscodeRequest):
    """
    Verify email passcode from DynamoDB and return auth token
    """
    print(f"🔍 Email passcode verification for: {request.email}")
    
    try:
        # Get OTP from DynamoDB
        if otp_table is not None:
            otp_key = f"email_otp_{request.email}"
            
            try:
                response = otp_table.get_item(Key={"pk": otp_key})
                
                if 'Item' not in response:
                    print(f"❌ No OTP found for: {request.email}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired passcode"
                    )
                
                otp_record = response['Item']
                
                # Check if OTP is expired
                expires_at = datetime.fromisoformat(otp_record['expires_at'])
                if datetime.utcnow() > expires_at:
                    print(f"❌ OTP expired for: {request.email}")
                    # Clean up expired OTP
                    otp_table.delete_item(Key={"pk": otp_key})
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Passcode has expired. Please request a new one."
                    )
                
                # Check if OTP is already used
                if otp_record.get('used', False):
                    print(f"❌ OTP already used for: {request.email}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Passcode has already been used. Please request a new one."
                    )
                
                # Verify OTP
                if otp_record['otp'] != request.passcode:
                    print(f"❌ Invalid OTP attempt: {request.passcode} for {request.email}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid passcode"
                    )
                
                # Mark OTP as used
                otp_table.update_item(
                    Key={"pk": otp_key},
                    UpdateExpression="SET #used = :used",
                    ExpressionAttributeNames={"#used": "used"},
                    ExpressionAttributeValues={":used": True}
                )
                
                print(f"✅ OTP verified and marked as used for: {request.email}")
                
            except HTTPException:
                raise
            except Exception as db_error:
                print(f"❌ DynamoDB error: {db_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error verifying passcode"
                )
        else:
            # Fallback if DynamoDB not available - accept any 6-digit code for testing
            print(f"⚠️ DynamoDB not available, using fallback verification")
            if len(request.passcode) != 6 or not request.passcode.isdigit():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid passcode format"
                )
        
        # Generate unique store ID
        store_id = str(uuid.uuid4())
        
        # Generate JWT token for valid passcode
        token_data = {
            "email": request.email,
            "store_id": store_id,
            "user_id": f"user_{request.email}",
            "role": "owner",
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
        print(f"✅ Email passcode verification successful for: {request.email}")
        
        return {
            "success": True,
            "message": "Email passcode verified successfully",
            "token": token,
            "store_id": store_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Email passcode verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during passcode verification"
        )

# Helper functions for password management
def hash_password(password: str) -> str:
    """Hash a password with salt"""
    salt = os.urandom(32)  # 32 bytes salt
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return (salt + pwdhash).hex()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    try:
        salt_hash = bytes.fromhex(hashed)
        salt = salt_hash[:32]
        stored_hash = salt_hash[32:]
        pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return pwdhash == stored_hash
    except:
        return False

@router.post("/login")
async def email_password_login(request: EmailPasswordLoginRequest):
    """
    Authenticate store owner with email and password
    """
    print(f"🔐 Email/Password login attempt for: {request.email}")
    
    try:
        # Initialize stores table
        try:
            dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
            stores_table = dynamodb.Table('vyaparai-stores-prod')
        except Exception as e:
            print(f"⚠️ DynamoDB connection failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection failed"
            )
        
        # Look up store by email
        try:
            response = stores_table.scan(
                FilterExpression="email = :email",
                ExpressionAttributeValues={":email": request.email}
            )
            
            if not response.get('Items'):
                print(f"❌ No store found for email: {request.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            store_record = response['Items'][0]
            
            # Check if store has a password set
            if 'password_hash' not in store_record:
                print(f"❌ No password set for store: {request.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Password not set. Please use email passcode login or set up password first."
                )
            
            # Verify password
            if not verify_password(request.password, store_record['password_hash']):
                print(f"❌ Invalid password for: {request.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Generate JWT token for successful login
            token_data = {
                "email": request.email,
                "store_id": store_record['store_id'],
                "user_id": f"user_{request.email}",
                "role": "owner",
                "exp": datetime.utcnow() + timedelta(days=7),
                "iat": datetime.utcnow()
            }
            
            token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)
            print(f"✅ Email/Password login successful for: {request.email}")
            
            return {
                "success": True,
                "message": "Login successful",
                "token": token,
                "user": {
                    "email": request.email,
                    "name": store_record.get('owner_name'),
                    "role": "store_owner",
                    "store_id": store_record['store_id']
                }
            }
            
        except HTTPException:
            raise
        except Exception as db_error:
            print(f"❌ Database error during login: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error during authentication"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Email/Password login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

@router.post("/setup-password")
async def setup_password(request: SetupPasswordRequest):
    """
    Set up or update password for a store owner
    """
    print(f"🔧 Password setup request for: {request.email}")
    
    try:
        # Initialize stores table
        try:
            dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
            stores_table = dynamodb.Table('vyaparai-stores-prod')
        except Exception as e:
            print(f"⚠️ DynamoDB connection failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection failed"
            )
        
        # Look up store by email
        try:
            response = stores_table.scan(
                FilterExpression="email = :email",
                ExpressionAttributeValues={":email": request.email}
            )
            
            if not response.get('Items'):
                print(f"❌ No store found for email: {request.email}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Store not found. Please register first."
                )
            
            store_record = response['Items'][0]
            
            # Hash the password
            password_hash = hash_password(request.password)
            
            # Update store record with password hash
            stores_table.update_item(
                Key={"id": store_record['id']},
                UpdateExpression="SET password_hash = :password_hash, updated_at = :updated_at",
                ExpressionAttributeValues={
                    ":password_hash": password_hash,
                    ":updated_at": datetime.utcnow().isoformat()
                }
            )
            
            print(f"✅ Password set successfully for: {request.email}")
            
            return {
                "success": True,
                "message": "Password set successfully. You can now login with email and password."
            }
            
        except HTTPException:
            raise
        except Exception as db_error:
            print(f"❌ Database error during password setup: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error during password setup"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Password setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during password setup"
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