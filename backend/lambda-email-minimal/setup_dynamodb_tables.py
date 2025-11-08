"""
Setup DynamoDB tables for VyaparAI Email Authentication
Creates the required tables with proper indexes and TTL settings
"""

import boto3
import logging
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_dynamodb_tables():
    """Create all required DynamoDB tables"""
    
    try:
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        
        # 1. Passcodes table - for storing email passcodes with TTL
        try:
            passcodes_table = dynamodb.create_table(
                TableName='vyaparai-passcodes-dev',
                KeySchema=[
                    {'AttributeName': 'pk', 'KeyType': 'HASH'},
                    {'AttributeName': 'sk', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'pk', 'AttributeType': 'S'},
                    {'AttributeName': 'sk', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            # Wait for table to be created
            passcodes_table.wait_until_exists()
            
            # Enable TTL on the table
            dynamodb_client = boto3.client('dynamodb', region_name='ap-south-1')
            dynamodb_client.update_time_to_live(
                TableName='vyaparai-passcodes-dev',
                TimeToLiveSpecification={
                    'Enabled': True,
                    'AttributeName': 'ttl'
                }
            )
            
            logger.info("✅ Created vyaparai-passcodes-dev table with TTL")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                logger.info("📋 vyaparai-passcodes-dev table already exists")
            else:
                logger.error(f"❌ Error creating passcodes table: {e}")
        
        # 2. Update stores table to ensure it exists (if it doesn't)
        try:
            stores_table = dynamodb.create_table(
                TableName='vyaparai-stores-dev',
                KeySchema=[
                    {'AttributeName': 'pk', 'KeyType': 'HASH'},
                    {'AttributeName': 'sk', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'pk', 'AttributeType': 'S'},
                    {'AttributeName': 'sk', 'AttributeType': 'S'},
                    {'AttributeName': 'gsi1pk', 'AttributeType': 'S'},
                    {'AttributeName': 'gsi1sk', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'GSI1',
                        'KeySchema': [
                            {'AttributeName': 'gsi1pk', 'KeyType': 'HASH'},
                            {'AttributeName': 'gsi1sk', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            stores_table.wait_until_exists()
            logger.info("✅ Created vyaparai-stores-dev table")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                logger.info("📋 vyaparai-stores-dev table already exists")
            else:
                logger.error(f"❌ Error creating stores table: {e}")
        
        # 3. Sessions table (if needed for future features)
        try:
            sessions_table = dynamodb.create_table(
                TableName='vyaparai-sessions-dev',
                KeySchema=[
                    {'AttributeName': 'pk', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'pk', 'AttributeType': 'S'},
                    {'AttributeName': 'gsi1pk', 'AttributeType': 'S'},
                    {'AttributeName': 'gsi1sk', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'GSI1',
                        'KeySchema': [
                            {'AttributeName': 'gsi1pk', 'KeyType': 'HASH'},
                            {'AttributeName': 'gsi1sk', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            sessions_table.wait_until_exists()
            
            # Enable TTL on sessions table
            dynamodb_client.update_time_to_live(
                TableName='vyaparai-sessions-dev',
                TimeToLiveSpecification={
                    'Enabled': True,
                    'AttributeName': 'ttl'
                }
            )
            
            logger.info("✅ Created vyaparai-sessions-dev table with TTL")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                logger.info("📋 vyaparai-sessions-dev table already exists")
            else:
                logger.error(f"❌ Error creating sessions table: {e}")
                
        logger.info("🎉 DynamoDB table setup completed!")
        
    except Exception as e:
        logger.error(f"❌ Failed to setup DynamoDB tables: {e}")
        raise

def seed_sample_stores():
    """Add sample store data for testing"""
    try:
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        stores_table = dynamodb.Table('vyaparai-stores-dev')
        
        sample_stores = [
            {
                'pk': 'STORE#STORE-001',
                'sk': 'STORE#STORE-001',
                'gsi1pk': 'EMAIL#owner@vyaparai.com',
                'gsi1sk': '2024-01-01T00:00:00Z',
                'store_id': 'STORE-001',
                'name': 'VyaparAI Demo Store',
                'contact_info': {
                    'email': 'owner@vyaparai.com',
                    'phone': '+919876543210',
                    'owner_name': 'Rajesh Kumar'
                },
                'address': {
                    'street': '123 Main Street',
                    'city': 'Mumbai',
                    'state': 'Maharashtra',
                    'pincode': '400001'
                },
                'status': 'active',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z'
            },
            {
                'pk': 'STORE#STORE-002',
                'sk': 'STORE#STORE-002',
                'gsi1pk': 'EMAIL#test@vyaparai.com',
                'gsi1sk': '2024-01-01T00:00:00Z',
                'store_id': 'STORE-002',
                'name': 'Test Grocery Store',
                'contact_info': {
                    'email': 'test@vyaparai.com',
                    'phone': '+919876543211',
                    'owner_name': 'Suresh Patel'
                },
                'address': {
                    'street': '456 Market Road',
                    'city': 'Delhi',
                    'state': 'Delhi',
                    'pincode': '110001'
                },
                'status': 'active',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z'
            },
            {
                'pk': 'STORE#STORE-003',
                'sk': 'STORE#STORE-003',
                'gsi1pk': 'EMAIL#admin@vyaparai.com',
                'gsi1sk': '2024-01-01T00:00:00Z',
                'store_id': 'STORE-003',
                'name': 'Admin Test Store',
                'contact_info': {
                    'email': 'admin@vyaparai.com',
                    'phone': '+919876543212',
                    'owner_name': 'Admin User'
                },
                'address': {
                    'street': '789 Admin Street',
                    'city': 'Bangalore',
                    'state': 'Karnataka',
                    'pincode': '560001'
                },
                'status': 'active',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z'
            },
            {
                'pk': 'STORE#STORE-004',
                'sk': 'STORE#STORE-004',
                'gsi1pk': 'EMAIL#prakashsukumar@gmail.com',
                'gsi1sk': '2024-01-01T00:00:00Z',
                'store_id': 'STORE-004',
                'name': 'Prakash Store',
                'contact_info': {
                    'email': 'prakashsukumar@gmail.com',
                    'phone': '+919876543213',
                    'owner_name': 'Prakash Kumar'
                },
                'address': {
                    'street': '101 Store Lane',
                    'city': 'Chennai',
                    'state': 'Tamil Nadu',
                    'pincode': '600001'
                },
                'status': 'active',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z'
            },
            {
                'pk': 'STORE#STORE-005',
                'sk': 'STORE#STORE-005',
                'gsi1pk': 'EMAIL#devprakashsen@gmail.com',
                'gsi1sk': '2024-01-01T00:00:00Z',
                'store_id': 'STORE-005',
                'name': 'Dev Prakash Store',
                'contact_info': {
                    'email': 'devprakashsen@gmail.com',
                    'phone': '+919876543214',
                    'owner_name': 'Dev Prakash Sen'
                },
                'address': {
                    'street': '202 Dev Street',
                    'city': 'Kolkata',
                    'state': 'West Bengal',
                    'pincode': '700001'
                },
                'status': 'active',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z'
            }
        ]
        
        # Insert sample stores
        for store in sample_stores:
            try:
                stores_table.put_item(Item=store)
                logger.info(f"✅ Added sample store: {store['name']} ({store['contact_info']['email']})")
            except ClientError as e:
                logger.warning(f"⚠️ Could not add store {store['name']}: {e}")
        
        logger.info("🎉 Sample store data seeded successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to seed sample stores: {e}")

if __name__ == "__main__":
    print("🚀 Setting up DynamoDB tables for VyaparAI Email Authentication...")
    create_dynamodb_tables()
    
    print("\\n📊 Seeding sample store data...")
    seed_sample_stores()
    
    print("\\n✅ Setup completed! The following tables are ready:")
    print("   • vyaparai-passcodes-dev (with TTL)")
    print("   • vyaparai-stores-dev (with GSI)")
    print("   • vyaparai-sessions-dev (with TTL)")
    print("\\n📧 Sample emails for testing:")
    print("   • owner@vyaparai.com")
    print("   • test@vyaparai.com") 
    print("   • admin@vyaparai.com")
    print("   • prakashsukumar@gmail.com")
    print("   • devprakashsen@gmail.com")