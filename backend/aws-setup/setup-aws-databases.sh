#!/bin/bash

# ============================================
# VyaparAI AWS Database Setup Script
# Sets up both RDS PostgreSQL and DynamoDB
# ============================================

set -e

echo "================================================"
echo "VyaparAI AWS Database Setup"
echo "This will create AWS RDS PostgreSQL and DynamoDB tables"
echo "================================================"

# Configuration
AWS_REGION="ap-south-1"
RDS_DB_NAME="vyaparai"
RDS_USERNAME="vyaparai_admin"
RDS_INSTANCE_ID="vyaparai-postgres-prod"
RDS_INSTANCE_CLASS="db.t3.micro"  # Free tier eligible
RDS_STORAGE="20"  # GB
SECURITY_GROUP_NAME="vyaparai-db-sg"
VPC_ID=""  # Will be fetched

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check AWS credentials
echo -e "${YELLOW}Checking AWS credentials...${NC}"
aws sts get-caller-identity --region $AWS_REGION > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}AWS credentials not configured. Run 'aws configure' first.${NC}"
    exit 1
fi

echo -e "${GREEN}AWS credentials verified!${NC}"

# ============================================
# STEP 1: Create Security Group for RDS
# ============================================
echo -e "\n${YELLOW}Step 1: Setting up Security Group...${NC}"

# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs --region $AWS_REGION --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text)

# Check if security group exists
SG_ID=$(aws ec2 describe-security-groups --region $AWS_REGION --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null)

if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
    echo "Creating security group..."
    SG_ID=$(aws ec2 create-security-group \
        --group-name $SECURITY_GROUP_NAME \
        --description "Security group for VyaparAI databases" \
        --vpc-id $VPC_ID \
        --region $AWS_REGION \
        --output text)
    
    # Add inbound rules
    # PostgreSQL port from anywhere (for development - restrict in production!)
    aws ec2 authorize-security-group-ingress \
        --group-id $SG_ID \
        --protocol tcp \
        --port 5432 \
        --cidr 0.0.0.0/0 \
        --region $AWS_REGION
    
    echo -e "${GREEN}Security group created: $SG_ID${NC}"
else
    echo -e "${GREEN}Security group already exists: $SG_ID${NC}"
fi

# ============================================
# STEP 2: Create RDS PostgreSQL Instance
# ============================================
echo -e "\n${YELLOW}Step 2: Creating RDS PostgreSQL instance...${NC}"

# Generate random password
RDS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

# Check if RDS instance exists
RDS_STATUS=$(aws rds describe-db-instances --db-instance-identifier $RDS_INSTANCE_ID --region $AWS_REGION --query "DBInstances[0].DBInstanceStatus" --output text 2>/dev/null)

if [ -z "$RDS_STATUS" ] || [ "$RDS_STATUS" == "None" ]; then
    echo "Creating RDS instance (this will take 5-10 minutes)..."
    
    aws rds create-db-instance \
        --db-instance-identifier $RDS_INSTANCE_ID \
        --db-instance-class $RDS_INSTANCE_CLASS \
        --engine postgres \
        --engine-version "14.10" \
        --master-username $RDS_USERNAME \
        --master-user-password "$RDS_PASSWORD" \
        --allocated-storage $RDS_STORAGE \
        --vpc-security-group-ids $SG_ID \
        --db-name $RDS_DB_NAME \
        --backup-retention-period 7 \
        --no-multi-az \
        --publicly-accessible \
        --storage-type gp2 \
        --region $AWS_REGION
    
    echo -e "${YELLOW}Waiting for RDS instance to be available...${NC}"
    aws rds wait db-instance-available --db-instance-identifier $RDS_INSTANCE_ID --region $AWS_REGION
    
    # Get endpoint
    RDS_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier $RDS_INSTANCE_ID --region $AWS_REGION --query "DBInstances[0].Endpoint.Address" --output text)
    
    echo -e "${GREEN}RDS instance created successfully!${NC}"
    echo -e "${GREEN}Endpoint: $RDS_ENDPOINT${NC}"
    
    # Save credentials
    cat > rds-credentials.txt << EOF
RDS PostgreSQL Credentials
==========================
Endpoint: $RDS_ENDPOINT
Port: 5432
Database: $RDS_DB_NAME
Username: $RDS_USERNAME
Password: $RDS_PASSWORD

Connection String:
postgresql://$RDS_USERNAME:$RDS_PASSWORD@$RDS_ENDPOINT:5432/$RDS_DB_NAME

IMPORTANT: Save these credentials securely and delete this file!
EOF
    
    echo -e "${YELLOW}Credentials saved to rds-credentials.txt${NC}"
else
    RDS_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier $RDS_INSTANCE_ID --region $AWS_REGION --query "DBInstances[0].Endpoint.Address" --output text)
    echo -e "${GREEN}RDS instance already exists: $RDS_ENDPOINT${NC}"
fi

# ============================================
# STEP 3: Create DynamoDB Tables
# ============================================
echo -e "\n${YELLOW}Step 3: Creating DynamoDB tables...${NC}"

# Function to create DynamoDB table
create_dynamodb_table() {
    TABLE_NAME=$1
    KEY_NAME=$2
    KEY_TYPE=$3  # S for String, N for Number
    
    # Check if table exists
    TABLE_STATUS=$(aws dynamodb describe-table --table-name $TABLE_NAME --region $AWS_REGION --query "Table.TableStatus" --output text 2>/dev/null)
    
    if [ -z "$TABLE_STATUS" ] || [ "$TABLE_STATUS" == "None" ]; then
        echo "Creating table: $TABLE_NAME"
        
        aws dynamodb create-table \
            --table-name $TABLE_NAME \
            --attribute-definitions AttributeName=$KEY_NAME,AttributeType=$KEY_TYPE \
            --key-schema AttributeName=$KEY_NAME,KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --region $AWS_REGION \
            --tags Key=Environment,Value=Production Key=Application,Value=VyaparAI
        
        # Wait for table to be active
        aws dynamodb wait table-exists --table-name $TABLE_NAME --region $AWS_REGION
        echo -e "${GREEN}Table $TABLE_NAME created${NC}"
    else
        echo -e "${GREEN}Table $TABLE_NAME already exists${NC}"
    fi
}

# Create all required DynamoDB tables
create_dynamodb_table "vyaparai-stores-prod" "id" "S"
create_dynamodb_table "vyaparai-orders-prod" "order_id" "S"
create_dynamodb_table "vyaparai-stock-prod" "product_id" "S"
create_dynamodb_table "vyaparai-users-prod" "id" "S"
create_dynamodb_table "vyaparai-customers-prod" "id" "S"

# ============================================
# STEP 4: Deploy PostgreSQL Schema
# ============================================
echo -e "\n${YELLOW}Step 4: Deploying PostgreSQL schema...${NC}"

# Wait a bit more for RDS to be fully ready
sleep 10

# Check if psql is installed
if command -v psql &> /dev/null; then
    echo "Deploying database schema..."
    
    # Export password for psql
    export PGPASSWORD="$RDS_PASSWORD"
    
    # Run migration scripts
    psql -h $RDS_ENDPOINT -U $RDS_USERNAME -d $RDS_DB_NAME -f ../database/migrations/create_inventory_schema.sql
    psql -h $RDS_ENDPOINT -U $RDS_USERNAME -d $RDS_DB_NAME -f ../database/seeds/seed_generic_products.sql
    
    echo -e "${GREEN}Schema deployed successfully!${NC}"
else
    echo -e "${YELLOW}psql not installed. Please install PostgreSQL client to deploy schema.${NC}"
    echo "You can deploy manually using:"
    echo "psql -h $RDS_ENDPOINT -U $RDS_USERNAME -d $RDS_DB_NAME -f ../database/migrations/create_inventory_schema.sql"
fi

# ============================================
# STEP 5: Create Environment Configuration
# ============================================
echo -e "\n${YELLOW}Step 5: Creating environment configuration...${NC}"

cat > ../.env.production << EOF
# VyaparAI Production Environment Variables
# Generated on $(date)

# PostgreSQL RDS
DB_HOST=$RDS_ENDPOINT
DB_PORT=5432
DB_NAME=$RDS_DB_NAME
DB_USER=$RDS_USERNAME
DB_PASSWORD=$RDS_PASSWORD
DATABASE_URL=postgresql://$RDS_USERNAME:$RDS_PASSWORD@$RDS_ENDPOINT:5432/$RDS_DB_NAME

# DynamoDB
AWS_REGION=$AWS_REGION
DYNAMODB_ORDERS_TABLE=vyaparai-orders-prod
DYNAMODB_STORES_TABLE=vyaparai-stores-prod
DYNAMODB_STOCK_TABLE=vyaparai-stock-prod
DYNAMODB_USERS_TABLE=vyaparai-users-prod
DYNAMODB_CUSTOMERS_TABLE=vyaparai-customers-prod

# API Endpoints
API_BASE_URL=https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws
LAMBDA_FUNCTION_NAME=vyaparai-api-prod
EOF

echo -e "${GREEN}Environment configuration created in .env.production${NC}"

# ============================================
# STEP 6: Update Lambda Environment Variables
# ============================================
echo -e "\n${YELLOW}Step 6: Updating Lambda function environment...${NC}"

aws lambda update-function-configuration \
    --function-name vyaparai-api-prod \
    --environment "Variables={
        DB_HOST=$RDS_ENDPOINT,
        DB_PORT=5432,
        DB_NAME=$RDS_DB_NAME,
        DB_USER=$RDS_USERNAME,
        DB_PASSWORD=$RDS_PASSWORD,
        AWS_REGION=$AWS_REGION,
        DYNAMODB_ORDERS_TABLE=vyaparai-orders-prod,
        DYNAMODB_STORES_TABLE=vyaparai-stores-prod,
        DYNAMODB_STOCK_TABLE=vyaparai-stock-prod
    }" \
    --region $AWS_REGION

echo -e "${GREEN}Lambda environment updated!${NC}"

# ============================================
# SUMMARY
# ============================================
echo -e "\n================================================"
echo -e "${GREEN}AWS Database Setup Complete!${NC}"
echo -e "================================================"
echo -e "\nResources Created:"
echo -e "1. RDS PostgreSQL: $RDS_ENDPOINT"
echo -e "2. DynamoDB Tables:"
echo -e "   - vyaparai-stores-prod"
echo -e "   - vyaparai-orders-prod"
echo -e "   - vyaparai-stock-prod"
echo -e "   - vyaparai-users-prod"
echo -e "   - vyaparai-customers-prod"
echo -e "\n${YELLOW}IMPORTANT:${NC}"
echo -e "1. Save the credentials from rds-credentials.txt"
echo -e "2. Update your local .env file with production values"
echo -e "3. Test the connection using the test script"
echo -e "\n${RED}Security Note:${NC}"
echo -e "The RDS instance is publicly accessible for development."
echo -e "In production, restrict the security group to specific IPs."
echo -e "================================================"