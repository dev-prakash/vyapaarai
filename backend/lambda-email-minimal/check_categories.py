import boto3
from collections import Counter

dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

print("Scanning vyaparai-global-products-prod for category values...")

response = dynamodb.scan(
    TableName='vyaparai-global-products-prod',
    ProjectionExpression='category'
)

categories = []
for item in response.get('Items', []):
    category = item.get('category', {}).get('S', '')
    if category:
        categories.append(category)

# Continue scanning if there are more items
while 'LastEvaluatedKey' in response:
    response = dynamodb.scan(
        TableName='vyaparai-global-products-prod',
        ProjectionExpression='category',
        ExclusiveStartKey=response['LastEvaluatedKey']
    )
    for item in response.get('Items', []):
        category = item.get('category', {}).get('S', '')
        if category:
            categories.append(category)

# Count categories
category_counts = Counter(categories)

print(f"\nTotal products: {len(categories)}")
print(f"Unique categories: {len(category_counts)}")
print("\nCategory distribution:")
for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {category}: {count} products")
