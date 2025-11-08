#!/bin/bash

echo "🚀 VyaparAI AWS Setup Script"
echo "============================"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not installed${NC}"
    echo "Install from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
aws sts get-caller-identity > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

# Get AWS account info
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-ap-south-1}

echo -e "${GREEN}✓ AWS Account: $ACCOUNT_ID${NC}"
echo -e "${GREEN}✓ Region: $REGION${NC}"

# Create deployment directory
mkdir -p deployment

# Create S3 buckets
echo -e "\n${YELLOW}Creating S3 buckets...${NC}"

# Deployment bucket
aws s3 mb s3://vyaparai-deployment-$ACCOUNT_ID --region $REGION 2>/dev/null || true

# Frontend bucket
aws s3 mb s3://vyaparai-frontend-$ACCOUNT_ID --region $REGION 2>/dev/null || true

# Enable static website hosting
aws s3 website s3://vyaparai-frontend-$ACCOUNT_ID \
    --index-document index.html \
    --error-document index.html

# Create bucket policy for public access
cat > /tmp/bucket-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::vyaparai-frontend-$ACCOUNT_ID/*"
        }
    ]
}
EOF

aws s3api put-bucket-policy \
    --bucket vyaparai-frontend-$ACCOUNT_ID \
    --policy file:///tmp/bucket-policy.json

echo -e "${GREEN}✓ S3 buckets created${NC}"

# Create DynamoDB tables
echo -e "\n${YELLOW}Creating DynamoDB tables...${NC}"

# Orders table
aws dynamodb create-table \
    --table-name vyaparai-orders-prod \
    --attribute-definitions \
        AttributeName=pk,AttributeType=S \
        AttributeName=sk,AttributeType=S \
        AttributeName=gsi1pk,AttributeType=S \
        AttributeName=gsi1sk,AttributeType=S \
    --key-schema \
        AttributeName=pk,KeyType=HASH \
        AttributeName=sk,KeyType=RANGE \
    --global-secondary-indexes \
        "IndexName=gsi1,Keys=[{AttributeName=gsi1pk,KeyType=HASH},{AttributeName=gsi1sk,KeyType=RANGE}],Projection={ProjectionType=ALL},BillingMode=PAY_PER_REQUEST" \
    --billing-mode PAY_PER_REQUEST \
    --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
    --region $REGION 2>/dev/null || echo "Orders table exists"

# Sessions table
aws dynamodb create-table \
    --table-name vyaparai-sessions-prod \
    --attribute-definitions \
        AttributeName=pk,AttributeType=S \
    --key-schema \
        AttributeName=pk,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region $REGION 2>/dev/null || echo "Sessions table exists"

echo -e "${GREEN}✓ DynamoDB tables created${NC}"

# Create RDS PostgreSQL instance
echo -e "\n${YELLOW}Creating RDS PostgreSQL...${NC}"
echo -e "${YELLOW}Note: This will take 5-10 minutes${NC}"

aws rds create-db-instance \
    --db-instance-identifier vyaparai-postgres-prod \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 15.4 \
    --master-username vyaparai_admin \
    --master-user-password "VyaparAI2024Secure!" \
    --allocated-storage 20 \
    --storage-type gp3 \
    --publicly-accessible \
    --backup-retention-period 7 \
    --region $REGION 2>/dev/null || echo "RDS instance exists"

# Create Lambda execution role
echo -e "\n${YELLOW}Creating IAM roles...${NC}"

cat > /tmp/trust-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF

aws iam create-role \
    --role-name vyaparai-lambda-role \
    --assume-role-policy-document file:///tmp/trust-policy.json \
    2>/dev/null || echo "Lambda role exists"

# Attach policies
aws iam attach-role-policy \
    --role-name vyaparai-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam attach-role-policy \
    --role-name vyaparai-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess

aws iam attach-role-policy \
    --role-name vyaparai-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonRDSFullAccess

# Create custom policy for S3 access
cat > /tmp/s3-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::vyaparai-frontend-$ACCOUNT_ID",
                "arn:aws:s3:::vyaparai-frontend-$ACCOUNT_ID/*",
                "arn:aws:s3:::vyaparai-deployment-$ACCOUNT_ID",
                "arn:aws:s3:::vyaparai-deployment-$ACCOUNT_ID/*"
            ]
        }
    ]
}
EOF

aws iam create-policy \
    --policy-name vyaparai-s3-policy \
    --policy-document file:///tmp/s3-policy.json \
    2>/dev/null || echo "S3 policy exists"

aws iam attach-role-policy \
    --role-name vyaparai-lambda-role \
    --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/vyaparai-s3-policy

echo -e "${GREEN}✓ IAM roles created${NC}"

# Create API Gateway
echo -e "\n${YELLOW}Creating API Gateway...${NC}"

API_ID=$(aws apigatewayv2 create-api \
    --name vyaparai-api \
    --protocol-type HTTP \
    --cors-configuration "AllowOrigins=*,AllowMethods=*,AllowHeaders=*" \
    --query ApiId \
    --output text 2>/dev/null) || API_ID="existing"

if [ "$API_ID" != "existing" ]; then
    echo -e "${GREEN}✓ API Gateway created: $API_ID${NC}"
    echo "API_GATEWAY_ID=$API_ID" >> deployment/.env.production
fi

# Create ElastiCache Redis cluster (optional for caching)
echo -e "\n${YELLOW}Creating ElastiCache Redis...${NC}"

# Create subnet group
aws elasticache create-cache-subnet-group \
    --cache-subnet-group-name vyaparai-redis-subnet \
    --cache-subnet-group-description "VyaparAI Redis subnet group" \
    --subnet-ids subnet-12345678 \
    --region $REGION 2>/dev/null || echo "Redis subnet group exists"

# Create Redis cluster
aws elasticache create-cache-cluster \
    --cache-cluster-id vyaparai-redis-prod \
    --engine redis \
    --cache-node-type cache.t3.micro \
    --num-cache-nodes 1 \
    --cache-subnet-group-name vyaparai-redis-subnet \
    --region $REGION 2>/dev/null || echo "Redis cluster exists"

echo -e "${GREEN}✓ ElastiCache Redis created${NC}"

# Create CloudWatch log group
echo -e "\n${YELLOW}Creating CloudWatch log group...${NC}"

aws logs create-log-group \
    --log-group-name /aws/lambda/vyaparai-api-prod \
    --region $REGION 2>/dev/null || echo "Log group exists"

echo -e "${GREEN}✓ CloudWatch log group created${NC}"

# Output summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}AWS Infrastructure Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Resources created:"
echo "  • S3 Frontend: vyaparai-frontend-$ACCOUNT_ID"
echo "  • S3 Deployment: vyaparai-deployment-$ACCOUNT_ID"
echo "  • DynamoDB: vyaparai-orders-prod, vyaparai-sessions-prod"
echo "  • RDS: vyaparai-postgres-prod"
echo "  • Lambda Role: vyaparai-lambda-role"
echo "  • API Gateway: vyaparai-api"
echo "  • ElastiCache: vyaparai-redis-prod"
echo "  • CloudWatch: /aws/lambda/vyaparai-api-prod"
echo ""
echo "Next step: Run ./deployment/deploy-backend.sh"

# Clean up temporary files
rm -f /tmp/bucket-policy.json /tmp/trust-policy.json /tmp/s3-policy.json



