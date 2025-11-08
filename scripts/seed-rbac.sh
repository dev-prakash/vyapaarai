#!/bin/bash
# Seed RBAC data into DynamoDB tables

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FILE="$SCRIPT_DIR/seed-rbac-data.json"

echo "🚀 Starting RBAC data seeding..."

# Read the JSON file
if [ ! -f "$DATA_FILE" ]; then
    echo "❌ Error: seed-rbac-data.json not found"
    exit 1
fi

# Seed Permissions
echo ""
echo "📝 Seeding permissions..."
PERMISSIONS=$(jq -c '.permissions[]' "$DATA_FILE")
COUNT=0
while IFS= read -r permission; do
    PERM_ID=$(echo "$permission" | jq -r '.permission_id')
    echo "  Adding permission: $PERM_ID"

    aws dynamodb put-item \
        --table-name vyaparai-permissions-prod \
        --item "{
            \"permission_id\": {\"S\": \"$(echo "$permission" | jq -r '.permission_id')\"},
            \"name\": {\"S\": \"$(echo "$permission" | jq -r '.name')\"},
            \"description\": {\"S\": \"$(echo "$permission" | jq -r '.description')\"},
            \"category\": {\"S\": \"$(echo "$permission" | jq -r '.category')\"},
            \"resource\": {\"S\": \"$(echo "$permission" | jq -r '.resource')\"},
            \"action\": {\"S\": \"$(echo "$permission" | jq -r '.action')\"},
            \"status\": {\"S\": \"$(echo "$permission" | jq -r '.status')\"},
            \"created_at\": {\"S\": \"$(echo "$permission" | jq -r '.created_at')\"}
        }" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        ((COUNT++))
    else
        echo "  ⚠️  Failed to add $PERM_ID"
    fi
done <<< "$PERMISSIONS"
echo "✅ Added $COUNT permissions"

# Seed Roles
echo ""
echo "👥 Seeding roles..."
ROLES=$(jq -c '.roles[]' "$DATA_FILE")
COUNT=0
while IFS= read -r role; do
    ROLE_ID=$(echo "$role" | jq -r '.role_id')
    echo "  Adding role: $ROLE_ID"

    # Get permissions as StringSet
    PERMS=$(echo "$role" | jq -r '.permissions | map("{\"S\": \"" + . + "\"}") | join(", ")')

    aws dynamodb put-item \
        --table-name vyaparai-roles-prod \
        --item "{
            \"role_id\": {\"S\": \"$(echo "$role" | jq -r '.role_id')\"},
            \"role_name\": {\"S\": \"$(echo "$role" | jq -r '.role_name')\"},
            \"description\": {\"S\": \"$(echo "$role" | jq -r '.description')\"},
            \"permissions\": {\"SS\": [$(echo "$PERMS")]},
            \"hierarchy_level\": {\"N\": \"$(echo "$role" | jq -r '.hierarchy_level')\"},
            \"is_system_role\": {\"BOOL\": $(echo "$role" | jq -r '.is_system_role')},
            \"status\": {\"S\": \"$(echo "$role" | jq -r '.status')\"},
            \"created_at\": {\"S\": \"$(echo "$role" | jq -r '.created_at')\"}
        }" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        ((COUNT++))
    else
        echo "  ⚠️  Failed to add $ROLE_ID"
    fi
done <<< "$ROLES"
echo "✅ Added $COUNT roles"

echo ""
echo "🎉 RBAC seeding completed!"
echo ""
echo "📊 Summary:"
aws dynamodb describe-table --table-name vyaparai-permissions-prod --query 'Table.ItemCount' --output text | xargs -I {} echo "  Permissions table: {} items"
aws dynamodb describe-table --table-name vyaparai-roles-prod --query 'Table.ItemCount' --output text | xargs -I {} echo "  Roles table: {} items"
