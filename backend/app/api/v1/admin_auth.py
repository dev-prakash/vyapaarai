"""
Admin Authentication API Endpoints
Secure authentication for admin users with bcrypt password verification
"""

import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

from app.core.security import (
    get_jwt_secret, get_jwt_algorithm,
    create_admin_token, verify_token,
    JWT_ADMIN_TOKEN_EXPIRE_HOURS
)
from app.core.password import hash_password, verify_password
from app.core.audit import log_auth_success, log_auth_failure
from app.core.database import get_dynamodb, USERS_TABLE

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/admin/auth", tags=["admin-authentication"])

# JWT Configuration - imported from centralized security module
# DO NOT define JWT_SECRET here - use get_jwt_secret() instead

# DynamoDB setup - use centralized connection manager
dynamodb = get_dynamodb()
users_table = dynamodb.Table(USERS_TABLE) if dynamodb else None

# Security scheme
security = HTTPBearer()


async def get_current_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get current authenticated admin user from JWT token

    Args:
        credentials: HTTP Authorization credentials containing JWT token

    Returns:
        User information dict

    Raises:
        HTTPException: If token is invalid or user doesn't have admin permissions
    """
    try:
        token = credentials.credentials

        # Decode and verify JWT token using centralized security module
        payload = verify_token(token, expected_type="admin")

        # Extract user information
        user_data = {
            'id': payload.get('sub'),
            'email': payload.get('email'),
            'role': payload.get('role'),
            'name': payload.get('name', '')
        }

        # Verify admin role
        if user_data['role'] not in ['admin', 'super_admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        return user_data

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
    except Exception as e:
        logger.error(f"Error verifying admin token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


class AdminLoginRequest(BaseModel):
    """Admin login request model"""
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., min_length=6, description="Admin password")


class AdminLoginResponse(BaseModel):
    """Admin login response model"""
    success: bool
    token: str
    user: dict
    message: str


# Password functions are now imported from app.core.password
# hash_password() - Hash a password using bcrypt
# verify_password() - Verify a password against bcrypt hash


def create_jwt_token(user_data: dict) -> str:
    """
    Create JWT token for authenticated admin user using centralized security module

    Args:
        user_data: User information to encode in token

    Returns:
        JWT token string
    """
    payload = {
        'sub': user_data['id'],
        'email': user_data['email'],
        'role': user_data['role'],
        'name': user_data.get('name', '')
    }

    return create_admin_token(payload)


@router.post("/login", response_model=AdminLoginResponse, summary="Admin Login")
async def admin_login(login_request: AdminLoginRequest, request: Request):
    """
    Authenticate admin user with email and password

    **Features:**
    - Email and password authentication
    - Bcrypt password verification
    - JWT token generation
    - Role-based access (admin, super_admin only)
    - Login tracking

    **Returns:**
    - JWT token for authenticated sessions
    - User profile information

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/admin/auth/login" \\
         -H "Content-Type: application/json" \\
         -d '{
           "email": "nimda.vai@gmail.com",
           "password": "your_password"
         }'
    ```
    """
    try:
        logger.info(f"Admin login attempt for: {login_request.email}")

        # Query DynamoDB for user by email
        response = users_table.scan(
            FilterExpression='email = :email',
            ExpressionAttributeValues={':email': login_request.email}
        )

        if not response.get('Items'):
            logger.warning(f"Admin login failed: User not found - {login_request.email}")
            log_auth_failure(login_request.email, "admin_password", "User not found", request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        user = response['Items'][0]

        # Check if user has admin role
        user_role = user.get('role', '')
        if user_role not in ['admin', 'super_admin']:
            logger.warning(f"Admin login failed: Insufficient permissions - {login_request.email} (role: {user_role})")
            log_auth_failure(login_request.email, "admin_password", f"Insufficient permissions (role: {user_role})", request)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required. You do not have permission."
            )

        # Check if account is active
        if user.get('status') != 'active':
            logger.warning(f"Admin login failed: Account inactive - {login_request.email}")
            log_auth_failure(login_request.email, "admin_password", "Account inactive", request)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact support."
            )

        # Verify password
        password_hash = user.get('password_hash', '')
        if not password_hash:
            logger.error(f"Admin login failed: No password hash found - {login_request.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication configuration error"
            )

        if not verify_password(login_request.password, password_hash):
            logger.warning(f"Admin login failed: Invalid password - {login_request.email}")
            log_auth_failure(login_request.email, "admin_password", "Invalid password", request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Update last login timestamp
        try:
            users_table.update_item(
                Key={'id': user['id']},
                UpdateExpression='SET last_login = :timestamp',
                ExpressionAttributeValues={
                    ':timestamp': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to update last_login: {str(e)}")
            # Don't fail login if timestamp update fails

        # Create JWT token
        user_data = {
            'id': user['id'],
            'email': user['email'],
            'role': user['role'],
            'name': user.get('name', 'Admin User')
        }

        token = create_jwt_token(user_data)

        logger.info(f"Admin login successful: {login_request.email}")

        # Audit log: successful admin login
        log_auth_success(user['id'], "admin_password", request)

        return AdminLoginResponse(
            success=True,
            token=token,
            user=user_data,
            message="Login successful"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login. Please try again."
        )


@router.post("/verify", summary="Verify JWT Token")
async def verify_token(token: str):
    """
    Verify JWT token validity

    **Parameters:**
    - token: JWT token to verify

    **Returns:**
    - User information if token is valid
    """
    try:
        payload = verify_token(token, expected_type="admin")
        return {
            "success": True,
            "user": {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "role": payload.get("role"),
                "name": payload.get("name")
            }
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


@router.get("/health", summary="Admin Auth Health Check")
async def health_check():
    """Health check endpoint for admin authentication service"""
    return {
        "status": "healthy",
        "service": "admin-auth",
        "timestamp": datetime.utcnow().isoformat()
    }
