import redis
import json
import os
import hashlib
from functools import wraps
from typing import Optional, Any, Callable
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

