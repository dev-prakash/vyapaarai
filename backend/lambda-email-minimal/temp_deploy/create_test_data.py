#!/usr/bin/env python3
"""
Script to create comprehensive test data for VyapaarAI:
- 2 new stores
- 2 new store owners
- 2 new customers
- Sample inventory for all 3 stores
- Initial reviews
"""

import json
import boto3
from datetime import datetime
from ulid import ULID
import hashlib
import random

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

TABLE_NAMES = {
    'stores': 'vyaparai-stores-prod',
    'users': 'vyaparai-users-prod',
    'customers': 'vyaparai-customers-prod',
    'inventory': 'vyaparai-inventory-prod',
    'reviews': 'vyaparai-reviews-prod',
    'products': 'vyaparai-products-prod'
}

def generate_id(prefix):
    """Generate unique ID with prefix"""
    return f"{prefix}-{ULID()}"

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_store(store_data):
    """Create a new store"""
    store_id = generate_id('STORE')
    timestamp = datetime.now().isoformat()

    # Create address JSON
    address_json = json.dumps({
        'street': store_data['address']['street'],
        'city': store_data['address']['city'],
        'state': store_data['address']['state'],
        'pincode': store_data['address']['pincode']
    })

    # Create settings JSON
    settings_json = json.dumps({
        'store_type': store_data['store_type'],
        'description': store_data['description'],
        'tagline': store_data['tagline'],
        'delivery_radius': 5,
        'min_order_amount': 100,
        'business_hours': {
            'open': store_data['business_hours']['open'],
            'close': store_data['business_hours']['close']
        },
        'social_media': {
            'whatsapp': store_data['social_media']['whatsapp'],
            'facebook': store_data['social_media'].get('facebook', ''),
            'instagram': store_data['social_media'].get('instagram', '')
        }
    })

    item = {
        'id': {'S': store_id},
        'store_id': {'S': store_id},
        'name': {'S': store_data['name']},
        'address': {'S': address_json},
        'phone': {'S': store_data['phone']},
        'email': {'S': store_data['email']},
        'settings': {'S': settings_json},
        'status': {'S': 'active'},
        'owner_name': {'S': store_data.get('owner_name', '')},
        'latitude': {'N': store_data.get('latitude', '0')},
        'longitude': {'N': store_data.get('longitude', '0')},
        'created_at': {'S': timestamp},
        'updated_at': {'S': timestamp}
    }

    dynamodb.put_item(TableName=TABLE_NAMES['stores'], Item=item)
    return store_id

def create_store_owner(owner_data, store_id):
    """Create a new store owner"""
    user_id = f"user_{owner_data['email']}"
    timestamp = datetime.now().isoformat()

    item = {
        'id': {'S': user_id},
        'email': {'S': owner_data['email']},
        'password_hash': {'S': hash_password(owner_data['password'])},
        'password_algorithm': {'S': 'sha256'},
        'name': {'S': owner_data['name']},
        'phone': {'S': owner_data['phone']},
        'role': {'S': 'store_owner'},
        'store_id': {'S': store_id},
        'status': {'S': 'active'},
        'created_by': {'S': 'system'},
        'created_at': {'S': timestamp},
        'updated_at': {'S': timestamp}
    }

    dynamodb.put_item(TableName=TABLE_NAMES['users'], Item=item)
    return user_id

def create_customer(customer_data):
    """Create a new customer"""
    customer_id = f"customer_{customer_data['email']}"
    timestamp = datetime.now().isoformat()

    # Create address JSON
    address_json = json.dumps({
        'street': customer_data['address']['street'],
        'city': customer_data['address']['city'],
        'state': customer_data['address']['state'],
        'pincode': customer_data['address']['pincode']
    })

    item = {
        'id': {'S': customer_id},
        'email': {'S': customer_data['email']},
        'password_hash': {'S': hash_password(customer_data['password'])},
        'password_algorithm': {'S': 'sha256'},
        'name': {'S': customer_data['name']},
        'phone': {'S': customer_data['phone']},
        'address': {'S': address_json},
        'role': {'S': 'customer'},
        'status': {'S': 'active'},
        'created_by': {'S': 'system'},
        'created_at': {'S': timestamp},
        'updated_at': {'S': timestamp}
    }

    dynamodb.put_item(TableName=TABLE_NAMES['customers'], Item=item)
    return customer_id

def get_random_products(category=None, count=10):
    """Get random products from global catalog"""
    if category:
        response = dynamodb.scan(
            TableName=TABLE_NAMES['products'],
            FilterExpression='category = :cat',
            ExpressionAttributeValues={':cat': {'S': category}},
            Limit=count
        )
    else:
        response = dynamodb.scan(
            TableName=TABLE_NAMES['products'],
            Limit=count
        )

    return response.get('Items', [])

def create_inventory_item(store_id, product):
    """Create inventory item for a store"""
    inventory_id = generate_id('INV')
    timestamp = datetime.now().isoformat() + 'Z'

    item = {
        'inventory_id': {'S': inventory_id},
        'store_id': {'S': store_id},
        'product_id': {'S': product['id']['S']},
        'product_name': {'S': product['name']['S']},
        'category': {'S': product['category']['S']},
        'price': {'N': product['price']['N']},
        'unit': {'S': product['unit']['S']},
        'stock_quantity': {'N': str(random.randint(10, 100))},
        'in_stock': {'BOOL': True},
        'created_at': {'S': timestamp},
        'updated_at': {'S': timestamp}
    }

    if 'barcode' in product:
        item['barcode'] = product['barcode']

    if 'image' in product:
        item['image'] = product['image']

    if 'description' in product:
        item['description'] = product['description']

    dynamodb.put_item(TableName=TABLE_NAMES['inventory'], Item=item)
    return inventory_id

def main():
    print("=" * 80)
    print("CREATING TEST DATA FOR VYAPARAI")
    print("=" * 80)
    print()

    # Store 2: Green Valley Grocery
    print("Creating Store 2: Green Valley Grocery...")
    store2_data = {
        'name': 'Green Valley Grocery',
        'store_type': 'Grocery & Vegetables',
        'address': {
            'street': 'Shop 15, Sector 12 Market',
            'city': 'Noida',
            'state': 'Uttar Pradesh',
            'pincode': '201301'
        },
        'phone': '+919876543210',
        'email': 'contact@greenvalleygrocery.com',
        'description': 'Fresh vegetables, fruits, and daily groceries delivered to your doorstep. We source directly from local farms to ensure the freshest produce for our customers.',
        'tagline': 'Farm Fresh, Daily Fresh',
        'business_hours': {'open': '07:00', 'close': '22:00'},
        'social_media': {
            'whatsapp': '+919876543210',
            'facebook': 'https://facebook.com/greenvalleygrocery',
            'instagram': 'https://instagram.com/greenvalleygrocery'
        },
        'latitude': '28.5955',
        'longitude': '77.3910'
    }
    store2_id = create_store(store2_data)
    print(f"  ✓ Store created: {store2_id}")

    # Owner 2
    print("Creating Owner 2: Priya Sharma...")
    owner2_data = {
        'email': 'priya.sharma@greenvalley.com',
        'password': 'GreenValley@2024',
        'name': 'Priya Sharma',
        'phone': '+919876543210'
    }
    owner2_id = create_store_owner(owner2_data, store2_id)
    print(f"  ✓ Owner created: {owner2_id}")

    # Store 3: Tech Hub Electronics
    print("\nCreating Store 3: Tech Hub Electronics...")
    store3_data = {
        'name': 'Tech Hub Electronics',
        'store_type': 'Electronics & Gadgets',
        'address': {
            'street': 'B-42, Gomti Nagar Extension',
            'city': 'Lucknow',
            'state': 'Uttar Pradesh',
            'pincode': '226010'
        },
        'phone': '+919988776655',
        'email': 'support@techhubelectronics.com',
        'description': 'Your one-stop destination for all electronics and gadgets. From smartphones to home appliances, we offer the latest technology at competitive prices with warranty and after-sales support.',
        'tagline': 'Smart Tech, Smart Prices',
        'business_hours': {'open': '10:00', 'close': '20:00'},
        'social_media': {
            'whatsapp': '+919988776655',
            'facebook': '',
            'instagram': ''
        },
        'latitude': '26.8724',
        'longitude': '81.0086'
    }
    store3_id = create_store(store3_data)
    print(f"  ✓ Store created: {store3_id}")

    # Owner 3
    print("Creating Owner 3: Amit Verma...")
    owner3_data = {
        'email': 'amit.verma@techhub.com',
        'password': 'TechHub@2024',
        'name': 'Amit Verma',
        'phone': '+919988776655'
    }
    owner3_id = create_store_owner(owner3_data, store3_id)
    print(f"  ✓ Owner created: {owner3_id}")

    # Customer 1
    print("\nCreating Customer 1: Anjali Gupta...")
    customer1_data = {
        'email': 'anjali.gupta@gmail.com',
        'password': 'Anjali@2024',
        'name': 'Anjali Gupta',
        'phone': '+919123456789',
        'address': {
            'street': 'Flat 301, Green Apartments',
            'city': 'Lucknow',
            'state': 'Uttar Pradesh',
            'pincode': '226001'
        }
    }
    customer1_id = create_customer(customer1_data)
    print(f"  ✓ Customer created: {customer1_id}")

    # Customer 2
    print("Creating Customer 2: Rahul Singh...")
    customer2_data = {
        'email': 'rahul.singh@gmail.com',
        'password': 'Rahul@2024',
        'name': 'Rahul Singh',
        'phone': '+919234567890',
        'address': {
            'street': 'House 45, Sector 15',
            'city': 'Noida',
            'state': 'Uttar Pradesh',
            'pincode': '201301'
        }
    }
    customer2_id = create_customer(customer2_data)
    print(f"  ✓ Customer created: {customer2_id}")

    print("\n" + "=" * 80)
    print("TEST DATA CREATION COMPLETED!")
    print("=" * 80)
    print(f"\nStore 2 ID: {store2_id}")
    print(f"Store 3 ID: {store3_id}")
    print(f"Customer 1 ID: {customer1_id}")
    print(f"Customer 2 ID: {customer2_id}")
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
