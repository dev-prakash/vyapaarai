#!/usr/bin/env python3
"""
Script to populate inventory for all 3 stores with products from global catalog
"""

import json
import boto3
from datetime import datetime
from ulid import ULID
import random

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

TABLE_NAMES = {
    'stores': 'vyaparai-stores-prod',
    'products': 'vyaparai-products-prod',
    'inventory': 'vyaparai-store-inventory-prod'
}

# Store IDs (update these with actual IDs)
STORES = {
    'STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV': {  # Morning Star Bakery
        'name': 'Morning Star Bakery and General Store',
        'type': 'Bakery & General Store',
        'categories': ['Biscuits & Cookies', 'Snacks & Namkeen', 'Tea, Coffee & Beverages',
                      'Sugar, Salt & Sweeteners', 'Ready-to-Eat & Instant Foods']
    },
    'STORE-01K8K2V0HJYSKDNSRXR1CY9GY4': {  # Green Valley Grocery
        'name': 'Green Valley Grocery',
        'type': 'Grocery & Vegetables',
        'categories': ['Rice & Grains', 'Pulses & Dals', 'Cooking Oils & Ghee',
                      'Spices & Masalas', 'Condiments & Sauces', 'Dairy Products']
    },
    'STORE-01K8K2V1T0XTA7FHAY3ST82KZ2': {  # Tech Hub Electronics
        'name': 'Tech Hub Electronics',
        'type': 'Electronics & Gadgets',
        'categories': []  # No food products - skip for now
    }
}

def generate_id(prefix):
    """Generate unique ID with prefix"""
    return f"{prefix}-{ULID()}"

def get_products_by_categories(categories):
    """Get products from global catalog by categories"""
    products = []

    for category in categories:
        response = dynamodb.scan(
            TableName=TABLE_NAMES['products'],
            FilterExpression='category = :cat',
            ExpressionAttributeValues={':cat': {'S': category}}
        )
        products.extend(response.get('Items', []))

    return products

def create_inventory_item(store_id, product):
    """Create inventory item for a store"""
    timestamp = datetime.now().isoformat() + 'Z'
    stock_qty = random.randint(15, 150)
    cost_price = float(product['price']['N'])
    selling_price = cost_price * 1.25  # 25% markup

    item = {
        'store_id': {'S': store_id},
        'product_id': {'S': product['id']['S']},
        'global_product_id': {'S': product['id']['S']},
        'sku': {'S': product.get('barcode', {}).get('S', product['id']['S'])},
        'brand': {'S': product['brand']['S']},
        'notes': {'S': product['name']['S']},
        'description': {'S': product['description']['S']},
        'current_stock': {'N': str(stock_qty)},
        'min_stock_level': {'N': '10'},
        'max_stock_level': {'N': '200'},
        'reorder_point': {'N': '20'},
        'cost_price': {'N': product['price']['N']},
        'selling_price': {'N': str(int(selling_price))},
        'discount_percentage': {'N': '0'},
        'location': {'S': ''},
        'image': {'S': product['image']['S']},
        'is_active': {'BOOL': True},
        'created_at': {'S': timestamp},
        'updated_at': {'S': timestamp}
    }

    if 'barcode' in product:
        item['barcode'] = product['barcode']

    dynamodb.put_item(TableName=TABLE_NAMES['inventory'], Item=item)
    return product['id']['S']

def main():
    print("=" * 80)
    print("POPULATING STORE INVENTORY")
    print("=" * 80)
    print()

    for store_id, store_info in STORES.items():
        if not store_info['categories']:
            print(f"Skipping {store_info['name']} - no food categories")
            print()
            continue

        print(f"Processing {store_info['name']}...")
        print(f"  Store ID: {store_id}")
        print(f"  Type: {store_info['type']}")
        print(f"  Categories: {', '.join(store_info['categories'])}")
        print()

        # Get products for this store's categories
        products = get_products_by_categories(store_info['categories'])

        if not products:
            print(f"  ⚠ No products found for categories: {store_info['categories']}")
            print()
            continue

        print(f"  Found {len(products)} products")
        print(f"  Adding inventory items...")
        print()

        success_count = 0
        for idx, product in enumerate(products, 1):
            try:
                inventory_id = create_inventory_item(store_id, product)
                success_count += 1
                print(f"  {idx:3d}. ✓ {product['name']['S'][:50]:50s} | Stock: {random.randint(15, 150)} | ₹{product['price']['N']}")
            except Exception as e:
                print(f"  {idx:3d}. ✗ {product['name']['S'][:50]:50s} | ERROR: {str(e)}")

        print()
        print(f"  Summary: Added {success_count}/{len(products)} items to {store_info['name']}")
        print()
        print("-" * 80)
        print()

    print("=" * 80)
    print("INVENTORY POPULATION COMPLETED!")
    print("=" * 80)

if __name__ == '__main__':
    main()
