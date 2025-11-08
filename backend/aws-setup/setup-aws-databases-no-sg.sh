#!/bin/bash

# VyaparAI AWS Database Setup Script (Without Security Group Creation)
# This version uses the default VPC security group instead of creating a new one
# Use this if you don't have EC2 permissions

set -e  # Exit on error

echo "==========================================="
echo "VyaparAI AWS Database Setup (No SG Version)"
echo "==========================================="

# Configuration
AWS_REGION="ap-south-1"
DB_INSTANCE_ID="vyaparai-postgres-prod"
DB_NAME="vyaparai"
DB_USER="vyaparai_admin"
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "/@\" " | cut -c1-25)
DB_INSTANCE_CLASS="db.t3.micro"
DB_STORAGE="20"

# DynamoDB Tables
DYNAMODB_TABLES=(
    "vyaparai-stores-prod"
    "vyaparai-orders-prod"
    "vyaparai-stock-prod"
    "vyaparai-users-prod"
    "vyaparai-customers-prod"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command_exists aws; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Install with: pip install awscli"
    exit 1
fi

if ! command_exists psql; then
    echo -e "${YELLOW}Warning: psql is not installed. You won't be able to deploy schema automatically${NC}"
    echo "Install PostgreSQL client to enable schema deployment"
fi

# Check AWS credentials
echo -e "\n${YELLOW}Checking AWS credentials...${NC}"
aws sts get-caller-identity --region $AWS_REGION || {
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
}

# Get default VPC
echo -e "\n${YELLOW}Getting default VPC...${NC}"
DEFAULT_VPC=$(aws ec2 describe-vpcs --region $AWS_REGION --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text)

if [ "$DEFAULT_VPC" == "None" ] || [ -z "$DEFAULT_VPC" ]; then
    echo -e "${RED}Error: No default VPC found${NC}"
    exit 1
fi

echo "Default VPC: $DEFAULT_VPC"

# Get default security group
echo -e "\n${YELLOW}Getting default security group...${NC}"
DEFAULT_SG=$(aws ec2 describe-security-groups --region $AWS_REGION --filters "Name=vpc-id,Values=$DEFAULT_VPC" "Name=group-name,Values=default" --query "SecurityGroups[0].GroupId" --output text)

if [ "$DEFAULT_SG" == "None" ] || [ -z "$DEFAULT_SG" ]; then
    echo -e "${RED}Error: No default security group found${NC}"
    exit 1
fi

echo "Default Security Group: $DEFAULT_SG"

# Update default security group to allow PostgreSQL
echo -e "\n${YELLOW}Updating default security group for PostgreSQL access...${NC}"
aws ec2 authorize-security-group-ingress \
    --group-id $DEFAULT_SG \
    --protocol tcp \
    --port 5432 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION 2>/dev/null || {
    echo "PostgreSQL rule might already exist (that's OK)"
}

# Create RDS PostgreSQL instance
echo -e "\n${GREEN}Creating RDS PostgreSQL instance...${NC}"
echo "This will take 5-10 minutes..."

aws rds create-db-instance \
    --db-instance-identifier $DB_INSTANCE_ID \
    --db-instance-class $DB_INSTANCE_CLASS \
    --engine postgres \
    --engine-version "15.4" \
    --master-username $DB_USER \
    --master-user-password "$DB_PASSWORD" \
    --db-name $DB_NAME \
    --allocated-storage $DB_STORAGE \
    --vpc-security-group-ids $DEFAULT_SG \
    --backup-retention-period 7 \
    --no-multi-az \
    --publicly-accessible \
    --storage-encrypted \
    --region $AWS_REGION \
    --tags "Key=Project,Value=VyaparAI" "Key=Environment,Value=Production" || {
    echo -e "${YELLOW}RDS instance might already exist${NC}"
}

# Wait for RDS to be available
echo -e "\n${YELLOW}Waiting for RDS instance to be available...${NC}"
echo "This typically takes 5-10 minutes. Please be patient..."

while true; do
    STATUS=$(aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_ID --region $AWS_REGION --query "DBInstances[0].DBInstanceStatus" --output text 2>/dev/null || echo "creating")
    
    if [ "$STATUS" == "available" ]; then
        echo -e "${GREEN}RDS instance is ready!${NC}"
        break
    elif [ "$STATUS" == "failed" ] || [ "$STATUS" == "deleting" ]; then
        echo -e "${RED}RDS instance creation failed${NC}"
        exit 1
    else
        echo "Current status: $STATUS (waiting...)"
        sleep 30
    fi
done

# Get RDS endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_ID --region $AWS_REGION --query "DBInstances[0].Endpoint.Address" --output text)

echo -e "${GREEN}RDS Endpoint: $RDS_ENDPOINT${NC}"

# Save RDS credentials
echo -e "\n${YELLOW}Saving RDS credentials...${NC}"
cat > rds-credentials.txt << EOF
RDS PostgreSQL Credentials
==========================
Endpoint: $RDS_ENDPOINT
Port: 5432
Database: $DB_NAME
Username: $DB_USER
Password: $DB_PASSWORD

Connection String:
postgresql://$DB_USER:$DB_PASSWORD@$RDS_ENDPOINT:5432/$DB_NAME

psql Command:
psql -h $RDS_ENDPOINT -U $DB_USER -d $DB_NAME

IMPORTANT: Save these credentials securely!
EOF

echo -e "${GREEN}Credentials saved to rds-credentials.txt${NC}"

# Deploy database schema
if command_exists psql; then
    echo -e "\n${YELLOW}Deploying database schema...${NC}"
    
    export PGPASSWORD="$DB_PASSWORD"
    
    # Create schema
    psql -h $RDS_ENDPOINT -U $DB_USER -d $DB_NAME -f ../database/migrations/create_inventory_schema.sql || {
        echo -e "${YELLOW}Schema might already exist${NC}"
    }
    
    # Seed generic products
    psql -h $RDS_ENDPOINT -U $DB_USER -d $DB_NAME -f ../database/seeds/seed_generic_products.sql || {
        echo -e "${YELLOW}Products might already be seeded${NC}"
    }
    
    unset PGPASSWORD
    echo -e "${GREEN}Schema deployed successfully!${NC}"
else
    echo -e "${YELLOW}psql not installed. Please deploy schema manually using:${NC}"
    echo "psql -h $RDS_ENDPOINT -U $DB_USER -d $DB_NAME -f ../database/migrations/create_inventory_schema.sql"
    echo "psql -h $RDS_ENDPOINT -U $DB_USER -d $DB_NAME -f ../database/seeds/seed_generic_products.sql"
fi

# Create DynamoDB tables
echo -e "\n${GREEN}Creating DynamoDB tables...${NC}"

for TABLE in "${DYNAMODB_TABLES[@]}"; do
    echo "Creating table: $TABLE"
    
    if [ "$TABLE" == "vyaparai-stores-prod" ] || [ "$TABLE" == "vyaparai-users-prod" ] || [ "$TABLE" == "vyaparai-customers-prod" ]; then
        # Tables with 'id' as primary key
        aws dynamodb create-table \
            --table-name $TABLE \
            --attribute-definitions AttributeName=id,AttributeType=S \
            --key-schema AttributeName=id,KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --tags "Key=Project,Value=VyaparAI" "Key=Environment,Value=Production" \
            --region $AWS_REGION 2>/dev/null || {
            echo "  Table $TABLE might already exist"
        }
    elif [ "$TABLE" == "vyaparai-orders-prod" ]; then
        # Orders table with composite key
        aws dynamodb create-table \
            --table-name $TABLE \
            --attribute-definitions \
                AttributeName=store_id,AttributeType=S \
                AttributeName=order_id,AttributeType=S \
            --key-schema \
                AttributeName=store_id,KeyType=HASH \
                AttributeName=order_id,KeyType=RANGE \
            --billing-mode PAY_PER_REQUEST \
            --tags "Key=Project,Value=VyaparAI" "Key=Environment,Value=Production" \
            --region $AWS_REGION 2>/dev/null || {
            echo "  Table $TABLE might already exist"
        }
    elif [ "$TABLE" == "vyaparai-stock-prod" ]; then
        # Stock table with composite key
        aws dynamodb create-table \
            --table-name $TABLE \
            --attribute-definitions \
                AttributeName=store_id,AttributeType=S \
                AttributeName=product_id,AttributeType=S \
            --key-schema \
                AttributeName=store_id,KeyType=HASH \
                AttributeName=product_id,KeyType=RANGE \
            --billing-mode PAY_PER_REQUEST \
            --tags "Key=Project,Value=VyaparAI" "Key=Environment,Value=Production" \
            --region $AWS_REGION 2>/dev/null || {
            echo "  Table $TABLE might already exist"
        }
    fi
done

echo -e "${GREEN}DynamoDB tables created!${NC}"

# Update Lambda environment variables
echo -e "\n${YELLOW}Updating Lambda function configuration...${NC}"

aws lambda update-function-configuration \
    --function-name vyaparai-api-prod \
    --environment "Variables={
        DB_HOST=$RDS_ENDPOINT,
        DB_PORT=5432,
        DB_NAME=$DB_NAME,
        DB_USER=$DB_USER,
        DB_PASSWORD=$DB_PASSWORD,
        DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@$RDS_ENDPOINT:5432/$DB_NAME,
        AWS_REGION=$AWS_REGION,
        DYNAMODB_ORDERS_TABLE=vyaparai-orders-prod,
        DYNAMODB_STORES_TABLE=vyaparai-stores-prod,
        DYNAMODB_STOCK_TABLE=vyaparai-stock-prod,
        DYNAMODB_USERS_TABLE=vyaparai-users-prod,
        DYNAMODB_CUSTOMERS_TABLE=vyaparai-customers-prod,
        USE_POSTGRESQL=true,
        USE_DYNAMODB=true,
        ENCRYPT_PII=true,
        MASK_PHONE_NUMBERS=true,
        AUDIT_LOGGING=true
    }" \
    --region $AWS_REGION || {
    echo -e "${YELLOW}Lambda function might not exist or you don't have permissions${NC}"
}

# Create .env.production file
echo -e "\n${YELLOW}Creating .env.production file...${NC}"

cat > ../.env.production << EOF
# VyaparAI AWS Production Configuration
# Generated on $(date)

# PostgreSQL RDS
DB_HOST=$RDS_ENDPOINT
DB_PORT=5432
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@$RDS_ENDPOINT:5432/$DB_NAME

# DynamoDB Configuration
AWS_REGION=$AWS_REGION
DYNAMODB_ORDERS_TABLE=vyaparai-orders-prod
DYNAMODB_STORES_TABLE=vyaparai-stores-prod
DYNAMODB_STOCK_TABLE=vyaparai-stock-prod
DYNAMODB_USERS_TABLE=vyaparai-users-prod
DYNAMODB_CUSTOMERS_TABLE=vyaparai-customers-prod

# Lambda API
API_BASE_URL=https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws
LAMBDA_FUNCTION_NAME=vyaparai-api-prod

# Security Settings
JWT_SECRET=$(openssl rand -base64 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)

# Feature Flags
USE_POSTGRESQL=true
USE_DYNAMODB=true
ENABLE_CACHING=false

# Data Privacy Settings
ENCRYPT_PII=true
MASK_PHONE_NUMBERS=true
AUDIT_LOGGING=true
EOF

echo -e "${GREEN}.env.production file created!${NC}"

# Summary
echo -e "\n${GREEN}==========================================="
echo "Setup Complete!"
echo "==========================================="
echo ""
echo "Next Steps:"
echo "1. Test connections: python3 test-connections.py"
echo "2. Update frontend .env.local with API URL"
echo "3. Restart your application"
echo ""
echo "RDS Endpoint: $RDS_ENDPOINT"
echo "Database: $DB_NAME"
echo "Username: $DB_USER"
echo ""
echo "IMPORTANT: Save the credentials from rds-credentials.txt securely!"
echo "==========================================="
echo ""
echo -e "${YELLOW}Note: Using default VPC security group.${NC}"
echo -e "${YELLOW}For production, consider creating dedicated security groups.${NC}"
echo -e "==========================================${NC}"