import redis
import json
import os
import hashlib
import threading
from functools import wraps
from typing import Optional, Any, Callable
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Redis connection
try:
    redis_client = redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    # Test connection
    redis_client.ping()
    REDIS_AVAILABLE = True
    logger.info("Redis connection established")
except Exception as e:
    logger.warning(f"Redis not available: {e}")
    REDIS_AVAILABLE = False
    redis_client = None

def cache_key_wrapper(*args, **kwargs) -> str:
    """Generate cache key from function arguments"""
    # Create a string representation of arguments
    key_parts = []
    
    # Add args
    for arg in args:
        if isinstance(arg, (dict, list)):
            key_parts.append(json.dumps(arg, sort_keys=True))
        else:
            key_parts.append(str(arg))
    
    # Add kwargs
    for key, value in sorted(kwargs.items()):
        if isinstance(value, (dict, list)):
            key_parts.append(f"{key}:{json.dumps(value, sort_keys=True)}")
        else:
            key_parts.append(f"{key}:{value}")
    
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()

def cache_result(expiry: int = 300, key_prefix: str = ""):
    """
    Decorator to cache function results in Redis
    
    Args:
        expiry: Cache expiry time in seconds (default: 5 minutes)
        key_prefix: Prefix for cache key (default: empty)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not REDIS_AVAILABLE:
                # If Redis is not available, just execute the function
                return await func(*args, **kwargs)
            
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{cache_key_wrapper(*args, **kwargs)}"
            
            # Try to get from cache
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            try:
                redis_client.setex(
                    cache_key,
                    expiry,
                    json.dumps(result, default=str)
                )
                logger.debug(f"Cached result for key: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache write error: {e}")
            
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache keys matching pattern
    
    Args:
        pattern: Redis pattern to match keys (e.g., "orders:*", "analytics:*")
    
    Returns:
        Number of keys deleted
    """
    if not REDIS_AVAILABLE:
        return 0
    
    try:
        deleted_count = 0
        for key in redis_client.scan_iter(match=pattern):
            redis_client.delete(key)
            deleted_count += 1
        logger.info(f"Invalidated {deleted_count} cache keys matching pattern: {pattern}")
        return deleted_count
    except Exception as e:
        logger.error(f"Cache invalidation error: {e}")
        return 0

def clear_all_cache() -> int:
    """
    Clear all cache keys
    
    Returns:
        Number of keys deleted
    """
    if not REDIS_AVAILABLE:
        return 0
    
    try:
        deleted_count = 0
        for key in redis_client.scan_iter():
            redis_client.delete(key)
            deleted_count += 1
        logger.info(f"Cleared all cache: {deleted_count} keys deleted")
        return deleted_count
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return 0

def get_cache_stats() -> dict:
    """
    Get cache statistics
    
    Returns:
        Dictionary with cache statistics
    """
    if not REDIS_AVAILABLE:
        return {"status": "unavailable"}
    
    try:
        info = redis_client.info()
        return {
            "status": "available",
            "used_memory": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses")
        }
    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        return {"status": "error", "error": str(e)}

# Cache key patterns for easy invalidation
CACHE_PATTERNS = {
    "orders": "orders:*",
    "analytics": "analytics:*",
    "customers": "customers:*",
    "inventory": "inventory:*",
    "products": "inventory:products:*",
    "categories": "inventory:categories:*"
}

def invalidate_orders_cache():
    """Invalidate all order-related cache"""
    return invalidate_cache(CACHE_PATTERNS["orders"])

def invalidate_analytics_cache():
    """Invalidate all analytics-related cache"""
    return invalidate_cache(CACHE_PATTERNS["analytics"])

def invalidate_customers_cache():
    """Invalidate all customer-related cache"""
    return invalidate_cache(CACHE_PATTERNS["customers"])

def invalidate_inventory_cache():
    """Invalidate all inventory-related cache"""
    return invalidate_cache(CACHE_PATTERNS["inventory"])

def invalidate_products_cache():
    """Invalidate all product-related cache"""
    return invalidate_cache(CACHE_PATTERNS["products"])

def invalidate_categories_cache():
    """Invalidate all category-related cache"""
    return invalidate_cache(CACHE_PATTERNS["categories"])


# =============================================================================
# OTP Storage Functions
# =============================================================================
# These functions provide secure OTP storage with automatic expiration.
# Uses Redis when available, falls back to in-memory storage for development.
#
# SECURITY NOTE: In-memory storage is NOT suitable for production with multiple
# workers. Always use Redis in production for proper distributed locking.

# In-memory fallback storage for OTPs (used when Redis is unavailable)
_otp_memory_storage: dict = {}
# Thread lock for safe concurrent access to in-memory storage
_otp_memory_lock = threading.Lock()

OTP_KEY_PREFIX = "otp:"
OTP_DEFAULT_EXPIRY = 300  # 5 minutes in seconds
OTP_MAX_ATTEMPTS = 5  # Maximum verification attempts before lockout


def store_otp_redis(phone: str, otp_data: dict, expiry_seconds: int = OTP_DEFAULT_EXPIRY) -> bool:
    """
    Store OTP data in Redis with automatic expiration.

    Args:
        phone: Phone number (used as key)
        otp_data: Dictionary with OTP and metadata (otp, created_at, attempts, etc.)
        expiry_seconds: Time until OTP expires (default: 5 minutes)

    Returns:
        True if stored successfully, False otherwise
    """
    key = f"{OTP_KEY_PREFIX}{phone}"

    if REDIS_AVAILABLE and redis_client:
        try:
            # Store as JSON with TTL
            redis_client.setex(
                key,
                expiry_seconds,
                json.dumps(otp_data, default=str)
            )
            logger.debug(f"OTP stored in Redis for: {phone[-4:].rjust(len(phone), '*')}")
            return True
        except Exception as e:
            logger.warning(f"Redis OTP store failed, using memory fallback: {e}")

    # Fallback to in-memory storage with thread-safe access
    with _otp_memory_lock:
        otp_data['_memory_expires_at'] = (datetime.utcnow() + timedelta(seconds=expiry_seconds)).isoformat()
        _otp_memory_storage[phone] = otp_data
        logger.debug(f"OTP stored in memory for: {phone[-4:].rjust(len(phone), '*')}")
    return True


def get_otp_redis(phone: str) -> Optional[dict]:
    """
    Retrieve OTP data from Redis or memory fallback.

    Args:
        phone: Phone number to look up

    Returns:
        OTP data dictionary or None if not found/expired
    """
    key = f"{OTP_KEY_PREFIX}{phone}"

    if REDIS_AVAILABLE and redis_client:
        try:
            data = redis_client.get(key)
            if data:
                logger.debug(f"OTP retrieved from Redis for: {phone[-4:].rjust(len(phone), '*')}")
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"Redis OTP get failed, checking memory fallback: {e}")

    # Fallback to in-memory storage with thread-safe access
    with _otp_memory_lock:
        if phone in _otp_memory_storage:
            otp_data = _otp_memory_storage[phone].copy()  # Return a copy to prevent external modification
            # Check if memory entry has expired
            expires_at = otp_data.get('_memory_expires_at')
            if expires_at:
                if datetime.utcnow() > datetime.fromisoformat(expires_at):
                    del _otp_memory_storage[phone]
                    logger.debug(f"OTP expired in memory for: {phone[-4:].rjust(len(phone), '*')}")
                    return None
            logger.debug(f"OTP retrieved from memory for: {phone[-4:].rjust(len(phone), '*')}")
            return otp_data

    return None


def update_otp_redis(phone: str, otp_data: dict) -> bool:
    """
    Update OTP data while preserving TTL.

    Args:
        phone: Phone number
        otp_data: Updated OTP data dictionary

    Returns:
        True if updated successfully, False otherwise
    """
    key = f"{OTP_KEY_PREFIX}{phone}"

    if REDIS_AVAILABLE and redis_client:
        try:
            # Get remaining TTL
            ttl = redis_client.ttl(key)
            if ttl > 0:
                redis_client.setex(
                    key,
                    ttl,
                    json.dumps(otp_data, default=str)
                )
                logger.debug(f"OTP updated in Redis for: {phone[-4:].rjust(len(phone), '*')}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis OTP update failed, updating memory fallback: {e}")

    # Fallback to in-memory storage with thread-safe access
    with _otp_memory_lock:
        if phone in _otp_memory_storage:
            # Preserve the memory expiry timestamp
            expires_at = _otp_memory_storage[phone].get('_memory_expires_at')
            otp_data['_memory_expires_at'] = expires_at
            _otp_memory_storage[phone] = otp_data
            logger.debug(f"OTP updated in memory for: {phone[-4:].rjust(len(phone), '*')}")
            return True

    return False


def delete_otp_redis(phone: str) -> bool:
    """
    Delete OTP data (after successful verification or too many attempts).

    Args:
        phone: Phone number

    Returns:
        True if deleted, False if not found
    """
    key = f"{OTP_KEY_PREFIX}{phone}"
    deleted = False

    if REDIS_AVAILABLE and redis_client:
        try:
            result = redis_client.delete(key)
            deleted = result > 0
            if deleted:
                logger.debug(f"OTP deleted from Redis for: {phone[-4:].rjust(len(phone), '*')}")
        except Exception as e:
            logger.warning(f"Redis OTP delete failed: {e}")

    # Also clean up memory fallback with thread-safe access
    with _otp_memory_lock:
        if phone in _otp_memory_storage:
            del _otp_memory_storage[phone]
            deleted = True
            logger.debug(f"OTP deleted from memory for: {phone[-4:].rjust(len(phone), '*')}")

    return deleted


def increment_otp_attempts(phone: str) -> tuple[int, bool]:
    """
    Atomically increment OTP verification attempts.

    This is the critical function for preventing race conditions during
    concurrent verification attempts. Returns the new attempt count and
    whether max attempts have been exceeded.

    Args:
        phone: Phone number

    Returns:
        Tuple of (new_attempts_count, exceeded_max_attempts)
        Returns (-1, True) if OTP not found
    """
    key = f"{OTP_KEY_PREFIX}{phone}"

    if REDIS_AVAILABLE and redis_client:
        try:
            # Use Redis WATCH/MULTI/EXEC for atomic increment
            pipe = redis_client.pipeline(True)  # True for transactional pipeline
            while True:
                try:
                    pipe.watch(key)
                    data = pipe.get(key)
                    if not data:
                        pipe.unwatch()
                        return (-1, True)

                    otp_data = json.loads(data)
                    otp_data['attempts'] = otp_data.get('attempts', 0) + 1
                    new_attempts = otp_data['attempts']
                    exceeded = new_attempts >= OTP_MAX_ATTEMPTS

                    # Get remaining TTL
                    ttl = pipe.ttl(key)

                    pipe.multi()
                    if exceeded:
                        # Delete on max attempts
                        pipe.delete(key)
                    else:
                        pipe.setex(key, max(ttl, 1), json.dumps(otp_data, default=str))
                    pipe.execute()

                    logger.debug(f"OTP attempts incremented to {new_attempts} for: {phone[-4:].rjust(len(phone), '*')}")
                    return (new_attempts, exceeded)
                except redis.WatchError:
                    # Another client modified the key, retry
                    continue
        except Exception as e:
            logger.warning(f"Redis atomic increment failed, using memory fallback: {e}")

    # Fallback to in-memory storage with thread-safe access
    with _otp_memory_lock:
        if phone not in _otp_memory_storage:
            return (-1, True)

        otp_data = _otp_memory_storage[phone]

        # Check expiration
        expires_at = otp_data.get('_memory_expires_at')
        if expires_at and datetime.utcnow() > datetime.fromisoformat(expires_at):
            del _otp_memory_storage[phone]
            return (-1, True)

        # Atomic increment within lock
        otp_data['attempts'] = otp_data.get('attempts', 0) + 1
        new_attempts = otp_data['attempts']
        exceeded = new_attempts >= OTP_MAX_ATTEMPTS

        if exceeded:
            del _otp_memory_storage[phone]
            logger.debug(f"OTP deleted after max attempts for: {phone[-4:].rjust(len(phone), '*')}")

        logger.debug(f"OTP attempts incremented to {new_attempts} for: {phone[-4:].rjust(len(phone), '*')}")
        return (new_attempts, exceeded)


def get_otp_storage_status() -> dict:
    """
    Get OTP storage status for monitoring.

    Returns:
        Dictionary with storage backend and stats
    """
    with _otp_memory_lock:
        memory_count = len(_otp_memory_storage)

    status = {
        "backend": "redis" if REDIS_AVAILABLE else "memory",
        "memory_entries": memory_count,
        "thread_safe": True,
        "max_attempts": OTP_MAX_ATTEMPTS
    }

    if REDIS_AVAILABLE and redis_client:
        try:
            # Count OTP keys in Redis
            otp_keys = list(redis_client.scan_iter(match=f"{OTP_KEY_PREFIX}*"))
            status["redis_otp_count"] = len(otp_keys)
        except Exception as e:
            status["redis_error"] = str(e)

    return status

