#!/usr/bin/env python3
"""
Test AWS Database Connections
Verifies both PostgreSQL RDS and DynamoDB connections
"""

import os
import sys
import json
import boto3
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env.production')

# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

def test_postgresql_connection():
    """Test PostgreSQL RDS connection"""
    print(f"\n{Colors.BLUE}Testing PostgreSQL RDS Connection...{Colors.END}")
    
    try:
        # Get connection parameters
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        
        if not all([db_host, db_name, db_user, db_password]):
            print(f"{Colors.RED}✗ Missing PostgreSQL credentials in .env.production{Colors.END}")
            return False
        
        print(f"Connecting to {db_host}:{db_port}/{db_name}...")
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            connect_timeout=10
        )
        
        cur = conn.cursor()
        
        # Test query - count tables
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        table_count = cur.fetchone()[0]
        
        print(f"{Colors.GREEN}✓ PostgreSQL connected successfully!{Colors.END}")
        print(f"  Database: {db_name}")
        print(f"  Tables found: {table_count}")
        
        # Check specific tables
        important_tables = [
            'categories', 'brands', 'generic_products', 'store_products',
            'stores', 'orders', 'stock_movements'
        ]
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = ANY(%s)
        """, (important_tables,))
        
        existing_tables = [row[0] for row in cur.fetchall()]
        
        print(f"\n  Key tables present:")
        for table in important_tables:
            if table in existing_tables:
                print(f"    {Colors.GREEN}✓{Colors.END} {table}")
            else:
                print(f"    {Colors.RED}✗{Colors.END} {table} (missing)")
        
        # Check generic products count
        try:
            cur.execute("SELECT COUNT(*) FROM generic_products")
            product_count = cur.fetchone()[0]
            print(f"\n  Generic products loaded: {product_count}")
        except:
            pass
        
        cur.close()
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        print(f"{Colors.RED}✗ PostgreSQL connection failed:{Colors.END}")
        print(f"  {str(e)}")
        return False
    except Exception as e:
        print(f"{Colors.RED}✗ Unexpected error:{Colors.END}")
        print(f"  {str(e)}")
        return False

def test_dynamodb_connection():
    """Test DynamoDB connection"""
    print(f"\n{Colors.BLUE}Testing DynamoDB Connection...{Colors.END}")
    
    try:
        # Get AWS region
        aws_region = os.getenv('AWS_REGION', 'ap-south-1')
        
        # Create DynamoDB client
        dynamodb = boto3.client('dynamodb', region_name=aws_region)
        
        # List tables
        response = dynamodb.list_tables()
        all_tables = response.get('TableNames', [])
        
        # Filter VyaparAI tables
        vyaparai_tables = [t for t in all_tables if 'vyaparai' in t.lower()]
        
        print(f"{Colors.GREEN}✓ DynamoDB connected successfully!{Colors.END}")
        print(f"  Region: {aws_region}")
        print(f"  VyaparAI tables found: {len(vyaparai_tables)}")
        
        # Check specific tables
        required_tables = [
            'vyaparai-stores-prod',
            'vyaparai-orders-prod',
            'vyaparai-stock-prod',
            'vyaparai-users-prod',
            'vyaparai-customers-prod'
        ]
        
        print(f"\n  Table status:")
        for table_name in required_tables:
            if table_name in vyaparai_tables:
                # Get table details
                try:
                    table_info = dynamodb.describe_table(TableName=table_name)
                    item_count = table_info['Table'].get('ItemCount', 0)
                    status = table_info['Table'].get('TableStatus', 'UNKNOWN')
                    print(f"    {Colors.GREEN}✓{Colors.END} {table_name} ({status}, {item_count} items)")
                except:
                    print(f"    {Colors.YELLOW}?{Colors.END} {table_name} (exists but couldn't get details)")
            else:
                print(f"    {Colors.RED}✗{Colors.END} {table_name} (not found)")
        
        return True
        
    except Exception as e:
        print(f"{Colors.RED}✗ DynamoDB connection failed:{Colors.END}")
        print(f"  {str(e)}")
        print(f"\n  Make sure AWS credentials are configured:")
        print(f"    aws configure")
        return False

def test_lambda_endpoint():
    """Test Lambda API endpoint"""
    print(f"\n{Colors.BLUE}Testing Lambda API Endpoint...{Colors.END}")
    
    try:
        import requests
        
        api_url = os.getenv('API_BASE_URL', 'https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws')
        
        # Test health endpoint
        response = requests.get(f"{api_url}/health", timeout=5)
        
        if response.status_code == 200:
            print(f"{Colors.GREEN}✓ Lambda API is accessible!{Colors.END}")
            print(f"  Endpoint: {api_url}")
            print(f"  Status: {response.status_code}")
            
            # Try to parse response
            try:
                data = response.json()
                print(f"  Response: {json.dumps(data, indent=2)}")
            except:
                print(f"  Response: {response.text[:100]}")
            
            return True
        else:
            print(f"{Colors.YELLOW}⚠ Lambda API returned status {response.status_code}{Colors.END}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"{Colors.RED}✗ Lambda API connection failed:{Colors.END}")
        print(f"  {str(e)}")
        return False
    except ImportError:
        print(f"{Colors.YELLOW}⚠ 'requests' library not installed. Install with: pip install requests{Colors.END}")
        return False

def test_data_insertion():
    """Test data insertion capabilities"""
    print(f"\n{Colors.BLUE}Testing Data Insertion...{Colors.END}")
    
    try:
        # Test DynamoDB insertion
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        
        # Create test store
        test_store = {
            'id': f'test-store-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'store_name': 'Test Store (Delete Me)',
            'owner_name': 'Test Owner',
            'phone': '9999999999',
            'email': 'test@vyaparai.com',
            'address': 'Test Address',
            'created_at': datetime.now().isoformat(),
            'test_flag': True  # Mark as test data
        }
        
        table = dynamodb.Table('vyaparai-stores-prod')
        table.put_item(Item=test_store)
        
        print(f"{Colors.GREEN}✓ Successfully inserted test store: {test_store['id']}{Colors.END}")
        
        # Clean up test data
        table.delete_item(Key={'id': test_store['id']})
        print(f"  Test data cleaned up")
        
        return True
        
    except Exception as e:
        print(f"{Colors.RED}✗ Data insertion test failed:{Colors.END}")
        print(f"  {str(e)}")
        return False

def main():
    """Run all connection tests"""
    print("=" * 60)
    print(f"{Colors.BLUE}VyaparAI Database Connection Test{Colors.END}")
    print("=" * 60)
    
    results = {
        'PostgreSQL': test_postgresql_connection(),
        'DynamoDB': test_dynamodb_connection(),
        'Lambda API': test_lambda_endpoint(),
        'Data Insertion': test_data_insertion()
    }
    
    print("\n" + "=" * 60)
    print(f"{Colors.BLUE}Test Summary:{Colors.END}")
    print("=" * 60)
    
    all_passed = True
    for service, passed in results.items():
        status = f"{Colors.GREEN}✓ PASSED{Colors.END}" if passed else f"{Colors.RED}✗ FAILED{Colors.END}"
        print(f"{service:.<20} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print(f"\n{Colors.GREEN}🎉 All tests passed! Your databases are ready.{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.YELLOW}⚠ Some tests failed. Please check the configuration.{Colors.END}")
        return 1

if __name__ == "__main__":
    sys.exit(main())