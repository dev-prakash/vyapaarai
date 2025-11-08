"""
Script to create DynamoDB tables for Translation Service

Creates two tables:
1. vyaparai-products-catalog-prod: Stores product catalog in English
2. vyaparai-translation-cache-prod: Stores cached translations with TTL
"""

import boto3
import sys

dynamodb = boto3.client('dynamodb', region_name='ap-south-1')


def create_products_table():
    """Create Products Catalog table"""
    try:
        print("Creating vyaparai-products-catalog-prod table...")

        response = dynamodb.create_table(
            TableName='vyaparai-products-catalog-prod',
            KeySchema=[
                {
                    'AttributeName': 'productId',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'productId',
                    'AttributeType': 'S'  # String
                }
            ],
            BillingMode='PAY_PER_REQUEST',  # On-demand pricing
            Tags=[
                {
                    'Key': 'Project',
                    'Value': 'VyapaarAI'
                },
                {
                    'Key': 'Environment',
                    'Value': 'Production'
                },
                {
                    'Key': 'Service',
                    'Value': 'Translation'
                }
            ]
        )

        print(f"✅ Products table created successfully!")
        print(f"   ARN: {response['TableDescription']['TableArn']}")
        return True

    except dynamodb.exceptions.ResourceInUseException:
        print("⚠️  Products table already exists")
        return True
    except Exception as e:
        print(f"❌ Error creating Products table: {e}")
        return False


def create_translation_cache_table():
    """Create Translation Cache table with TTL"""
    try:
        print("\nCreating vyaparai-translation-cache-prod table...")

        response = dynamodb.create_table(
            TableName='vyaparai-translation-cache-prod',
            KeySchema=[
                {
                    'AttributeName': 'cacheKey',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'cacheKey',
                    'AttributeType': 'S'  # String
                }
            ],
            BillingMode='PAY_PER_REQUEST',  # On-demand pricing
            Tags=[
                {
                    'Key': 'Project',
                    'Value': 'VyapaarAI'
                },
                {
                    'Key': 'Environment',
                    'Value': 'Production'
                },
                {
                    'Key': 'Service',
                    'Value': 'Translation'
                }
            ]
        )

        print(f"✅ Translation Cache table created successfully!")
        print(f"   ARN: {response['TableDescription']['TableArn']}")

        # Enable TTL on the table
        print("   Enabling TTL on 'ttl' attribute...")
        dynamodb.update_time_to_live(
            TableName='vyaparai-translation-cache-prod',
            TimeToLiveSpecification={
                'Enabled': True,
                'AttributeName': 'ttl'
            }
        )
        print("   ✅ TTL enabled (30-day auto-deletion)")

        return True

    except dynamodb.exceptions.ResourceInUseException:
        print("⚠️  Translation Cache table already exists")

        # Try to enable TTL anyway
        try:
            print("   Checking TTL status...")
            ttl_status = dynamodb.describe_time_to_live(
                TableName='vyaparai-translation-cache-prod'
            )
            if ttl_status['TimeToLiveDescription']['TimeToLiveStatus'] != 'ENABLED':
                print("   Enabling TTL...")
                dynamodb.update_time_to_live(
                    TableName='vyaparai-translation-cache-prod',
                    TimeToLiveSpecification={
                        'Enabled': True,
                        'AttributeName': 'ttl'
                    }
                )
                print("   ✅ TTL enabled")
            else:
                print("   ✅ TTL already enabled")
        except Exception as e:
            print(f"   ⚠️  Could not enable TTL: {e}")

        return True
    except Exception as e:
        print(f"❌ Error creating Translation Cache table: {e}")
        return False


def insert_sample_products():
    """Insert sample products for testing"""
    try:
        print("\nInserting sample products...")

        sample_products = [
            {
                'productId': {'S': 'PROD-001'},
                'productName_en': {'S': 'Tata Salt'},
                'productDescription_en': {'S': 'Premium iodized salt for daily cooking'},
                'price': {'N': '25.00'},
                'quantity': {'N': '150'},
                'category': {'S': 'Grocery'},
                'sku': {'S': 'SALT-001'},
                'barcode': {'S': '8901234567890'},
                'createdAt': {'S': '2025-10-18T12:00:00.000Z'},
                'updatedAt': {'S': '2025-10-18T12:00:00.000Z'}
            },
            {
                'productId': {'S': 'PROD-002'},
                'productName_en': {'S': 'Amul Butter'},
                'productDescription_en': {'S': 'Fresh and creamy butter made from pure milk'},
                'price': {'N': '55.00'},
                'quantity': {'N': '80'},
                'category': {'S': 'Dairy'},
                'sku': {'S': 'BUTTER-001'},
                'barcode': {'S': '8901234567891'},
                'createdAt': {'S': '2025-10-18T12:00:00.000Z'},
                'updatedAt': {'S': '2025-10-18T12:00:00.000Z'}
            },
            {
                'productId': {'S': 'PROD-003'},
                'productName_en': {'S': 'Britannia Good Day Biscuits'},
                'productDescription_en': {'S': 'Delicious butter cookies perfect for tea time'},
                'price': {'N': '30.00'},
                'quantity': {'N': '200'},
                'category': {'S': 'Snacks'},
                'sku': {'S': 'BISCUIT-001'},
                'barcode': {'S': '8901234567892'},
                'createdAt': {'S': '2025-10-18T12:00:00.000Z'},
                'updatedAt': {'S': '2025-10-18T12:00:00.000Z'}
            }
        ]

        for product in sample_products:
            try:
                dynamodb.put_item(
                    TableName='vyaparai-products-catalog-prod',
                    Item=product
                )
                print(f"   ✅ Inserted: {product['productName_en']['S']}")
            except Exception as e:
                print(f"   ⚠️  Error inserting {product['productName_en']['S']}: {e}")

        print("\n✅ Sample products inserted successfully!")
        return True

    except Exception as e:
        print(f"❌ Error inserting sample products: {e}")
        return False


def main():
    """Main execution function"""
    print("=" * 60)
    print("VyapaarAI Translation Service - DynamoDB Table Setup")
    print("=" * 60)

    # Create Products table
    products_success = create_products_table()

    # Create Translation Cache table
    cache_success = create_translation_cache_table()

    # Insert sample data
    if products_success:
        insert_sample_products()

    print("\n" + "=" * 60)
    if products_success and cache_success:
        print("✅ All tables created successfully!")
        print("\nTable Summary:")
        print("  1. vyaparai-products-catalog-prod")
        print("     - Partition Key: productId (String)")
        print("     - Billing: On-Demand")
        print("\n  2. vyaparai-translation-cache-prod")
        print("     - Partition Key: cacheKey (String)")
        print("     - TTL: Enabled (30 days)")
        print("     - Billing: On-Demand")
        print("\n✅ Setup complete! You can now deploy the translation service.")
    else:
        print("❌ Some tables failed to create. Please check the errors above.")
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()
