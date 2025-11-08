import boto3
import random

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

# Scan all products
response = dynamodb.scan(TableName='vyaparai-global-products-prod')
products = response['Items']

# Continue scanning if there are more items
while 'LastEvaluatedKey' in response:
    response = dynamodb.scan(
        TableName='vyaparai-global-products-prod',
        ExclusiveStartKey=response['LastEvaluatedKey']
    )
    products.extend(response['Items'])

print(f"Found {len(products)} products")

# Update each product with MRP and description
for product in products:
    product_id = product['product_id']['S']
    name = product.get('name', {}).get('S', '')
    brand = product.get('brand', {}).get('S', '')
    category = product.get('category', {}).get('S', '')
    pack_size = product.get('attributes', {}).get('M', {}).get('pack_size', {}).get('S', '')
    unit = product.get('attributes', {}).get('M', {}).get('unit', {}).get('S', '')

    # Generate realistic MRP based on category (in Rupees)
    mrp_ranges = {
        'Rice & Grains': (40, 200),
        'Pulses & Lentils': (50, 180),
        'Oil & Ghee': (100, 500),
        'Dairy Products': (20, 100),
        'Snacks': (10, 50),
        'Beverages': (15, 80),
        'Juices': (20, 120),
        'Spices': (15, 100),
        'Spices & Condiments': (15, 100),
        'Personal Care': (30, 300),
        'Household Items': (50, 400)
    }

    mrp_range = mrp_ranges.get(category, (20, 150))
    mrp = random.randint(mrp_range[0], mrp_range[1])

    # Generate description
    description = f"{name}"
    if brand:
        description += f" by {brand}"
    if pack_size and unit:
        description += f" - {pack_size}{unit} pack"
    if category:
        description += f". Category: {category}"

    # Update the product
    try:
        dynamodb.update_item(
            TableName='vyaparai-global-products-prod',
            Key={'product_id': {'S': product_id}},
            UpdateExpression='SET mrp = :mrp, description = :desc, updated_at = :updated',
            ExpressionAttributeValues={
                ':mrp': {'N': str(mrp)},
                ':desc': {'S': description},
                ':updated': {'S': '2025-10-29T00:40:00.000000Z'}
            }
        )
        print(f"Updated {product_id}: {name} - MRP: ₹{mrp}")
    except Exception as e:
        print(f"Error updating {product_id}: {e}")

print("Done!")
