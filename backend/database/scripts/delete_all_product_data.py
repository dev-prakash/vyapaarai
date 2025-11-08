"""
Delete all product-related data from DynamoDB tables
This script will remove all items from:
- vyaparai-products-prod (4 items)
- vyaparai-global-products-prod (16 items)
- vyaparai-store-inventory-prod (0 items)
"""

import boto3
import logging
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_all_items_from_table(table_name, key_schema):
    """
    Delete all items from a DynamoDB table

    Args:
        table_name: Name of the table
        key_schema: List of key attributes (e.g., ['id'] or ['store_id', 'product_id'])
    """
    try:
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        table = dynamodb.Table(table_name)

        # Scan to get all items
        response = table.scan()
        items = response['Items']

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])

        if not items:
            logger.info(f"✅ {table_name}: Already empty (0 items)")
            return 0

        # Delete each item
        deleted_count = 0
        for item in items:
            # Build the key for deletion
            key = {attr: item[attr] for attr in key_schema}

            try:
                table.delete_item(Key=key)
                deleted_count += 1

                if deleted_count % 10 == 0:
                    logger.info(f"   Deleted {deleted_count}/{len(items)} items from {table_name}...")

            except ClientError as e:
                logger.error(f"❌ Error deleting item from {table_name}: {e}")

        logger.info(f"✅ {table_name}: Deleted {deleted_count} items")
        return deleted_count

    except Exception as e:
        logger.error(f"❌ Error processing {table_name}: {e}")
        return 0

def main():
    """Delete all product-related data from DynamoDB tables"""

    logger.info("🗑️  Starting deletion of all product-related data...")
    logger.info("=" * 60)

    total_deleted = 0

    # 1. Delete from vyaparai-products-prod
    logger.info("\\n📦 Processing vyaparai-products-prod...")
    count = delete_all_items_from_table('vyaparai-products-prod', ['id'])
    total_deleted += count

    # 2. Delete from vyaparai-global-products-prod
    logger.info("\\n🌍 Processing vyaparai-global-products-prod...")
    count = delete_all_items_from_table('vyaparai-global-products-prod', ['product_id'])
    total_deleted += count

    # 3. Delete from vyaparai-store-inventory-prod
    logger.info("\\n🏪 Processing vyaparai-store-inventory-prod...")
    count = delete_all_items_from_table('vyaparai-store-inventory-prod', ['store_id', 'product_id'])
    total_deleted += count

    logger.info("\\n" + "=" * 60)
    logger.info(f"🎉 Deletion complete! Total items deleted: {total_deleted}")
    logger.info("=" * 60)

    # Verify deletion
    logger.info("\\n🔍 Verifying deletion...")
    dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

    tables = [
        'vyaparai-products-prod',
        'vyaparai-global-products-prod',
        'vyaparai-store-inventory-prod'
    ]

    for table_name in tables:
        response = dynamodb.scan(
            TableName=table_name,
            Select='COUNT'
        )
        count = response['Count']
        if count == 0:
            logger.info(f"   ✅ {table_name}: {count} items (empty)")
        else:
            logger.warning(f"   ⚠️  {table_name}: {count} items (not empty!)")

if __name__ == "__main__":
    print("\\n⚠️  WARNING: This will delete ALL product-related data from DynamoDB!")
    print("The following tables will be affected:")
    print("   • vyaparai-products-prod")
    print("   • vyaparai-global-products-prod")
    print("   • vyaparai-store-inventory-prod")
    print("\\n")

    confirmation = input("Are you sure you want to proceed? Type 'DELETE' to confirm: ")

    if confirmation == 'DELETE':
        main()
    else:
        print("\\n❌ Deletion cancelled.")
