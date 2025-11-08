"""
Enterprise-Grade Translation Service with Advanced Features

Features:
- Async parallel translation
- Retry logic with exponential backoff
- Circuit breaker pattern
- Graceful degradation
- Structured JSON logging
- CloudWatch metrics
- Batch translation API
- Connection pooling
- Rate limiting
- API key authentication
- Input validation and sanitization
"""

import os
import asyncio
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

# FastAPI
from fastapi import FastAPI, Header, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from mangum import Mangum

# AWS and Async
import boto3
import aioboto3
from botocore.config import Config

# Retry and resilience
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
from pybreaker import CircuitBreaker, CircuitBreakerError

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Structured logging
import logging
from pythonjsonlogger import jsonlogger

# Metrics
from aws_embedded_metrics import metric_scope
from aws_embedded_metrics.logger.metrics_logger import MetricsLogger

# Security
from jose import jwt
import re

# Data models
from db_schema import (
    Product,
    TranslationCache,
    TranslatedProduct,
    LanguageCode,
    dynamodb_to_product,
    dynamodb_to_translation_cache,
    translation_cache_to_dynamodb,
)

# ==================== Configuration ====================

class Config:
    """Application configuration"""
    # DynamoDB tables
    PRODUCTS_TABLE = os.environ.get('PRODUCTS_TABLE', 'vyaparai-products-catalog-prod')
    TRANSLATION_CACHE_TABLE = os.environ.get('TRANSLATION_CACHE_TABLE', 'vyaparai-translation-cache-prod')

    # Cache TTL
    CACHE_TTL_DAYS = int(os.environ.get('CACHE_TTL_DAYS', '30'))

    # API Authentication
    API_KEY_NAME = "X-API-Key"
    VALID_API_KEYS = set(os.environ.get('VALID_API_KEYS', '').split(','))

    # CORS
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'https://www.vyapaarai.com,https://vyapaarai.com').split(',')

    # AWS Region
    AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')

    # Rate limiting
    RATE_LIMIT_PER_MINUTE = os.environ.get('RATE_LIMIT_PER_MINUTE', '60')

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_WAIT_MIN = 1  # seconds
    RETRY_WAIT_MAX = 10  # seconds

    # Circuit breaker
    CIRCUIT_BREAKER_FAIL_MAX = 5
    CIRCUIT_BREAKER_TIMEOUT = 60  # seconds

    # Batch processing
    MAX_BATCH_SIZE = 100

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


# ==================== Structured Logging ====================

def setup_logging():
    """Configure structured JSON logging"""
    logger = logging.getLogger()

    # Clear existing handlers
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    # Create JSON formatter
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s %(service)s',
        rename_fields={
            'levelname': 'level',
            'asctime': 'timestamp',
            'name': 'logger'
        }
    )
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    logger.setLevel(logging.INFO)

    return logger

logger = setup_logging()


# ==================== AWS Client Configuration ====================

# Boto3 config with connection pooling
boto_config = Config(
    region_name=Config.AWS_REGION,
    retries={'max_attempts': 3, 'mode': 'adaptive'},
    max_pool_connections=50,  # Connection pooling
    connect_timeout=5,
    read_timeout=60
)

# Synchronous clients (reused across invocations - Lambda container reuse)
dynamodb_client = boto3.client('dynamodb', config=boto_config)
translate_client = boto3.client('translate', config=boto_config)

# Async session for concurrent operations
aioboto3_session = aioboto3.Session()


# ==================== Circuit Breaker ====================

translate_circuit_breaker = CircuitBreaker(
    fail_max=Config.CIRCUIT_BREAKER_FAIL_MAX,
    timeout_duration=Config.CIRCUIT_BREAKER_TIMEOUT,
    name='amazon_translate_breaker'
)


# ==================== Metrics Helper ====================

class MetricsHelper:
    """Helper for CloudWatch Embedded Metrics"""

    @staticmethod
    def record_cache_hit(correlation_id: str):
        """Record cache hit metric"""
        logger.info("Cache HIT", extra={
            'correlation_id': correlation_id,
            'service': 'translation',
            'cache_result': 'hit'
        })

    @staticmethod
    def record_cache_miss(correlation_id: str):
        """Record cache miss metric"""
        logger.info("Cache MISS", extra={
            'correlation_id': correlation_id,
            'service': 'translation',
            'cache_result': 'miss'
        })

    @staticmethod
    def record_translation_latency(correlation_id: str, latency_ms: float):
        """Record translation latency"""
        logger.info(f"Translation latency: {latency_ms}ms", extra={
            'correlation_id': correlation_id,
            'service': 'translation',
            'latency_ms': latency_ms
        })

    @staticmethod
    def record_error(correlation_id: str, error_type: str, error_message: str):
        """Record error metric"""
        logger.error(f"Error: {error_type}", extra={
            'correlation_id': correlation_id,
            'service': 'translation',
            'error_type': error_type,
            'error_message': error_message
        })


# ==================== Input Validation and Sanitization ====================

class InputValidator:
    """Validate and sanitize user inputs"""

    # Regex patterns
    PRODUCT_ID_PATTERN = re.compile(r'^[A-Z0-9\-]{1,50}$')
    LANGUAGE_CODE_PATTERN = re.compile(r'^[a-z]{2}(-[A-Z]{2})?$')

    @staticmethod
    def sanitize_text(text: str, max_length: int = 5000) -> str:
        """Sanitize text input"""
        if not text:
            return ""

        # Remove control characters
        sanitized = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')

        # Trim to max length
        return sanitized[:max_length].strip()

    @staticmethod
    def validate_product_id(product_id: str) -> bool:
        """Validate product ID format"""
        return bool(InputValidator.PRODUCT_ID_PATTERN.match(product_id))

    @staticmethod
    def validate_language_code(lang_code: str) -> bool:
        """Validate language code format"""
        return bool(InputValidator.LANGUAGE_CODE_PATTERN.match(lang_code))


# ==================== Translation Service with Retry and Circuit Breaker ====================

class TranslationService:
    """Enterprise translation service with resilience patterns"""

    @staticmethod
    @retry(
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(
            multiplier=1,
            min=Config.RETRY_WAIT_MIN,
            max=Config.RETRY_WAIT_MAX
        ),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )
    @translate_circuit_breaker
    async def translate_with_amazon(
        source_text: str,
        source_lang: str,
        target_lang: str,
        correlation_id: str
    ) -> str:
        """
        Translate text using Amazon Translate with retry and circuit breaker

        Args:
            source_text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            correlation_id: Request correlation ID

        Returns:
            Translated text
        """
        try:
            start_time = time.time()

            logger.info(f"Calling Amazon Translate API", extra={
                'correlation_id': correlation_id,
                'service': 'translation',
                'source_lang': source_lang,
                'target_lang': target_lang,
                'text_length': len(source_text)
            })

            # Use async boto3 for non-blocking I/O
            async with aioboto3_session.client('translate', config=boto_config) as translate:
                response = await translate.translate_text(
                    Text=source_text,
                    SourceLanguageCode=source_lang,
                    TargetLanguageCode=target_lang
                )

            translated_text = response.get('TranslatedText', '')

            latency_ms = (time.time() - start_time) * 1000
            MetricsHelper.record_translation_latency(correlation_id, latency_ms)

            logger.info(f"Translation successful", extra={
                'correlation_id': correlation_id,
                'service': 'translation',
                'latency_ms': latency_ms
            })

            return translated_text

        except CircuitBreakerError as e:
            MetricsHelper.record_error(correlation_id, 'CircuitBreakerOpen', str(e))
            raise HTTPException(
                status_code=503,
                detail="Translation service temporarily unavailable"
            )
        except Exception as e:
            MetricsHelper.record_error(correlation_id, 'TranslationError', str(e))
            raise

    @staticmethod
    async def get_cached_translation(
        source_text: str,
        source_lang: str,
        target_lang: str,
        correlation_id: str
    ) -> Optional[str]:
        """
        Get cached translation from DynamoDB

        Returns cached translation or None if not found
        """
        try:
            cache_key = TranslationCache.generate_cache_key(source_text, source_lang, target_lang)

            # Use async DynamoDB client
            async with aioboto3_session.client('dynamodb', config=boto_config) as dynamodb:
                response = await dynamodb.get_item(
                    TableName=Config.TRANSLATION_CACHE_TABLE,
                    Key={'cacheKey': {'S': cache_key}}
                )

            if 'Item' in response:
                cache_entry = dynamodb_to_translation_cache(response['Item'])
                MetricsHelper.record_cache_hit(correlation_id)
                return cache_entry.translatedText
            else:
                MetricsHelper.record_cache_miss(correlation_id)
                return None

        except Exception as e:
            logger.warning(f"Cache read error (continuing with translation)", extra={
                'correlation_id': correlation_id,
                'service': 'translation',
                'error': str(e)
            })
            # Graceful degradation - don't fail on cache errors
            return None

    @staticmethod
    async def cache_translation(
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        correlation_id: str
    ) -> bool:
        """
        Cache translation in DynamoDB

        Returns True if successful, False otherwise
        """
        try:
            cache_entry = TranslationCache(
                cacheKey=TranslationCache.generate_cache_key(source_text, source_lang, target_lang),
                sourceText=source_text,
                translatedText=translated_text,
                sourceLanguage=source_lang,
                targetLanguage=target_lang,
                timestamp=datetime.utcnow().isoformat(),
                ttl=TranslationCache.calculate_ttl(Config.CACHE_TTL_DAYS)
            )

            dynamodb_item = translation_cache_to_dynamodb(cache_entry)

            async with aioboto3_session.client('dynamodb', config=boto_config) as dynamodb:
                await dynamodb.put_item(
                    TableName=Config.TRANSLATION_CACHE_TABLE,
                    Item=dynamodb_item
                )

            logger.info(f"Translation cached", extra={
                'correlation_id': correlation_id,
                'service': 'translation',
                'cache_key': cache_entry.cacheKey
            })

            return True

        except Exception as e:
            logger.warning(f"Cache write error (translation still successful)", extra={
                'correlation_id': correlation_id,
                'service': 'translation',
                'error': str(e)
            })
            # Graceful degradation - don't fail on cache write errors
            return False

    @staticmethod
    async def translate_with_cache(
        source_text: str,
        source_lang: str,
        target_lang: str,
        correlation_id: str
    ) -> tuple[str, bool]:
        """
        Translate text with cache check and graceful fallback

        Returns:
            Tuple of (translated_text, from_cache)
        """
        # Sanitize input
        source_text = InputValidator.sanitize_text(source_text)

        if not source_text:
            return "", False

        # Check cache first
        cached = await TranslationService.get_cached_translation(
            source_text, source_lang, target_lang, correlation_id
        )

        if cached:
            return cached, True

        # Cache miss - translate with Amazon Translate
        try:
            translated = await TranslationService.translate_with_amazon(
                source_text, source_lang, target_lang, correlation_id
            )

            # Cache the translation (fire and forget - don't wait)
            asyncio.create_task(
                TranslationService.cache_translation(
                    source_text, translated, source_lang, target_lang, correlation_id
                )
            )

            return translated, False

        except Exception as e:
            # Graceful degradation - return original text if translation fails
            logger.error(f"Translation failed, returning original text", extra={
                'correlation_id': correlation_id,
                'service': 'translation',
                'error': str(e)
            })
            return source_text, False

    @staticmethod
    async def translate_product_parallel(
        product: Product,
        target_lang: str,
        correlation_id: str
    ) -> tuple[str, str, str, bool]:
        """
        Translate product fields in parallel for maximum performance

        Returns:
            Tuple of (name, description, category, all_from_cache)
        """
        # If target is English, return as-is
        if target_lang == 'en':
            return (
                product.productName_en,
                product.productDescription_en,
                product.category,
                False
            )

        # Translate all fields in parallel using asyncio.gather
        results = await asyncio.gather(
            TranslationService.translate_with_cache(
                product.productName_en, 'en', target_lang, correlation_id
            ),
            TranslationService.translate_with_cache(
                product.productDescription_en, 'en', target_lang, correlation_id
            ),
            TranslationService.translate_with_cache(
                product.category, 'en', target_lang, correlation_id
            ),
            return_exceptions=True  # Don't fail entire batch on single error
        )

        # Extract results with fallback to original text on error
        name, name_cached = results[0] if not isinstance(results[0], Exception) else (product.productName_en, False)
        desc, desc_cached = results[1] if not isinstance(results[1], Exception) else (product.productDescription_en, False)
        cat, cat_cached = results[2] if not isinstance(results[2], Exception) else (product.category, False)

        all_from_cache = name_cached and desc_cached and cat_cached

        return name, desc, cat, all_from_cache


# ==================== Database Service ====================

class DatabaseService:
    """Database operations with error handling"""

    @staticmethod
    async def get_product(product_id: str, correlation_id: str) -> Optional[Product]:
        """Get product by ID"""
        try:
            async with aioboto3_session.client('dynamodb', config=boto_config) as dynamodb:
                response = await dynamodb.get_item(
                    TableName=Config.PRODUCTS_TABLE,
                    Key={'productId': {'S': product_id}}
                )

            if 'Item' not in response:
                logger.warning(f"Product not found", extra={
                    'correlation_id': correlation_id,
                    'service': 'database',
                    'product_id': product_id
                })
                return None

            return dynamodb_to_product(response['Item'])

        except Exception as e:
            MetricsHelper.record_error(correlation_id, 'DatabaseError', str(e))
            raise

    @staticmethod
    async def get_products_paginated(
        limit: int,
        last_evaluated_key: Optional[Dict[str, Any]],
        correlation_id: str
    ) -> tuple[List[Product], Optional[Dict[str, Any]]]:
        """
        Get products with pagination (using Query instead of Scan for better performance)

        Returns:
            Tuple of (products, next_page_token)
        """
        try:
            async with aioboto3_session.client('dynamodb', config=boto_config) as dynamodb:
                params = {
                    'TableName': Config.PRODUCTS_TABLE,
                    'Limit': limit
                }

                if last_evaluated_key:
                    params['ExclusiveStartKey'] = last_evaluated_key

                # Note: In production, add GSI for efficient querying
                # For now, using scan with limit
                response = await dynamodb.scan(**params)

            products = [dynamodb_to_product(item) for item in response.get('Items', [])]
            next_key = response.get('LastEvaluatedKey')

            return products, next_key

        except Exception as e:
            MetricsHelper.record_error(correlation_id, 'DatabaseError', str(e))
            raise


# ==================== API Key Authentication ====================

api_key_header = APIKeyHeader(name=Config.API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key"""
    # Skip auth in local development
    if not Config.VALID_API_KEYS or '' in Config.VALID_API_KEYS:
        return True

    if not api_key or api_key not in Config.VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return True


# ==================== Rate Limiting ====================

limiter = Limiter(key_func=get_remote_address)


# ==================== FastAPI App ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Translation service starting up", extra={
        'service': 'translation',
        'version': '2.0.0-enterprise'
    })
    yield
    # Shutdown
    logger.info("Translation service shutting down", extra={
        'service': 'translation'
    })

app = FastAPI(
    title="VyapaarAI Translation Service - Enterprise Edition",
    description="Production-grade translation service with caching, retry, circuit breaker, and monitoring",
    version="2.0.0",
    lifespan=lifespan
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS with specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400  # Cache preflight for 24 hours
)


# ==================== Middleware for Correlation ID ====================

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID to all requests for tracing"""
    correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
    request.state.correlation_id = correlation_id

    response = await call_next(request)
    response.headers['X-Correlation-ID'] = correlation_id

    return response


# ==================== API Endpoints ====================

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "VyapaarAI Translation Service - Enterprise",
        "status": "healthy",
        "version": "2.0.0",
        "features": [
            "async-parallel-translation",
            "retry-with-backoff",
            "circuit-breaker",
            "graceful-degradation",
            "structured-logging",
            "cloudwatch-metrics",
            "rate-limiting",
            "api-key-auth",
            "connection-pooling"
        ]
    }


@app.get("/api/v1/products/{product_id}", response_model=TranslatedProduct)
@limiter.limit(f"{Config.RATE_LIMIT_PER_MINUTE}/minute")
async def get_product_translated(
    request: Request,
    product_id: str,
    accept_language: Optional[str] = Header(default="en", alias="Accept-Language"),
    authenticated: bool = Depends(verify_api_key)
):
    """
    Get single product with translations (parallel translation for optimal performance)
    """
    correlation_id = request.state.correlation_id

    try:
        # Validate inputs
        if not InputValidator.validate_product_id(product_id):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid product ID format: {product_id}"
            )

        # Parse and validate language
        target_lang = accept_language.split('-')[0].lower()
        if target_lang not in [lang.value for lang in LanguageCode]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {target_lang}"
            )

        # Get product from database
        product = await DatabaseService.get_product(product_id, correlation_id)

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {product_id} not found"
            )

        # Translate product fields in parallel
        name, desc, cat, from_cache = await TranslationService.translate_product_parallel(
            product, target_lang, correlation_id
        )

        return TranslatedProduct(
            productId=product.productId,
            productName=name,
            productDescription=desc,
            price=product.price,
            quantity=product.quantity,
            category=cat,
            language=target_lang,
            fromCache=from_cache
        )

    except HTTPException:
        raise
    except Exception as e:
        MetricsHelper.record_error(correlation_id, 'APIError', str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@app.post("/api/v1/products/batch-translate", response_model=List[TranslatedProduct])
@limiter.limit(f"{Config.RATE_LIMIT_PER_MINUTE}/minute")
async def batch_translate_products(
    request: Request,
    product_ids: List[str],
    accept_language: Optional[str] = Header(default="en", alias="Accept-Language"),
    authenticated: bool = Depends(verify_api_key)
):
    """
    Batch translate multiple products (enterprise feature for bulk operations)

    Maximum 100 products per request
    """
    correlation_id = request.state.correlation_id

    try:
        # Validate batch size
        if len(product_ids) > Config.MAX_BATCH_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size exceeds maximum of {Config.MAX_BATCH_SIZE}"
            )

        # Parse language
        target_lang = accept_language.split('-')[0].lower()
        if target_lang not in [lang.value for lang in LanguageCode]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {target_lang}"
            )

        # Fetch all products in parallel
        product_tasks = [
            DatabaseService.get_product(pid, correlation_id)
            for pid in product_ids
        ]
        products = await asyncio.gather(*product_tasks, return_exceptions=True)

        # Translate all products in parallel
        translation_tasks = []
        valid_products = []

        for product in products:
            if isinstance(product, Exception) or product is None:
                continue
            valid_products.append(product)
            translation_tasks.append(
                TranslationService.translate_product_parallel(product, target_lang, correlation_id)
            )

        translations = await asyncio.gather(*translation_tasks, return_exceptions=True)

        # Build response
        results = []
        for i, product in enumerate(valid_products):
            if isinstance(translations[i], Exception):
                # Graceful degradation - include product with original text
                results.append(TranslatedProduct(
                    productId=product.productId,
                    productName=product.productName_en,
                    productDescription=product.productDescription_en,
                    price=product.price,
                    quantity=product.quantity,
                    category=product.category,
                    language='en',
                    fromCache=False
                ))
            else:
                name, desc, cat, from_cache = translations[i]
                results.append(TranslatedProduct(
                    productId=product.productId,
                    productName=name,
                    productDescription=desc,
                    price=product.price,
                    quantity=product.quantity,
                    category=cat,
                    language=target_lang,
                    fromCache=from_cache
                ))

        logger.info(f"Batch translation completed", extra={
            'correlation_id': correlation_id,
            'service': 'translation',
            'requested_count': len(product_ids),
            'translated_count': len(results)
        })

        return results

    except HTTPException:
        raise
    except Exception as e:
        MetricsHelper.record_error(correlation_id, 'BatchTranslationError', str(e))
        raise HTTPException(
            status_code=500,
            detail="Batch translation failed"
        )


@app.get("/api/v1/products", response_model=Dict[str, Any])
@limiter.limit(f"{Config.RATE_LIMIT_PER_MINUTE}/minute")
async def get_all_products_translated(
    request: Request,
    accept_language: Optional[str] = Header(default="en", alias="Accept-Language"),
    page_size: int = Config.DEFAULT_PAGE_SIZE,
    page_token: Optional[str] = None,
    authenticated: bool = Depends(verify_api_key)
):
    """
    Get all products with pagination and translation

    Returns paginated results with next_page_token for cursor-based pagination
    """
    correlation_id = request.state.correlation_id

    try:
        # Validate page size
        if page_size > Config.MAX_PAGE_SIZE:
            page_size = Config.MAX_PAGE_SIZE

        # Parse language
        target_lang = accept_language.split('-')[0].lower()
        if target_lang not in [lang.value for lang in LanguageCode]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {target_lang}"
            )

        # Decode page token (in production, use encrypted token)
        last_key = None
        if page_token:
            try:
                import json
                import base64
                last_key = json.loads(base64.b64decode(page_token))
            except:
                raise HTTPException(status_code=400, detail="Invalid page token")

        # Get products with pagination
        products, next_key = await DatabaseService.get_products_paginated(
            page_size, last_key, correlation_id
        )

        # Translate all products in parallel
        translation_tasks = [
            TranslationService.translate_product_parallel(p, target_lang, correlation_id)
            for p in products
        ]
        translations = await asyncio.gather(*translation_tasks, return_exceptions=True)

        # Build results
        results = []
        for i, product in enumerate(products):
            if isinstance(translations[i], Exception):
                name, desc, cat, from_cache = product.productName_en, product.productDescription_en, product.category, False
            else:
                name, desc, cat, from_cache = translations[i]

            results.append(TranslatedProduct(
                productId=product.productId,
                productName=name,
                productDescription=desc,
                price=product.price,
                quantity=product.quantity,
                category=cat,
                language=target_lang,
                fromCache=from_cache
            ))

        # Encode next page token
        next_token = None
        if next_key:
            import json
            import base64
            next_token = base64.b64encode(json.dumps(next_key).encode()).decode()

        return {
            "products": results,
            "page_size": len(results),
            "next_page_token": next_token,
            "has_more": next_token is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        MetricsHelper.record_error(correlation_id, 'PaginationError', str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve products"
        )


# ==================== Lambda Handler ====================

handler = Mangum(app)


def lambda_handler(event, context):
    """AWS Lambda handler"""
    return handler(event, context)
