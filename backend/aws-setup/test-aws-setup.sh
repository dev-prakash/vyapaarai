#!/bin/bash

# Simple AWS Setup Test Script
# Tests DynamoDB and provides RDS connection info

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "==========================================="
echo "Testing VyaparAI AWS Database Setup"
echo "==========================================="

# Test DynamoDB
echo -e "\n${YELLOW}Testing DynamoDB Tables...${NC}"

TABLES=(
    "vyaparai-stores-prod"
    "vyaparai-orders-prod"
    "vyaparai-stock-prod"
    "vyaparai-users-prod"
    "vyaparai-customers-prod"
)

ALL_GOOD=true

for TABLE in "${TABLES[@]}"; do
    STATUS=$(aws dynamodb describe-table --table-name $TABLE --region ap-south-1 --query "Table.TableStatus" --output text 2>/dev/null)
    
    if [ "$STATUS" == "ACTIVE" ]; then
        ITEM_COUNT=$(aws dynamodb describe-table --table-name $TABLE --region ap-south-1 --query "Table.ItemCount" --output text 2>/dev/null)
        echo -e "  ${GREEN}✓${NC} $TABLE (Active, $ITEM_COUNT items)"
    else
        echo -e "  ${RED}✗${NC} $TABLE (Not found or not active)"
        ALL_GOOD=false
    fi
done

# Test RDS
echo -e "\n${YELLOW}Testing RDS PostgreSQL...${NC}"

RDS_STATUS=$(aws rds describe-db-instances --db-instance-identifier vyaparai-postgres-prod --region ap-south-1 --query "DBInstances[0].DBInstanceStatus" --output text 2>/dev/null)
RDS_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier vyaparai-postgres-prod --region ap-south-1 --query "DBInstances[0].Endpoint.Address" --output text 2>/dev/null)

if [ "$RDS_STATUS" == "available" ]; then
    echo -e "  ${GREEN}✓${NC} RDS Instance: Available"
    echo -e "  Endpoint: $RDS_ENDPOINT"
    echo -e "  Database: vyaparai"
    echo -e "  Username: vyaparai_admin"
    echo -e "  Port: 5432"
else
    echo -e "  ${RED}✗${NC} RDS Instance: $RDS_STATUS"
    ALL_GOOD=false
fi

# Test Lambda
echo -e "\n${YELLOW}Testing Lambda API...${NC}"

LAMBDA_URL="https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$LAMBDA_URL/health")

if [ "$HTTP_STATUS" == "200" ]; then
    echo -e "  ${GREEN}✓${NC} Lambda API: Responding ($HTTP_STATUS)"
    echo -e "  URL: $LAMBDA_URL"
else
    echo -e "  ${YELLOW}⚠${NC} Lambda API: Status $HTTP_STATUS"
fi

# Summary
echo -e "\n==========================================="
if [ "$ALL_GOOD" = true ]; then
    echo -e "${GREEN}✓ All AWS services are ready!${NC}"
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "1. Update the DB_PASSWORD in backend/.env.production"
    echo "2. Deploy the database schema (if not done):"
    echo "   psql -h $RDS_ENDPOINT -U vyaparai_admin -d vyaparai -f ../database/migrations/create_inventory_schema.sql"
    echo "3. Update Lambda environment variables if needed"
    echo "4. Test store registration from the frontend"
else
    echo -e "${YELLOW}⚠ Some services need attention${NC}"
fi
echo "==========================================="

# Create test store
echo -e "\n${YELLOW}Creating test store in DynamoDB...${NC}"

TEST_STORE_ID="test-$(date +%s)"
aws dynamodb put-item \
    --table-name vyaparai-stores-prod \
    --item "{
        \"id\": {\"S\": \"$TEST_STORE_ID\"},
        \"store_name\": {\"S\": \"Test Store\"},
        \"owner_name\": {\"S\": \"Test Owner\"},
        \"phone\": {\"S\": \"9999999999\"},
        \"email\": {\"S\": \"test@vyaparai.com\"},
        \"address\": {\"S\": \"Test Address\"},
        \"created_at\": {\"S\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}
    }" \
    --region ap-south-1 2>/dev/null && echo -e "${GREEN}✓ Test store created: $TEST_STORE_ID${NC}" || echo -e "${RED}✗ Failed to create test store${NC}"

# Delete test store
aws dynamodb delete-item \
    --table-name vyaparai-stores-prod \
    --key "{\"id\": {\"S\": \"$TEST_STORE_ID\"}}" \
    --region ap-south-1 2>/dev/null && echo -e "${GREEN}✓ Test store deleted${NC}"