import time
import logging
from functools import wraps
from typing import Callable, Any
import json

logger = logging.getLogger(__name__)

def monitor_performance(func: Callable) -> Callable:
    """Decorator to monitor API endpoint performance"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Log performance metrics
            PerformanceMonitor.log_metric(
                f"{func.__module__}.{func.__name__}",
                duration,
                "ms"
            )
            
            # Log slow queries
            if duration > 1000:  # More than 1 second
                logger.warning(f"Slow API call: {func.__name__} took {duration:.2f}ms")
            
            return result
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"Error in {func.__name__} after {duration:.2f}ms: {str(e)}")
            raise
    return wrapper

class PerformanceMonitor:
    @staticmethod
    def log_metric(metric_name: str, value: float, unit: str = "ms"):
        """Log performance metrics"""
        logger.info(f"METRIC: {metric_name}={value:.2f}{unit}")
    
    @staticmethod
    def log_api_call(endpoint: str, method: str, duration: float, status_code: int = 200):
        """Log API call details"""
        logger.info(f"API: {method} {endpoint} - {duration:.2f}ms - {status_code}")
    
    @staticmethod
    def log_database_query(query: str, duration: float, rows_affected: int = 0):
        """Log database query performance"""
        logger.info(f"DB: {query[:50]}... - {duration:.2f}ms - {rows_affected} rows")
    
    @staticmethod
    def log_cache_hit(key: str, duration: float):
        """Log cache hit performance"""
        logger.info(f"CACHE_HIT: {key} - {duration:.2f}ms")
    
    @staticmethod
    def log_cache_miss(key: str, duration: float):
        """Log cache miss performance"""
        logger.info(f"CACHE_MISS: {key} - {duration:.2f}ms")

class ErrorLogger:
    @staticmethod
    def log_error(error_type: str, message: str, context: dict = None):
        """Log application errors with context"""
        error_data = {
            "type": error_type,
            "message": message,
            "timestamp": time.time(),
            "context": context or {}
        }
        logger.error(f"ERROR: {json.dumps(error_data)}")
    
    @staticmethod
    def log_api_error(endpoint: str, method: str, error: Exception, user_id: str = None):
        """Log API errors with context"""
        ErrorLogger.log_error(
            "api_error",
            str(error),
            {
                "endpoint": endpoint,
                "method": method,
                "user_id": user_id,
                "error_type": type(error).__name__
            }
        )

class HealthMonitor:
    @staticmethod
    def check_system_health() -> dict:
        """Check system health metrics"""
        import psutil
        
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "timestamp": time.time()
        }
    
    @staticmethod
    def log_health_metrics():
        """Log system health metrics"""
        health = HealthMonitor.check_system_health()
        logger.info(f"HEALTH: CPU={health['cpu_percent']}% MEM={health['memory_percent']}% DISK={health['disk_percent']}%")

