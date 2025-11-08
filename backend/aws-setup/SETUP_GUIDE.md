# VyaparAI AWS Database Setup Guide

## 📋 Prerequisites

1. **AWS Account** with appropriate permissions (see IAM Requirements below)
2. **AWS CLI** installed and configured
3. **PostgreSQL client** (psql) for schema deployment
4. **Python 3.8+** for running test scripts

## ⚠️ IAM Permission Requirements

Your AWS IAM user needs these permissions to run the setup:
- **RDS**: Create and manage database instances
- **DynamoDB**: Create and manage tables
- **EC2**: Create security groups (or use alternative script)
- **Lambda**: Update function configuration

### Option 1: Quick Fix with AWS Managed Policies
Attach these policies to your IAM user:
- `AmazonRDSFullAccess`
- `AmazonDynamoDBFullAccess`
- `AmazonEC2FullAccess`
- `AWSLambda_FullAccess`

### Option 2: Custom Minimal Permissions
Use the policy in `iam-policy-vyaparai-deploy.json`:
```bash
aws iam create-policy \
  --policy-name VyaparAIDeploymentPolicy \
  --policy-document file://iam-policy-vyaparai-deploy.json

aws iam attach-user-policy \
  --user-name your-iam-user \
  --policy-arn arn:aws:iam::YOUR-ACCOUNT:policy/VyaparAIDeploymentPolicy
```

### Option 3: No EC2 Permissions? Use Alternative Script
If you can't get EC2 permissions, use the no-security-group version:
```bash
./setup-aws-databases-no-sg.sh
```
This uses the default VPC security group instead of creating a new one.

## 🚀 Quick Setup

### Step 1: Configure AWS CLI
```bash
# If not already configured
aws configure

# Enter your AWS credentials:
# AWS Access Key ID: [your-key]
# AWS Secret Access Key: [your-secret]
# Default region: ap-south-1
# Default output format: json
```

### Step 2: Install Dependencies
```bash
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend/aws-setup
pip install -r requirements.txt
```

### Step 3: Run Setup Script
```bash
# Make script executable
chmod +x setup-aws-databases.sh

# Run the setup
./setup-aws-databases.sh
```

This script will:
- ✅ Create RDS PostgreSQL instance
- ✅ Create all DynamoDB tables
- ✅ Deploy database schema
- ✅ Configure security groups
- ✅ Update Lambda environment variables
- ✅ Generate credentials file

### Step 4: Test Connections
```bash
python3 test-connections.py
```

## 📊 Database Architecture

### PostgreSQL RDS (Relational Data)
- **Instance Type**: db.t3.micro (Free tier)
- **Storage**: 20 GB
- **Database**: vyaparai
- **Tables**: 
  - Inventory management (products, categories, brands)
  - Store management
  - Order management
  - Customer data

### DynamoDB (NoSQL Data)
- **Tables**:
  - `vyaparai-stores-prod` - Store registrations
  - `vyaparai-orders-prod` - Order transactions
  - `vyaparai-stock-prod` - Real-time stock levels
  - `vyaparai-users-prod` - User accounts
  - `vyaparai-customers-prod` - Customer profiles

## 🔒 Security & Privacy Implementation

### Data Privacy Features
1. **PII Encryption**: Phone numbers, emails encrypted at rest
2. **Data Masking**: Sensitive data masked in logs and displays
3. **Store Isolation**: Each store can only access its own data
4. **Access Control**: Role-based permissions (customer, staff, owner, admin)
5. **Audit Logging**: All data access logged for compliance

### Security Configuration
```python
# In your .env file
ENCRYPT_PII=true
MASK_PHONE_NUMBERS=true
AUDIT_LOGGING=true
```

## 🔧 Local Development Configuration

### Update Frontend Environment
```bash
# In frontend-pwa directory
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/frontend-pwa

# Create .env.local
cat > .env.local << EOF
REACT_APP_API_URL=https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws
REACT_APP_USE_AWS_DB=true
EOF
```

### Update Backend Environment
```bash
# Copy AWS environment file
cp .env.aws .env.production

# Update with your RDS credentials from rds-credentials.txt
# Edit DB_HOST, DB_PASSWORD in .env.production
```

## 🧪 Testing the Setup

### 1. Test Store Registration
```javascript
// In browser console at localhost:3001
// Clear local data first
resetVyaparAI()

// Then register a new store through the UI
// Data should save to AWS DynamoDB
```

### 2. Verify Data in AWS Console
- Go to [DynamoDB Console](https://console.aws.amazon.com/dynamodbv2/)
- Select `vyaparai-stores-prod` table
- Click "Items" tab to see registered stores

### 3. Test PostgreSQL Data
```bash
# Connect to RDS
psql -h your-rds-endpoint.rds.amazonaws.com -U vyaparai_admin -d vyaparai

# Check tables
\dt

# Check generic products
SELECT COUNT(*) FROM generic_products;
```

## 🏗️ Architecture Decisions

### Why Hybrid (PostgreSQL + DynamoDB)?
1. **PostgreSQL**: Complex relationships, inventory management, reporting
2. **DynamoDB**: High-speed transactions, real-time updates, scalability

### Data Flow
1. **Store Registration** → DynamoDB (vyaparai-stores-prod)
2. **Product Catalog** → PostgreSQL (generic_products, store_products)
3. **Orders** → DynamoDB first, then PostgreSQL for analytics
4. **Real-time Stock** → DynamoDB (vyaparai-stock-prod)
5. **Analytics** → PostgreSQL (aggregated data)

## 📝 Important Notes

### Cost Considerations
- **RDS t3.micro**: ~$15/month after free tier
- **DynamoDB**: Pay-per-request (~$0.25 per million requests)
- **Total estimated**: ~$20-30/month for development

### Production Recommendations
1. **RDS**: Enable Multi-AZ for high availability
2. **Security Group**: Restrict to specific IPs
3. **Backups**: Enable automated backups
4. **Encryption**: Enable encryption at rest
5. **Monitoring**: Set up CloudWatch alarms

## 🛠️ Troubleshooting

### Connection Issues
```bash
# Check RDS security group
aws ec2 describe-security-groups --group-names vyaparai-db-sg --region ap-south-1

# Check RDS status
aws rds describe-db-instances --db-instance-identifier vyaparai-postgres-prod --region ap-south-1
```

### DynamoDB Issues
```bash
# List tables
aws dynamodb list-tables --region ap-south-1

# Check table status
aws dynamodb describe-table --table-name vyaparai-stores-prod --region ap-south-1
```

### Lambda Connection Issues
```bash
# Update Lambda environment
aws lambda update-function-configuration \
  --function-name vyaparai-api-prod \
  --environment "Variables={DB_HOST=your-rds-endpoint,DB_PASSWORD=your-password}" \
  --region ap-south-1
```

## 🗑️ Cleanup (If Needed)

### Delete All Resources
```bash
# Delete RDS instance (BE CAREFUL!)
aws rds delete-db-instance \
  --db-instance-identifier vyaparai-postgres-prod \
  --skip-final-snapshot \
  --region ap-south-1

# Delete DynamoDB tables
aws dynamodb delete-table --table-name vyaparai-stores-prod --region ap-south-1
aws dynamodb delete-table --table-name vyaparai-orders-prod --region ap-south-1
# ... repeat for other tables

# Delete security group
aws ec2 delete-security-group --group-id sg-xxxxx --region ap-south-1
```

## 📞 Support

If you encounter issues:
1. Check CloudWatch logs for Lambda function
2. Verify AWS credentials and permissions
3. Ensure security groups allow connections
4. Check the test-connections.py output for specific errors

---

**Remember**: Always keep your credentials secure and never commit them to version control!