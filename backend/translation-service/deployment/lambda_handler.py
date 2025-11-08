"""
Simple Translation Service with MOCK Mode Support
Cost-controlled version for testing
"""

import os
import json
from typing import Optional

# Minimal imports
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

# ==================== Configuration ====================

TRANSLATION_MODE = os.environ.get('TRANSLATION_MODE', 'mock')
ENABLE_AMAZON_TRANSLATE = os.environ.get('ENABLE_AMAZON_TRANSLATE', 'false').lower() == 'true'
API_KEY = os.environ.get('VALID_API_KEYS', 'test-key')
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*').split(';')

# Mock translations
MOCK_TRANSLATIONS = {
    'hi': {
        'Tata Salt': 'टाटा नमक [MOCK]',
        'Premium iodized salt for daily cooking': 'दैनिक खाना पकाने के लिए प्रीमियम आयोडीन युक्त नमक [MOCK]',
        'Grocery': 'किराना [MOCK]',
        'Amul Butter': 'अमूल मक्खन [MOCK]',
        'Fresh and creamy butter made from pure milk': 'शुद्ध दूध से बना ताजा और मलाईदार मक्खन [MOCK]',
        'Dairy': 'डेयरी [MOCK]',
        'Britannia Good Day Biscuits': 'ब्रिटानिया गुड डे बिस्कुट [MOCK]',
        'Delicious butter cookies perfect for tea time': 'चाय के समय के लिए एकदम सही स्वादिष्ट बटर कुकीज़ [MOCK]',
        'Snacks': 'नाश्ता [MOCK]'
    },
    'mr': {
        'Tata Salt': 'टाटा मीठ [MOCK]',
        'Premium iodized salt for daily cooking': 'दैनंदिन स्वयंपाकासाठी प्रीमियम आयोडीन युक्त मीठ [MOCK]',
        'Grocery': 'किराणा माल [MOCK]',
        'Amul Butter': 'अमूल लोणी [MOCK]',
        'Fresh and creamy butter made from pure milk': 'शुद्ध दुधापासून बनवलेले ताजे आणि मलईदार लोणी [MOCK]',
        'Dairy': 'दुग्धशाळा [MOCK]',
        'Britannia Good Day Biscuits': 'ब्रिटानिया गुड डे बिस्किटे [MOCK]',
        'Delicious butter cookies perfect for tea time': 'चहाच्या वेळेसाठी योग्य मस्त लोणी कुकीज [MOCK]',
        'Snacks': 'स्नॅक्स [MOCK]'
    },
    'ta': {
        'Tata Salt': 'டாடா உப்பு [MOCK]',
        'Premium iodized salt for daily cooking': 'தினசரி சமையலுக்கான பிரீமியம் அயோடின் உப்பு [MOCK]',
        'Grocery': 'மளிகை [MOCK]',
        'Amul Butter': 'அமுல் வெண்ணெய் [MOCK]',
        'Fresh and creamy butter made from pure milk': 'தூய்மையான பாலில் இருந்து தயாரிக்கப்பட்ட புதிய வெண்ணெய் [MOCK]',
        'Dairy': 'பால் பண்ணை [MOCK]',
        'Britannia Good Day Biscuits': 'பிரிட்டானியா குட் டே பிஸ்கட் [MOCK]',
        'Delicious butter cookies perfect for tea time': 'தேநீர் நேரத்திற்கு ஏற்ற சுவையான பிஸ்கட் [MOCK]',
        'Snacks': 'சிற்றுண்டி [MOCK]'
    }
}

# Sample products (hardcoded for testing)
SAMPLE_PRODUCTS = {
    'PROD-001': {
        'productId': 'PROD-001',
        'productName': 'Tata Salt',
        'productDescription': 'Premium iodized salt for daily cooking',
        'price': 25.00,
        'quantity': 150,
        'category': 'Grocery'
    },
    'PROD-002': {
        'productId': 'PROD-002',
        'productName': 'Amul Butter',
        'productDescription': 'Fresh and creamy butter made from pure milk',
        'price': 55.00,
        'quantity': 80,
        'category': 'Dairy'
    },
    'PROD-003': {
        'productId': 'PROD-003',
        'productName': 'Britannia Good Day Biscuits',
        'productDescription': 'Delicious butter cookies perfect for tea time',
        'price': 30.00,
        'quantity': 200,
        'category': 'Snacks'
    }
}

# ==================== FastAPI App ====================

app = FastAPI(
    title="VyapaarAI Translation Service - Simple",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ['*'] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Helper Functions ====================

def get_mock_translation(text: str, target_lang: str) -> str:
    """Get mock translation"""
    if target_lang == 'en' or target_lang not in MOCK_TRANSLATIONS:
        return text

    return MOCK_TRANSLATIONS.get(target_lang, {}).get(text, text + ' [MOCK]')

def translate_product(product: dict, target_lang: str) -> dict:
    """Translate product fields"""
    if TRANSLATION_MODE == 'disabled' or target_lang == 'en':
        return {
            **product,
            'language': 'en',
            'fromCache': False,
            'mode': TRANSLATION_MODE
        }

    if TRANSLATION_MODE == 'mock':
        return {
            'productId': product['productId'],
            'productName': get_mock_translation(product['productName'], target_lang),
            'productDescription': get_mock_translation(product['productDescription'], target_lang),
            'price': product['price'],
            'quantity': product['quantity'],
            'category': get_mock_translation(product['category'], target_lang),
            'language': target_lang,
            'fromCache': False,
            'mode': 'mock'
        }

    # For other modes, return English (not implemented yet)
    return {
        **product,
        'language': 'en',
        'fromCache': False,
        'mode': TRANSLATION_MODE,
        'note': f'{TRANSLATION_MODE} mode not fully implemented - returning English'
    }

# ==================== API Endpoints ====================

@app.get("/")
async def health_check():
    """Health check"""
    return {
        "service": "VyapaarAI Translation Service - Simple",
        "status": "healthy",
        "version": "1.0.0",
        "mode": TRANSLATION_MODE,
        "features": ["mock-mode", "cost-controlled", "simple-api"],
        "cost_estimate": "$0/month (MOCK mode)" if TRANSLATION_MODE == 'mock' else "Unknown"
    }

@app.get("/api/v1/cost-info")
async def cost_info():
    """Get cost control information"""
    return {
        "translation_mode": TRANSLATION_MODE,
        "amazon_translate_enabled": ENABLE_AMAZON_TRANSLATE,
        "estimated_monthly_cost": "$1.50" if TRANSLATION_MODE == 'mock' else "$40-60",
        "available_languages": ["en", "hi", "mr", "ta"],
        "sample_products_count": len(SAMPLE_PRODUCTS)
    }

@app.get("/api/v1/products/{product_id}")
async def get_product(
    product_id: str,
    accept_language: Optional[str] = Header(default="en", alias="Accept-Language"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")
):
    """Get product with translation"""

    # API key check (simple)
    if API_KEY != 'test-key' and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Get product
    product = SAMPLE_PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    # Parse language
    target_lang = accept_language.split('-')[0].lower()

    # Translate
    return translate_product(product, target_lang)

@app.get("/api/v1/products")
async def get_all_products(
    accept_language: Optional[str] = Header(default="en", alias="Accept-Language"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")
):
    """Get all products with translation"""

    # API key check
    if API_KEY != 'test-key' and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Parse language
    target_lang = accept_language.split('-')[0].lower()

    # Translate all products
    return {
        "products": [translate_product(p, target_lang) for p in SAMPLE_PRODUCTS.values()],
        "count": len(SAMPLE_PRODUCTS),
        "language": target_lang,
        "mode": TRANSLATION_MODE
    }

# ==================== Lambda Handler ====================

handler = Mangum(app)

def lambda_handler(event, context):
    """AWS Lambda handler"""
    return handler(event, context)
