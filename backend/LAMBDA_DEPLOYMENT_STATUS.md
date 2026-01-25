# VyaparAI Lambda Deployment Status

**Date:** December 15, 2025
**Lambda Function:** vyaparai-api-prod
**Region:** ap-south-1
**Lambda Function URL:** https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws
**Frontend URL:** https://www.vyapaarai.com

---

## Current Status: FULLY OPERATIONAL

### Latest Deployment: December 15, 2025

All systems are operational. The Lambda function is running successfully with the following configuration:

| Setting | Value |
|---------|-------|
| Runtime | Python 3.11 |
| Architecture | x86_64 |
| Memory | 1024 MB |
| Timeout | 30 seconds |
| Handler | lambda_handler.handler |
| Package Size | ~37 MB |

---

## Recent Changes (December 15, 2025)

### Backend Fixes

1. **Order Count Increment** - Fixed customer `order_count` not updating when orders are created
   - File: `app/api/v1/customer_orders.py`
   - Added atomic increment of `order_count` and `total_spent` fields after successful order creation

2. **Lambda Architecture Change** - Changed from arm64 to x86_64
   - Issue: Compiled Python dependencies (pydantic_core, bcrypt, etc.) were built for x86_64
   - Solution: Updated Lambda architecture to match dependency binaries

3. **Trusted Host Configuration** - Added Lambda Function URL to allowed hosts
   - File: `app/main.py`
   - Added `6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws` to TrustedHostMiddleware

4. **Product Media Router Disabled** - Temporarily disabled due to missing PIL/Pillow dependency
   - File: `app/api/v1/__init__.py`
   - The product_media_router is commented out until Pillow is added to the Lambda package

### Frontend Fixes

1. **Dashboard Orders Display** - Fixed CustomerAccountDashboard.tsx to fetch and display actual orders
   - Previously showed hardcoded "No orders yet" message
   - Now fetches orders via customerOrderService when Orders tab is selected

2. **OrderTracking Number Formatting** - Fixed `toFixed()` errors
   - DynamoDB returns Decimal as strings, wrapped numeric values with `Number()` before `.toFixed()`
   - Files fixed: `OrderTracking.tsx`, `OrderDetails.tsx`

---

## Deployment Procedure

### Quick Deploy (app code only)

```bash
# 1. Download and extract the backup package
aws s3 cp s3://vyaparai-lambda-deployments/backend/lambda-backup.zip /tmp/
cd /tmp && unzip lambda-backup.zip -d lambda-extract

# 2. Replace the app folder with your updated code
rm -rf /tmp/lambda-extract/app
cp -r /path/to/vyaparai/backend/app /tmp/lambda-extract/

# 3. Create new deployment package
cd /tmp/lambda-extract && zip -r /tmp/lambda-deploy.zip . -x "*.pyc" -x "*__pycache__*"

# 4. Upload to S3
aws s3 cp /tmp/lambda-deploy.zip s3://vyaparai-lambda-deployments/backend/lambda-deploy.zip

# 5. Deploy to Lambda (using Python/boto3 for architecture support)
python3 << 'EOF'
import boto3
client = boto3.client('lambda', region_name='ap-south-1')
response = client.update_function_code(
    FunctionName='vyaparai-api-prod',
    S3Bucket='vyaparai-lambda-deployments',
    S3Key='backend/lambda-deploy.zip',
    Architectures=['x86_64']
)
print(f"Deployed! Status: {response['LastUpdateStatus']}")
EOF

# 6. Verify deployment
curl https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/health
```

### Frontend Deploy

```bash
# 1. Build frontend
cd /path/to/frontend-pwa
npm run build

# 2. Deploy to S3
aws s3 sync dist/ s3://www.vyapaarai.com/ --delete

# 3. Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id E1UY93SVXV8QOF --paths "/*"
```

---

## Environment Variables

The Lambda function has these environment variables configured:

```bash
# Core
ENVIRONMENT=production
AWS_REGION=ap-south-1

# Database
USE_DYNAMODB=true
DYNAMODB_ORDERS_TABLE=vyaparai-orders-prod
DYNAMODB_CUSTOMERS_TABLE=vyaparai-customers-prod
DYNAMODB_STORES_TABLE=vyaparai-stores-prod
DYNAMODB_STOCK_TABLE=vyaparai-stock-prod
DYNAMODB_USERS_TABLE=vyaparai-users-prod

# PostgreSQL (for legacy support)
USE_POSTGRESQL=true
DATABASE_URL=postgresql://vyaparai_admin:***@vyaparai-postgres-prod...

# Authentication
JWT_SECRET=vyaparai-jwt-secret-key-2025-prod-secure
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_CUSTOMER_TOKEN_EXPIRE_DAYS=30

# Cache (disabled in Lambda)
ENABLE_CACHING=false
REDIS_URL=redis://localhost:6379
```

---

## Lambda Package Contents

The deployment package includes:

- `lambda_handler.py` - Entry point using Mangum adapter
- `app/` - FastAPI application code
- `mangum/` - ASGI to Lambda adapter
- `fastapi/`, `starlette/`, `pydantic/` - Web framework
- `boto3/`, `botocore/` - AWS SDK
- `bcrypt/`, `PyJWT/` - Authentication libraries
- Various other Python dependencies

**Note:** The package uses x86_64 compiled binaries. Do NOT change Lambda architecture to arm64.

---

## API Endpoints

### Health Check
```bash
curl https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/health
```

### Customer Authentication
```bash
# Login
curl -X POST https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/customer/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'
```

### Customer Orders
```bash
# Get orders (requires auth token)
curl https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/customer/orders \
  -H "Authorization: Bearer <token>"
```

---

## Troubleshooting

### Issue: "Invalid host header"
**Cause:** The request host is not in the TrustedHostMiddleware allowed_hosts list
**Solution:** Add the host to `app/main.py` in the `allowed_hosts` array

### Issue: "No module named 'xyz'"
**Cause:** Missing dependency in Lambda package
**Solution:** Download backup package, add the dependency, repackage and deploy

### Issue: Architecture mismatch errors
**Cause:** Compiled Python modules are for wrong architecture
**Solution:** Ensure Lambda is set to x86_64 (not arm64)

### Issue: Cold start timeouts
**Cause:** Lambda initialization takes too long
**Solution:** Increase timeout or use Provisioned Concurrency

---

## Monitoring

### CloudWatch Logs
```bash
aws logs describe-log-streams \
  --log-group-name /aws/lambda/vyaparai-api-prod \
  --order-by LastEventTime --descending --max-items 5
```

### Recent Errors
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/vyaparai-api-prod \
  --filter-pattern "ERROR" \
  --limit 20
```

---

## S3 Backup Packages

| File | Description |
|------|-------------|
| `lambda-backup.zip` | Original working package (Dec 4, 2025) |
| `lambda-deploy-v2.zip` | Latest deployment with all fixes |

Location: `s3://vyaparai-lambda-deployments/backend/`

---

## Success Criteria

- [x] Lambda deployment package built
- [x] Code uploaded to Lambda
- [x] Function state: Active
- [x] Health endpoint responding
- [x] Customer authentication working
- [x] Customer orders API working
- [x] DynamoDB connections verified
- [x] Frontend deployed and working
- [ ] Product media upload (pending Pillow dependency)

---

**Status:** FULLY OPERATIONAL
**Last Updated:** December 15, 2025
