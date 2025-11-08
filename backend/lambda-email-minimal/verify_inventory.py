import boto3

dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

stores = [
    ('store_01JFJAZ7E2M8H3QX5VWN9KR1CP', 'Green Valley Grocery'),
    ('store_01JFJB0D7YMQP8X9K2N4T6VZWH', 'Tech Hub Electronics')
]

for store_id, store_name in stores:
    print(f"\n{'='*60}")
    print(f"{store_name}")
    print('='*60)
    
    response = dynamodb.query(
        TableName='vyaparai-store-inventory-prod',
        KeyConditionExpression='store_id = :store_id',
        ExpressionAttributeValues={
            ':store_id': {'S': store_id}
        }
    )
    
    items = response.get('Items', [])
    print(f"Total products: {len(items)}")
    
    if items:
        # Show first 3 products as sample
        print("\nSample products:")
        for i, item in enumerate(items[:3], 1):
            product_name = item.get('product_name', {}).get('S', 'N/A')
            current_stock = item.get('current_stock', {}).get('N', '0')
            cost_price = item.get('cost_price', {}).get('N', '0')
            selling_price = item.get('selling_price', {}).get('N', '0')
            location = item.get('location', {}).get('S', 'N/A')
            discount = item.get('discount_percentage', {}).get('N', '0')
            
            print(f"\n{i}. {product_name}")
            print(f"   Stock: {current_stock} | Location: {location}")
            print(f"   Cost: ₹{cost_price} | Selling: ₹{selling_price} | Discount: {discount}%")

print("\n" + "="*60)
print("✅ Verification complete!")
