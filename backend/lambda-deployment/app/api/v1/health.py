from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import asyncio
from datetime import datetime
import os
import psutil
import platform

from app.database.session import get_db
from app.core.config import settings

router = APIRouter()

@router.get("/health")
async def detailed_health_check(db: Session = Depends(get_db)):
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
    
    # Database connectivity check (PostgreSQL)
    try:
        db.execute("SELECT 1").fetchone()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "PostgreSQL connection successful",
            "type": "postgresql"
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
            "type": "postgresql",
            "error": str(e)
        }
        overall_healthy = False
    
    # DynamoDB check
    try:
        import boto3
        dynamodb = boto3.client('dynamodb', region_name='ap-south-1')
        dynamodb.describe_table(TableName='vyaparai-orders-prod')
        health_status["checks"]["dynamodb"] = {
            "status": "healthy",
            "message": "DynamoDB connection successful",
            "table": "vyaparai-orders-prod"
        }
    except Exception as e:
        health_status["checks"]["dynamodb"] = {
            "status": "unhealthy",
            "message": f"DynamoDB connection failed: {str(e)}",
            "table": "vyaparai-orders-prod",
            "error": str(e)
        }
        # Don't mark overall as unhealthy for DynamoDB issues (optional service)
    
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
    
    # Redis check (if configured)
    try:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            health_status["checks"]["redis"] = {
                "status": "healthy",
                "message": "Redis connection successful",
                "configured": True
            }
        else:
            health_status["checks"]["redis"] = {
                "status": "warning",
                "message": "Redis not configured",
                "configured": False
            }
    except Exception as e:
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}",
            "error": str(e)
        }
        # Don't mark overall as unhealthy for Redis issues (optional service)
    
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
