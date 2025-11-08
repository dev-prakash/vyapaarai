# VyapaarAI Deployment & Testing Strategy

## Current Issue Summary

The Lambda handler was missing the `CORSMiddleware` import, causing runtime crashes when deploying changes.

## Fixed Issues

1. ✅ Added missing import: `from fastapi.middleware.cors import CORSMiddleware`
2. ✅ Added DELETE endpoint for global products: `DELETE /api/v1/admin/products/{product_id}`

## Enterprise Best Practices for CORS

### Current Approach (Hybrid)
- FastAPI middleware handles CORS
- API Gateway passes through

### Recommended Enterprise Approach

**Option 1: API Gateway CORS (Recommended)**
```yaml
# Configure in API Gateway Console or CloudFormation
Resources:
  ApiGateway:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      CorsConfiguration:
        AllowOrigins:
          - https://www.vyapaarai.com
          - https://vyapaarai.com
        AllowMethods:
          - GET
          - POST
          - PUT
          - DELETE
          - OPTIONS
        AllowHeaders:
          - Content-Type
          - Authorization
          - X-Requested-With
        AllowCredentials: true
        MaxAge: 3600
```

**Benefits:**
- OPTIONS requests never hit Lambda (cost savings)
- ~80% reduction in Lambda invocations for CORS preflight
- API Gateway handles it natively
- No middleware overhead in Lambda

**Option 2: Keep Current Hybrid (What we have)**
- Keep FastAPI middleware for flexibility
- Ensure imports are correct
- Good for development, acceptable for production

## Safe Testing Strategy

### 1. Local Testing Environment

```bash
# Install dependencies locally
cd backend/lambda-email-minimal/lambda-csv-minimal
pip install -r requirements.txt

# Run FastAPI locally
uvicorn lambda_handler:app --reload --port 8000

# Test endpoints
curl -X OPTIONS http://localhost:8000/api/v1/admin/auth/login \
  -H "Origin: https://www.vyapaarai.com" \
  -H "Access-Control-Request-Method: POST" \
  -i

curl -X DELETE http://localhost:8000/api/v1/admin/products/TEST123 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -i
```

### 2. Create a Staging Lambda Function

```bash
# Create staging function
aws lambda create-function \
  --function-name vyaparai-api-staging \
  --runtime python3.11 \
  --handler lambda_handler.lambda_handler \
  --role arn:aws:iam::491065739648:role/vyaparai-lambda-role \
  --zip-file fileb://deployment-with-delete.zip \
  --timeout 30 \
  --memory-size 1024

# Create staging API Gateway
# Point to staging Lambda
# Test thoroughly before deploying to prod
```

### 3. Blue-Green Deployment

```bash
# Create alias for current version
aws lambda create-alias \
  --function-name vyaparai-api-prod \
  --name blue \
  --function-version $CURRENT_VERSION

# Deploy new version
aws lambda update-function-code \
  --function-name vyaparai-api-prod \
  --zip-file fileb://deployment-with-delete.zip

# Publish new version
NEW_VERSION=$(aws lambda publish-version \
  --function-name vyaparai-api-prod \
  --query 'Version' \
  --output text)

# Create green alias
aws lambda create-alias \
  --function-name vyaparai-api-prod \
  --name green \
  --function-version $NEW_VERSION

# Test green endpoint
# If good: update API Gateway to point to green
# If bad: rollback to blue
```

## Deployment Checklist

### Pre-Deployment
- [ ] All imports are present
- [ ] Local testing passes
- [ ] Staging deployment tested
- [ ] CORS OPTIONS request tested
- [ ] All endpoints return proper responses

### Deployment Steps

1. **Package with all dependencies**
```bash
# Clean and rebuild
rm -rf temp_deploy deployment-*.zip
mkdir temp_deploy

# Extract current working deployment
cd temp_deploy
unzip ../deployment-inventory-working.zip

# Copy updated handler
cp ../lambda_handler.py .

# Create new deployment package
zip -r ../deployment-with-delete.zip .
cd ..
```

2. **Verify package integrity**
```bash
# Check lambda_handler.py is included
unzip -l deployment-with-delete.zip | grep lambda_handler.py

# Check all dependencies are present
unzip -l deployment-with-delete.zip | grep -E "(fastapi|mangum|jwt)"
```

3. **Deploy to staging first**
```bash
aws lambda update-function-code \
  --function-name vyaparai-api-staging \
  --zip-file fileb://deployment-with-delete.zip
```

4. **Test staging**
```bash
# Test OPTIONS
curl -X OPTIONS https://STAGING_API_URL/api/v1/admin/auth/login \
  -H "Origin: https://www.vyapaarai.com" \
  -H "Access-Control-Request-Method: POST" \
  -i

# Should return 200 with CORS headers

# Test DELETE
curl -X DELETE https://STAGING_API_URL/api/v1/admin/products/TEST_ID \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -i

# Should return 200 with success message
```

5. **Deploy to production**
```bash
# Only after staging tests pass
aws lambda update-function-code \
  --function-name vyaparai-api-prod \
  --zip-file fileb://deployment-with-delete.zip
```

6. **Monitor production**
```bash
# Watch logs in real-time
aws logs tail /aws/lambda/vyaparai-api-prod --follow

# Check error rate in CloudWatch
```

7. **Rollback if needed**
```bash
# Keep previous working deployment
aws lambda update-function-code \
  --function-name vyaparai-api-prod \
  --zip-file fileb://deployment-inventory-working.zip
```

## API Gateway CORS Migration (Future Enhancement)

### Step 1: Configure API Gateway CORS
- Go to API Gateway Console
- Select your HTTP API
- Configure CORS settings
- Deploy changes

### Step 2: Remove FastAPI CORS Middleware
```python
# Comment out or remove
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
```

### Step 3: Test
- Verify OPTIONS requests still work
- Verify actual requests work
- Monitor Lambda invocation count (should decrease)

### Expected Benefits
- ~80% reduction in OPTIONS-related Lambda invocations
- Lower latency for preflight requests
- Better separation of concerns

## Monitoring & Alerts

### Key Metrics to Watch
1. Lambda invocation count
2. Lambda error rate
3. API Gateway 4xx/5xx errors
4. CORS preflight success rate
5. Response time

### CloudWatch Alarms
```bash
# Create alarm for high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name vyaparai-api-high-error-rate \
  --alarm-description "Alert if Lambda error rate exceeds 5%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold
```

## Cost Optimization

### Current Costs (Estimated)
- Lambda invocations: ~10,000/month (including OPTIONS)
- Data transfer: Minimal
- API Gateway: Pay per request

### After API Gateway CORS Migration
- Lambda invocations: ~2,000/month (80% reduction)
- Cost savings: ~$0.50-$1.00/month per 10k requests
- At scale (1M requests): ~$50/month savings

## Security Considerations

### Current Configuration
- `allow_origins=["*"]` - TOO PERMISSIVE

### Recommended Configuration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.vyapaarai.com",
        "https://vyapaarai.com",
        "http://localhost:5173",  # Development only
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,  # Cache preflight for 1 hour
)
```

### Benefits
- Prevents CSRF attacks
- Reduces attack surface
- Complies with security best practices

## Conclusion

**Immediate Fix:**
- Added missing `CORSMiddleware` import
- Added DELETE endpoint for global products
- Ready for safe deployment

**Long-term Recommendation:**
- Migrate CORS handling to API Gateway
- Set up staging environment
- Implement blue-green deployments
- Restrict CORS origins to production domains only
