#!/bin/bash

# Complete DynamoDB Setup - Create missing tables
# Some tables already exist, we'll create the missing ones

set -e

AWS_REGION="ap-south-1"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "==========================================="
echo "Creating Missing DynamoDB Tables"
echo "==========================================="

# Tables that need to be created
echo -e "\n${YELLOW}Creating vyaparai-stores-prod table...${NC}"
aws dynamodb create-table \
    --table-name vyaparai-stores-prod \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --tags "Key=Project,Value=VyaparAI" "Key=Environment,Value=Production" \
    --region $AWS_REGION 2>/dev/null && echo -e "${GREEN}✓ Created vyaparai-stores-prod${NC}" || echo "Table vyaparai-stores-prod already exists"

echo -e "\n${YELLOW}Creating vyaparai-users-prod table...${NC}"
aws dynamodb create-table \
    --table-name vyaparai-users-prod \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --tags "Key=Project,Value=VyaparAI" "Key=Environment,Value=Production" \
    --region $AWS_REGION 2>/dev/null && echo -e "${GREEN}✓ Created vyaparai-users-prod${NC}" || echo "Table vyaparai-users-prod already exists"

echo -e "\n${YELLOW}Creating vyaparai-customers-prod table...${NC}"
aws dynamodb create-table \
    --table-name vyaparai-customers-prod \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --tags "Key=Project,Value=VyaparAI" "Key=Environment,Value=Production" \
    --region $AWS_REGION 2>/dev/null && echo -e "${GREEN}✓ Created vyaparai-customers-prod${NC}" || echo "Table vyaparai-customers-prod already exists"

# List all tables to confirm
echo -e "\n${YELLOW}Verifying all tables...${NC}"
echo "Current VyaparAI tables:"
aws dynamodb list-tables --region $AWS_REGION | grep -i vyaparai | sort

echo -e "\n${GREEN}DynamoDB setup complete!${NC}"
echo "==========================================="