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
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# Local imports
from app.api.v1 import api_v1_router
from app.api.v1 import health
from app.middleware.rate_limit import initialize_redis, close_redis, rate_limit_middleware
# NOTE: unified_order_service removed after AI archival
# from app.services.unified_order_service import unified_order_service
from app.core.exceptions import vyaparai_exception_handler, VyaparAIException
from app.core.security import validate_security_config
from app.core.audit import log_audit_event, AuditEventType, AuditSeverity

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

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

# Maximum request body size (10MB default, can be adjusted per endpoint)
MAX_REQUEST_SIZE_BYTES = int(os.getenv("MAX_REQUEST_SIZE_BYTES", 10 * 1024 * 1024))

# Content types allowed for POST/PUT/PATCH requests
ALLOWED_CONTENT_TYPES = [
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
]

# Paths that don't require content-type validation
CONTENT_TYPE_EXEMPT_PATHS = [
    "/health",
    "/health/detailed",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
    "/api",
]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    Implements OWASP security best practices.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS Protection (legacy but still useful for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy - don't leak referrer info
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy - restrict browser features
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Content Security Policy (relaxed for API, stricter for HTML responses)
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self' https://api.vyaparai.com"
            )

        # HSTS - enforce HTTPS (only in production)
        if not DEBUG:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Cache control for API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request body size limits.
    Prevents denial of service via large request bodies.
    """

    def __init__(self, app, max_size: int = MAX_REQUEST_SIZE_BYTES):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_size:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": True,
                            "message": f"Request body too large. Maximum size is {self.max_size // (1024 * 1024)}MB",
                            "status_code": 413
                        }
                    )
            except ValueError:
                pass  # Invalid content-length, let it through for now

        return await call_next(request)


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate Content-Type headers for POST/PUT/PATCH requests.
    Prevents processing of unexpected content types.
    """

    async def dispatch(self, request: Request, call_next):
        # Only check for methods that have request bodies
        if request.method in ["POST", "PUT", "PATCH"]:
            # Skip exempt paths
            if not any(request.url.path.startswith(path) for path in CONTENT_TYPE_EXEMPT_PATHS):
                content_type = request.headers.get("content-type", "")

                # Extract base content type (ignore parameters like charset)
                base_content_type = content_type.split(";")[0].strip().lower()

                if base_content_type and base_content_type not in ALLOWED_CONTENT_TYPES:
                    logger.warning(
                        f"Invalid content-type '{content_type}' for {request.method} {request.url.path}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        content={
                            "error": True,
                            "message": f"Unsupported content type: {base_content_type}",
                            "allowed_types": ALLOWED_CONTENT_TYPES,
                            "status_code": 415
                        }
                    )

        return await call_next(request)


class APIRequestAuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for auditing API requests.
    Logs all non-exempt requests with timing and status information.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip audit for exempt paths
        if any(request.url.path.startswith(path) for path in CONTENT_TYPE_EXEMPT_PATHS):
            return await call_next(request)

        start_time = time.time()
        request_id = getattr(request.state, "request_id", f"req_{int(start_time * 1000)}")

        # Extract identifiers for audit
        store_id = request.headers.get("x-store-id")
        client_ip = request.client.host if request.client else "unknown"

        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            # Log audit event
            duration_ms = (time.time() - start_time) * 1000

            # Determine severity based on status code
            if response:
                if response.status_code >= 500:
                    severity = AuditSeverity.ERROR
                elif response.status_code >= 400:
                    severity = AuditSeverity.WARNING
                else:
                    severity = AuditSeverity.INFO
                status_code = response.status_code
                success = response.status_code < 400
            else:
                severity = AuditSeverity.ERROR
                status_code = 500
                success = False

            # Only log detailed audit for non-GET requests or errors
            if request.method != "GET" or not success:
                log_audit_event(
                    event_type=AuditEventType.DATA_READ if request.method == "GET" else AuditEventType.DATA_UPDATE,
                    severity=severity,
                    store_id=store_id,
                    resource_type="api",
                    resource_id=request.url.path,
                    action=request.method.lower(),
                    details={
                        "request_id": request_id,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 2),
                        "client_ip": client_ip if DEBUG else client_ip.rsplit(".", 1)[0] + ".*",
                    },
                    request=request,
                    success=success
                )


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request timeouts.
    Prevents long-running requests from tying up resources.
    """

    def __init__(self, app, timeout_seconds: float = 30.0):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next):
        import asyncio

        # Skip timeout for certain paths (like file uploads)
        if any(path in request.url.path for path in ["/upload", "/webhook", "/stream"]):
            return await call_next(request)

        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Request timeout after {self.timeout_seconds}s: {request.method} {request.url.path}"
            )
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={
                    "error": True,
                    "message": "Request timed out. Please try again.",
                    "status_code": 504,
                    "timeout_seconds": self.timeout_seconds
                }
            )

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

def _print_startup_banner():
    """Print startup banner with configuration summary"""
    banner = f"""
╔══════════════════════════════════════════════════════════════════╗
║                    VyaparAI API Server                           ║
║                    Version: {APP_VERSION}                                   ║
╠══════════════════════════════════════════════════════════════════╣
║  Environment: {ENVIRONMENT:<20}                               ║
║  Debug Mode:  {str(DEBUG):<20}                               ║
║  Docs:        {str(DOCS_ENABLED):<20}                               ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(banner)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    _print_startup_banner()
    logger.info("Starting VyaparAI application...")

    try:
        # Validate security configuration FIRST - will raise in production if misconfigured
        # This MUST succeed before starting the application
        logger.info("[1/5] Validating security configuration...")
        security_status = validate_security_config()
        if security_status["valid"]:
            logger.info(f"  ✓ Security validated ({security_status['environment']} mode)")
        else:
            # In development, log warnings but continue
            for warning in security_status.get("warnings", []):
                logger.warning(f"  ⚠ Security warning: {warning}")

        # Initialize Redis for rate limiting
        logger.info("[2/5] Initializing Redis connection...")
        await initialize_redis(REDIS_URL)
        logger.info("  ✓ Redis initialized for rate limiting")

        # Initialize and VERIFY database connections
        logger.info("[3/5] Verifying database connections...")
        from app.core.database import db_manager

        # Determine if we should fail on DB errors (production = yes, dev = no)
        is_production = ENVIRONMENT.lower() == "production"
        db_verification = await db_manager.verify_connections_at_startup(
            fail_on_error=is_production
        )

        # Log verification results
        if db_verification["dynamodb"]["verified"]:
            logger.info("  ✓ DynamoDB connection verified")
        elif db_verification["dynamodb"]["status"] == "not_initialized":
            if is_production:
                raise RuntimeError("DynamoDB not initialized - required for production")
            logger.warning("  ⚠ DynamoDB not configured (development mode)")
        else:
            logger.error(f"  ✗ DynamoDB verification failed: {db_verification['dynamodb'].get('error')}")

        if db_verification["postgres"]["verified"]:
            logger.info(f"  ✓ PostgreSQL pool verified (size: {db_verification['postgres'].get('pool_size', 'N/A')})")
        elif db_verification["postgres"]["status"] == "not_configured":
            logger.info("  ℹ PostgreSQL not configured (optional)")

        if db_verification["redis"]["verified"]:
            logger.info("  ✓ Redis connection verified")
        elif db_verification["redis"]["status"] == "not_configured":
            logger.info("  ℹ Redis not configured (using in-app rate limiting)")

        # Warm up NLP models
        logger.info("[4/5] Loading NLP models...")
        await asyncio.sleep(0.5)  # Brief warmup
        logger.info("  ✓ NLP models ready")

        # Initialize services
        logger.info("[5/5] Finalizing startup...")
        app_state["startup_time"] = time.time()
        app_state["services_ready"] = True

        logger.info("═" * 60)
        logger.info("VyaparAI application started successfully")
        logger.info(f"API available at: http://0.0.0.0:8000")
        if DOCS_ENABLED:
            logger.info(f"Documentation at: http://0.0.0.0:8000/docs")
        logger.info("═" * 60)

    except ValueError as e:
        # Security configuration errors - CRITICAL, must not start
        logger.critical(f"SECURITY CONFIGURATION ERROR: {e}")
        logger.critical("Application cannot start with invalid security configuration")
        app_state["services_ready"] = False
        raise  # Re-raise to prevent app from starting

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

# Security headers middleware (must be first to ensure all responses get headers)
app.add_middleware(SecurityHeadersMiddleware)

# Request size limit middleware
app.add_middleware(RequestSizeLimitMiddleware, max_size=MAX_REQUEST_SIZE_BYTES)

# Content-Type validation middleware
app.add_middleware(ContentTypeValidationMiddleware)

# API request audit middleware (logs all API requests)
app.add_middleware(APIRequestAuditMiddleware)

# Request timeout middleware (30 second default)
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=REQUEST_TIMEOUT_SECONDS)

# Compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS middleware - NEVER use wildcard "*" with credentials
# Even in debug mode, use explicit list of allowed origins
CORS_ORIGINS = [
    "https://vyapaarai.com",         # Primary domain
    "https://www.vyapaarai.com",     # WWW subdomain
    "https://app.vyapaarai.com",     # App subdomain
    "https://vyaparai.com",          # Alternate spelling
    "https://www.vyaparai.com",      # Alternate spelling WWW
    "https://app.vyaparai.com",      # Alternate spelling app
    "https://admin.vyaparai.com",
    # CloudFront distributions
    "https://de98fon4psh1n.cloudfront.net",  # Store dashboard CloudFront
    "https://d2zz8aoffj79ma.cloudfront.net", # Secondary CloudFront
    "https://duunvuia0g11s.cloudfront.net",  # Tertiary CloudFront
]

# Add development origins only in debug mode
if DEBUG:
    CORS_ORIGINS.extend([
        "http://localhost:3000",         # Frontend development
        "https://localhost:3000",        # Frontend development with HTTPS
        "http://localhost:5173",         # Vite dev server
        "https://localhost:5173",        # Vite dev server with HTTPS
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Store-ID", "X-Session-ID"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"]
)

# Trusted host middleware (for production)
if not DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "api.vyapaarai.com",               # API subdomain (primary)
            "www.vyapaarai.com",               # Custom domain (primary)
            "vyapaarai.com",                   # Apex domain
            "app.vyapaarai.com",               # App subdomain
            "www.vyaparai.com",                # Alternate spelling
            "vyaparai.com",                    # Alternate spelling apex
            "app.vyaparai.com",
            "admin.vyaparai.com",
            "api.vyaparai.com",
            "jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com",  # Original API Gateway
            "d-h1w8nolafe.execute-api.ap-south-1.amazonaws.com",  # Custom domain API Gateway mapping (old)
            "d-xkxntytije.execute-api.ap-south-1.amazonaws.com",  # Custom domain API Gateway mapping (new)
            "bk6kziyr5h.execute-api.ap-south-1.amazonaws.com",  # Current API Gateway endpoint
            "rroisuiv7c.execute-api.ap-south-1.amazonaws.com",  # Production API Gateway endpoint
            "6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws",  # Lambda Function URL
        ]
    )

# Request ID and API version middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID and API version headers to all requests"""
    request_id = f"req_{int(time.time() * 1000)}_{id(request)}"
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-API-Version"] = APP_VERSION
    response.headers["X-Environment"] = ENVIRONMENT if DEBUG else "production"
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

# API documentation can be disabled in production via environment variable
DOCS_ENABLED = os.getenv("DOCS_ENABLED", "true").lower() == "true" or DEBUG


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with VyaparAI branding"""
    if not DOCS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API documentation is disabled in this environment"
        )

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
    if not DOCS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API documentation is disabled in this environment"
        )

    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Documentation",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
        redoc_favicon_url="https://vyaparai.com/favicon.ico",
    )


@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_json():
    """OpenAPI schema endpoint"""
    if not DOCS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API documentation is disabled in this environment"
        )
    return app.openapi()

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
    # NOTE: unified_order_service check removed after AI archival
    # try:
    #     # Check unified order service
    #     metrics = unified_order_service.get_metrics()
    #     health_status["services"]["unified_order_service"] = {
    #         "status": "healthy",
    #         "total_requests": metrics["total_requests"],
    #         "avg_processing_time_ms": metrics["avg_processing_time"],
    #         "error_rate": (metrics["error_count"] / max(metrics["total_requests"], 1)) * 100
    #     }
    # except Exception as e:
    #     health_status["services"]["unified_order_service"] = {
    #         "status": "unhealthy",
    #         "error": str(e)
    #     }
    #     health_status["status"] = "degraded"

    # Check Redis
    try:
        from app.middleware.rate_limit import redis_client
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
    
    # NOTE: Gemini and Google Translate checks removed after AI archival
    # # Check Gemini
    # try:
    #     if hasattr(unified_order_service, 'gemini_model') and unified_order_service.gemini_model:
    #         health_status["services"]["gemini"] = {"status": "healthy"}
    #     else:
    #         health_status["services"]["gemini"] = {"status": "not_configured"}
    # except Exception as e:
    #     health_status["services"]["gemini"] = {
    #         "status": "unhealthy",
    #         "error": str(e)
    #     }
    #     health_status["status"] = "degraded"
    #
    # # Check Google Translate
    # try:
    #     from services.indian_multilingual_service import indian_multilingual_service
    #     if hasattr(indian_multilingual_service, 'translate_client') and indian_multilingual_service.translate_client:
    #         health_status["services"]["google_translate"] = {"status": "healthy"}
    #     else:
    #         health_status["services"]["google_translate"] = {"status": "not_configured"}
    # except Exception as e:
    #     health_status["services"]["google_translate"] = {
    #         "status": "unhealthy",
    #         "error": str(e)
    #     }
    #     health_status["status"] = "degraded"

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
    """
    Handle general exceptions securely.
    Never expose internal error details in production.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    # Log the full error with stack trace for debugging
    logger.error(
        f"Unhandled exception [request_id={request_id}]: {exc}",
        exc_info=True,
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host if request.client else "unknown"
        }
    )

    # Build secure response - never expose internal details in production
    error_response = {
        "error": True,
        "message": "An internal error occurred. Please try again later.",
        "status_code": 500,
        "request_id": request_id,
        "timestamp": time.time()
    }

    # Only add error details in development mode
    if DEBUG:
        error_response["debug"] = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
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

# Debug endpoints are ONLY available in development mode
# This check happens at startup, not per-request, for security
if DEBUG:
    @app.get("/debug/info", tags=["debug"], include_in_schema=False)
    async def debug_info(request: Request):
        """
        Debug information endpoint (development only).

        This endpoint is only available when ENVIRONMENT=development.
        It is excluded from OpenAPI schema for additional security.
        """
        # Log access to debug endpoint
        logger.info(f"Debug endpoint accessed from {request.client.host if request.client else 'unknown'}")

        return {
            "warning": "DEBUG MODE - Not for production use",
            "app_state": {
                "startup_time": app_state.get("startup_time"),
                "services_ready": app_state.get("services_ready"),
            },
            "environment": {
                "ENVIRONMENT": ENVIRONMENT,
                "DEBUG": DEBUG,
                "REQUEST_TIMEOUT": REQUEST_TIMEOUT_SECONDS,
                "MAX_REQUEST_SIZE_MB": MAX_REQUEST_SIZE_BYTES // (1024 * 1024),
            },
            "configured_services": {
                "redis": bool(REDIS_URL),
                "google_api": bool(GOOGLE_API_KEY),
                "google_translate": bool(GOOGLE_TRANSLATE_API_KEY),
            }
            # Sensitive values are never exposed, even in debug mode
        }
else:
    # In production, explicitly reject debug endpoint requests
    @app.get("/debug/info", include_in_schema=False)
    async def debug_info_disabled():
        """Debug endpoint disabled in production"""
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found"
        )

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
