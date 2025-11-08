# VyaparAI Database Location & Access Guide

## Current Database Architecture

The VyaparAI application uses a **HYBRID approach** with both DynamoDB and PostgreSQL (planned). Currently, most data is stored in **AWS DynamoDB**.

---

## 🔵 **AWS DynamoDB Tables (Currently Active)**

These tables are **ACTUALLY IN USE** by the deployed Lambda function:

| Table Name | Purpose | Status |
|------------|---------|--------|
| `vyaparai-orders-prod` | Stores orders and order items | ✅ ACTIVE |
| `vyaparai-stores-prod` | Store registration and profiles | ✅ ACTIVE |
| `vyaparai-stock-prod` | Stock/inventory tracking | ✅ ACTIVE |
| `vyaparai-users-prod` | User accounts (if exists) | ❓ MAYBE |
| `vyaparai-customers-prod` | Customer data (if exists) | ❓ MAYBE |

### **How to Access DynamoDB Tables:**

#### Option 1: AWS Console (Web Interface)
```
1. Go to: https://console.aws.amazon.com/dynamodbv2/
2. Select Region: ap-south-1 (Mumbai)
3. Click on "Tables" in left sidebar
4. Click on table name to view/edit items
```

#### Option 2: AWS CLI
```bash
# List all tables
aws dynamodb list-tables --region ap-south-1

# Scan table (view all items)
aws dynamodb scan --table-name vyaparai-orders-prod --region ap-south-1

# Delete all items from a table (BE CAREFUL!)
aws dynamodb scan --table-name vyaparai-stores-prod --region ap-south-1 \
  --query "Items[].{id: id.S}" --output json | \
  jq -r '.[] | .id' | \
  while read id; do
    aws dynamodb delete-item --table-name vyaparai-stores-prod \
      --key "{\"id\": {\"S\": \"$id\"}}" --region ap-south-1
  done
```

#### Option 3: Python Script (Provided)
```bash
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend/database/scripts
python3 reset_dynamodb_data.py
```

---

## 🟢 **PostgreSQL Tables (PLANNED/LOCAL ONLY)**

These tables are **DEFINED but NOT YET DEPLOYED** to production. They exist only in SQL migration files:

### Core Tables (Defined in migrations):
| Table Category | Tables | Location | Status |
|----------------|--------|----------|--------|
| **User & Auth** | users, otp_verifications | PostgreSQL | 📝 PLANNED |
| **Store Management** | stores, store_users | PostgreSQL | 📝 PLANNED |
| **Inventory** | categories, brands, generic_products, store_products, stock_movements, product_batches, suppliers, purchase_orders | PostgreSQL | 📝 PLANNED |
| **Orders** | orders, order_items, order_status_history | PostgreSQL | 📝 PLANNED |
| **Customer** | customers, customer_addresses | PostgreSQL | 📝 PLANNED |
| **Analytics** | inventory_snapshots, product_metrics, daily_store_metrics | PostgreSQL | 📝 PLANNED |
| **Other** | notifications, customer_feedback, pricing_rules | PostgreSQL | 📝 PLANNED |

### **These PostgreSQL tables are NOT active in production!**

If you have a local PostgreSQL instance:
```bash
# Connect to local PostgreSQL
psql -U postgres -d vyaparai

# Run migrations (if database exists)
psql -U postgres -d vyaparai -f /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend/database/migrations/create_inventory_schema.sql

# Delete all data (if tables exist)
psql -U postgres -d vyaparai -f /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend/database/scripts/reset_store_data.sql
```

---

## 🔴 **IMPORTANT: Current Production Reality**

### What's Actually Happening:
1. **Lambda Function** (`lambda_handler.py`) is deployed to AWS
2. It uses **DynamoDB ONLY** for data storage
3. PostgreSQL code exists but is **NOT connected** in production
4. Store registration saves to **DynamoDB** (`vyaparai-stores-prod`)
5. Orders save to **DynamoDB** (`vyaparai-orders-prod`)

### Data Storage Summary:
- ✅ **Stores**: DynamoDB (`vyaparai-stores-prod`)
- ✅ **Orders**: DynamoDB (`vyaparai-orders-prod`)
- ✅ **Stock**: DynamoDB (`vyaparai-stock-prod`)
- ❌ **Generic Products**: Not implemented (mock data in code)
- ❌ **Inventory**: Not implemented (mock data in frontend)
- ❌ **Users**: Partially in DynamoDB, mostly in localStorage

---

## 🧹 **How to Delete All Data**

### **1. Clear DynamoDB (Production Data)**
```bash
# Use the provided Python script
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend/database/scripts
python3 reset_dynamodb_data.py

# Type 'YES' when prompted
```

### **2. Clear Browser Data**
```javascript
// Open browser console at localhost:3001
resetVyaparAI()
```

### **3. Clear PostgreSQL (If Local DB Exists)**
```bash
# Only if you have local PostgreSQL
psql -U postgres -d vyaparai -f /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend/database/scripts/reset_store_data.sql
```

---

## 📊 **Quick Check: What Tables Exist in DynamoDB**

```python
import boto3

dynamodb = boto3.client('dynamodb', region_name='ap-south-1')
response = dynamodb.list_tables()

print("Existing DynamoDB Tables:")
for table in response['TableNames']:
    if 'vyaparai' in table:
        print(f"  - {table}")
```

---

## 🚀 **Recommended Action for Testing**

For a clean test environment:

1. **Clear DynamoDB tables** (stores your actual data):
   ```bash
   python3 /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend/database/scripts/reset_dynamodb_data.py
   ```

2. **Clear browser storage**:
   ```javascript
   resetVyaparAI()  // in browser console
   ```

3. **Start fresh**:
   - Browse website
   - Register new store
   - Data will be saved to DynamoDB

---

## ⚠️ **Note on Future Migration**

The PostgreSQL schema is ready but not deployed. To migrate from DynamoDB to PostgreSQL in the future:

1. Deploy PostgreSQL database (AWS RDS or similar)
2. Run migration scripts to create tables
3. Update Lambda handler to use PostgreSQL (`inventory_handler.py` has the code)
4. Migrate existing DynamoDB data to PostgreSQL
5. Update environment variables in Lambda

Currently, the app is **100% functional with DynamoDB only**.