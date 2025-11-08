"""
DynamoDB Schema Definitions for Translation Service

This module defines the schema for two DynamoDB tables:
1. Products Table: Stores product catalog data in source language (English)
2. TranslationCache Table: Stores cached translations to avoid repeated API calls
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class LanguageCode(str, Enum):
    """Supported language codes"""
    ENGLISH = "en"
    HINDI = "hi"
    MARATHI = "mr"
    TAMIL = "ta"
    TELUGU = "te"
    BENGALI = "bn"


# ==================== Products Table Schema ====================

class Product(BaseModel):
    """
    Product schema for the Products table

    DynamoDB Table Name: vyaparai-products-catalog-prod
    Partition Key: productId (String)
    """
    productId: str = Field(..., description="Unique product identifier (PK)")
    productName_en: str = Field(..., description="Product name in English")
    productDescription_en: str = Field(..., description="Product description in English")
    price: float = Field(..., description="Product price in INR")
    quantity: int = Field(..., description="Available quantity")
    category: str = Field(..., description="Product category")
    sku: Optional[str] = Field(None, description="Stock Keeping Unit")
    barcode: Optional[str] = Field(None, description="Product barcode")
    imageUrl: Optional[str] = Field(None, description="Product image URL")
    createdAt: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Creation timestamp")
    updatedAt: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Last update timestamp")

    class Config:
        schema_extra = {
            "example": {
                "productId": "PROD-001",
                "productName_en": "Tata Salt",
                "productDescription_en": "Premium iodized salt for daily cooking",
                "price": 25.00,
                "quantity": 150,
                "category": "Grocery",
                "sku": "SALT-001",
                "barcode": "8901234567890",
                "createdAt": "2025-10-18T12:00:00.000Z",
                "updatedAt": "2025-10-18T12:00:00.000Z"
            }
        }


# DynamoDB item structure for Products table
def product_to_dynamodb(product: Product) -> Dict[str, Any]:
    """Convert Product Pydantic model to DynamoDB item format"""
    return {
        'productId': {'S': product.productId},
        'productName_en': {'S': product.productName_en},
        'productDescription_en': {'S': product.productDescription_en},
        'price': {'N': str(product.price)},
        'quantity': {'N': str(product.quantity)},
        'category': {'S': product.category},
        'sku': {'S': product.sku} if product.sku else {'NULL': True},
        'barcode': {'S': product.barcode} if product.barcode else {'NULL': True},
        'imageUrl': {'S': product.imageUrl} if product.imageUrl else {'NULL': True},
        'createdAt': {'S': product.createdAt},
        'updatedAt': {'S': product.updatedAt}
    }


def dynamodb_to_product(item: Dict[str, Any]) -> Product:
    """Convert DynamoDB item to Product Pydantic model"""
    return Product(
        productId=item.get('productId', {}).get('S', ''),
        productName_en=item.get('productName_en', {}).get('S', ''),
        productDescription_en=item.get('productDescription_en', {}).get('S', ''),
        price=float(item.get('price', {}).get('N', '0')),
        quantity=int(item.get('quantity', {}).get('N', '0')),
        category=item.get('category', {}).get('S', ''),
        sku=item.get('sku', {}).get('S'),
        barcode=item.get('barcode', {}).get('S'),
        imageUrl=item.get('imageUrl', {}).get('S'),
        createdAt=item.get('createdAt', {}).get('S', ''),
        updatedAt=item.get('updatedAt', {}).get('S', '')
    )


# ==================== TranslationCache Table Schema ====================

class TranslationCache(BaseModel):
    """
    Translation cache schema for the TranslationCache table

    DynamoDB Table Name: vyaparai-translation-cache-prod
    Partition Key: cacheKey (String) - Format: {sourceText}__en__{targetLanguage}
    TTL Attribute: ttl (Number) - Auto-delete after 30 days
    """
    cacheKey: str = Field(..., description="Composite key: sourceText__sourceLanguage__targetLanguage")
    sourceText: str = Field(..., description="Original text in source language")
    translatedText: str = Field(..., description="Translated text in target language")
    sourceLanguage: str = Field(default="en", description="Source language code")
    targetLanguage: str = Field(..., description="Target language code")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Cache creation time")
    ttl: int = Field(..., description="TTL expiration timestamp (Unix epoch)")

    @staticmethod
    def generate_cache_key(source_text: str, source_lang: str, target_lang: str) -> str:
        """Generate a unique cache key"""
        # Normalize the source text to handle case sensitivity
        normalized_text = source_text.strip().lower()
        return f"{normalized_text}__{source_lang}__{target_lang}"

    @staticmethod
    def calculate_ttl(days: int = 30) -> int:
        """Calculate TTL expiration timestamp (30 days from now by default)"""
        from datetime import datetime, timedelta
        expiration_date = datetime.utcnow() + timedelta(days=days)
        return int(expiration_date.timestamp())

    class Config:
        schema_extra = {
            "example": {
                "cacheKey": "tata salt__en__hi",
                "sourceText": "Tata Salt",
                "translatedText": "टाटा नमक",
                "sourceLanguage": "en",
                "targetLanguage": "hi",
                "timestamp": "2025-10-18T12:00:00.000Z",
                "ttl": 1731945600
            }
        }


# DynamoDB item structure for TranslationCache table
def translation_cache_to_dynamodb(cache: TranslationCache) -> Dict[str, Any]:
    """Convert TranslationCache Pydantic model to DynamoDB item format"""
    return {
        'cacheKey': {'S': cache.cacheKey},
        'sourceText': {'S': cache.sourceText},
        'translatedText': {'S': cache.translatedText},
        'sourceLanguage': {'S': cache.sourceLanguage},
        'targetLanguage': {'S': cache.targetLanguage},
        'timestamp': {'S': cache.timestamp},
        'ttl': {'N': str(cache.ttl)}
    }


def dynamodb_to_translation_cache(item: Dict[str, Any]) -> TranslationCache:
    """Convert DynamoDB item to TranslationCache Pydantic model"""
    return TranslationCache(
        cacheKey=item.get('cacheKey', {}).get('S', ''),
        sourceText=item.get('sourceText', {}).get('S', ''),
        translatedText=item.get('translatedText', {}).get('S', ''),
        sourceLanguage=item.get('sourceLanguage', {}).get('S', 'en'),
        targetLanguage=item.get('targetLanguage', {}).get('S', ''),
        timestamp=item.get('timestamp', {}).get('S', ''),
        ttl=int(item.get('ttl', {}).get('N', '0'))
    )


# ==================== Response Models ====================

class TranslatedProduct(BaseModel):
    """Response model for translated product"""
    productId: str
    productName: str
    productDescription: str
    price: float
    quantity: int
    category: str
    language: str
    fromCache: bool = Field(default=False, description="Whether translation was from cache")

    class Config:
        schema_extra = {
            "example": {
                "productId": "PROD-001",
                "productName": "टाटा नमक",
                "productDescription": "दैनिक खाना पकाने के लिए प्रीमियम आयोडीन युक्त नमक",
                "price": 25.00,
                "quantity": 150,
                "category": "किराना",
                "language": "hi",
                "fromCache": True
            }
        }
