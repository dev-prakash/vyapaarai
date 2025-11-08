#!/usr/bin/env python3
"""
Reset DynamoDB Tables for VyaparAI
Cleans all store-specific data from DynamoDB tables
"""

import boto3
import sys
from botocore.exceptions import ClientError

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')

def clear_table(table_name):
    """Clear all items from a DynamoDB table"""
    try:
        table = dynamodb.Table(table_name)
        
        # Scan and delete all items
        scan = table.scan()
        items = scan['Items']
        
        if not items:
            print(f"✓ Table {table_name} is already empty")
            return
        
        print(f"Deleting {len(items)} items from {table_name}...")
        
        with table.batch_writer() as batch:
            for item in items:
                # Adjust the key based on your table's partition key
                if 'id' in item:
                    batch.delete_item(Key={'id': item['id']})
                elif 'order_id' in item:
                    batch.delete_item(Key={'order_id': item['order_id']})
                elif 'product_id' in item:
                    batch.delete_item(Key={'product_id': item['product_id']})
                elif 'store_id' in item:
                    batch.delete_item(Key={'store_id': item['store_id']})
        
        # Handle pagination if there are more items
        while 'LastEvaluatedKey' in scan:
            scan = table.scan(ExclusiveStartKey=scan['LastEvaluatedKey'])
            items = scan['Items']
            
            with table.batch_writer() as batch:
                for item in items:
                    if 'id' in item:
                        batch.delete_item(Key={'id': item['id']})
                    elif 'order_id' in item:
                        batch.delete_item(Key={'order_id': item['order_id']})
                    elif 'product_id' in item:
                        batch.delete_item(Key={'product_id': item['product_id']})
                    elif 'store_id' in item:
                        batch.delete_item(Key={'store_id': item['store_id']})
        
        print(f"✓ Successfully cleared table {table_name}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"⚠ Table {table_name} does not exist")
        else:
            print(f"✗ Error clearing table {table_name}: {e}")
    except Exception as e:
        print(f"✗ Unexpected error with table {table_name}: {e}")

def main():
    """Main function to clear all relevant DynamoDB tables"""
    
    print("=" * 60)
    print("VyaparAI DynamoDB Data Reset")
    print("This will DELETE all store, order, and user data!")
    print("=" * 60)
    
    # Confirm before proceeding
    confirm = input("\nAre you sure you want to proceed? Type 'YES' to confirm: ")
    if confirm != 'YES':
        print("Operation cancelled.")
        sys.exit(0)
    
    print("\nStarting data cleanup...\n")
    
    # List of tables to clear
    tables_to_clear = [
        'vyaparai-orders-prod',
        'vyaparai-stores-prod',
        'vyaparai-stock-prod',
        'vyaparai-users-prod',
        'vyaparai-customers-prod',
        # Add any other DynamoDB tables here
    ]
    
    for table_name in tables_to_clear:
        clear_table(table_name)
    
    print("\n" + "=" * 60)
    print("✓ DynamoDB cleanup complete!")
    print("All store-specific data has been removed.")
    print("You can now start fresh with store registration.")
    print("=" * 60)

if __name__ == "__main__":
    main()