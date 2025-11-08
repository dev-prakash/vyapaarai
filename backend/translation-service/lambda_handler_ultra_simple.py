"""
Ultra Simple Translation Service - No Pydantic
MOCK mode for testing - Cost: $1.50/month
"""

import json

# Mock translations database
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
    }
}

# Sample products
PRODUCTS = {
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

def get_mock_translation(text, target_lang):
    """Get mock translation"""
    if target_lang == 'en' or target_lang not in MOCK_TRANSLATIONS:
        return text
    return MOCK_TRANSLATIONS.get(target_lang, {}).get(text, text + ' [MOCK]')

def translate_product(product, target_lang):
    """Translate product to target language"""
    if target_lang == 'en':
        return {
            **product,
            'language': 'en',
            'fromCache': False,
            'mode': 'mock'
        }

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

def lambda_handler(event, context):
    """Main Lambda handler"""

    # Parse request
    path = event.get('rawPath', event.get('path', ''))
    method = event.get('requestContext', {}).get('http', {}).get('method', event.get('httpMethod', 'GET'))
    headers = event.get('headers', {})

    # Get language from header
    accept_language = headers.get('accept-language', headers.get('Accept-Language', 'en'))
    target_lang = accept_language.split('-')[0].lower()

    # Handle routes
    if path == '/':
        # Health check
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': '*'
            },
            'body': json.dumps({
                'service': 'VyapaarAI Translation Service - MOCK Mode',
                'status': 'healthy',
                'version': '1.0.0',
                'mode': 'mock',
                'cost_estimate': '$1.50/month',
                'features': ['mock-translations', 'cost-controlled', 'simple-api']
            })
        }

    elif path == '/api/v1/cost-info':
        # Cost info endpoint
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'translation_mode': 'mock',
                'amazon_translate_enabled': False,
                'estimated_monthly_cost': '$1.50',
                'estimated_daily_cost': '$0.05',
                'available_languages': ['en', 'hi', 'mr'],
                'sample_products_count': len(PRODUCTS)
            })
        }

    elif path.startswith('/api/v1/products/'):
        # Single product
        product_id = path.split('/')[-1]
        product = PRODUCTS.get(product_id)

        if not product:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Product {product_id} not found'})
            }

        translated = translate_product(product, target_lang)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(translated)
        }

    elif path == '/api/v1/products':
        # All products
        products = [translate_product(p, target_lang) for p in PRODUCTS.values()]

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'products': products,
                'count': len(products),
                'language': target_lang,
                'mode': 'mock'
            })
        }

    else:
        # Not found
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Not found', 'path': path})
        }
