#!/bin/bash

# Delete all product-related data from DynamoDB tables
# This script uses AWS CLI to delete items

echo "🗑️  Deleting all product-related data from DynamoDB..."
echo "============================================================"

# Function to delete all items from a table
delete_table_items() {
    local table_name=$1
    local key_attrs=$2

    echo ""
    echo "📦 Processing $table_name..."

    # Get all items
    items=$(aws dynamodb scan --table-name "$table_name" --output json)

    # Count items
    count=$(echo "$items" | jq '.Items | length')

    if [ "$count" -eq 0 ]; then
        echo "   ✅ Already empty (0 items)"
        return
    fi

    echo "   Found $count items to delete..."

    # Delete each item
    deleted=0
    echo "$items" | jq -c '.Items[]' | while read -r item; do
        # Extract key based on table schema
        if [ "$table_name" == "vyaparai-products-prod" ]; then
            key=$(echo "$item" | jq '{id: .id}')
        elif [ "$table_name" == "vyaparai-global-products-prod" ]; then
            key=$(echo "$item" | jq '{product_id: .product_id}')
        elif [ "$table_name" == "vyaparai-store-inventory-prod" ]; then
            key=$(echo "$item" | jq '{store_id: .store_id, product_id: .product_id}')
        fi

        # Delete item
        aws dynamodb delete-item \
            --table-name "$table_name" \
            --key "$key" \
            --output text > /dev/null 2>&1

        deleted=$((deleted + 1))

        if [ $((deleted % 5)) -eq 0 ]; then
            echo "   Deleted $deleted items..."
        fi
    done

    echo "   ✅ Deleted all items from $table_name"
}

# Delete from each table
delete_table_items "vyaparai-products-prod" "id"
delete_table_items "vyaparai-global-products-prod" "product_id"
delete_table_items "vyaparai-store-inventory-prod" "store_id,product_id"

echo ""
echo "============================================================"
echo "🎉 Deletion complete!"
echo "============================================================"

# Verify deletion
echo ""
echo "🔍 Verifying deletion..."

for table in "vyaparai-products-prod" "vyaparai-global-products-prod" "vyaparai-store-inventory-prod"; do
    count=$(aws dynamodb scan --table-name "$table" --select COUNT --output json | jq '.Count')
    if [ "$count" -eq 0 ]; then
        echo "   ✅ $table: $count items (empty)"
    else
        echo "   ⚠️  $table: $count items (not empty!)"
    fi
done

echo ""
echo "✅ Done!"
