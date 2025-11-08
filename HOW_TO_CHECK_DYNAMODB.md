# 📊 How to Check DynamoDB Data

## 🔍 Method 1: AWS CLI (Command Line)

### Check if stores table is empty BEFORE registration:
```bash
# Count items in stores table
aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 --select COUNT

# See all stores (should be empty)
aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1

# Pretty format with jq (if you have jq installed)
aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 | jq '.Items'
```

### After registering a store, check again:
```bash
# See the new store data
aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 | jq '.Items[0]'

# See specific fields only
aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 | jq '.Items[] | {store_name: .store_name.S, phone: .phone.S, owner: .owner_name.S}'
```

## 🌐 Method 2: AWS Console (Web Browser)

### Steps:
1. **Open AWS Console**: https://console.aws.amazon.com/
2. **Sign in** with your AWS account
3. **Navigate to DynamoDB**:
   - Search "DynamoDB" in the search bar
   - Or go directly to: https://console.aws.amazon.com/dynamodbv2/
4. **Select Region**: Make sure "Asia Pacific (Mumbai) ap-south-1" is selected (top right)
5. **Click "Tables"** in left sidebar
6. **Find "vyaparai-stores-prod"** table and click on it
7. **Click "Explore table items"** button
8. **You'll see**:
   - Before registration: "No items found"
   - After registration: Your store data will appear

## 🛠️ Method 3: Quick Check Scripts

### Create a quick check script:
```bash
# Save this as check-stores.sh
#!/bin/bash
echo "=== VyaparAI Stores in DynamoDB ==="
COUNT=$(aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 --select COUNT --output text --query Count)
echo "Total stores: $COUNT"

if [ "$COUNT" -gt "0" ]; then
    echo -e "\nStore Details:"
    aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 --output json | \
    jq -r '.Items[] | "Store: \(.store_name.S // .name.S) | Owner: \(.owner_name.S) | Phone: \(.phone.S)"'
else
    echo "No stores registered yet."
fi
```

Make it executable and run:
```bash
chmod +x check-stores.sh
./check-stores.sh
```

## 📋 All DynamoDB Tables Status

### Check all tables at once:
```bash
# Create check-all-tables.sh
#!/bin/bash
echo "=== VyaparAI DynamoDB Tables Status ==="
for table in vyaparai-stores-prod vyaparai-orders-prod vyaparai-stock-prod vyaparai-users-prod vyaparai-customers-prod; do
    COUNT=$(aws dynamodb scan --table-name $table --region ap-south-1 --select COUNT --output text --query Count)
    echo "$table: $COUNT items"
done
```

## 🧪 Complete Test Flow

### 1. Before Registration - Check Empty:
```bash
aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 --select COUNT
# Output: 0
```

### 2. Register Store in App:
- Go to http://localhost:3001
- Click "Register Your Store"
- Fill form and submit

### 3. Immediately Check After Registration:
```bash
aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 | jq '.Items[0]'
```

You'll see something like:
```json
{
  "id": {"S": "STORE-2024-xxxxx"},
  "store_name": {"S": "Test Store"},
  "owner_name": {"S": "John Doe"},
  "phone": {"S": "+919999999999"},
  "email": {"S": "test@example.com"},
  "address": {"S": "123 Test Street"},
  "created_at": {"S": "2024-01-30T10:30:00Z"}
}
```

## 💡 Pro Tips:

### Watch real-time changes:
```bash
# Run this in a terminal to auto-refresh every 2 seconds
watch -n 2 'aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 --select COUNT --output text --query Count'
```

### Delete a test store (cleanup):
```bash
# First get the store ID
STORE_ID=$(aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 --output json | jq -r '.Items[0].id.S')

# Delete it
aws dynamodb delete-item --table-name vyaparai-stores-prod --key "{\"id\":{\"S\":\"$STORE_ID\"}}" --region ap-south-1
```

## 🎯 Summary:
- **Easiest**: Use AWS Console web interface
- **Fastest**: Use AWS CLI commands
- **Best for testing**: Create the check scripts above

Choose whichever method you're most comfortable with!