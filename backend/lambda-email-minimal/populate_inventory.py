import boto3
import random
from datetime import datetime, timezone
from ulid import ULID

dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

# Store information
stores = [
    {
        'store_id': 'store_01JFJAZ7E2M8H3QX5VWN9KR1CP',
        'store_name': 'Green Valley Grocery',
        'store_type': 'Grocery & Vegetables',
        'categories': ['Instant Foods', 'Spices', 'Dairy', 'Beverages', 'Pulses', 'Condiments', 
                      'Atta/Flour', 'Staples', 'Rice', 'Tea', 'Sauce', 'Oils & Ghee', 
                      'Cooking Oil', 'Ghee', 'Spice Blend']
    },
    {
        'store_id': 'store_01JFJB0D7YMQP8X9K2N4T6VZWH',
        'store_name': 'Tech Hub Electronics',
        'store_type': 'General Store',
        'categories': ['Biscuits', 'Snacks', 'Beverages', 'Tea', 'Coffee', 'Instant Foods',
                      'Namkeen', 'Noodles', 'Ready-to-Eat', 'Instant Meals', 'Breakfast',
                      'Juices', 'Dairy', 'Condiments', 'Household', 'Personal Care']
    }
]

def get_global_products_by_categories(categories):
    """Get products from global catalog filtered by categories"""
    products = []
    
    response = dynamodb.scan(
        TableName='vyaparai-global-products-prod'
    )
    
    for item in response.get('Items', []):
        category = item.get('category', {}).get('S', '')
        if category in categories:
            products.append(item)
    
    # Continue scanning if there are more items
    while 'LastEvaluatedKey' in response:
        response = dynamodb.scan(
            TableName='vyaparai-global-products-prod',
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        for item in response.get('Items', []):
            category = item.get('category', {}).get('S', '')
            if category in categories:
                products.append(item)
    
    return products

def add_inventory_item(store_id, product, store_name):
    """Add a product to store inventory"""
    
    product_id = product.get('product_id', {}).get('S', '')
    product_name = product.get('name', {}).get('S', '')
    
    # Generate realistic inventory values
    current_stock = random.randint(10, 200)
    min_stock = random.randint(5, 15)
    max_stock = current_stock + random.randint(50, 150)
    reorder_point = random.randint(min_stock + 5, min_stock + 20)
    
    # Price calculations (cost price between 10-500, selling price with 15-35% markup)
    cost_price = round(random.uniform(10, 500), 2)
    markup = random.uniform(0.15, 0.35)
    selling_price = round(cost_price * (1 + markup), 2)
    
    # Random discount (0-10%)
    discount = random.choice([0, 0, 0, 5, 10])  # More likely to have no discount
    
    # Random location
    location = random.choice(['Aisle 1', 'Aisle 2', 'Aisle 3', 'Storage', 'Counter'])
    
    now = datetime.now(timezone.utc).isoformat()
    inventory_id = str(ULID())
    
    item = {
        'store_id': {'S': store_id},
        'inventory_id': {'S': inventory_id},
        'product_id': {'S': product_id},
        'product_name': {'S': product_name},
        'current_stock': {'N': str(current_stock)},
        'min_stock_level': {'N': str(min_stock)},
        'max_stock_level': {'N': str(max_stock)},
        'reorder_point': {'N': str(reorder_point)},
        'cost_price': {'N': str(cost_price)},
        'selling_price': {'N': str(selling_price)},
        'discount_percentage': {'N': str(discount)},
        'location': {'S': location},
        'is_active': {'BOOL': True},
        'created_at': {'S': now},
        'updated_at': {'S': now}
    }
    
    try:
        dynamodb.put_item(
            TableName='vyaparai-store-inventory-prod',
            Item=item
        )
        return True
    except Exception as e:
        print(f"Error adding {product_name}: {str(e)}")
        return False

# Process each store
for store in stores:
    print(f"\nProcessing {store['store_name']}...")
    print(f"Store Type: {store['store_type']}")
    print(f"Target Categories: {', '.join(store['categories'])}")
    
    # Get products for this store's categories
    products = get_global_products_by_categories(store['categories'])
    print(f"Found {len(products)} matching products")
    
    if not products:
        print(f"⚠ No products found for {store['store_name']}")
        continue
    
    # Randomly select 25-35 products
    num_products = min(random.randint(25, 35), len(products))
    selected_products = random.sample(products, num_products)
    
    print(f"Adding {num_products} products to inventory...")
    
    success_count = 0
    for product in selected_products:
        if add_inventory_item(store['store_id'], product, store['store_name']):
            success_count += 1
    
    print(f"✓ Added {success_count} products to {store['store_name']}")

print("\n✅ Inventory population complete!")
