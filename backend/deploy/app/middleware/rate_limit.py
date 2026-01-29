"""
Rate Limiting Middleware for VyaparAI API
Provides distributed rate limiting using Redis
"""

import time
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import json

# Configure logging
logger = logging.getLogger(__name__)

# Redis connection (will be initialized in main.py)
redis_client: Optional[redis.Redis] = None

# Rate limit configurations
RATE_LIMITS = {
    "customer_phone": {
        "requests_per_minute": 100,
        "window_seconds": 60
    },
    "store_id": {
        "requests_per_minute": 1000,
        "window_seconds": 60
    },
    "ip_address": {
        "requests_per_minute": 200,
        "window_seconds": 60
    },
    # Stricter limits for authentication endpoints
    "auth_otp_send": {
        "requests_per_minute": 5,  # Max 5 OTP requests per minute per phone
        "window_seconds": 60
    },
    "auth_otp_verify": {
        "requests_per_minute": 10,  # Max 10 verify attempts per minute per phone
        "window_seconds": 60
    },
    "auth_login": {
        "requests_per_minute": 10,  # Max 10 login attempts per minute per IP
        "window_seconds": 60
    },
    "auth_register": {
        "requests_per_minute": 5,  # Max 5 registration attempts per minute per IP
        "window_seconds": 60
    },
    "auth_password_reset": {
        "requests_per_minute": 3,  # Max 3 password reset requests per minute
        "window_seconds": 60
    }
}

async def get_redis_client() -> redis.Redis:
    """Get Redis client instance"""
    global redis_client
    if redis_client is None:
        # Fallback to in-memory rate limiting if Redis is not available
        logger.warning("Redis not available, using in-memory rate limiting")
        return None
    return redis_client

async def check_rate_limit(
    key: str,
    limit_type: str,
    request: Request
) -> bool:
    """
    Check rate limit for a given key
    
    Args:
        key: Rate limit key (phone, store_id, or IP)
        limit_type: Type of rate limit (customer_phone, store_id, ip_address)
        request: FastAPI request object
        
    Returns:
        True if within rate limit, False otherwise
    """
    try:
        redis_client = await get_redis_client()
        
        if redis_client is None:
            # In-memory fallback (not distributed)
            return await check_rate_limit_memory(key, limit_type)
        
        # Get rate limit configuration
        config = RATE_LIMITS.get(limit_type, RATE_LIMITS["ip_address"])
        max_requests = config["requests_per_minute"]
        window_seconds = config["window_seconds"]
        
        # Create Redis key
        redis_key = f"rate_limit:{limit_type}:{key}"
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        # Use Redis pipeline for atomic operations
        async with redis_client.pipeline() as pipe:
            # Remove old entries (older than window)
            await pipe.zremrangebyscore(redis_key, 0, window_start)
            
            # Count current requests in window
            await pipe.zcard(redis_key)
            
            # Add current request timestamp
            await pipe.zadd(redis_key, {str(current_time): current_time})
            
            # Set expiry on the key
            await pipe.expire(redis_key, window_seconds)
            
            # Execute pipeline
            results = await pipe.execute()
            
            current_requests = results[1]  # zcard result
        
        # Check if within limit
        if current_requests >= max_requests:
            logger.warning(f"Rate limit exceeded for {limit_type}: {key}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        # Allow request if rate limiting fails
        return True

async def check_rate_limit_memory(
    key: str,
    limit_type: str
) -> bool:
    """
    In-memory rate limiting fallback
    
    Args:
        key: Rate limit key
        limit_type: Type of rate limit
        
    Returns:
        True if within rate limit, False otherwise
    """
    # In-memory storage for fallback
    if not hasattr(check_rate_limit_memory, '_memory_storage'):
        check_rate_limit_memory._memory_storage = {}
    
    config = RATE_LIMITS.get(limit_type, RATE_LIMITS["ip_address"])
    max_requests = config["requests_per_minute"]
    window_seconds = config["window_seconds"]
    
    current_time = time.time()
    window_start = current_time - window_seconds
    
    # Get or create storage for this key
    if key not in check_rate_limit_memory._memory_storage:
        check_rate_limit_memory._memory_storage[key] = []
    
    # Remove old entries
    check_rate_limit_memory._memory_storage[key] = [
        timestamp for timestamp in check_rate_limit_memory._memory_storage[key]
        if timestamp > window_start
    ]
    
    # Check current count
    current_requests = len(check_rate_limit_memory._memory_storage[key])
    
    if current_requests >= max_requests:
        return False
    
    # Add current request
    check_rate_limit_memory._memory_storage[key].append(current_time)
    
    return True

async def rate_limit_dependency(request: Request) -> bool:
    """
    Rate limiting dependency for FastAPI endpoints
    
    Args:
        request: FastAPI request object
        
    Returns:
        True if request is allowed
        
    Raises:
        HTTPException: If rate limit is exceeded
    """
    try:
        # Extract rate limit keys from request
        rate_limit_keys = []
        
        # Check for customer phone in request body
        if request.method == "POST":
            try:
                body = await request.json()
                if isinstance(body, dict):
                    customer_phone = body.get("customer_phone")
                    if customer_phone:
                        rate_limit_keys.append(("customer_phone", customer_phone))
                    
                    store_id = body.get("store_id")
                    if store_id:
                        rate_limit_keys.append(("store_id", store_id))
            except:
                pass  # Ignore JSON parsing errors
        
        # Check for customer phone in query parameters
        customer_phone = request.query_params.get("customer_phone")
        if customer_phone:
            rate_limit_keys.append(("customer_phone", customer_phone))
        
        # Check for store_id in query parameters
        store_id = request.query_params.get("store_id")
        if store_id:
            rate_limit_keys.append(("store_id", store_id))
        
        # Always check IP address
        client_ip = request.client.host
        rate_limit_keys.append(("ip_address", client_ip))
        
        # Check all rate limits
        for limit_type, key in rate_limit_keys:
            if not await check_rate_limit(key, limit_type, request):
                # Calculate retry after time
                config = RATE_LIMITS.get(limit_type, RATE_LIMITS["ip_address"])
                retry_after = config["window_seconds"]
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit_type": limit_type,
                        "key": key,
                        "retry_after": retry_after
                    },
                    headers={"Retry-After": str(retry_after)}
                )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        # Allow request if rate limiting fails
        return True

async def initialize_redis(redis_url: str = "redis://localhost:6379"):
    """
    Initialize Redis connection for rate limiting
    
    Args:
        redis_url: Redis connection URL
    """
    global redis_client
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        # Test connection
        await redis_client.ping()
        logger.info("Redis connected successfully for rate limiting")
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}")
        redis_client = None

async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")

# Authentication paths that need stricter rate limiting
AUTH_PATHS = {
    "/api/v1/auth/send-otp": "auth_otp_send",
    "/api/v1/auth/verify-otp": "auth_otp_verify",
    "/api/v1/auth/login": "auth_login",
    "/api/v1/customer/auth/send-otp": "auth_otp_send",
    "/api/v1/customer/auth/verify-otp": "auth_otp_verify",
    "/api/v1/customer/auth/login": "auth_login",
    "/api/v1/customer/auth/register": "auth_register",
    "/api/v1/admin/auth/login": "auth_login",
    "/api/v1/auth/send-email-passcode": "auth_otp_send",
    "/api/v1/auth/verify-email-passcode": "auth_otp_verify",
}


# Rate limit middleware for automatic application
async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware for automatic rate limiting

    Args:
        request: FastAPI request object
        call_next: Next middleware/endpoint

    Returns:
        Response from next middleware/endpoint
    """
    # Skip rate limiting for health checks and docs
    if request.url.path in ["/health", "/health/detailed", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)

    try:
        # Check if this is an authentication endpoint requiring stricter limits
        path = request.url.path
        if path in AUTH_PATHS:
            limit_type = AUTH_PATHS[path]

            # Get the key based on limit type
            key = None
            if limit_type in ["auth_otp_send", "auth_otp_verify"]:
                # Try to get phone/email from request body
                try:
                    body_bytes = await request.body()
                    body = json.loads(body_bytes.decode())
                    key = body.get("phone") or body.get("email")

                    # Reset body stream for endpoint to read
                    async def receive():
                        return {"type": "http.request", "body": body_bytes}
                    request._receive = receive
                except:
                    pass

            # Fallback to IP address
            if not key:
                key = request.client.host if request.client else "unknown"

            # Check stricter auth rate limit
            if not await check_rate_limit(key, limit_type, request):
                config = RATE_LIMITS.get(limit_type, RATE_LIMITS["ip_address"])
                retry_after = config["window_seconds"]

                logger.warning(f"Auth rate limit exceeded for {path}: {key[-4:].rjust(len(key), '*') if key and len(key) > 4 else '****'}")

                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Please try again in {retry_after} seconds.",
                        "retry_after": retry_after
                    },
                    headers={"Retry-After": str(retry_after)}
                )

        # Apply general rate limiting
        await rate_limit_dependency(request)
        return await call_next(request)

    except HTTPException as e:
        if e.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": e.headers.get("Retry-After", 60)
                },
                headers={"Retry-After": e.headers.get("Retry-After", "60")}
            )
        raise

# Utility functions for manual rate limit checking
async def get_rate_limit_status(key: str, limit_type: str) -> Dict[str, Any]:
    """
    Get current rate limit status for a key
    
    Args:
        key: Rate limit key
        limit_type: Type of rate limit
        
    Returns:
        Dictionary with rate limit status
    """
    try:
        redis_client = await get_redis_client()
        
        if redis_client is None:
            return {"error": "Redis not available"}
        
        config = RATE_LIMITS.get(limit_type, RATE_LIMITS["ip_address"])
        max_requests = config["requests_per_minute"]
        window_seconds = config["window_seconds"]
        
        redis_key = f"rate_limit:{limit_type}:{key}"
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        # Get current requests in window
        current_requests = await redis_client.zcount(redis_key, window_start, current_time)
        
        return {
            "key": key,
            "limit_type": limit_type,
            "current_requests": current_requests,
            "max_requests": max_requests,
            "window_seconds": window_seconds,
            "remaining_requests": max(0, max_requests - current_requests),
            "reset_time": current_time + window_seconds
        }
        
    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}")
        return {"error": str(e)}

async def reset_rate_limit(key: str, limit_type: str) -> bool:
    """
    Reset rate limit for a key (admin function)

    Args:
        key: Rate limit key
        limit_type: Type of rate limit

    Returns:
        True if reset successful
    """
    try:
        redis_client = await get_redis_client()

        if redis_client is None:
            return False

        redis_key = f"rate_limit:{limit_type}:{key}"
        await redis_client.delete(redis_key)

        logger.info(f"Rate limit reset for {limit_type}: {key}")
        return True

    except Exception as e:
        logger.error(f"Error resetting rate limit: {e}")
        return False


# =============================================================================
# Authentication-specific Rate Limiting
# =============================================================================

async def check_auth_rate_limit(
    key: str,
    limit_type: str,
    request: Request
) -> None:
    """
    Check authentication-specific rate limit.
    Raises HTTPException if rate limit exceeded.

    Args:
        key: Rate limit key (phone, email, or IP)
        limit_type: Type of auth rate limit
        request: FastAPI request object

    Raises:
        HTTPException: If rate limit is exceeded
    """
    if not await check_rate_limit(key, limit_type, request):
        config = RATE_LIMITS.get(limit_type, RATE_LIMITS["ip_address"])
        retry_after = config["window_seconds"]

        logger.warning(f"Auth rate limit exceeded: {limit_type} for key: {key[-4:].rjust(len(key), '*') if len(key) > 4 else '****'}")

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Too many requests",
                "message": f"Rate limit exceeded. Please try again in {retry_after} seconds.",
                "retry_after": retry_after
            },
            headers={"Retry-After": str(retry_after)}
        )


def create_auth_rate_limit_dependency(limit_type: str, key_param: str = "ip"):
    """
    Factory function to create authentication rate limit dependencies.

    Args:
        limit_type: Type of rate limit (e.g., 'auth_otp_send', 'auth_login')
        key_param: What to use as rate limit key ('ip', 'phone', 'email')

    Returns:
        FastAPI dependency function

    Usage:
        @router.post("/send-otp")
        async def send_otp(
            request: SendOTPRequest,
            _: None = Depends(create_auth_rate_limit_dependency("auth_otp_send", "phone"))
        ):
            ...
    """
    async def rate_limit_check(request: Request):
        # Get the key based on key_param
        key = None

        if key_param == "ip":
            key = request.client.host if request.client else "unknown"
        elif key_param in ["phone", "email"]:
            # Try to get from request body
            try:
                body = await request.json()
                # Reset the body stream for subsequent reads
                async def receive():
                    return {"type": "http.request", "body": json.dumps(body).encode()}
                request._receive = receive

                if isinstance(body, dict):
                    key = body.get(key_param)
            except:
                pass

            # Fallback to IP if no phone/email found
            if not key:
                key = request.client.host if request.client else "unknown"

        if key:
            await check_auth_rate_limit(key, limit_type, request)

    return rate_limit_check


# Pre-built dependencies for common auth operations
async def rate_limit_otp_send(request: Request):
    """Rate limit for OTP send endpoints"""
    # Get phone from request body
    key = None
    try:
        body = await request.json()
        # Store body for reuse
        request.state.body = body
        if isinstance(body, dict):
            key = body.get("phone")
    except:
        pass

    if not key:
        key = request.client.host if request.client else "unknown"

    await check_auth_rate_limit(key, "auth_otp_send", request)


async def rate_limit_otp_verify(request: Request):
    """Rate limit for OTP verify endpoints"""
    key = None
    try:
        # Try to get stored body first
        body = getattr(request.state, 'body', None)
        if body is None:
            body = await request.json()
            request.state.body = body
        if isinstance(body, dict):
            key = body.get("phone")
    except:
        pass

    if not key:
        key = request.client.host if request.client else "unknown"

    await check_auth_rate_limit(key, "auth_otp_verify", request)


async def rate_limit_login(request: Request):
    """Rate limit for login endpoints"""
    key = request.client.host if request.client else "unknown"
    await check_auth_rate_limit(key, "auth_login", request)


async def rate_limit_register(request: Request):
    """Rate limit for registration endpoints"""
    key = request.client.host if request.client else "unknown"
    await check_auth_rate_limit(key, "auth_register", request)
