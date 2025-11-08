"""
Translation Service with DynamoDB Caching and Amazon Translate Integration

This module provides a FastAPI-based translation microservice that:
1. Retrieves product data from DynamoDB
2. Checks translation cache before calling Amazon Translate
3. Caches new translations for future use
4. Returns translated product information
"""

import os
import logging
import boto3
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from db_schema import (
    Product,
    TranslationCache,
    TranslatedProduct,
    LanguageCode,
    dynamodb_to_product,
    dynamodb_to_translation_cache,
    translation_cache_to_dynamodb,
    product_to_dynamodb
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="VyapaarAI Translation Service",
    description="Dynamic translation service with DynamoDB caching",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AWS clients
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')
translate = boto3.client('translate', region_name='ap-south-1')

# DynamoDB table names
PRODUCTS_TABLE = os.environ.get('PRODUCTS_TABLE', 'vyaparai-products-catalog-prod')
TRANSLATION_CACHE_TABLE = os.environ.get('TRANSLATION_CACHE_TABLE', 'vyaparai-translation-cache-prod')

# Translation cache TTL (30 days)
CACHE_TTL_DAYS = 30


def get_product_from_db(product_id: str) -> Optional[Product]:
    """
    Retrieve product from DynamoDB Products table

    Args:
        product_id: Unique product identifier

    Returns:
        Product object if found, None otherwise
    """
    try:
        response = dynamodb.get_item(
            TableName=PRODUCTS_TABLE,
            Key={'productId': {'S': product_id}}
        )

        if 'Item' not in response:
            logger.warning(f"Product {product_id} not found in database")
            return None

        return dynamodb_to_product(response['Item'])

    except Exception as e:
        logger.error(f"Error retrieving product {product_id}: {e}")
        return None


def get_cached_translation(source_text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """
    Check if translation exists in cache

    Args:
        source_text: Text to translate
        source_lang: Source language code
        target_lang: Target language code

    Returns:
        Cached translation if found, None otherwise
    """
    try:
        cache_key = TranslationCache.generate_cache_key(source_text, source_lang, target_lang)

        response = dynamodb.get_item(
            TableName=TRANSLATION_CACHE_TABLE,
            Key={'cacheKey': {'S': cache_key}}
        )

        if 'Item' in response:
            cache_entry = dynamodb_to_translation_cache(response['Item'])
            logger.info(f"Cache HIT for key: {cache_key}")
            return cache_entry.translatedText
        else:
            logger.info(f"Cache MISS for key: {cache_key}")
            return None

    except Exception as e:
        logger.error(f"Error checking cache for '{source_text}': {e}")
        return None


def translate_text_with_amazon_translate(source_text: str, source_lang: str, target_lang: str) -> str:
    """
    Translate text using Amazon Translate API

    Args:
        source_text: Text to translate
        source_lang: Source language code
        target_lang: Target language code

    Returns:
        Translated text

    Raises:
        Exception if translation fails
    """
    try:
        logger.info(f"Translating '{source_text}' from {source_lang} to {target_lang} using Amazon Translate")

        response = translate.translate_text(
            Text=source_text,
            SourceLanguageCode=source_lang,
            TargetLanguageCode=target_lang
        )

        translated_text = response.get('TranslatedText', '')
        logger.info(f"Translation successful: '{source_text}' -> '{translated_text}'")

        return translated_text

    except Exception as e:
        logger.error(f"Amazon Translate error: {e}")
        raise Exception(f"Translation failed: {str(e)}")


def cache_translation(source_text: str, translated_text: str, source_lang: str, target_lang: str) -> bool:
    """
    Store translation in cache

    Args:
        source_text: Original text
        translated_text: Translated text
        source_lang: Source language code
        target_lang: Target language code

    Returns:
        True if caching successful, False otherwise
    """
    try:
        cache_entry = TranslationCache(
            cacheKey=TranslationCache.generate_cache_key(source_text, source_lang, target_lang),
            sourceText=source_text,
            translatedText=translated_text,
            sourceLanguage=source_lang,
            targetLanguage=target_lang,
            timestamp=datetime.utcnow().isoformat(),
            ttl=TranslationCache.calculate_ttl(CACHE_TTL_DAYS)
        )

        dynamodb_item = translation_cache_to_dynamodb(cache_entry)

        dynamodb.put_item(
            TableName=TRANSLATION_CACHE_TABLE,
            Item=dynamodb_item
        )

        logger.info(f"Cached translation: {cache_entry.cacheKey}")
        return True

    except Exception as e:
        logger.error(f"Error caching translation: {e}")
        return False


def translate_with_cache(source_text: str, source_lang: str, target_lang: str) -> tuple[str, bool]:
    """
    Get translation with cache check

    Args:
        source_text: Text to translate
        source_lang: Source language code
        target_lang: Target language code

    Returns:
        Tuple of (translated_text, from_cache)
    """
    # Check cache first
    cached_translation = get_cached_translation(source_text, source_lang, target_lang)

    if cached_translation:
        return cached_translation, True

    # Cache miss - call Amazon Translate
    translated_text = translate_text_with_amazon_translate(source_text, source_lang, target_lang)

    # Cache the new translation
    cache_translation(source_text, translated_text, source_lang, target_lang)

    return translated_text, False


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "VyapaarAI Translation Service",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/api/v1/products/{product_id}", response_model=TranslatedProduct)
async def get_product_translated(
    product_id: str,
    accept_language: Optional[str] = Header(default="en", alias="Accept-Language")
):
    """
    Get product with translated name and description

    Args:
        product_id: Product ID to retrieve
        accept_language: Target language code (from Accept-Language header)

    Returns:
        TranslatedProduct with name and description in target language

    Example:
        GET /api/v1/products/PROD-001
        Headers: Accept-Language: hi

        Response:
        {
            "productId": "PROD-001",
            "productName": "टाटा नमक",
            "productDescription": "दैनिक खाना पकाने के लिए प्रीमियम आयोडीन युक्त नमक",
            "price": 25.00,
            "quantity": 150,
            "category": "किराना",
            "language": "hi",
            "fromCache": true
        }
    """
    try:
        # Parse target language from header (handle formats like "hi" or "hi-IN")
        target_lang = accept_language.split('-')[0].lower()

        # Validate language code
        if target_lang not in [lang.value for lang in LanguageCode]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {target_lang}. Supported: {[lang.value for lang in LanguageCode]}"
            )

        # Retrieve product from database
        product = get_product_from_db(product_id)

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {product_id} not found"
            )

        # If target language is English, return as-is
        if target_lang == 'en':
            return TranslatedProduct(
                productId=product.productId,
                productName=product.productName_en,
                productDescription=product.productDescription_en,
                price=product.price,
                quantity=product.quantity,
                category=product.category,
                language='en',
                fromCache=False
            )

        # Translate product name
        translated_name, name_from_cache = translate_with_cache(
            product.productName_en,
            'en',
            target_lang
        )

        # Translate product description
        translated_description, desc_from_cache = translate_with_cache(
            product.productDescription_en,
            'en',
            target_lang
        )

        # Translate category
        translated_category, category_from_cache = translate_with_cache(
            product.category,
            'en',
            target_lang
        )

        # Check if all translations came from cache
        from_cache = name_from_cache and desc_from_cache and category_from_cache

        return TranslatedProduct(
            productId=product.productId,
            productName=translated_name,
            productDescription=translated_description,
            price=product.price,
            quantity=product.quantity,
            category=translated_category,
            language=target_lang,
            fromCache=from_cache
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing product translation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Translation service error: {str(e)}"
        )


@app.get("/api/v1/products", response_model=list[TranslatedProduct])
async def get_all_products_translated(
    accept_language: Optional[str] = Header(default="en", alias="Accept-Language"),
    limit: int = 100
):
    """
    Get all products with translations

    Args:
        accept_language: Target language code
        limit: Maximum number of products to return

    Returns:
        List of TranslatedProduct objects
    """
    try:
        target_lang = accept_language.split('-')[0].lower()

        # Scan products table (in production, use pagination)
        response = dynamodb.scan(
            TableName=PRODUCTS_TABLE,
            Limit=limit
        )

        products = []
        for item in response.get('Items', []):
            product = dynamodb_to_product(item)

            if target_lang == 'en':
                products.append(TranslatedProduct(
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
                # Translate each product
                translated_name, name_cached = translate_with_cache(
                    product.productName_en, 'en', target_lang
                )
                translated_desc, desc_cached = translate_with_cache(
                    product.productDescription_en, 'en', target_lang
                )
                translated_category, cat_cached = translate_with_cache(
                    product.category, 'en', target_lang
                )

                products.append(TranslatedProduct(
                    productId=product.productId,
                    productName=translated_name,
                    productDescription=translated_desc,
                    price=product.price,
                    quantity=product.quantity,
                    category=translated_category,
                    language=target_lang,
                    fromCache=name_cached and desc_cached and cat_cached
                ))

        return products

    except Exception as e:
        logger.error(f"Error retrieving products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Lambda handler
handler = Mangum(app)


def lambda_handler(event, context):
    """AWS Lambda handler function"""
    return handler(event, context)
