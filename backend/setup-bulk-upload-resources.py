#!/usr/bin/env python3
"""
Setup AWS resources for CSV bulk upload functionality
"""

import boto3
import json
from botocore.exceptions import ClientError

def create_s3_bucket():
    """Create S3 bucket for temporary CSV files"""
    s3_client = boto3.client('s3')
    bucket_name = 'vyapaarai-bulk-uploads-prod'
    
    try:
        # Check if bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ S3 bucket '{bucket_name}' already exists")
        return bucket_name
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            # Bucket doesn't exist, create it
            try:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': 'ap-south-1'}
                )
                print(f"✅ Created S3 bucket '{bucket_name}'")
                
                # Set lifecycle policy to delete files after 7 days
                lifecycle_policy = {
                    'Rules': [
                        {
                            'ID': 'DeleteTempFiles',
                            'Status': 'Enabled',
                            'Filter': {'Prefix': 'bulk-uploads/'},
                            'Expiration': {'Days': 7}
                        }
                    ]
                }
                
                s3_client.put_bucket_lifecycle_configuration(
                    Bucket=bucket_name,
                    LifecycleConfiguration=lifecycle_policy
                )
                print(f"✅ Set lifecycle policy for bucket '{bucket_name}'")
                
                return bucket_name
            except ClientError as create_error:
                print(f"❌ Failed to create S3 bucket: {create_error}")
                return None
        else:
            print(f"❌ Error checking S3 bucket: {e}")
            return None

def create_dynamodb_table():
    """Create DynamoDB table for bulk upload jobs"""
    dynamodb = boto3.client('dynamodb')
    table_name = 'vyaparai-bulk-upload-jobs-prod'
    
    try:
        # Check if table exists
        dynamodb.describe_table(TableName=table_name)
        print(f"✅ DynamoDB table '{table_name}' already exists")
        return table_name
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            # Table doesn't exist, create it
            try:
                response = dynamodb.create_table(
                    TableName=table_name,
                    KeySchema=[
                        {
                            'AttributeName': 'job_id',
                            'KeyType': 'HASH'
                        }
                    ],
                    AttributeDefinitions=[
                        {
                            'AttributeName': 'job_id',
                            'AttributeType': 'S'
                        }
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )
                
                # Wait for table to be created
                waiter = dynamodb.get_waiter('table_exists')
                waiter.wait(TableName=table_name)
                
                print(f"✅ Created DynamoDB table '{table_name}'")
                return table_name
            except ClientError as create_error:
                print(f"❌ Failed to create DynamoDB table: {create_error}")
                return None
        else:
            print(f"❌ Error checking DynamoDB table: {e}")
            return None

def create_iam_policy():
    """Create IAM policy for bulk upload operations"""
    iam = boto3.client('iam')
    policy_name = 'VyaparAIBulkUploadPolicy'
    
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                "Resource": "arn:aws:s3:::vyapaarai-bulk-uploads-prod/*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                "Resource": "arn:aws:dynamodb:ap-south-1:*:table/vyaparai-bulk-upload-jobs-prod"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                "Resource": "arn:aws:dynamodb:ap-south-1:*:table/vyaparai-products-prod"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": "arn:aws:lambda:ap-south-1:*:function:vyapaarai-image-processing"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                "Resource": "arn:aws:s3:::vyapaarai-product-images-prod/*"
            }
        ]
    }
    
    try:
        # Check if policy exists
        iam.get_policy(PolicyArn=f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:policy/{policy_name}")
        print(f"✅ IAM policy '{policy_name}' already exists")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            # Policy doesn't exist, create it
            try:
                response = iam.create_policy(
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document),
                    Description='Policy for VyaparAI bulk upload operations'
                )
                print(f"✅ Created IAM policy '{policy_name}'")
            except ClientError as create_error:
                print(f"❌ Failed to create IAM policy: {create_error}")
        else:
            print(f"❌ Error checking IAM policy: {e}")

def main():
    """Main setup function"""
    print("🚀 Setting up AWS resources for CSV bulk upload...")
    print("=" * 50)
    
    # Create S3 bucket
    print("\n📦 Creating S3 bucket...")
    bucket_name = create_s3_bucket()
    
    # Create DynamoDB table
    print("\n🗄️ Creating DynamoDB table...")
    table_name = create_dynamodb_table()
    
    # Create IAM policy
    print("\n🔐 Creating IAM policy...")
    create_iam_policy()
    
    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print(f"📦 S3 Bucket: {bucket_name}")
    print(f"🗄️ DynamoDB Table: {table_name}")
    print(f"🔐 IAM Policy: VyaparAIBulkUploadPolicy")
    print("\n📋 Next steps:")
    print("1. Attach the IAM policy to your Lambda execution role")
    print("2. Deploy the updated Lambda function")
    print("3. Test the CSV bulk upload functionality")

if __name__ == "__main__":
    main()
