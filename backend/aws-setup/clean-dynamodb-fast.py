#!/usr/bin/env python3
"""
Fast DynamoDB table cleaner using batch operations
"""

import boto3
from botocore.exceptions import ClientError

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

def clean_table(table_name, key_schema):
    """Delete all items from a DynamoDB table"""
    print(f"\nCleaning {table_name}...")
    
    try:
        # Scan all items
        response = dynamodb.scan(TableName=table_name)
        items = response.get('Items', [])
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = dynamodb.scan(
                TableName=table_name,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        
        if not items:
            print(f"  ✓ {table_name} is already empty")
            return
        
        print(f"  Found {len(items)} items to delete")
        
        # Delete items in batches
        deleted = 0
        for item in items:
            try:
                # Build the key
                key = {}
                for key_attr in key_schema:
                    if key_attr in item:
                        key[key_attr] = item[key_attr]
                
                if key:
                    dynamodb.delete_item(
                        TableName=table_name,
                        Key=key
                    )
                    deleted += 1
                    if deleted % 10 == 0:
                        print(f"    Deleted {deleted}/{len(items)} items...")
            except Exception as e:
                print(f"    Error deleting item: {e}")
        
        print(f"  ✓ Deleted {deleted} items from {table_name}")
        
    except ClientError as e:
        print(f"  ✗ Error: {e}")

# Define tables and their key schemas
tables = {
    'vyaparai-stores-prod': ['id'],
    'vyaparai-orders-prod': ['store_id', 'order_id'],
    'vyaparai-stock-prod': ['store_id', 'product_id'],
    'vyaparai-users-prod': ['id'],
    'vyaparai-customers-prod': ['id']
}

print("=" * 50)
print("DynamoDB Table Cleanup")
print("=" * 50)

# Clean each table
for table_name, key_schema in tables.items():
    clean_table(table_name, key_schema)

print("\n" + "=" * 50)
print("✓ All tables cleaned!")
print("=" * 50)

# Show final counts
print("\nFinal status:")
for table_name in tables.keys():
    try:
        response = dynamodb.scan(TableName=table_name, Select='COUNT')
        count = response['Count']
        print(f"  {table_name}: {count} items")
    except:
        print(f"  {table_name}: Error checking")