from fastapi import APIRouter, HTTPException
import asyncio
from datetime import datetime
import os
import psutil
import platform
import time
from typing import Dict, Any, Optional

from app.core.config import settings
from app.core.database import db_manager, ORDERS_TABLE, STORES_TABLE

router = APIRouter()

# Health check timeout (seconds)
HEALTH_CHECK_TIMEOUT = 5


async def run_with_timeout(coro, timeout: float, default: Dict[str, Any]) -> Dict[str, Any]:
    """Run a coroutine with timeout, return default on failure"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return {**default, "status": "timeout", "message": f"Check timed out after {timeout}s"}
    except Exception as e:
        return {**default, "status": "error", "message": str(e)}

@router.get("/health")
async def detailed_health_check():
    """
    Comprehensive health check endpoint
    Returns detailed system health information
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "service": "VyaparAI API",
        "checks": {}
    }
    
    overall_healthy = True

    # Database connection health check using centralized manager
    async def check_dynamodb() -> Dict[str, Any]:
        """Check DynamoDB connectivity with timeout"""
        start = time.time()
        try:
            dynamodb_client = db_manager.get_dynamodb_client()
            if not dynamodb_client:
                return {
                    "status": "not_configured",
                    "message": "DynamoDB client not initialized"
                }

            # Use describe_table which is fast and confirms connectivity
            response = dynamodb_client.describe_table(TableName=ORDERS_TABLE)
            latency_ms = (time.time() - start) * 1000

            return {
                "status": "healthy",
                "message": "DynamoDB connection successful",
                "table": ORDERS_TABLE,
                "table_status": response.get('Table', {}).get('TableStatus', 'unknown'),
                "latency_ms": round(latency_ms, 2)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"DynamoDB connection failed: {str(e)}",
                "table": ORDERS_TABLE
            }

    # Run DynamoDB check with timeout
    health_status["checks"]["dynamodb"] = await run_with_timeout(
        check_dynamodb(),
        timeout=HEALTH_CHECK_TIMEOUT,
        default={"table": ORDERS_TABLE}
    )

    # Mark overall as unhealthy if DynamoDB is critical
    if health_status["checks"]["dynamodb"].get("status") == "unhealthy":
        overall_healthy = False
    
    # Gemini API check
    try:
        # Check if Gemini API key is configured
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            health_status["checks"]["gemini_api"] = {
                "status": "healthy",
                "message": "Gemini API key configured",
                "configured": True
            }
        else:
            health_status["checks"]["gemini_api"] = {
                "status": "warning",
                "message": "Gemini API key not configured",
                "configured": False
            }
    except Exception as e:
        health_status["checks"]["gemini_api"] = {
            "status": "unhealthy",
            "message": f"Gemini API check failed: {str(e)}",
            "error": str(e)
        }
        # Don't mark overall as unhealthy for external API issues
    
    # Redis check with async and timeout
    async def check_redis() -> Dict[str, Any]:
        """Check Redis connectivity with timeout"""
        start = time.time()
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return {
                "status": "not_configured",
                "message": "Redis URL not configured",
                "configured": False
            }

        try:
            redis_client = await db_manager.get_redis()
            if redis_client:
                await redis_client.ping()
                latency_ms = (time.time() - start) * 1000
                return {
                    "status": "healthy",
                    "message": "Redis connection successful",
                    "configured": True,
                    "latency_ms": round(latency_ms, 2)
                }
            else:
                return {
                    "status": "warning",
                    "message": "Redis client not available",
                    "configured": True
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Redis connection failed: {str(e)}",
                "configured": True
            }

    health_status["checks"]["redis"] = await run_with_timeout(
        check_redis(),
        timeout=HEALTH_CHECK_TIMEOUT,
        default={"configured": False}
    )
    # Redis is optional, don't mark overall as unhealthy
    
    # System resources check
    try:
        # Memory usage
        memory = psutil.virtual_memory()
        health_status["checks"]["system_resources"] = {
            "status": "healthy",
            "message": "System resources normal",
            "memory": {
                "total": f"{memory.total / (1024**3):.2f} GB",
                "available": f"{memory.available / (1024**3):.2f} GB",
                "percent_used": f"{memory.percent:.1f}%"
            },
            "cpu_count": psutil.cpu_count(),
            "platform": platform.system()
        }
        
        # Check if memory usage is high
        if memory.percent > 90:
            health_status["checks"]["system_resources"]["status"] = "warning"
            health_status["checks"]["system_resources"]["message"] = "High memory usage detected"
            
    except Exception as e:
        health_status["checks"]["system_resources"] = {
            "status": "warning",
            "message": f"Unable to check system resources: {str(e)}",
            "error": str(e)
        }
    
    # Environment variables check
    try:
        required_env_vars = [
            "DATABASE_URL",
            "SECRET_KEY",
            "AWS_REGION"
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            health_status["checks"]["environment"] = {
                "status": "warning",
                "message": f"Missing environment variables: {', '.join(missing_vars)}",
                "missing_vars": missing_vars
            }
        else:
            health_status["checks"]["environment"] = {
                "status": "healthy",
                "message": "All required environment variables configured"
            }
    except Exception as e:
        health_status["checks"]["environment"] = {
            "status": "warning",
            "message": f"Environment check failed: {str(e)}",
            "error": str(e)
        }
    
    # Set overall status
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    # Add summary
    healthy_checks = sum(1 for check in health_status["checks"].values() if check.get("status") == "healthy")
    total_checks = len(health_status["checks"])
    health_status["summary"] = {
        "total_checks": total_checks,
        "healthy_checks": healthy_checks,
        "unhealthy_checks": sum(1 for check in health_status["checks"].values() if check.get("status") == "unhealthy"),
        "warning_checks": sum(1 for check in health_status["checks"].values() if check.get("status") == "warning")
    }
    
    # Return appropriate HTTP status
    if not overall_healthy:
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

@router.get("/health/simple")
async def simple_health_check():
    """
    Simple health check endpoint for load balancers
    Returns basic status without detailed checks
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "VyaparAI API"
    }
