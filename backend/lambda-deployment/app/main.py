"""
VyaparAI FastAPI Application
Main application entry point with comprehensive API structure
"""

import os
import time
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
import uvicorn

# Local imports
from app.api.v1 import api_v1_router
from app.api.v1 import health
from app.middleware.rate_limit import initialize_redis, close_redis, rate_limit_middleware
from app.services.unified_order_service import unified_order_service
from app.core.exceptions import vyaparai_exception_handler, VyaparAIException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Environment variables
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT == "development"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")

# Application metadata
APP_TITLE = "VyaparAI Order Processing API"
APP_DESCRIPTION = """
VyaparAI is an intelligent order processing system for Indian grocery stores.

## Features

* **Multi-language Support**: Process orders in 18+ Indian languages
* **Multi-channel Support**: WhatsApp, RCS, SMS, and Web interfaces
* **AI-Powered Responses**: Gemini integration for natural conversations
* **Real-time Processing**: Sub-millisecond order processing
* **Comprehensive Analytics**: Detailed metrics and monitoring

## Quick Start

1. **Process an Order**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/orders/process" \\
        -H "Content-Type: application/json" \\
        -d '{
          "message": "I want to order 2 kg rice and 1 packet salt",
          "channel": "whatsapp",
          "customer_phone": "+919876543210"
        }'
   ```

2. **Check Order Status**:
   ```bash
   curl "http://localhost:8000/api/v1/orders/{order_id}"
   ```

3. **View Metrics**:
   ```bash
   curl "http://localhost:8000/api/v1/orders/metrics"
   ```

## API Documentation

* **Swagger UI**: `/docs`
* **ReDoc**: `/redoc`
* **OpenAPI Schema**: `/openapi.json`

## Health Checks

* **Basic Health**: `/health`
* **Detailed Health**: `/health/detailed`
"""
APP_VERSION = "1.0.0"

# Global state for application lifecycle
app_state: Dict[str, Any] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("Starting VyaparAI application...")
    
    try:
        # Initialize Redis for rate limiting
        await initialize_redis(REDIS_URL)
        logger.info("Redis initialized for rate limiting")
        
        # Warm up NLP models
        logger.info("Warming up NLP models...")
        await asyncio.sleep(1)  # Simulate model loading
        logger.info("NLP models ready")
        
        # Initialize services
        app_state["startup_time"] = time.time()
        app_state["services_ready"] = True
        
        logger.info("VyaparAI application started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        app_state["services_ready"] = False
    
    yield
    
    # Shutdown
    logger.info("Shutting down VyaparAI application...")
    
    try:
        # Close Redis connection
        await close_redis()
        logger.info("Redis connection closed")
        
        # Cleanup other resources
        logger.info("Cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Create FastAPI application
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    debug=DEBUG,
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
)

# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

# Compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if DEBUG else [
        "https://vyaparai.com",
        "https://app.vyaparai.com",
        "https://admin.vyaparai.com",
        "http://localhost:3000",  # Frontend development
        "https://localhost:3000",  # Frontend development with HTTPS
        "http://localhost:5173",   # Vite dev server
        "https://localhost:5173"   # Vite dev server with HTTPS
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Trusted host middleware (for production)
if not DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "vyaparai.com",
            "app.vyaparai.com",
            "admin.vyaparai.com",
            "api.vyaparai.com"
        ]
    )

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests"""
    request_id = f"req_{int(time.time() * 1000)}_{id(request)}"
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Response time middleware
@app.middleware("http")
async def add_response_time(request: Request, call_next):
    """Add response time header"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware_wrapper(request: Request, call_next):
    """Rate limiting middleware wrapper"""
    return await rate_limit_middleware(request, call_next)

# =============================================================================
# CUSTOM DOCUMENTATION
# =============================================================================

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with VyaparAI branding"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "docExpansion": "list",
            "filter": True,
            "showExtensions": True,
            "showCommonExtensions": True,
        }
    )

@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    """Custom ReDoc with VyaparAI branding"""
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Documentation",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
        redoc_favicon_url="https://vyaparai.com/favicon.ico",
    )

def custom_openapi():
    """Custom OpenAPI schema with VyaparAI branding"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add custom info
    openapi_schema["info"]["x-logo"] = {
        "url": "https://vyaparai.com/logo.png"
    }
    
    # Add server information
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.vyaparai.com",
            "description": "Production server"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@app.get("/health", tags=["health"])
async def health_check():
    """
    Basic health check endpoint
    
    Returns:
        Basic health status
    """
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": APP_VERSION,
        "environment": ENVIRONMENT
    }

@app.get("/health/detailed", tags=["health"])
async def detailed_health_check():
    """
    Detailed health check endpoint
    
    Checks all service components and returns detailed status.
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "uptime": time.time() - app_state.get("startup_time", time.time()),
        "services": {}
    }
    
    # Check services
    try:
        # Check unified order service
        metrics = unified_order_service.get_metrics()
        health_status["services"]["unified_order_service"] = {
            "status": "healthy",
            "total_requests": metrics["total_requests"],
            "avg_processing_time_ms": metrics["avg_processing_time"],
            "error_rate": (metrics["error_count"] / max(metrics["total_requests"], 1)) * 100
        }
    except Exception as e:
        health_status["services"]["unified_order_service"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        from middleware.rate_limit import redis_client
        if redis_client:
            await redis_client.ping()
            health_status["services"]["redis"] = {"status": "healthy"}
        else:
            health_status["services"]["redis"] = {"status": "not_configured"}
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check Gemini
    try:
        if hasattr(unified_order_service, 'gemini_model') and unified_order_service.gemini_model:
            health_status["services"]["gemini"] = {"status": "healthy"}
        else:
            health_status["services"]["gemini"] = {"status": "not_configured"}
    except Exception as e:
        health_status["services"]["gemini"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check Google Translate
    try:
        from services.indian_multilingual_service import indian_multilingual_service
        if hasattr(indian_multilingual_service, 'translate_client') and indian_multilingual_service.translate_client:
            health_status["services"]["google_translate"] = {"status": "healthy"}
        else:
            health_status["services"]["google_translate"] = {"status": "not_configured"}
    except Exception as e:
        health_status["services"]["google_translate"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    return health_status

# =============================================================================
# ROOT ENDPOINTS
# =============================================================================

@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint with API information
    
    Returns:
        API information and quick links
    """
    return {
        "message": "Welcome to VyaparAI Order Processing API",
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_schema": "/openapi.json"
        },
        "health_checks": {
            "basic": "/health",
            "detailed": "/health/detailed"
        },
        "quick_start": {
            "process_order": "POST /api/v1/orders/process",
            "check_status": "GET /api/v1/orders/{order_id}",
            "view_metrics": "GET /api/v1/orders/metrics"
        },
        "features": [
            "Multi-language order processing",
            "WhatsApp/RCS/SMS support",
            "AI-powered responses",
            "Real-time analytics",
            "Rate limiting",
            "Comprehensive monitoring"
        ]
    }

@app.get("/api", tags=["root"])
async def api_info():
    """
    API information endpoint
    
    Returns:
        Detailed API information
    """
    return {
        "api_name": "VyaparAI Order Processing API",
        "version": APP_VERSION,
        "description": "Intelligent order processing for Indian grocery stores",
        "endpoints": {
            "orders": {
                "base_path": "/api/v1/orders",
                "endpoints": [
                    "POST /process - Process order message",
                    "POST /confirm/{order_id} - Confirm order",
                    "GET /{order_id} - Get order status",
                    "POST /{order_id}/cancel - Cancel order",
                    "GET /history/{customer_phone} - Get order history",
                    "GET /metrics - Get processing metrics"
                ]
            },
            "webhooks": {
                "base_path": "/api/v1/orders/webhooks",
                "endpoints": [
                    "POST /whatsapp - WhatsApp webhook",
                    "POST /rcs - RCS webhook",
                    "POST /sms - SMS webhook"
                ]
            }
        },
        "supported_languages": [
            "English", "Hindi", "Bengali", "Tamil", "Telugu", "Marathi",
            "Gujarati", "Kannada", "Malayalam", "Punjabi", "Odia",
            "Assamese", "Urdu", "Konkani", "Sindhi", "Nepali", "Kashmiri"
        ],
        "supported_channels": [
            "WhatsApp", "RCS", "SMS", "Web"
        ]
    }

# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(VyaparAIException)
async def vyaparai_exception_handler_wrapper(request: Request, exc: VyaparAIException):
    """Handle VyaparAI exceptions with standardized format"""
    return await vyaparai_exception_handler(request, exc)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "request_id": getattr(request.state, "request_id", "unknown"),
            "timestamp": time.time()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "Internal server error",
            "status_code": 500,
            "request_id": getattr(request.state, "request_id", "unknown"),
            "timestamp": time.time()
        }
    )

# =============================================================================
# ROUTER INCLUSION
# =============================================================================

# Include API v1 router
app.include_router(api_v1_router)

# Include health router
app.include_router(health.router, prefix="/api/v1", tags=["health"])

# Include RCS webhook router
try:
    from channels.rcs import rcs_webhook_router
    app.include_router(rcs_webhook_router)
    logger.info("RCS webhook router included")
except ImportError as e:
    logger.warning(f"RCS webhook router not available: {e}")

# Include WebSocket support
try:
    from websocket.socket_manager import get_socket_app
    import socketio
    
    # Create Socket.IO app
    socket_app = get_socket_app()
    
    # Mount Socket.IO app directly
    app.mount("/socket.io", socket_app)
    
    logger.info("WebSocket support included")
except ImportError as e:
    logger.warning(f"WebSocket support not available: {e}")

# =============================================================================
# DEVELOPMENT UTILITIES
# =============================================================================

if DEBUG:
    @app.get("/debug/info", tags=["debug"])
    async def debug_info():
        """Debug information endpoint (development only)"""
        return {
            "app_state": app_state,
            "environment_variables": {
                "ENVIRONMENT": ENVIRONMENT,
                "DEBUG": DEBUG,
                "REDIS_URL": REDIS_URL,
                "GOOGLE_API_KEY": "***" if GOOGLE_API_KEY else None,
                "GOOGLE_TRANSLATE_API_KEY": "***" if GOOGLE_TRANSLATE_API_KEY else None
            },
            "services": {
                "unified_order_service": {
                    "metrics": unified_order_service.get_metrics(),
                    "performance": unified_order_service.get_performance_summary()
                }
            }
        }

# =============================================================================
# APPLICATION STARTUP
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=DEBUG,
        log_level="info" if not DEBUG else "debug",
        access_log=True
    )
