#!/bin/bash

# Clean all DynamoDB tables for fresh testing
# This script deletes all items from VyaparAI DynamoDB tables

set -e

AWS_REGION="ap-south-1"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "==========================================="
echo "Cleaning DynamoDB Tables for Fresh Testing"
echo "==========================================="

# Function to delete all items from a table
delete_all_items() {
    local table_name=$1
    echo -e "\n${YELLOW}Cleaning table: $table_name${NC}"
    
    # Get the key schema for the table
    KEY_SCHEMA=$(aws dynamodb describe-table --table-name $table_name --region $AWS_REGION --query "Table.KeySchema[0].AttributeName" --output text)
    
    # Scan and delete all items
    echo "Scanning for items..."
    
    if [ "$table_name" == "vyaparai-orders-prod" ]; then
        # Orders table has composite key (store_id, order_id)
        aws dynamodb scan --table-name $table_name --region $AWS_REGION --output json | \
        jq -r '.Items[] | @json' | \
        while read -r item; do
            store_id=$(echo "$item" | jq -r '.store_id.S')
            order_id=$(echo "$item" | jq -r '.order_id.S')
            if [ ! -z "$store_id" ] && [ ! -z "$order_id" ]; then
                aws dynamodb delete-item \
                    --table-name $table_name \
                    --key "{\"store_id\":{\"S\":\"$store_id\"},\"order_id\":{\"S\":\"$order_id\"}}" \
                    --region $AWS_REGION 2>/dev/null
                echo -n "."
            fi
        done
    elif [ "$table_name" == "vyaparai-stock-prod" ]; then
        # Stock table has composite key (store_id, product_id)
        aws dynamodb scan --table-name $table_name --region $AWS_REGION --output json | \
        jq -r '.Items[] | @json' | \
        while read -r item; do
            store_id=$(echo "$item" | jq -r '.store_id.S')
            product_id=$(echo "$item" | jq -r '.product_id.S')
            if [ ! -z "$store_id" ] && [ ! -z "$product_id" ]; then
                aws dynamodb delete-item \
                    --table-name $table_name \
                    --key "{\"store_id\":{\"S\":\"$store_id\"},\"product_id\":{\"S\":\"$product_id\"}}" \
                    --region $AWS_REGION 2>/dev/null
                echo -n "."
            fi
        done
    else
        # Tables with single key (id)
        aws dynamodb scan --table-name $table_name --region $AWS_REGION --output json | \
        jq -r '.Items[].id.S' | \
        while read -r id; do
            if [ ! -z "$id" ]; then
                aws dynamodb delete-item \
                    --table-name $table_name \
                    --key "{\"id\":{\"S\":\"$id\"}}" \
                    --region $AWS_REGION 2>/dev/null
                echo -n "."
            fi
        done
    fi
    
    echo ""
    
    # Verify table is empty
    COUNT=$(aws dynamodb scan --table-name $table_name --region $AWS_REGION --select COUNT --output json | jq -r '.Count')
    if [ "$COUNT" == "0" ]; then
        echo -e "${GREEN}✓ $table_name cleaned (0 items)${NC}"
    else
        echo -e "${YELLOW}⚠ $table_name still has $COUNT items${NC}"
    fi
}

# Clean all tables
TABLES=(
    "vyaparai-stores-prod"
    "vyaparai-orders-prod"
    "vyaparai-stock-prod"
    "vyaparai-users-prod"
    "vyaparai-customers-prod"
)

for TABLE in "${TABLES[@]}"; do
    delete_all_items $TABLE
done

echo -e "\n==========================================="
echo -e "${GREEN}All DynamoDB tables cleaned!${NC}"
echo "==========================================="

# Show final status
echo -e "\n${YELLOW}Final table status:${NC}"
for TABLE in "${TABLES[@]}"; do
    COUNT=$(aws dynamodb scan --table-name $TABLE --region $AWS_REGION --select COUNT --output json | jq -r '.Count')
    echo "  $TABLE: $COUNT items"
done