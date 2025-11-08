#!/usr/bin/env python3
"""
Script to insert 100 global products into vyaparai-products-prod DynamoDB table
"""

import json
import boto3
from datetime import datetime
from ulid import ULID

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')
TABLE_NAME = 'vyaparai-products-prod'

def generate_product_id():
    """Generate unique product ID using ULID"""
    return f"PROD-{ULID()}"

def insert_product(product_data):
    """Insert a single product into DynamoDB"""
    product_id = generate_product_id()
    timestamp = datetime.utcnow().isoformat() + 'Z'

    item = {
        'id': {'S': product_id},
        'name': {'S': product_data['name']},
        'brand': {'S': product_data['brand']},
        'category': {'S': product_data['category']},
        'price': {'N': str(product_data['price'])},
        'unit': {'S': product_data['unit']},
        'description': {'S': product_data['description']},
        'image': {'S': product_data['image']},
        'created_at': {'S': timestamp},
        'updated_at': {'S': timestamp},
        'is_active': {'BOOL': True},
        'is_global': {'BOOL': True}  # Flag to indicate global catalog product
    }

    # Add barcode only if it exists
    if product_data.get('barcode'):
        item['barcode'] = {'S': product_data['barcode']}

    try:
        dynamodb.put_item(
            TableName=TABLE_NAME,
            Item=item
        )
        return product_id, True, None
    except Exception as e:
        return product_id, False, str(e)

def main():
    """Main function to insert all products"""
    print("=" * 80)
    print("INSERTING 100 GLOBAL PRODUCTS INTO DYNAMODB")
    print("=" * 80)
    print()

    # Load products from JSON file
    with open('global_products_catalog.json', 'r') as f:
        data = json.load(f)

    products = data['products']
    total_products = len(products)

    print(f"Total products to insert: {total_products}")
    print()

    success_count = 0
    failed_count = 0
    failed_products = []

    # Insert each product
    for idx, product in enumerate(products, 1):
        product_id, success, error = insert_product(product)

        if success:
            success_count += 1
            status = "✓ SUCCESS"
            print(f"{idx:3d}. {status} | {product_id} | {product['name'][:40]:40s} | ₹{product['price']:>6}")
        else:
            failed_count += 1
            status = "✗ FAILED"
            failed_products.append({
                'name': product['name'],
                'error': error
            })
            print(f"{idx:3d}. {status} | ERROR | {product['name'][:40]:40s} | {error}")

    # Summary
    print()
    print("=" * 80)
    print("INSERTION SUMMARY")
    print("=" * 80)
    print(f"Total Products:    {total_products}")
    print(f"Successfully Added: {success_count} ✓")
    print(f"Failed:            {failed_count} ✗")
    print()

    if failed_products:
        print("Failed Products:")
        for fp in failed_products:
            print(f"  - {fp['name']}: {fp['error']}")
        print()

    # Category breakdown
    print("Category Breakdown:")
    category_counts = {}
    for product in products:
        cat = product['category']
        category_counts[cat] = category_counts.get(cat, 0) + 1

    for category, count in sorted(category_counts.items()):
        print(f"  - {category:35s}: {count:2d} products")

    print()
    print("=" * 80)

    # Products with barcodes
    products_with_barcodes = sum(1 for p in products if p.get('barcode'))
    print(f"Products with barcodes: {products_with_barcodes}/{total_products}")
    print(f"Products without barcodes: {total_products - products_with_barcodes}/{total_products}")
    print()
    print("=" * 80)
    print("DONE!")
    print("=" * 80)

if __name__ == '__main__':
    main()
