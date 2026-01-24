#!/usr/bin/env python3
"""
Debug script for VyaparAI data persistence
Tests DynamoDB connectivity, permissions, and data flow
"""
import boto3
import json
import sys
from datetime import datetime
from decimal import Decimal

# Colors for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def print_section(title):
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}{title}{NC}")
    print(f"{BLUE}{'='*60}{NC}")

def print_success(msg):
    print(f"{GREEN}✅ {msg}{NC}")

def print_error(msg):
    print(f"{RED}❌ {msg}{NC}")

def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{NC}")

def print_info(msg):
    print(f"ℹ️  {msg}")

# Configuration
REGION = 'ap-south-1'
LAMBDA_FUNCTION = 'vyaparai-api-prod'
ORDERS_TABLE = 'vyaparai-orders-prod'
INVENTORY_TABLE = 'vyaparai-store-inventory-prod'
STORES_TABLE = 'vyaparai-stores-prod'

def check_lambda_config():
    """Check Lambda function configuration"""
    print_section("1. LAMBDA CONFIGURATION")

    try:
        lambda_client = boto3.client('lambda', region_name=REGION)
        response = lambda_client.get_function_configuration(
            FunctionName=LAMBDA_FUNCTION
        )

        print_success(f"Lambda function: {response['FunctionName']}")
        print_info(f"Runtime: {response['Runtime']}")
        print_info(f"Timeout: {response['Timeout']} seconds")
        print_info(f"Memory: {response['MemorySize']} MB")

        # Check environment variables
        env_vars = response.get('Environment', {}).get('Variables', {})
        print_info(f"\nEnvironment variables ({len(env_vars)} total):")

        important_vars = ['DATABASE_URL', 'ENVIRONMENT', 'AWS_REGION']
        for var in important_vars:
            value = env_vars.get(var, 'NOT SET')
            if value == 'NOT SET':
                print_warning(f"  {var}: {value}")
            else:
                print_success(f"  {var}: {value}")

        # Check IAM role
        role_arn = response['Role']
        print_info(f"\nIAM Role: {role_arn}")

        return True

    except Exception as e:
        print_error(f"Failed to get Lambda config: {e}")
        return False

def check_lambda_permissions():
    """Check Lambda IAM permissions for DynamoDB"""
    print_section("2. IAM PERMISSIONS")

    try:
        lambda_client = boto3.client('lambda', region_name=REGION)
        response = lambda_client.get_function_configuration(
            FunctionName=LAMBDA_FUNCTION
        )

        role_arn = response['Role']
        role_name = role_arn.split('/')[-1]

        iam_client = boto3.client('iam')

        # Get attached policies
        policies_response = iam_client.list_attached_role_policies(
            RoleName=role_name
        )

        print_info(f"Attached policies for role '{role_name}':")
        for policy in policies_response['AttachedPolicies']:
            print_success(f"  - {policy['PolicyName']}")

            # Check if it's a DynamoDB policy
            if 'DynamoDB' in policy['PolicyName'] or 'Dynamo' in policy['PolicyName']:
                print_info(f"    ✓ DynamoDB policy detected")

        # Get inline policies
        inline_policies = iam_client.list_role_policies(RoleName=role_name)
        if inline_policies['PolicyNames']:
            print_info(f"\nInline policies:")
            for policy_name in inline_policies['PolicyNames']:
                print_success(f"  - {policy_name}")

        return True

    except Exception as e:
        print_error(f"Failed to check permissions: {e}")
        return False

def check_dynamodb_tables():
    """Check if DynamoDB tables exist and are accessible"""
    print_section("3. DYNAMODB TABLES")

    dynamodb = boto3.client('dynamodb', region_name=REGION)
    tables_to_check = [ORDERS_TABLE, INVENTORY_TABLE, STORES_TABLE]

    all_ok = True
    for table_name in tables_to_check:
        try:
            response = dynamodb.describe_table(TableName=table_name)
            table = response['Table']

            print_success(f"{table_name}")
            print_info(f"  Status: {table['TableStatus']}")
            print_info(f"  Item count: {table['ItemCount']}")
            print_info(f"  Size: {table['TableSizeBytes'] / 1024:.2f} KB")

            # Show key schema
            key_schema = table['KeySchema']
            keys = [f"{k['AttributeName']} ({k['KeyType']})" for k in key_schema]
            print_info(f"  Keys: {', '.join(keys)}")

        except Exception as e:
            print_error(f"{table_name}: {e}")
            all_ok = False

    return all_ok

def test_direct_dynamodb_write():
    """Test writing directly to DynamoDB"""
    print_section("4. DIRECT DYNAMODB WRITE TEST")

    try:
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table(ORDERS_TABLE)

        # Create a test order
        test_order_id = f"TEST-DEBUG-{int(datetime.now().timestamp())}"
        test_item = {
            'store_id': 'STORE-01K8NJ40V9KFKX2Y2FMK466WFH',
            'id': test_order_id,
            'customer_id': '+919999000000',
            'customer_phone': '+919999000000',
            'status': 'test',
            'intent': 'debug_test',
            'channel': 'debug',
            'language': 'en',
            'total_amount': Decimal('999.99'),
            'confidence': Decimal('1.0'),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'items': [],
            'entities': []
        }

        print_info(f"Writing test order: {test_order_id}")
        table.put_item(Item=test_item)
        print_success("Write successful!")

        # Verify the write
        print_info("Verifying write...")
        response = table.get_item(
            Key={
                'store_id': test_item['store_id'],
                'id': test_order_id
            }
        )

        if 'Item' in response:
            print_success("Verification successful! Order found in DynamoDB")
            print_info(f"  Order ID: {response['Item']['id']}")
            print_info(f"  Total: ₹{response['Item']['total_amount']}")

            # Clean up
            print_info("Cleaning up test order...")
            table.delete_item(
                Key={
                    'store_id': test_item['store_id'],
                    'id': test_order_id
                }
            )
            print_success("Test order deleted")
        else:
            print_error("Verification failed! Order not found in DynamoDB")
            return False

        return True

    except Exception as e:
        print_error(f"Direct write test failed: {e}")
        return False

def check_recent_orders():
    """Check for recent orders in DynamoDB"""
    print_section("5. RECENT ORDERS")

    try:
        dynamodb = boto3.client('dynamodb', region_name=REGION)

        response = dynamodb.scan(
            TableName=ORDERS_TABLE,
            Limit=10,
            ProjectionExpression='id, store_id, customer_phone, total_amount, created_at, #status',
            ExpressionAttributeNames={'#status': 'status'}
        )

        items = response.get('Items', [])

        if not items:
            print_warning("No orders found in table")
            return False

        print_success(f"Found {len(items)} recent orders:")

        # Sort by created_at
        sorted_items = sorted(
            items,
            key=lambda x: x.get('created_at', {}).get('S', ''),
            reverse=True
        )

        for item in sorted_items[:5]:
            order_id = item.get('id', {}).get('S', 'N/A')
            total = item.get('total_amount', {}).get('N', '0')
            created = item.get('created_at', {}).get('S', 'N/A')
            status = item.get('status', {}).get('S', 'N/A')

            print_info(f"  {order_id} | ₹{total} | {status} | {created[:19]}")

        return True

    except Exception as e:
        print_error(f"Failed to fetch recent orders: {e}")
        return False

def check_cloudwatch_logs():
    """Check recent CloudWatch logs for errors"""
    print_section("6. CLOUDWATCH LOGS (Recent Errors)")

    try:
        logs_client = boto3.client('logs', region_name=REGION)
        log_group = f'/aws/lambda/{LAMBDA_FUNCTION}'

        # Get most recent log stream
        streams_response = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )

        if not streams_response['logStreams']:
            print_warning("No log streams found")
            return False

        stream_name = streams_response['logStreams'][0]['logStreamName']
        print_info(f"Checking log stream: {stream_name}")

        # Get recent log events
        events_response = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=stream_name,
            limit=50
        )

        # Filter for errors
        errors = []
        for event in events_response['events']:
            message = event['message']
            if any(word in message.lower() for word in ['error', 'exception', 'failed', 'traceback']):
                errors.append(message)

        if errors:
            print_warning(f"Found {len(errors)} error messages in recent logs:")
            for error in errors[-3:]:  # Show last 3 errors
                print(f"  {error[:200]}")
        else:
            print_success("No errors found in recent logs")

        return True

    except Exception as e:
        print_error(f"Failed to check CloudWatch logs: {e}")
        return False

def main():
    """Run all diagnostic tests"""
    print(f"\n{BLUE}🔍 VyaparAI Persistence Diagnostic Tool{NC}")
    print(f"{BLUE}Region: {REGION}{NC}")
    print(f"{BLUE}Lambda: {LAMBDA_FUNCTION}{NC}")

    results = {
        'Lambda Config': check_lambda_config(),
        'IAM Permissions': check_lambda_permissions(),
        'DynamoDB Tables': check_dynamodb_tables(),
        'Direct Write Test': test_direct_dynamodb_write(),
        'Recent Orders': check_recent_orders(),
        'CloudWatch Logs': check_cloudwatch_logs()
    }

    # Print summary
    print_section("DIAGNOSTIC SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        if result:
            print_success(f"{test}: PASS")
        else:
            print_error(f"{test}: FAIL")

    print(f"\n{BLUE}Results: {passed}/{total} tests passed{NC}")

    if passed == total:
        print_success("\n🎉 All diagnostic tests passed!")
        print_info("DynamoDB persistence is working correctly.")
        return 0
    else:
        print_warning(f"\n⚠️  {total - passed} test(s) failed")
        print_info("Review the output above for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
