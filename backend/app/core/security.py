"""
Centralized Security Configuration for VyaparAI

This module provides:
- JWT configuration with environment variable validation
- Token creation and verification utilities
- Security constants and helpers

All authentication modules should import JWT settings from here
instead of defining their own hardcoded values.
"""

import os

# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    # Environment detection
    "ENVIRONMENT",
    "IS_PRODUCTION",
    "IS_DEVELOPMENT",
    # JWT configuration
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
    "JWT_CUSTOMER_TOKEN_EXPIRE_DAYS",
    "JWT_ADMIN_TOKEN_EXPIRE_HOURS",
    "JWT_STORE_OWNER_TOKEN_EXPIRE_DAYS",
    # Configuration functions
    "validate_security_config",
    "get_jwt_secret",
    "get_jwt_algorithm",
    # Token creation
    "create_access_token",
    "create_refresh_token",
    "create_customer_token",
    "create_admin_token",
    "create_store_owner_token",
    # Token verification
    "verify_token",
    "decode_token_unsafe",
    # FastAPI dependencies
    "security_scheme",
    "get_current_user",
    "get_current_store_owner",
    "get_current_customer",
    "get_current_admin",
    "get_optional_current_user",
]
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt

logger = logging.getLogger(__name__)

# =============================================================================
# Environment Detection
# =============================================================================

ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION: bool = ENVIRONMENT == "production"
IS_DEVELOPMENT: bool = ENVIRONMENT == "development"

# =============================================================================
# JWT Configuration - Loaded from Environment
# =============================================================================

# Primary JWT secret - used for all token types
JWT_SECRET: str = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

# Token expiration settings (in minutes/hours/days)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Legacy support - customer tokens (longer expiry for mobile apps)
JWT_CUSTOMER_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_CUSTOMER_TOKEN_EXPIRE_DAYS", "30"))

# Admin tokens (shorter expiry for security)
JWT_ADMIN_TOKEN_EXPIRE_HOURS: int = int(os.getenv("JWT_ADMIN_TOKEN_EXPIRE_HOURS", "24"))

# Store owner tokens
JWT_STORE_OWNER_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_STORE_OWNER_TOKEN_EXPIRE_DAYS", "7"))

# =============================================================================
# Development Fallback
# =============================================================================

# Only used in development when JWT_SECRET is not set
# DEPRECATED: This fallback will be removed in v2.0. Always set JWT_SECRET.
_DEV_FALLBACK_SECRET = "dev_only_fallback_secret_not_for_production_use_32chars"
_DEV_FALLBACK_WARNED = False

def _get_jwt_secret() -> str:
    """
    Get JWT secret with environment-aware fallback.

    In production: Requires JWT_SECRET to be set and secure
    In development: Falls back to a development secret with warning
    """
    global JWT_SECRET

    if JWT_SECRET and len(JWT_SECRET) >= 32:
        return JWT_SECRET

    if IS_PRODUCTION:
        raise ValueError(
            "JWT_SECRET environment variable must be set and at least 32 characters in production. "
            "Generate a secure secret with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    # Development fallback
    if not JWT_SECRET:
        global _DEV_FALLBACK_WARNED
        if not _DEV_FALLBACK_WARNED:
            logger.warning(
                "DEPRECATED: JWT_SECRET not set - using development fallback. "
                "This fallback will be removed in v2.0. Always set JWT_SECRET. "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
            _DEV_FALLBACK_WARNED = True
        return _DEV_FALLBACK_SECRET

    if len(JWT_SECRET) < 32:
        logger.warning(
            f"JWT_SECRET is only {len(JWT_SECRET)} characters. "
            "Recommended minimum is 32 characters for security."
        )
        return JWT_SECRET

    return JWT_SECRET


# =============================================================================
# Configuration Validation
# =============================================================================

def validate_security_config() -> Dict[str, Any]:
    """
    Validate security configuration on application startup.

    Returns:
        Dict with validation results and any warnings

    Raises:
        ValueError: If critical security requirements not met in production
    """
    issues = []
    warnings = []

    # Check JWT_SECRET
    jwt_secret = os.getenv("JWT_SECRET", "")

    if not jwt_secret:
        if IS_PRODUCTION:
            issues.append("JWT_SECRET environment variable is not set")
        else:
            warnings.append("JWT_SECRET not set - using development fallback")
    elif len(jwt_secret) < 32:
        if IS_PRODUCTION:
            issues.append(f"JWT_SECRET is too short ({len(jwt_secret)} chars). Minimum 32 required.")
        else:
            warnings.append(f"JWT_SECRET is short ({len(jwt_secret)} chars). Recommend 32+.")

    # Check for obvious development secrets in production
    dangerous_patterns = [
        "dev_", "test_", "change_in_production", "your_",
        "secret", "password", "123", "abc"
    ]

    if IS_PRODUCTION and jwt_secret:
        for pattern in dangerous_patterns:
            if pattern.lower() in jwt_secret.lower():
                issues.append(
                    f"JWT_SECRET appears to contain development pattern '{pattern}'. "
                    "Use a cryptographically random secret in production."
                )
                break

    # Validate algorithm
    allowed_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
    if JWT_ALGORITHM not in allowed_algorithms:
        issues.append(f"JWT_ALGORITHM '{JWT_ALGORITHM}' is not supported. Use one of: {allowed_algorithms}")

    # Log results
    if issues:
        for issue in issues:
            logger.error(f"Security configuration error: {issue}")
        if IS_PRODUCTION:
            raise ValueError(f"Security configuration errors: {'; '.join(issues)}")

    for warning in warnings:
        logger.warning(f"Security configuration warning: {warning}")

    return {
        "valid": len(issues) == 0,
        "environment": ENVIRONMENT,
        "issues": issues,
        "warnings": warnings,
        "jwt_algorithm": JWT_ALGORITHM,
        "access_token_expire_minutes": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        "refresh_token_expire_days": JWT_REFRESH_TOKEN_EXPIRE_DAYS
    }


# =============================================================================
# Token Creation Utilities
# =============================================================================

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    token_type: str = "access"
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        expires_delta: Optional custom expiration time
        token_type: Type of token (access, refresh, etc.)

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": token_type
    })

    encoded_jwt = jwt.encode(to_encode, _get_jwt_secret(), algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.

    Args:
        user_id: User identifier to encode
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }

    encoded_jwt = jwt.encode(to_encode, _get_jwt_secret(), algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_customer_token(customer_data: Dict[str, Any]) -> str:
    """
    Create a JWT token for customers (longer expiry for mobile apps).

    Args:
        customer_data: Customer information to encode

    Returns:
        Encoded JWT token string
    """
    expire = datetime.utcnow() + timedelta(days=JWT_CUSTOMER_TOKEN_EXPIRE_DAYS)

    to_encode = {
        **customer_data,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "customer"
    }

    return jwt.encode(to_encode, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_admin_token(admin_data: Dict[str, Any]) -> str:
    """
    Create a JWT token for admin users (shorter expiry for security).

    Args:
        admin_data: Admin user information to encode

    Returns:
        Encoded JWT token string
    """
    expire = datetime.utcnow() + timedelta(hours=JWT_ADMIN_TOKEN_EXPIRE_HOURS)

    to_encode = {
        **admin_data,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "admin"
    }

    return jwt.encode(to_encode, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_store_owner_token(store_owner_data: Dict[str, Any]) -> str:
    """
    Create a JWT token for store owners.

    Args:
        store_owner_data: Store owner information to encode

    Returns:
        Encoded JWT token string
    """
    expire = datetime.utcnow() + timedelta(days=JWT_STORE_OWNER_TOKEN_EXPIRE_DAYS)

    to_encode = {
        **store_owner_data,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "store_owner"
    }

    return jwt.encode(to_encode, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


# =============================================================================
# Token Verification Utilities
# =============================================================================

def verify_token(
    token: str,
    expected_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string to verify
        expected_type: Optional expected token type to validate

    Returns:
        Decoded token payload

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid
        ValueError: If token type doesn't match expected
    """
    payload = jwt.decode(
        token,
        _get_jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        options={
            "verify_signature": True,
            "verify_exp": True,
            "require": ["exp", "iat"]
        }
    )

    if expected_type and payload.get("type") != expected_type:
        raise ValueError(f"Expected token type '{expected_type}', got '{payload.get('type')}'")

    return payload


def decode_token_unsafe(token: str) -> Dict[str, Any]:
    """
    Decode a JWT token WITHOUT verifying signature.
    Only use for debugging/logging - never trust the data!

    Args:
        token: JWT token string

    Returns:
        Decoded token payload (UNVERIFIED)
    """
    return jwt.decode(
        token,
        options={"verify_signature": False}
    )


# =============================================================================
# Exported Configuration (for backward compatibility)
# =============================================================================

def get_jwt_secret() -> str:
    """Get the active JWT secret. Use this instead of accessing JWT_SECRET directly."""
    return _get_jwt_secret()


def get_jwt_algorithm() -> str:
    """Get the JWT algorithm."""
    return JWT_ALGORITHM


# =============================================================================
# FastAPI Authentication Dependencies
# =============================================================================

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Security scheme for Bearer token authentication
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get any authenticated user from JWT token.
    Works with all token types (customer, admin, store_owner).

    Args:
        credentials: HTTP Authorization credentials containing JWT token

    Returns:
        User information dict with token payload

    Raises:
        HTTPException: If token is missing, invalid, or expired
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        token = credentials.credentials
        payload = verify_token(token)

        return {
            'user_id': payload.get('sub'),
            'email': payload.get('email'),
            'phone': payload.get('phone'),
            'role': payload.get('role'),
            'store_id': payload.get('store_id'),
            'customer_id': payload.get('customer_id'),
            'token_type': payload.get('type'),
            'payload': payload
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_store_owner(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get authenticated store owner from JWT token.
    Only allows store_owner token type.

    Args:
        credentials: HTTP Authorization credentials containing JWT token

    Returns:
        Store owner information dict

    Raises:
        HTTPException: If not a valid store owner token
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        token = credentials.credentials
        payload = verify_token(token, expected_type="store_owner")

        return {
            'user_id': payload.get('sub'),
            'phone': payload.get('phone'),
            'store_id': payload.get('store_id'),
            'role': payload.get('role', 'owner'),
            'token_type': 'store_owner',
            'payload': payload
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Store owner access required"
        )


async def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get authenticated customer from JWT token.
    Only allows customer token type.

    Args:
        credentials: HTTP Authorization credentials containing JWT token

    Returns:
        Customer information dict

    Raises:
        HTTPException: If not a valid customer token
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        token = credentials.credentials
        payload = verify_token(token, expected_type="customer")

        return {
            'customer_id': payload.get('customer_id') or payload.get('sub'),
            'email': payload.get('email'),
            'phone': payload.get('phone'),
            'token_type': 'customer',
            'payload': payload
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer access required"
        )


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get authenticated admin from JWT token.
    Only allows admin token type.

    Args:
        credentials: HTTP Authorization credentials containing JWT token

    Returns:
        Admin information dict

    Raises:
        HTTPException: If not a valid admin token
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        token = credentials.credentials
        payload = verify_token(token, expected_type="admin")

        user_role = payload.get('role')
        if user_role not in ['admin', 'super_admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )

        return {
            'user_id': payload.get('sub'),
            'email': payload.get('email'),
            'role': user_role,
            'name': payload.get('name', ''),
            'token_type': 'admin',
            'payload': payload
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency to optionally get authenticated user.
    Returns None if no token provided (useful for endpoints accessible both
    authenticated and unauthenticated).

    Args:
        credentials: HTTP Authorization credentials (optional)

    Returns:
        User information dict or None if not authenticated
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token)

        return {
            'user_id': payload.get('sub'),
            'email': payload.get('email'),
            'phone': payload.get('phone'),
            'role': payload.get('role'),
            'store_id': payload.get('store_id'),
            'customer_id': payload.get('customer_id'),
            'token_type': payload.get('type'),
            'payload': payload
        }
    except Exception:
        # Token invalid but optional - return None
        return None
