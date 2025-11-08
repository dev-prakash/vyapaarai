#!/usr/bin/env python3
"""
Populate inventory for 3 stores with realistic, meaningful product data
"""
import boto3
import random
from datetime import datetime
from decimal import Decimal

# Initialize DynamoDB
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

# Store configurations
STORES = {
    "STORE-01K8NJ40V9KFKX2Y2FMK466WFH": {
        "name": "Green Valley Grocery",
        "type": "grocery",
        "aisles": ["Aisle 1", "Aisle 2", "Aisle 3", "Aisle 4", "Cold Storage", "Dry Storage"]
    },
    "STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV": {
        "name": "Morning Star Bakery and General Store",
        "type": "bakery_general",
        "aisles": ["Shelf A", "Shelf B", "Shelf C", "Counter", "Display", "Back Room"]
    },
    "STORE-01K8NJ40V9KFKX2Y2FMK466WFJ": {
        "name": "Tech Hub Electronics",
        "type": "electronics",
        "aisles": ["Section 1", "Section 2", "Warehouse", "Display Counter", "Storage"]
    }
}

def get_global_products():
    """Fetch all products from global catalog"""
    response = dynamodb.scan(TableName='vyaparai-global-products-prod')
    products = []
    for item in response.get('Items', []):
        products.append({
            'product_id': item['product_id']['S'],
            'name': item.get('name', {}).get('S', ''),
            'category': item.get('category', {}).get('S', ''),
            'brand': item.get('brand', {}).get('S', ''),
            'mrp': float(item.get('mrp', {}).get('N', '0')),
            'barcode': item.get('barcode', {}).get('S', ''),
        })
    return products

def select_products_for_store(all_products, store_type):
    """Select appropriate products based on store type"""

    # Define category preferences for each store type
    category_preferences = {
        "grocery": {
            # High priority categories for grocery
            "high": ["Rice", "Pulses", "Atta/Flour", "Cooking Oil", "Oils & Ghee", "Spices",
                    "Spice Blend", "Spices & Condiments", "Dairy", "Dairy Products", "Staples",
                    "Condiments", "Pickles", "Pickle", "Tea", "Coffee", "Beverages"],
            # Medium priority
            "medium": ["Biscuits", "Snacks", "Instant Foods", "Noodles", "Breakfast", "Cereals",
                      "Namkeen", "Sauce", "Ketchup", "Ready-to-Eat", "Frozen", "Vegetables"],
            # Low priority (few items)
            "low": ["Personal Care", "Household", "Cleaners", "Soaps", "Toothpaste"]
        },
        "bakery_general": {
            "high": ["Breads", "Baking", "Atta/Flour", "Dairy", "Dairy Products", "Biscuits",
                    "Snacks", "Breakfast", "Cereals", "Tea", "Coffee", "Beverages", "Sweets", "Mithai"],
            "medium": ["Instant Foods", "Ready-to-Eat", "Condiments", "Sauce", "Namkeen",
                      "Chips", "Cooking Oil", "Spices"],
            "low": ["Rice", "Pulses", "Personal Care", "Household"]
        },
        "electronics": {
            # For electronics, we'll skip as there are no electronics in catalog
            # Instead treat as general store
            "high": ["Instant Foods", "Snacks", "Beverages", "Biscuits", "Breakfast"],
            "medium": ["Personal Care", "Household", "Dairy", "Tea", "Coffee"],
            "low": ["Staples", "Spices", "Condiments"]
        }
    }

    prefs = category_preferences.get(store_type, category_preferences["grocery"])
    selected = []

    # Select products based on priority
    for product in all_products:
        category = product['category']

        if category in prefs["high"]:
            # 80% chance to include
            if random.random() < 0.8:
                selected.append(product)
        elif category in prefs["medium"]:
            # 50% chance to include
            if random.random() < 0.5:
                selected.append(product)
        elif category in prefs["low"]:
            # 20% chance to include
            if random.random() < 0.2:
                selected.append(product)

    return selected

def generate_inventory_item(store_id, product, store_config):
    """Generate realistic inventory item for a product"""

    # Calculate pricing
    mrp = product['mrp']

    # Cost price: 60-80% of MRP
    cost_price = round(mrp * random.uniform(0.60, 0.80), 2)

    # Selling price: 85-95% of MRP (5-15% discount from MRP)
    selling_price = round(mrp * random.uniform(0.85, 0.95), 2)

    # Discount percentage
    discount_pct = round((1 - selling_price / mrp) * 100, 1) if mrp > 0 else 0

    # Stock levels based on category
    category = product['category']
    if category in ['Dairy', 'Dairy Products', 'Frozen', 'Vegetables', 'Breads']:
        # Perishables - lower stock
        current_stock = random.randint(10, 50)
        min_stock = random.randint(5, 15)
        max_stock = random.randint(50, 100)
    elif category in ['Rice', 'Pulses', 'Atta/Flour', 'Cooking Oil', 'Staples']:
        # Staples - higher stock
        current_stock = random.randint(50, 200)
        min_stock = random.randint(20, 40)
        max_stock = random.randint(150, 300)
    else:
        # Regular items
        current_stock = random.randint(20, 100)
        min_stock = random.randint(10, 25)
        max_stock = random.randint(80, 150)

    # Reorder point (slightly above min stock)
    reorder_point = min_stock + random.randint(5, 10)

    # Random location from store's aisles
    location = random.choice(store_config['aisles']) + f" Shelf {random.choice(['A', 'B', 'C', 'D', 'E', 'F'])}"

    # Generate inventory ID
    inventory_id = f"INV-{int(datetime.utcnow().timestamp())}-{random.randint(1000, 9999):04x}"

    return {
        'store_id': {'S': store_id},
        'product_id': {'S': product['product_id']},
        'inventory_id': {'S': inventory_id},
        'product_name': {'S': product['name']},
        'current_stock': {'N': str(current_stock)},
        'min_stock_level': {'N': str(min_stock)},
        'max_stock_level': {'N': str(max_stock)},
        'reorder_point': {'N': str(reorder_point)},
        'cost_price': {'N': str(cost_price)},
        'selling_price': {'N': str(selling_price)},
        'mrp': {'N': str(mrp)},
        'discount_percentage': {'N': str(discount_pct)},
        'location': {'S': location},
        'is_active': {'BOOL': True},
        'created_at': {'S': datetime.utcnow().isoformat()},
        'updated_at': {'S': datetime.utcnow().isoformat()}
    }

def populate_store_inventory(store_id, store_config, all_products):
    """Populate inventory for a single store"""
    print(f"\n{'='*60}")
    print(f"Populating inventory for: {store_config['name']}")
    print(f"Store ID: {store_id}")
    print(f"Store Type: {store_config['type']}")
    print(f"{'='*60}\n")

    # Select products appropriate for this store
    selected_products = select_products_for_store(all_products, store_config['type'])

    print(f"Selected {len(selected_products)} products for this store")

    # Check existing inventory
    existing = dynamodb.query(
        TableName='vyaparai-store-inventory-prod',
        KeyConditionExpression='store_id = :sid',
        ExpressionAttributeValues={':sid': {'S': store_id}}
    )
    existing_product_ids = {item['product_id']['S'] for item in existing.get('Items', [])}

    print(f"Found {len(existing_product_ids)} existing products in inventory")

    # Add products
    added_count = 0
    skipped_count = 0

    for product in selected_products:
        if product['product_id'] in existing_product_ids:
            skipped_count += 1
            continue

        inventory_item = generate_inventory_item(store_id, product, store_config)

        try:
            dynamodb.put_item(
                TableName='vyaparai-store-inventory-prod',
                Item=inventory_item
            )
            added_count += 1

            if added_count % 10 == 0:
                print(f"  Added {added_count} products...")

        except Exception as e:
            print(f"  Error adding {product['name']}: {e}")

    print(f"\n✓ Added {added_count} new products")
    print(f"  Skipped {skipped_count} existing products")
    print(f"  Total inventory: {added_count + len(existing_product_ids)} products")

def main():
    """Main function to populate all stores"""
    print("\n" + "="*60)
    print("STORE INVENTORY POPULATION SCRIPT")
    print("="*60)

    # Fetch all products from global catalog
    print("\nFetching products from global catalog...")
    all_products = get_global_products()
    print(f"✓ Found {len(all_products)} products in global catalog")

    # Populate each store
    for store_id, store_config in STORES.items():
        populate_store_inventory(store_id, store_config, all_products)

    print("\n" + "="*60)
    print("✓ ALL STORES POPULATED SUCCESSFULLY!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
