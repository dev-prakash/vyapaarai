#!/bin/bash

# Quick cleanup for orders table
echo "Cleaning vyaparai-orders-prod table..."

# Get all orders and delete them
aws dynamodb scan \
    --table-name vyaparai-orders-prod \
    --region ap-south-1 \
    --projection-expression "store_id,order_id" \
    --output json | \
jq -r '.Items[] | "\(.store_id.S)|\(.order_id.S)"' | \
while IFS='|' read -r store_id order_id; do
    aws dynamodb delete-item \
        --table-name vyaparai-orders-prod \
        --key "{\"store_id\":{\"S\":\"$store_id\"},\"order_id\":{\"S\":\"$order_id\"}}" \
        --region ap-south-1 &
done

# Wait for all background jobs
wait

echo "Orders table cleaned!"

# Clean stock table
echo "Cleaning vyaparai-stock-prod table..."
aws dynamodb scan \
    --table-name vyaparai-stock-prod \
    --region ap-south-1 \
    --projection-expression "store_id,product_id" \
    --output json | \
jq -r '.Items[] | "\(.store_id.S)|\(.product_id.S)"' | \
while IFS='|' read -r store_id product_id; do
    aws dynamodb delete-item \
        --table-name vyaparai-stock-prod \
        --key "{\"store_id\":{\"S\":\"$store_id\"},\"product_id\":{\"S\":\"$product_id\"}}" \
        --region ap-south-1
done

echo "Stock table cleaned!"

# Show final counts
echo -e "\nFinal status:"
aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 --select COUNT --output text --query Count
aws dynamodb scan --table-name vyaparai-orders-prod --region ap-south-1 --select COUNT --output text --query Count  
aws dynamodb scan --table-name vyaparai-stock-prod --region ap-south-1 --select COUNT --output text --query Count
aws dynamodb scan --table-name vyaparai-users-prod --region ap-south-1 --select COUNT --output text --query Count
aws dynamodb scan --table-name vyaparai-customers-prod --region ap-south-1 --select COUNT --output text --query Count